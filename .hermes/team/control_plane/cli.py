from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

FRAMEWORK_CORE_DIR = Path(__file__).resolve().parents[1] / "调度框架" / "core"
if str(FRAMEWORK_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_CORE_DIR))

from adapters import get_executor_adapter
from config import load_control_plane_config
from executor import ControlPlaneExecutor
from governance.approval import ApprovalGate
from governance.audit import AuditLogger
from governance.rbac import build_default_rbac_policy
from handoff_runtime import HandoffRunStore
from knowledge.analytics import (
    build_consumption_by_agent,
    build_high_risk_coverage,
    build_knowledge_effectiveness_report,
    build_knowledge_heat_ranking,
    build_pending_governance_counts,
    build_unused_recommendations,
)
from knowledge.governance import apply_governance_action
from knowledge.query import query_knowledge_records
from message_bus import get_bus
from models import (
    EventType,
    LockScope,
    RetryPolicy,
    RollbackPolicy,
    TaskCard,
    TaskEvent,
    TaskStatus,
)
from models import (
    TaskPriority as ControlTaskPriority,
)
from monitor import get_monitor
from observability.metrics import refresh_repository_metrics
from observability.prometheus_exporter import export_metrics_text
from runtime.context import build_tool_execution_context
from runtime.rules import build_knowledge_bundle
from store import TaskStore
from task_router import TaskPriority, TaskRouter
from tools.builtin import build_default_tool_registry
from tools.executor import ToolExecutor
from tools.session_store import SessionStore
from tools.transcript import ToolTranscriptStore
from validation import run_real_load_validation
from workflow_engine import (
    WorkflowEngine,
    default_workflow_definition_path,
    load_workflow_definition,
)
from workflow_runtime import WorkflowRunStore


def _normalize_handoff_record(record):
    normalized = dict(record)
    normalized.setdefault("continuation_status", None)
    normalized.setdefault("continued_at", None)
    if normalized.get("continuation_workflow_id") is None and (
        normalized.get("continuation_status") is not None or normalized.get("continued_at") is not None
    ):
        normalized["continuation_workflow_id"] = normalized.get("workflow_id")
    else:
        normalized.setdefault("continuation_workflow_id", None)
    for key in (
        "continuation_ready_steps",
        "continuation_completed_steps",
        "continuation_failed_steps",
    ):
        value = normalized.get(key)
        normalized[key] = list(value) if value is not None else []
    return normalized


def _extract_knowledge_recommendation(task):
    routing_reason = getattr(task, "routing_reason", None)
    if not isinstance(routing_reason, dict):
        return None
    recommendation = routing_reason.get("knowledge_recommendation")
    return recommendation if isinstance(recommendation, dict) else None


def _normalize_dispatch_actor(actor: str) -> str:
    normalized = str(actor or "").strip()
    if normalized in {"admin", "operator", "viewer"}:
        return normalized
    role_mappings = {
        "project-manager": "operator",
        "architect": "operator",
        "dba": "operator",
        "devops": "operator",
        "requirements-analyst": "operator",
        "ucd": "operator",
        "qa-functional": "operator",
        "qa-performance": "operator",
    }
    if normalized in role_mappings:
        return role_mappings[normalized]
    if normalized.startswith("backend-") or normalized.startswith("frontend-"):
        return "operator"
    return normalized


def _build_knowledge_bundles(result):
    bundles = {}
    recommendations = result.get("knowledge_recommendations", {})
    for step_id, recommendation in recommendations.items():
        if isinstance(recommendation, dict):
            bundles[step_id] = build_knowledge_bundle(recommendation)
    return bundles


def _workflow_knowledge_payload(payload):
    snapshot = dict(payload.get("snapshot") or {})
    knowledge_feedback = snapshot.get("knowledge_feedback") or {}
    knowledge_usage = snapshot.get("knowledge_usage") or {}
    filtered_snapshot = {
        "workflow_id": snapshot.get("workflow_id"),
        "status": snapshot.get("status"),
        "knowledge_feedback": knowledge_feedback,
        "knowledge_usage": knowledge_usage,
    }
    if snapshot.get("knowledge_recommendations") is not None:
        filtered_snapshot["knowledge_recommendations"] = snapshot.get("knowledge_recommendations")
    if snapshot.get("knowledge_bundles") is not None:
        filtered_snapshot["knowledge_bundles"] = snapshot.get("knowledge_bundles")
    return {"snapshot": filtered_snapshot, "events": payload.get("events", [])}


