from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FRAMEWORK_CORE_DIR = Path(__file__).resolve().parents[1] / "调度框架" / "core"
if str(FRAMEWORK_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_CORE_DIR))

from config import load_control_plane_config
from governance.approval import ApprovalGate
from governance.audit import AuditLogger
from governance.rbac import build_default_rbac_policy
from handoff_runtime import HandoffRunStore
from message_bus import get_bus
from monitor import get_monitor
from observability.metrics import refresh_repository_metrics
from observability.prometheus_exporter import export_metrics_text
from runner import run_task_batch
from runtime.context import build_tool_execution_context
from task_router import TaskPriority, TaskRouter
from tools.builtin import build_default_tool_registry
from tools.executor import ToolExecutor
from tools.session_store import SessionStore
from tools.transcript import ToolTranscriptStore
from validation import run_real_load_validation
from workflow_engine import WorkflowEngine, create_standard_project_workflow
from workflow_runtime import WorkflowRunStore


def build_parser():
    parser = argparse.ArgumentParser(description="Control plane unified CLI")
    subparsers = parser.add_subparsers(dest="command")

    dispatch = subparsers.add_parser("dispatch", help="通过主控制平面分发任务")
    dispatch.add_argument("task")
    dispatch.add_argument("--actor", default="admin")
    dispatch.add_argument("--priority", choices=["critical", "high", "normal", "low"], default="normal")

    workflow = subparsers.add_parser("workflow", help="执行标准工作流")
    workflow.add_argument("--name", default="项目开发")

    query = subparsers.add_parser("query", help="查询 workflow / handoff / audit")
    query.add_argument("resource", choices=["workflow", "handoff", "audit"])
    query.add_argument("--id")
    query.add_argument("--workflow-id")
    query.add_argument("--message-id")
    query.add_argument("--target-agent")
    query.add_argument("--status")
    query.add_argument("--action")
    query.add_argument("--actor", default="viewer")

    monitor = subparsers.add_parser("monitor", help="查看监控数据")
    monitor.add_argument("--dashboard", action="store_true")
    monitor.add_argument("--prometheus", action="store_true")

    batch = subparsers.add_parser("control-plane-run", help="运行控制平面批次")
    batch.add_argument("--max-workers", type=int, default=2)

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
    ApprovalGate(config.sensitive_actions)
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
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "workflow":
        engine = WorkflowEngine(task_router=TaskRouter(), message_bus=None)
        workflow = engine.create_workflow(
            "unified_cli_workflow",
            args.name,
            "standard workflow",
            create_standard_project_workflow(),
            {"project_name": args.name},
        )
        result = engine.execute_workflow(workflow.id)
        audit.log("workflow", {"workflow_id": workflow.id, "success": result.get("success", False)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    if args.command == "query":
        action = {
            "workflow": "query.workflow",
            "handoff": "query.handoff",
            "audit": "query.audit.read",
        }[args.resource]
        if not policy.is_allowed(args.actor, action):
            raise PermissionError("actor is not allowed to query")

        query_filters = {
            "id": args.id,
            "workflow_id": args.workflow_id,
            "message_id": args.message_id,
            "target_agent": args.target_agent,
            "status": args.status,
            "action": args.action,
        }

        if args.resource == "workflow":
            if not args.id:
                raise ValueError("workflow query requires --id")
            store = WorkflowRunStore(Path(config.directories["workflow_runtime_dir"]))
            payload = {
                "snapshot": store.read_snapshot(args.id),
                "events": store.list_step_events(args.id),
            }
            result_count = 1 if payload["snapshot"] is not None else 0
        elif args.resource == "handoff":
            store = HandoffRunStore(Path(config.directories["state_dir"]) / "handoffs")
            records = store.list_records(
                workflow_id=args.workflow_id,
                target_agent=args.target_agent,
                status=args.status,
            )
            if args.message_id:
                records = [record for record in records if record.get("message_id") == args.message_id]
            if args.status:
                records = [record for record in records if record.get("status") == args.status]
            payload = {"records": records}
            result_count = len(records)
        else:
            records = audit.read_all()
            if args.action:
                records = [record for record in records if record.get("action") == args.action]
            payload = {"records": records}
            result_count = len(records)

        audit.log(
            "query",
            {
                "actor": args.actor,
                "resource": args.resource,
                "filters": query_filters,
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
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    if args.command == "control-plane-run":
        result = run_task_batch(max_workers=args.max_workers)
        audit.log("control-plane-run", {"max_workers": args.max_workers})
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
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
