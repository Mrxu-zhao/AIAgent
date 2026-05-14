from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

from adapters import get_executor_adapter
from handoff_runtime import HandoffRunStore
from persistent_bus import PersistentMessageBus
from runtime.rules import repository_root
from tools.registry import ToolRegistry
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec
from workflow_runtime import WorkflowRunStore

FRAMEWORK_CORE_DIR = Path(__file__).resolve().parents[2] / "调度框架" / "core"
if str(FRAMEWORK_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_CORE_DIR))

from task_router import TaskPriority, TaskRouter  # noqa: E402


def dispatch_task_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    backend = str(payload.get("backend") or context.backend)
    agent_id = str(payload.get("agent_id") or context.agent_id)
    task = str(payload["task"])
    adapter = get_executor_adapter(backend)
    command = adapter.build_dispatch_command(agent_id, task)
    return ToolResult.ok_result(
        content=" ".join(command),
        structured_data={
            "command": command,
            "agent_id": agent_id,
            "backend": backend,
            "task": task,
        },
    )


def route_task_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    router = TaskRouter()
    agent_id, task = router.route_task(str(payload["task"]), TaskPriority.NORMAL)
    return ToolResult.ok_result(
        content=f"route:{agent_id}",
        structured_data={
            "agent_id": agent_id,
            "task_id": task.id,
            "intent": task.intent,
            "routing_reason": task.routing_reason,
        },
    )


def query_workflow_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    workflow_id = str(payload["workflow_id"])
    store = WorkflowRunStore(
        Path(payload["workflow_runtime_dir"]) if payload.get("workflow_runtime_dir") else None
    )
    return ToolResult.ok_result(
        content=f"workflow:{workflow_id}",
        structured_data={
            "snapshot": store.read_snapshot(workflow_id),
            "events": store.list_step_events(workflow_id),
        },
    )


def query_bus_status_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    base_dir = Path(payload["message_bus_dir"]) if payload.get("message_bus_dir") else None
    bus = PersistentMessageBus(base_dir=base_dir)
    return ToolResult.ok_result(
        content="bus-status",
        structured_data=bus.stats(),
    )


def query_handoff_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    store = HandoffRunStore(Path(payload["handoff_dir"]) if payload.get("handoff_dir") else None)
    records = store.list_records(
        workflow_id=payload.get("workflow_id"),
        target_agent=payload.get("target_agent"),
        status=payload.get("status"),
    )
    return ToolResult.ok_result(
        content=f"handoff:{len(records)}",
        structured_data={"records": records},
    )


def find_knowledge_files_handler(
    context: ToolExecutionContext,
    _payload: Dict[str, object],
) -> ToolResult:
    return ToolResult.ok_result(
        content=f"knowledge-files:{len(context.knowledge_bundle.get('paths', []))}",
        structured_data={
            "paths": list(context.knowledge_bundle.get("paths", [])),
            "resolved_paths": list(context.knowledge_bundle.get("resolved_paths", [])),
        },
        artifacts=list(context.knowledge_bundle.get("paths", [])),
    )


def read_knowledge_handler(context: ToolExecutionContext, _payload: Dict[str, object]) -> ToolResult:
    records = []
    for relative_path, resolved_path in zip(
        context.knowledge_bundle.get("paths", []),
        context.knowledge_bundle.get("resolved_paths", []),
    ):
        path = Path(resolved_path)
        if not path.exists():
            continue
        records.append(
            {
                "path": relative_path,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return ToolResult.ok_result(
        content=f"knowledge:{len(records)}",
        structured_data={"items": records},
        artifacts=[item["path"] for item in records],
    )


def read_file_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    root = repository_root().resolve()
    raw_path = Path(str(payload["path"]))
    resolved = (root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("path must stay within repository root")
    if not resolved.exists():
        raise ValueError(f"file does not exist: {resolved}")
    return ToolResult.ok_result(
        content=resolved.read_text(encoding="utf-8"),
        structured_data={"path": str(raw_path), "resolved_path": str(resolved)},
        artifacts=[str(raw_path)],
    )


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolSpec(
                name="route_task",
                description="route task to the best agent",
                input_schema={"task": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=route_task_handler,
                action="tool.route",
            ),
            ToolSpec(
                name="dispatch_task",
                description="build a backend dispatch command",
                input_schema={"task": "str", "agent_id": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=dispatch_task_handler,
                action="tool.dispatch",
            ),
            ToolSpec(
                name="query_workflow",
                description="read workflow runtime snapshot and events",
                input_schema={"workflow_id": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=query_workflow_handler,
                action="tool.read.workflow",
            ),
            ToolSpec(
                name="query_bus_status",
                description="read message bus counters",
                input_schema={},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=query_bus_status_handler,
                action="tool.read.bus",
            ),
            ToolSpec(
                name="query_handoff",
                description="read handoff runtime records",
                input_schema={"workflow_id": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=query_handoff_handler,
                action="tool.read.handoff",
            ),
            ToolSpec(
                name="find_knowledge_files",
                description="list recommended knowledge bundle files",
                input_schema={},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=find_knowledge_files_handler,
                action="tool.read.knowledge",
            ),
            ToolSpec(
                name="read_knowledge",
                description="read recommended knowledge bundle",
                input_schema={},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=read_knowledge_handler,
                action="tool.read.knowledge",
            ),
            ToolSpec(
                name="read_file",
                description="read a repository file",
                input_schema={"path": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=read_file_handler,
                action="tool.read.file",
            ),
        ]
    )