def _workflow_knowledge_summary(payload):
    snapshot = payload.get("snapshot") or {}
    feedback = snapshot.get("knowledge_feedback") or {}
    usage = (snapshot.get("knowledge_usage") or {}).get("summary") or {}
    return {
        "knowledge_feedback": {
            "decision_count": len(feedback.get("appended_decisions", [])),
            "risk_count": len(feedback.get("appended_risks", [])),
        },
        "knowledge_usage": {
            "recommended_count": len(usage.get("recommended_paths", [])),
            "consumed_count": len(usage.get("consumed_paths", [])),
            "unused_count": len(usage.get("unused_paths", [])),
            "feedback_score": float(usage.get("feedback_score", 0.0) or 0.0),
        },
    }


def _handoff_knowledge_only(records):
    return [record for record in records if record.get("knowledge_recommendation")]


def _handoff_knowledge_summary(records):
    knowledge_records = _handoff_knowledge_only(records)
    top_paths = []
    for record in knowledge_records:
        recommendation = record.get("knowledge_recommendation") or {}
        for group in ("team", "role", "instance"):
            for path in recommendation.get(group, []):
                if path not in top_paths:
                    top_paths.append(path)
    return {
        "record_count": len(records),
        "knowledge_record_count": len(knowledge_records),
        "top_knowledge_paths": top_paths[:10],
    }


def _knowledge_root() -> Path:
    return Path(__file__).resolve().parents[1] / "knowledge"


def _load_workflow_context(context_file: Optional[str]) -> Dict[str, Any]:
    if not context_file:
        return {}
    path = Path(context_file)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(raw)
    return {"project_context": raw}


def prototype_workflow_definition_path() -> Path:
    return Path(__file__).resolve().parents[2] / "workflows" / "prototype_delivery.json"


def _resolve_workflow_path(workflow_file: Optional[str], prototype: bool = False) -> Path:
    if workflow_file:
        return Path(workflow_file)
    if prototype:
        return prototype_workflow_definition_path()
    return default_workflow_definition_path()


