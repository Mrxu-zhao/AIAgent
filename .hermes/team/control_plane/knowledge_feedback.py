from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from knowledge.models import KnowledgeUsage

METADATA_TEMPLATE = "---\nowner: control-plane\nlast_reviewed: {date}\nsource: workflow-feedback\n---\n\n"
DECISION_HEADER = "# 关键决策记录\n\n| 日期 | 决策 | 理由 | 影响范围 |\n|------|------|------|----------|\n"
RISK_HEADER = "# 风险登记册\n\n| 风险 | 影响范围 | 预警信号 | 缓解策略 |\n|------|----------|----------|----------|\n"


def sync_workflow_feedback(
    knowledge_root: Path,
    workflow_id: str,
    collaboration_context: Dict[str, Any],
) -> Dict[str, Any]:
    knowledge_root.mkdir(parents=True, exist_ok=True)
    decision_log_path = knowledge_root / "decision-log.md"
    risk_register_path = knowledge_root / "risk-register.md"
    _ensure_file(decision_log_path, DECISION_HEADER)
    _ensure_file(risk_register_path, RISK_HEADER)

    appended_decisions = _append_decisions(
        decision_log_path,
        workflow_id,
        list(collaboration_context.get("decisions", [])),
    )
    appended_risks = _append_risks(
        risk_register_path,
        workflow_id,
        list(collaboration_context.get("risks", [])),
    )
    return {
        "decision_log_path": str(decision_log_path),
        "risk_register_path": str(risk_register_path),
        "appended_decisions": appended_decisions,
        "appended_risks": appended_risks,
    }


def record_knowledge_usage(
    workflow_id: str,
    knowledge_recommendations: Dict[str, Any],
    knowledge_bundles: Dict[str, Any],
    step_contexts: Dict[str, Any],
) -> Dict[str, Any]:
    step_records: List[Dict[str, Any]] = []
    aggregate_usage = KnowledgeUsage()

    for step_id, recommendation in sorted(knowledge_recommendations.items()):
        if not isinstance(recommendation, dict):
            continue
        bundle = knowledge_bundles.get(step_id) if isinstance(knowledge_bundles, dict) else {}
        bundle = bundle if isinstance(bundle, dict) else {}
        step_context = step_contexts.get(step_id) if isinstance(step_contexts, dict) else {}
        step_context = step_context if isinstance(step_context, dict) else {}

        recommended_paths = _flatten_recommended_paths(recommendation)
        consumed_paths = _dedupe_list(bundle.get("paths", []))
        unused_paths = [path for path in recommended_paths if path not in consumed_paths]
        expanded_paths = _dedupe_list(bundle.get("next_read", []))

        usage = KnowledgeUsage(
            recommended_paths=recommended_paths,
            consumed_paths=consumed_paths,
            expanded_paths=expanded_paths,
            unused_paths=unused_paths,
            decision_helpful_count=len(step_context.get("decisions", [])),
            risk_helpful_count=len(step_context.get("risks", [])),
        )
        usage.finalize_feedback_score()
        step_records.append(
            {
                "step_id": step_id,
                "agent": step_context.get("agent"),
                "usage": usage.to_dict(),
            }
        )
        _merge_usage(aggregate_usage, usage)

    aggregate_usage.finalize_feedback_score()
    return {
        "workflow_id": workflow_id,
        "steps": step_records,
        "summary": aggregate_usage.to_dict(),
    }


def _ensure_file(path: Path, header: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    if not path.exists():
        path.write_text(METADATA_TEMPLATE.format(date=today) + header, encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        path.write_text(METADATA_TEMPLATE.format(date=today) + text, encoding="utf-8")
        text = path.read_text(encoding="utf-8")
    if "last_reviewed:" not in text:
        path.write_text(text.replace("owner: control-plane", f"owner: control-plane\nlast_reviewed: {today}"), encoding="utf-8")
    else:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("last_reviewed:"):
                lines[index] = f"last_reviewed: {today}"
                break
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _flatten_recommended_paths(recommendation: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for group in ("team", "role", "instance"):
        paths.extend(recommendation.get(group, []))
    return _dedupe_list(paths)


def _dedupe_list(values: List[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _merge_usage(target: KnowledgeUsage, usage: KnowledgeUsage) -> None:
    target.recommended_paths = _dedupe_list(target.recommended_paths + usage.recommended_paths)
    target.consumed_paths = _dedupe_list(target.consumed_paths + usage.consumed_paths)
    target.expanded_paths = _dedupe_list(target.expanded_paths + usage.expanded_paths)
    target.unused_paths = _dedupe_list(target.unused_paths + usage.unused_paths)
    target.decision_helpful_count += int(usage.decision_helpful_count)
    target.risk_helpful_count += int(usage.risk_helpful_count)


def _append_decisions(path: Path, workflow_id: str, decisions: List[Any]) -> List[str]:
    text = path.read_text(encoding="utf-8")
    rows: List[str] = []
    today = datetime.now().strftime("%Y-%m-%d")
    for item in decisions:
        decision_summary = ""
        rationale = "workflow result"
        impact = f"workflow: {workflow_id}"
        if isinstance(item, dict):
            decision_summary = str(item.get("decision_summary", "")).strip()
            if item.get("step_id"):
                impact = f"workflow: {workflow_id}; step: {item['step_id']}"
        else:
            decision_summary = str(item).strip()
        if not decision_summary:
            continue
        marker = f"[{workflow_id}] {decision_summary}"
        if marker in text:
            continue
        row = f"| {today} | {marker} | {rationale} | {impact} |"
        rows.append(row)
        text += row + "\n"
    if rows:
        path.write_text(text, encoding="utf-8")
    return rows


def _append_risks(path: Path, workflow_id: str, risks: List[Any]) -> List[str]:
    text = path.read_text(encoding="utf-8")
    rows: List[str] = []
    for item in risks:
        risk_text = str(item).strip()
        if not risk_text:
            continue
        marker = f"| {risk_text} | workflow: {workflow_id} |"
        if marker in text:
            continue
        row = (
            f"| {risk_text} | workflow: {workflow_id} | "
            f"见工作流结果与 step_contexts | 在交付前复核对应步骤的风险缓解动作 |"
        )
        rows.append(row)
        text += row + "\n"
    if rows:
        path.write_text(text, encoding="utf-8")
    return rows
