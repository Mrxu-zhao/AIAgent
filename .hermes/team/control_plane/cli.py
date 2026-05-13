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
from message_bus import get_bus
from monitor import get_monitor
from observability.metrics import refresh_repository_metrics
from observability.prometheus_exporter import export_metrics_text
from runner import run_task_batch
from task_router import TaskPriority, TaskRouter
from validation import run_real_load_validation
from workflow_engine import WorkflowEngine, create_standard_project_workflow


def build_parser():
    parser = argparse.ArgumentParser(description="Control plane unified CLI")
    subparsers = parser.add_subparsers(dest="command")

    dispatch = subparsers.add_parser("dispatch", help="通过主控制平面分发任务")
    dispatch.add_argument("task")
    dispatch.add_argument("--actor", default="admin")
    dispatch.add_argument("--priority", choices=["critical", "high", "normal", "low"], default="normal")

    workflow = subparsers.add_parser("workflow", help="执行标准工作流")
    workflow.add_argument("--name", default="项目开发")

    monitor = subparsers.add_parser("monitor", help="查看监控数据")
    monitor.add_argument("--dashboard", action="store_true")
    monitor.add_argument("--prometheus", action="store_true")

    batch = subparsers.add_parser("control-plane-run", help="运行控制平面批次")
    batch.add_argument("--max-workers", type=int, default=2)

    validate = subparsers.add_parser("validate", help="运行真实负载验证")
    validate.add_argument("--replicas", type=int, default=4)
    validate.add_argument("--max-workers", type=int, default=4)

    return parser


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

    parser.print_help()
    return None


if __name__ == "__main__":
    main()