def _build_auto_approvals(definition: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    approvals = {}
    for step in definition.get("steps") or []:
        entry_checks = dict(step.get("entry_checks") or {})
        approval_required = bool(step.get("approval_required") or entry_checks.get("approval_required"))
        if str(step.get("type", "")).lower() != "human" and not approval_required:
            continue
        step_id = step.get("id")
        if not step_id:
            continue
        approvals[str(step_id)] = {
            "approved": True,
            "comment": "auto-approved by control plane cli",
        }
    return approvals


def _build_governance_bypass_context(definition: Dict[str, Any]) -> Dict[str, Any]:
    deliverables = set()
    quality_gates: Dict[str, Any] = {}
    coverage: Dict[str, float] = {}
    defect_closure_rate: Dict[str, float] = {}

    for step in definition.get("steps") or []:
        entry_checks = dict(step.get("entry_checks") or {})
        for deliverable in entry_checks.get("required_deliverables") or []:
            deliverables.add(str(deliverable))

        coverage_threshold = entry_checks.get("coverage_threshold")
        if isinstance(coverage_threshold, dict):
            for scope, threshold in coverage_threshold.items():
                coverage[str(scope)] = max(float(threshold), coverage.get(str(scope), 0.0))
        elif coverage_threshold is not None:
            coverage["overall"] = max(float(coverage_threshold), coverage.get("overall", 0.0))

        test_pass_rate = entry_checks.get("test_pass_rate")
        if isinstance(test_pass_rate, dict):
            current = dict(quality_gates.get("test_pass_rate") or {})
            for scope, threshold in test_pass_rate.items():
                current[str(scope)] = max(float(threshold), float(current.get(str(scope), 0.0)))
            quality_gates["test_pass_rate"] = current
        elif test_pass_rate is not None:
            quality_gates["test_pass_rate"] = max(float(test_pass_rate), float(quality_gates.get("test_pass_rate", 0.0)))

        closure_threshold = entry_checks.get("defect_closure_rate")
        if isinstance(closure_threshold, dict):
            for scope, threshold in closure_threshold.items():
                defect_closure_rate[str(scope)] = max(float(threshold), defect_closure_rate.get(str(scope), 0.0))
        elif closure_threshold is not None:
            defect_closure_rate["overall"] = max(float(closure_threshold), defect_closure_rate.get("overall", 0.0))

    if coverage:
        quality_gates["coverage"] = coverage
    if defect_closure_rate:
        quality_gates["defect_closure_rate"] = defect_closure_rate

    return {
        "deliverables": sorted(deliverables),
        "quality_gates": quality_gates,
    }


def _prepare_workflow_context(
    workflow_path: Path,
    context: Optional[Dict[str, Any]] = None,
    auto_approve: bool = False,
) -> Dict[str, Any]:
    prepared = dict(context or {})
    if not auto_approve:
        return prepared
    definition = load_workflow_definition(workflow_path)
    approvals = dict(prepared.get("approvals") or {})
    for step_id, approval in _build_auto_approvals(definition).items():
        approvals.setdefault(step_id, approval)
    prepared["approvals"] = approvals
    bypass = _build_governance_bypass_context(definition)
    prepared["deliverables"] = sorted(set(prepared.get("deliverables", [])) | set(bypass["deliverables"]))
    quality_gates = dict(prepared.get("quality_gates") or {})
    for key, value in bypass["quality_gates"].items():
        if isinstance(value, dict):
            merged = dict(quality_gates.get(key) or {})
            for scope, threshold in value.items():
                merged[scope] = max(float(threshold), float(merged.get(scope, 0.0)))
            quality_gates[key] = merged
        else:
            quality_gates[key] = max(float(value), float(quality_gates.get(key, 0.0)))
    prepared["quality_gates"] = quality_gates
    return prepared


def _execute_workflow_definition(
    workflow_path: Path,
    display_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
):
    definition = load_workflow_definition(workflow_path)
    engine = WorkflowEngine(task_router=TaskRouter(), message_bus=None)
    variables = dict(definition.get("variables") or {})
    if context:
        variables.update(context)
    workflow = engine.create_workflow(
        str(definition.get("workflow_id") or workflow_path.stem),
        display_name or str(definition.get("name") or workflow_path.stem),
        str(definition.get("description") or "workflow from definition"),
        list(definition.get("steps") or []),
        variables,
    )
    result = engine.execute_workflow(workflow.id)
    result["workflow_file"] = str(workflow_path)
    result["workflow_definition"] = {
        "workflow_id": definition.get("workflow_id"),
        "name": definition.get("name"),
    }
    result["knowledge_bundles"] = _build_knowledge_bundles(result)
    return result


def _subprocess_command_runner(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        result.runner_mode = "subprocess"
        return result
    except FileNotFoundError as exc:
        return SimpleNamespace(
            returncode=0,
            stdout=f"dry-run fallback: {command!r}",
            stderr="",
            runner_mode="dry-run-fallback",
            error=str(exc),
        )


def _spawn_command_runner(command):
    try:
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
            runner_mode="spawned",
            pid=process.pid,
        )
    except FileNotFoundError as exc:
        return SimpleNamespace(
            returncode=0,
            stdout=f"dry-run fallback: {command!r}",
            stderr="",
            runner_mode="dry-run-fallback",
            error=str(exc),
        )


def _dispatch_artifact_dir(config, task_id: str) -> Path:
    if config.directories.get("artifacts_dir"):
        artifacts_root = Path(config.directories["artifacts_dir"])
    elif config.directories.get("audit_log"):
        artifacts_root = Path(config.directories["audit_log"]).parent
    else:
        artifacts_root = Path(config.directories["state_dir"]).parent / "artifacts"
    target = artifacts_root / "dispatch" / task_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def _write_dispatch_command_artifact(
    artifact_dir: Path,
    command,
    *,
    task_text: str,
    agent_id: str,
    backend: str,
    wait: bool,
):
    metadata = {
        "command": list(command),
        "task": task_text,
        "agent": agent_id,
        "backend": backend,
        "wait_requested": bool(wait),
        "started_at": time.time(),
    }
    path = artifact_dir / "command.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _persist_dispatch_artifacts(
    artifact_dir: Path,
    command,
    result,
    *,
    task_text: str,
    agent_id: str,
    backend: str,
    wait: bool,
):
    command_path = artifact_dir / "command.json"
    if command_path.exists():
        metadata = json.loads(command_path.read_text(encoding="utf-8"))
    else:
        metadata = {
            "command": list(command),
            "task": task_text,
            "agent": agent_id,
            "backend": backend,
            "wait_requested": bool(wait),
        }
    metadata["returncode"] = int(getattr(result, "returncode", 1))
    metadata["runner_mode"] = getattr(result, "runner_mode", "subprocess")
    metadata["finished_at"] = time.time()
    command_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifact_dir / "stdout.txt").write_text(str(getattr(result, "stdout", "")), encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(str(getattr(result, "stderr", "")), encoding="utf-8")
    refs = sorted(str(path) for path in artifact_dir.rglob("*") if path.is_file())
    return refs


def _stale_task_timeout_seconds(config, snapshot: Dict[str, Any]) -> int:
    thresholds = getattr(config, "thresholds", {}) or {}
    configured_timeout = int(thresholds.get("task_timeout", 300))
    snapshot_timeout = snapshot.get("timeout_seconds")
    if snapshot_timeout is None:
        return max(1, configured_timeout)
    return max(1, min(int(snapshot_timeout), configured_timeout))


def _collect_dispatch_artifact_refs(config, task_id: str):
    artifact_dir = _dispatch_artifact_dir(config, task_id)
    return sorted(str(path) for path in artifact_dir.rglob("*") if path.is_file())


def _reap_stale_running_tasks(config, store: TaskStore, *, current_task_id: Optional[str] = None):
    state_dir = Path(config.directories["state_dir"])
    now = time.time()
    reaped = []
    for snapshot_path in state_dir.glob("*.json"):
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        task_id = str(snapshot.get("task_id") or snapshot_path.stem)
        if task_id == current_task_id:
            continue
        if snapshot.get("status") != TaskStatus.RUNNING.value:
            continue
        updated_at = snapshot.get("updated_at")
        if updated_at is None:
            continue
        stale_after = _stale_task_timeout_seconds(config, snapshot)
        if now - float(updated_at) < stale_after:
            continue
        try:
            store.append_event(
                TaskEvent(
                    event_id=f"evt-reap-{task_id}",
                    task_id=task_id,
                    event_type=EventType.TASK_FAILED,
                    agent_id="system",
                    timestamp=now,
                    attempt=1,
                    status_before=TaskStatus.RUNNING,
                    status_after=TaskStatus.FAILED,
                    summary="task interrupted before terminal event",
                    artifact_refs=_collect_dispatch_artifact_refs(config, task_id),
                    lock_scope=dict(snapshot.get("lock_scope") or {"files": [], "modules": [], "contracts": []}),
                    depends_on=list(snapshot.get("dependencies") or []),
                    metrics_delta={},
                    error_code="PROCESS_INTERRUPTED",
                ),
                expected_version=snapshot["version"],
            )
        except Exception as exc:
            if exc.__class__.__name__ != "VersionConflictError":
                raise
            continue
        reaped.append(task_id)
    return reaped


def execute_dispatch_task(
    task_id: str,
    task_text: str,
    agent_id: str,
    backend: str,
    config,
    wait: bool = False,
    command_runner=None,
):
    effective_config = config or load_control_plane_config()
    store = TaskStore(
        Path(effective_config.directories["state_dir"]),
        Path(effective_config.directories["events_dir"]),
    )
    reaped_tasks = _reap_stale_running_tasks(effective_config, store, current_task_id=task_id)
    snapshot_path = Path(effective_config.directories["state_dir"]) / f"{task_id}.json"
    card = TaskCard(
        task_id=task_id,
        title=f"Dispatch {task_id}",
        goal=task_text,
        scope=[".hermes/team/control_plane/cli.py"],
        lock_scope=LockScope(files=[], modules=["control_plane"], contracts=[]),
        inputs=["dispatch-task"],
        outputs=["command-output"],
        dependencies=[],
        owner_agent=agent_id,
        review_agent=agent_id,
        priority=ControlTaskPriority.P1,
        timeout_seconds=1200,
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=[0]),
        rollback_policy=RollbackPolicy(mode="code"),
        acceptance_criteria=["dispatch command executes"],
        executor_backend=backend,
    )
    if not snapshot_path.exists():
        store.register_task(card)
    runner_meta = {"mode": "subprocess"}
    artifact_dir = _dispatch_artifact_dir(effective_config, task_id)
    selected_runner = command_runner or (_subprocess_command_runner if wait else _spawn_command_runner)

    def wrapped_runner(command):
        _write_dispatch_command_artifact(
            artifact_dir,
            command,
            task_text=task_text,
            agent_id=agent_id,
            backend=backend,
            wait=wait,
        )
        base_result = selected_runner(command)
        artifact_refs = _persist_dispatch_artifacts(
            artifact_dir,
            command,
            base_result,
            task_text=task_text,
            agent_id=agent_id,
            backend=backend,
            wait=wait,
        )
        result = SimpleNamespace(
            returncode=getattr(base_result, "returncode", 1),
            stdout=getattr(base_result, "stdout", ""),
            stderr=getattr(base_result, "stderr", ""),
            runner_mode=getattr(base_result, "runner_mode", "subprocess"),
            artifact_refs=artifact_refs,
        )
        runner_meta["mode"] = getattr(result, "runner_mode", "subprocess")
        return result

    outcome = ControlPlaneExecutor(store=store).execute_task(
        card,
        get_executor_adapter(backend),
        wrapped_runner,
    )
    snapshot = store.read_snapshot(task_id)
    outcome["task_id"] = task_id
    outcome["agent"] = agent_id
    outcome["backend"] = backend
    outcome["final_status"] = snapshot["status"]
    outcome["runner_mode"] = runner_meta["mode"]
    outcome["waited"] = bool(wait)
    outcome["artifact_refs"] = list(outcome.get("artifact_refs", []))
    outcome["reaped_running_tasks"] = reaped_tasks
    return outcome


