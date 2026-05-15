from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

FRAMEWORK_CORE_DIR = Path(__file__).resolve().parents[1] / "调度框架" / "core"
if str(FRAMEWORK_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_CORE_DIR))

from config import load_control_plane_config
from governance.approval import ApprovalGate
from governance.audit import AuditLogger
from governance.rbac import build_default_rbac_policy
from handoff_runtime import HandoffRunStore
from knowledge.analytics import (
    build_consumption_by_agent,
    build_high_risk_coverage,
    build_knowledge_heat_ranking,
    build_pending_governance_counts,
    build_unused_recommendations,
)
from knowledge.governance import apply_governance_action
from knowledge.query import query_knowledge_records
from message_bus import get_bus
from monitor import get_monitor
from observability.metrics import refresh_repository_metrics
from observability.prometheus_exporter import export_metrics_text
from runtime.context import build_tool_execution_context
from runtime.rules import build_knowledge_bundle
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
from workflows.executor import execute_role_workflow


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
    filtered_snapshot = {
        "workflow_id": snapshot.get("workflow_id"),
        "status": snapshot.get("status"),
        "knowledge_feedback": knowledge_feedback,
    }
    if snapshot.get("knowledge_recommendations") is not None:
        filtered_snapshot["knowledge_recommendations"] = snapshot.get("knowledge_recommendations")
    if snapshot.get("knowledge_bundles") is not None:
        filtered_snapshot["knowledge_bundles"] = snapshot.get("knowledge_bundles")
    return {"snapshot": filtered_snapshot, "events": payload.get("events", [])}


def _workflow_knowledge_summary(payload):
    snapshot = payload.get("snapshot") or {}
    feedback = snapshot.get("knowledge_feedback") or {}
    return {
        "knowledge_feedback": {
            "decision_count": len(feedback.get("appended_decisions", [])),
            "risk_count": len(feedback.get("appended_risks", [])),
        }
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
    return json.loads(Path(context_file).read_text(encoding="utf-8"))


def _load_role_workflow_context(context_file: Optional[str]) -> Dict[str, Any]:
    return _load_workflow_context(context_file)


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


def build_parser():
    parser = argparse.ArgumentParser(description="Control plane unified CLI")
    subparsers = parser.add_subparsers(dest="command")

    dispatch = subparsers.add_parser("dispatch", help="通过主控制平面分发任务")
    dispatch.add_argument("task")
    dispatch.add_argument("--actor", default="admin")
    dispatch.add_argument("--priority", choices=["critical", "high", "normal", "low"], default="normal")

    workflow = subparsers.add_parser("workflow", help="执行标准工作流")
    workflow.add_argument("--name", default="项目开发")
    workflow.add_argument("--workflow-file")
    workflow.add_argument("--context-file")

    role_workflow = subparsers.add_parser("role-workflow", help="执行角色个人工作流")
    role_workflow.add_argument("--workflow-id", required=True)
    role_workflow.add_argument("--feature")
    role_workflow.add_argument("--stack")
    role_workflow.add_argument("--context-file")
    role_workflow.add_argument("--actor", default="admin")

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
    tool = registry.get(tool_name)
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
        if not policy.is_allowed(args.actor, "control_plane.dispatch"):
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
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "workflow":
        workflow_path = Path(args.workflow_file) if args.workflow_file else default_workflow_definition_path()
        context = _load_workflow_context(getattr(args, "context_file", None))
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

    if args.command == "role-workflow":
        context = _load_role_workflow_context(getattr(args, "context_file", None))
        if args.feature:
            context.setdefault("feature", args.feature)
            context.setdefault("Feature", args.feature.replace("-", " ").title().replace(" ", ""))
        if args.stack:
            context.setdefault("stack", args.stack)
        context.setdefault("actor", args.actor)
        result = execute_role_workflow(args.workflow_id, context_values=context)
        audit.log(
            "role-workflow",
            {
                "workflow_id": result.get("workflow_id"),
                "role": result.get("role"),
                "success": result.get("ok", False),
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
                "pending_governance_counts": build_pending_governance_counts(_knowledge_root()),
            }
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "control-plane-run":
        workflow_path = Path(args.workflow_file) if args.workflow_file else default_workflow_definition_path()
        context = _load_workflow_context(getattr(args, "context_file", None))
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
        result = run_real_load_validation(replicas=args.replicas, max_workers=args.max_workers)
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
    main()
