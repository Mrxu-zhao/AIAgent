from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge.models import KnowledgeUsage

METADATA_TEMPLATE = "---\nowner: control-plane\nlast_reviewed: {date}\nsource: workflow-feedback\n---\n\n"
DECISION_HEADER = "# 关键决策记录\n\n| 日期 | 决策 | 理由 | 影响范围 |\n|------|------|------|----------|\n"
RISK_HEADER = "# 风险登记册\n\n| 风险 | 影响范围 | 预警信号 | 缓解策略 |\n|------|----------|----------|----------|\n"


def sync_workflow_feedback(
    knowledge_root: Path,
    workflow_id: str,
    collaboration_context: Dict[str, Any],
    step_contexts: Optional[Dict[str, Any]] = None,
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
    lessons = _build_lessons(workflow_id, step_contexts or {})
    team_lessons_path = _resolve_team_lessons_path(knowledge_root)
    appended_team_lessons = _append_team_lessons(team_lessons_path, workflow_id, lessons)
    appended_instance_lessons = _append_instance_lessons(knowledge_root, lessons)
    return {
        "decision_log_path": str(decision_log_path),
        "risk_register_path": str(risk_register_path),
        "appended_decisions": appended_decisions,
        "appended_risks": appended_risks,
        "team_lessons_path": str(team_lessons_path),
        "appended_team_lessons": appended_team_lessons,
        "instance_lessons": appended_instance_lessons,
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


def _build_lessons(workflow_id: str, step_contexts: Dict[str, Any]) -> List[Dict[str, str]]:
    lessons: List[Dict[str, str]] = []
    for step_id, context in sorted(step_contexts.items()):
        if not isinstance(context, dict):
            continue
        agent = str(context.get("agent") or "").strip()
        summary = str(context.get("summary") or "").strip()
        decisions = list(context.get("decisions", []))
        risks = [str(item).strip() for item in context.get("risks", []) if str(item).strip()]
        if not agent or (not summary and not decisions and not risks):
            continue
        title = _extract_lesson_title(step_id, decisions, risks, summary)
        lesson = {
            "workflow_id": workflow_id,
            "step_id": step_id,
            "agent": agent,
            "title": title,
            "scenario": f"workflow: {workflow_id}; step: {step_id}; agent: {agent}",
            "action": _extract_lesson_action(decisions, summary, title),
            "result": summary or title,
            "prerequisite": risks[0] if risks else f"适用于 {step_id} 等类似工作流步骤",
            "dedupe_key": f"{agent}|{step_id}|{title}",
        }
        lessons.append(lesson)
    return lessons


def _extract_lesson_title(
    step_id: str,
    decisions: List[Any],
    risks: List[str],
    summary: str,
) -> str:
    if decisions:
        first_decision = decisions[0]
        if isinstance(first_decision, dict):
            title = str(first_decision.get("summary") or "").strip()
            if title:
                return title
        else:
            title = str(first_decision).strip()
            if title:
                return title
    if risks:
        return risks[0]
    if summary:
        return summary
    return f"{step_id} 的执行经验"


def _extract_lesson_action(decisions: List[Any], summary: str, fallback: str) -> str:
    if decisions:
        first_decision = decisions[0]
        if isinstance(first_decision, dict):
            rationale = str(first_decision.get("rationale") or "").strip()
            if rationale:
                return f"{fallback}；理由：{rationale}"
        else:
            decision_text = str(first_decision).strip()
            if decision_text:
                return decision_text
    return summary or fallback


def _resolve_team_lessons_path(knowledge_root: Path) -> Path:
    month = datetime.now().strftime("%Y-%m")
    return knowledge_root / "lessons" / f"workflow-lessons-{month}.md"


def _append_team_lessons(path: Path, workflow_id: str, lessons: List[Dict[str, str]]) -> List[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    if not path.exists():
        path.write_text(
            (
                f"# Workflow 实战经验（{month}）\n\n"
                "---\n"
                "owner: control-plane\n"
                f"last_reviewed: {today}\n"
                f"source: {workflow_id}\n"
                "scope: team\n"
                "---\n\n"
            ),
            encoding="utf-8",
        )
    text = path.read_text(encoding="utf-8")
    text = _replace_or_insert_metadata(text, "last_reviewed", today)
    text = _replace_or_insert_metadata(text, "source", workflow_id)
    appended: List[str] = []
    for lesson in lessons:
        marker = f"<!-- lesson-key: {lesson['dedupe_key']} -->"
        if marker in text:
            continue
        block = _render_team_lesson_block(lesson)
        text += block
        appended.append(lesson["title"])
    if appended:
        path.write_text(text, encoding="utf-8")
    else:
        path.write_text(text, encoding="utf-8")
    return appended


def _append_instance_lessons(knowledge_root: Path, lessons: List[Dict[str, str]]) -> Dict[str, List[str]]:
    appended: Dict[str, List[str]] = {}
    team_root = knowledge_root.parent
    for lesson in lessons:
        agent = lesson["agent"]
        path = team_root / "agents" / agent / "knowledge" / "recent-lessons.md"
        _ensure_recent_lessons_file(path, agent)
        text = path.read_text(encoding="utf-8")
        text = _ensure_month_section(text, datetime.now().strftime("%Y-%m"))
        marker = f"<!-- lesson-key: {lesson['dedupe_key']} -->"
        if marker in text:
            path.write_text(text, encoding="utf-8")
            continue
        insertion = _render_instance_lesson_block(lesson)
        month_header = f"## {datetime.now().strftime('%Y-%m')}"
        text = text.replace(month_header, month_header + "\n\n" + insertion, 1)
        path.write_text(text, encoding="utf-8")
        appended.setdefault(agent, []).append(lesson["title"])
    return appended


def _ensure_recent_lessons_file(path: Path, agent: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(
        (
            f"# {agent} - 最近经验\n\n"
            f"## {datetime.now().strftime('%Y-%m')}\n\n"
            "## 记录模板\n"
            "- 日期：\n"
            "- 场景：\n"
            "- 做法：\n"
            "- 结果：\n"
            "- 适用前提：\n"
            "- 是否可沉淀到角色层或团队层：\n"
        ),
        encoding="utf-8",
    )


def _ensure_month_section(text: str, month: str) -> str:
    header = f"## {month}"
    if header in text:
        return text
    template_marker = "## 记录模板"
    month_block = f"{header}\n\n"
    if template_marker in text:
        return text.replace(template_marker, month_block + template_marker, 1)
    suffix = "" if text.endswith("\n") else "\n"
    return text + suffix + "\n" + month_block


def _render_team_lesson_block(lesson: Dict[str, str]) -> str:
    return (
        f"## {datetime.now().strftime('%Y-%m-%d')}\n"
        f"<!-- lesson-key: {lesson['dedupe_key']} -->\n"
        f"### 经验：{lesson['title']}\n"
        f"- 场景：{lesson['scenario']}\n"
        f"- 做法：{lesson['action']}\n"
        f"- 结果：{lesson['result']}\n"
        f"- 适用前提：{lesson['prerequisite']}\n\n"
    )


def _render_instance_lesson_block(lesson: Dict[str, str]) -> str:
    return (
        f"<!-- lesson-key: {lesson['dedupe_key']} -->\n"
        f"### 经验：{lesson['title']}\n"
        f"- 场景：{lesson['scenario']}\n"
        f"- 做法：{lesson['action']}\n"
        f"- 结果：{lesson['result']}\n"
        f"- 适用前提：{lesson['prerequisite']}\n"
        "- 是否可沉淀到角色层或团队层：团队层 lessons\n"
    )


def _replace_or_insert_metadata(text: str, key: str, value: str) -> str:
    target = f"{key}:"
    lines = text.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(target):
            lines[index] = f"{key}: {value}"
            replaced = True
            break
    if not replaced and lines and lines[0] == "---":
        for index in range(1, len(lines)):
            if lines[index] == "---":
                lines.insert(index, f"{key}: {value}")
                replaced = True
                break
    suffix = "\n" if text.endswith("\n") or not lines else ""
    return "\n".join(lines) + suffix