def build_parser():
    parser = argparse.ArgumentParser(description="Control plane unified CLI")
    subparsers = parser.add_subparsers(dest="command")

    dispatch = subparsers.add_parser("dispatch", help="通过主控制平面分发任务")
    dispatch.add_argument("task")
    dispatch.add_argument("--actor", default="admin")
    dispatch.add_argument("--priority", choices=["critical", "high", "normal", "low"], default="normal")
    dispatch.add_argument("--backend")
    dispatch.add_argument("--execute", action="store_true")
    dispatch.add_argument("--wait", action="store_true")

    workflow = subparsers.add_parser("workflow", help="执行标准工作流")
    workflow.add_argument("--name", default="项目开发")
    workflow.add_argument("--workflow-file")
    workflow.add_argument("--context-file")
    workflow.add_argument("--prototype", action="store_true")
    workflow.add_argument("--auto-approve", action="store_true")

    query = subparsers.add_parser("query", help="查询 workflow / handoff / knowledge / audit")
    query.add_argument("resource", choices=["workflow", "handoff", "knowledge", "audit"])
    query.add_argument("--id")
    query.add_argument("--workflow-id")
    query.add_argument("--message-id")
    query.add_argument("--target-agent")
    query.add_argument("--status")
    query.add_argument("--action")
    query.add_argument("--agent")
    query.add_argument("--role")
    query.add_argument("--task-type")
    query.add_argument("--risk-tag")
    query.add_argument("--review-status")
    query.add_argument("--search")
    query.add_argument("--actor", default="viewer")
    query.add_argument("--prune", action="store_true")
    query.add_argument("--archive", action="store_true")
    query.add_argument("--delete", action="store_true")
    query.add_argument("--knowledge-only", action="store_true")
    query.add_argument("--summary", action="store_true")

    monitor = subparsers.add_parser("monitor", help="查看监控数据")
    monitor.add_argument("--dashboard", action="store_true")
    monitor.add_argument("--prometheus", action="store_true")

    batch = subparsers.add_parser("control-plane-run", help="运行控制平面批次")
    batch.add_argument("--max-workers", type=int, default=2)
    batch.add_argument("--workflow-file")
    batch.add_argument("--context-file")
    batch.add_argument("--name", default="项目开发")
    batch.add_argument("--prototype", action="store_true")
    batch.add_argument("--auto-approve", action="store_true")

    validate = subparsers.add_parser("validate", help="运行真实负载验证")
    validate.add_argument("--replicas", type=int, default=4)
    validate.add_argument("--max-workers", type=int, default=4)

    tool_run = subparsers.add_parser("tool-run", help="运行最小工具运行时")
    tool_run.add_argument("tool")
    tool_run.add_argument("task")
    tool_run.add_argument("--agent")
    tool_run.add_argument("--backend")
    tool_run.add_argument("--actor", default="admin")
    tool_run.add_argument("--session-id")
    tool_run.add_argument("--resume", action="store_true")

    tool_session = subparsers.add_parser("tool-session", help="查询 tool runtime session")
    tool_session_sub = tool_session.add_subparsers(dest="tool_session_command")
    tool_session_sub.add_parser("list", help="列出 session")
    tool_session_get = tool_session_sub.add_parser("get", help="读取指定 session")
    tool_session_get.add_argument("--session-id", required=True)

    return parser


def run_tool_command(
    tool_name: str,
    task: str,
    actor: str = "admin",
    requested_agent: str | None = None,
    backend_override: str | None = None,
    session_id: str | None = None,
    resume: bool = False,
    config=None,
):
    effective_config = config or load_control_plane_config()
    session_store = SessionStore(Path(effective_config.directories["state_dir"]) / "tool-runtime" / "sessions")
    if resume:
        if not session_id:
            raise ValueError("--resume requires --session-id")
        snapshot = session_store.read_session(session_id)
        context = build_tool_execution_context(
            task=snapshot["task"],
            router=TaskRouter(),
            requested_agent=snapshot["agent_id"],
            backend_override=snapshot["backend"],
        )
        context.intent = snapshot["intent"]
        context.knowledge_bundle = snapshot["knowledge_bundle"]
        context.actor = actor
        context.session_id = snapshot["session_id"]
    else:
        router = TaskRouter()
        context = build_tool_execution_context(
            task=task,
            router=router,
            requested_agent=requested_agent,
            backend_override=backend_override,
        )
        context.actor = actor
        created = session_store.create_session(
            task=task,
            agent_id=context.agent_id,
            backend=context.backend,
            knowledge_bundle=context.knowledge_bundle,
            intent=context.intent,
        )
        context.session_id = created["session_id"]
    registry = build_default_tool_registry()
    normalized_tool_name = tool_name.split(":", 1)[1] if tool_name.startswith("builtin:") else tool_name
    tool = registry.get(normalized_tool_name)
    transcript_path = Path(effective_config.directories["state_dir"]) / "tool-runtime" / "tool-transcript.jsonl"
    executor = ToolExecutor(transcript_store=ToolTranscriptStore(transcript_path))
    payload = {
        "task": task if not resume else snapshot["task"],
        "agent_id": context.agent_id,
        "backend": context.backend,
        "workflow_id": context.task_id,
        "handoff_dir": str(Path(effective_config.directories["state_dir"]) / "handoffs"),
        "workflow_runtime_dir": effective_config.directories.get("workflow_runtime_dir"),
        "message_bus_dir": effective_config.directories.get("message_bus_dir"),
    }
    result = executor.execute_many(context, [(tool, payload)])[0]
    session_store.update_session(
        context.session_id,
        status="done" if result.ok else "failed",
        last_tool_name=tool.name,
        last_tool_result={
            "ok": result.ok,
            "content_preview": result.content[:200],
            "error": result.error,
        },
        history_entry={
            "tool_name": tool.name,
            "ok": result.ok,
            "content_preview": result.content[:200],
        },
    )
    response = result.to_dict()
    response["session_id"] = context.session_id
    return response


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_control_plane_config()
    policy = build_default_rbac_policy()
    approval_gate = ApprovalGate(config.sensitive_actions)
    audit = AuditLogger(Path(config.directories["audit_log"]))

    if args.command == "dispatch":
        effective_actor = _normalize_dispatch_actor(args.actor)
        if not policy.is_allowed(effective_actor, "control_plane.dispatch"):
            raise PermissionError("actor is not allowed to dispatch")
        router = TaskRouter()
        bus = get_bus()
        for agent_id in router.agents:
            bus.register_agent(agent_id)
        priority = TaskPriority[args.priority.upper()]
        agent_id, task = router.route_task(args.task, priority)
        bus.send(bus.create_task_message(args.actor, agent_id, task.id, args.task))
        audit.log("dispatch", {"actor": args.actor, "task": args.task, "agent": agent_id})
        payload = {"agent": agent_id, "task_id": task.id}
        recommendation = _extract_knowledge_recommendation(task)
        if recommendation:
            payload["knowledge_recommendation"] = recommendation
            payload["knowledge_bundle"] = build_knowledge_bundle(recommendation)
        if args.execute:
            backend_recommendation = (
                getattr(task, "routing_reason", {}).get("backend_recommendation", {})
                if isinstance(getattr(task, "routing_reason", {}), dict)
                else {}
            )
            backend = args.backend or backend_recommendation.get("selected_backend") or config.default_executor
            payload["execution"] = execute_dispatch_task(
                task_id=task.id,
                task_text=args.task,
                agent_id=agent_id,
                backend=backend,
                config=config,
                wait=args.wait,
            )
            payload["success"] = bool(payload["execution"].get("success"))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "workflow":
        workflow_path = _resolve_workflow_path(args.workflow_file, prototype=getattr(args, "prototype", False))
        context = _load_workflow_context(getattr(args, "context_file", None))
        context = _prepare_workflow_context(
            workflow_path,
            context=context,
            auto_approve=getattr(args, "auto_approve", False),
        )
        context.setdefault("project_name", args.name)
        result = _execute_workflow_definition(
            workflow_path=workflow_path,
            display_name=args.name,
            context=context,
        )
        audit.log(
            "workflow",
            {
                "workflow_id": result.get("workflow_id"),
                "workflow_file": str(workflow_path),
                "success": result.get("success", False),
            },
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    if args.command == "query":
        manage_requested = any(getattr(args, name, False) for name in ("prune", "archive", "delete"))
        action = {
            "workflow": "query.workflow",
            "handoff": "query.handoff",
            "knowledge": "query.knowledge",
            "audit": "query.audit.read",
        }[args.resource]
        if not policy.is_allowed(args.actor, action):
            raise PermissionError("actor is not allowed to query")
        if manage_requested:
            manage_action = f"query.{args.resource}.manage"
            if not policy.is_allowed(args.actor, manage_action):
                raise PermissionError("actor is not allowed to manage runtime records")

        query_filters = {
            "id": getattr(args, "id", None),
            "workflow_id": getattr(args, "workflow_id", None),
            "message_id": getattr(args, "message_id", None),
            "target_agent": getattr(args, "target_agent", None),
            "status": getattr(args, "status", None),
            "action": getattr(args, "action", None),
        }
        extended_query_filters = {
            "agent": getattr(args, "agent", None),
            "role": getattr(args, "role", None),
            "task_type": getattr(args, "task_type", None),
            "risk_tag": getattr(args, "risk_tag", None),
            "review_status": getattr(args, "review_status", None),
            "search": getattr(args, "search", None),
        }

        if args.resource == "workflow":
            store = WorkflowRunStore(Path(config.directories["workflow_runtime_dir"]))
            if manage_requested:
                if sum(bool(getattr(args, name, False)) for name in ("prune", "archive", "delete")) > 1:
                    raise ValueError("workflow manage supports one action at a time")
                if getattr(args, "prune", False):
                    if approval_gate.requires_approval("workflow.prune"):
                        raise PermissionError("workflow prune requires approval")
                    payload = store.prune_workflows(status=getattr(args, "status", None))
                    audit.log(
                        "workflow.prune",
                        {
                            "actor": args.actor,
                            "status": getattr(args, "status", None),
                            **payload,
                        },
                    )
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                    return payload
                if not getattr(args, "id", None):
                    raise ValueError("workflow manage requires --id")
                if getattr(args, "archive", False):
                    if approval_gate.requires_approval("workflow.archive"):
                        raise PermissionError("workflow archive requires approval")
                    payload = store.archive_workflow(getattr(args, "id", None))
                    audit.log(
                        "workflow.archive",
                        {
                            "actor": args.actor,
                            "workflow_id": getattr(args, "id", None),
                            **payload,
                        },
                    )
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                    return payload
                if approval_gate.requires_approval("workflow.delete"):
                    raise PermissionError("workflow delete requires approval")
                payload = store.delete_workflow(getattr(args, "id", None))
                audit.log(
                    "workflow.delete",
                    {
                        "actor": args.actor,
                        "workflow_id": getattr(args, "id", None),
                        **payload,
                    },
                )
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return payload
            if not getattr(args, "id", None):
                raise ValueError("workflow query requires --id")
            payload = {
                "snapshot": store.read_snapshot(getattr(args, "id", None)),
                "events": store.list_step_events(getattr(args, "id", None)),
            }
            if args.knowledge_only:
                payload = _workflow_knowledge_payload(payload)
            if args.summary:
                payload["summary"] = _workflow_knowledge_summary(payload)
            result_count = 1 if payload["snapshot"] is not None else 0
        elif args.resource == "handoff":
            handoff_dir = config.directories.get("handoff_runtime_dir")
            if handoff_dir is None:
                handoff_dir = str(Path(config.directories["state_dir"]) / "handoffs")
            store = HandoffRunStore(Path(handoff_dir))
            if manage_requested:
                if sum(bool(getattr(args, name, False)) for name in ("prune", "archive", "delete")) > 1:
                    raise ValueError("handoff manage supports one action at a time")
                filters = {
                    "workflow_id": getattr(args, "workflow_id", None),
                    "message_id": getattr(args, "message_id", None),
                    "target_agent": getattr(args, "target_agent", None),
                    "status": getattr(args, "status", None),
                }
                if not any(filters.values()):
                    raise ValueError("handoff manage requires at least one filter")
                if getattr(args, "prune", False):
                    if approval_gate.requires_approval("handoff.prune"):
                        raise PermissionError("handoff prune requires approval")
                    deleted = store.prune_records(
                        workflow_id=getattr(args, "workflow_id", None),
                        message_id=getattr(args, "message_id", None),
                        target_agent=getattr(args, "target_agent", None),
                        status=getattr(args, "status", None),
                    )
                    payload = {"deleted_count": deleted}
                    audit.log(
                        "handoff.prune",
                        {
                            "actor": args.actor,
                            **filters,
                            **payload,
                        },
                    )
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                    return payload
                if getattr(args, "archive", False):
                    if approval_gate.requires_approval("handoff.archive"):
                        raise PermissionError("handoff archive requires approval")
                    payload = store.archive_records(
                        workflow_id=getattr(args, "workflow_id", None),
                        message_id=getattr(args, "message_id", None),
                        target_agent=getattr(args, "target_agent", None),
                        status=getattr(args, "status", None),
                    )
                    audit.log(
                        "handoff.archive",
                        {
                            "actor": args.actor,
                            **filters,
                            **payload,
                        },
                    )
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                    return payload
                if approval_gate.requires_approval("handoff.delete"):
                    raise PermissionError("handoff delete requires approval")
                deleted = store.delete_records(
                    workflow_id=getattr(args, "workflow_id", None),
                    message_id=getattr(args, "message_id", None),
                    target_agent=getattr(args, "target_agent", None),
                    status=getattr(args, "status", None),
                )
                payload = {"deleted_count": deleted}
                audit.log(
                    "handoff.delete",
                    {
                        "actor": args.actor,
                        **filters,
                        **payload,
                    },
                )
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return payload
            try:
                records = store.list_records(
                    workflow_id=getattr(args, "workflow_id", None),
                    target_agent=getattr(args, "target_agent", None),
                    status=getattr(args, "status", None),
                    message_id=getattr(args, "message_id", None),
                )
            except TypeError:
                records = store.list_records(
                    workflow_id=getattr(args, "workflow_id", None),
                    target_agent=getattr(args, "target_agent", None),
                    status=getattr(args, "status", None),
                )
                if getattr(args, "message_id", None):
                    records = [
                        record for record in records if record.get("message_id") == getattr(args, "message_id", None)
                    ]
            if getattr(args, "status", None):
                records = [record for record in records if record.get("status") == getattr(args, "status", None)]
            normalized_records = [_normalize_handoff_record(record) for record in records]
            if args.knowledge_only:
                normalized_records = _handoff_knowledge_only(normalized_records)
            payload = {"records": normalized_records}
            if args.summary:
                payload["summary"] = _handoff_knowledge_summary(normalized_records if args.knowledge_only else [_normalize_handoff_record(record) for record in records])
            result_count = len(records)
        elif args.resource == "knowledge":
            if args.action in {"accept", "reject", "archive"} and args.id:
                payload = apply_governance_action(
                    knowledge_root=_knowledge_root(),
                    action=args.action,
                    actor=args.actor,
                    entry_id=args.id,
                )
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return payload
            payload = query_knowledge_records(
                root=_knowledge_root(),
                query_text=extended_query_filters["search"],
                filters={
                    "agent": extended_query_filters["agent"],
                    "role": extended_query_filters["role"],
                    "task_type": extended_query_filters["task_type"],
                    "risk_tag": extended_query_filters["risk_tag"],
                    "review_status": extended_query_filters["review_status"],
                    "workflow_id": args.workflow_id,
                },
            )
            result_count = len(payload["records"])
        else:
            records = audit.read_all()
            if args.action:
                records = [record for record in records if record.get("action") == args.action]
            payload = {"records": records}
            result_count = len(records)

        audit_filters = dict(query_filters)
        audit_filters.update({key: value for key, value in extended_query_filters.items() if value is not None})
        audit.log(
            "query",
            {
                "actor": args.actor,
                "resource": args.resource,
                "filters": audit_filters,
                "result_count": result_count,
            },
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "monitor":
        monitor = get_monitor()
        if args.prometheus:
            refresh_repository_metrics()
            text = export_metrics_text()
            print(text, end="")
            return text
        payload = monitor.get_dashboard_data() if args.dashboard or not args.prometheus else {}
        task_router = getattr(monitor, "task_router", None)
        workflow_runtime_dir = getattr(monitor, "workflow_runtime_dir", None)
        payload.update(
            {
                "knowledge_heat_ranking": build_knowledge_heat_ranking(task_router),
                "knowledge_consumption_by_agent": build_consumption_by_agent(task_router),
                "unused_recommendations": build_unused_recommendations(task_router),
                "high_risk_workflow_coverage": build_high_risk_coverage(workflow_runtime_dir),
                "knowledge_effectiveness_report": build_knowledge_effectiveness_report(workflow_runtime_dir),
                "pending_governance_counts": build_pending_governance_counts(_knowledge_root()),
            }
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "control-plane-run":
        workflow_path = _resolve_workflow_path(args.workflow_file, prototype=getattr(args, "prototype", False))
        context = _load_workflow_context(getattr(args, "context_file", None))
        context = _prepare_workflow_context(
            workflow_path,
            context=context,
            auto_approve=getattr(args, "auto_approve", False),
        )
        context.setdefault("max_workers", args.max_workers)
        context.setdefault("project_name", args.name)
        result = _execute_workflow_definition(
            workflow_path=workflow_path,
            display_name=args.name,
            context=context,
        )
        audit.log(
            "control-plane-run",
            {
                "max_workers": args.max_workers,
                "workflow_id": result.get("workflow_id"),
                "workflow_file": str(workflow_path),
                "success": result.get("success", False),
            },
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    if args.command == "validate":
        artifacts_dir = Path(config.directories.get("artifacts_dir", Path(config.directories["audit_log"]).parent))
        validation_root = artifacts_dir / "validation-suite" / f"cli-run-{int(time.time() * 1000)}"
        result = run_real_load_validation(
            replicas=args.replicas,
            max_workers=args.max_workers,
            state_dir=validation_root / "state",
            events_dir=validation_root / "events",
        )
        checks = result.get("checks", {})
        result["success"] = all(
            checks.get(key, False)
            for key in ("all_tasks_done", "no_failed_tasks", "no_blocked_tasks", "no_conflicted_tasks")
        )
        audit.log("validate", {"replicas": args.replicas, "max_workers": args.max_workers})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    if args.command == "tool-run":
        result = run_tool_command(
            tool_name=args.tool,
            task=args.task,
            actor=args.actor,
            requested_agent=args.agent,
            backend_override=args.backend,
            session_id=args.session_id,
            resume=args.resume,
            config=config,
        )
        audit.log(
            "tool-run",
            {"tool": args.tool, "actor": args.actor, "session_id": result.get("session_id")},
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    if args.command == "tool-session":
        session_store = SessionStore(Path(config.directories["state_dir"]) / "tool-runtime" / "sessions")
        if args.tool_session_command == "list":
            payload = {"sessions": session_store.list_sessions()}
        elif args.tool_session_command == "get":
            payload = session_store.read_session(args.session_id)
        else:
            payload = {"sessions": session_store.list_sessions()}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    parser.print_help()
    return None


if __name__ == "__main__":
    result = main()
    raise SystemExit(0 if (result is None or result.get("success", True)) else 1)
