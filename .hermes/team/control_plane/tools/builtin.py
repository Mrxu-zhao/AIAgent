from __future__ import annotations

from pathlib import Path
from typing import Dict

from adapters import get_executor_adapter
from handoff_runtime import HandoffRunStore
from tools.registry import ToolRegistry
from tools.spec import ToolExecutionContext, ToolResult, ToolSpec
from workflow_runtime import WorkflowRunStore


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


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolSpec(
                name="dispatch_task",
                description="build a backend dispatch command",
                input_schema={"task": "str", "agent_id": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=dispatch_task_handler,
            ),
            ToolSpec(
                name="query_workflow",
                description="read workflow runtime snapshot and events",
                input_schema={"workflow_id": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=query_workflow_handler,
            ),
            ToolSpec(
                name="query_handoff",
                description="read handoff runtime records",
                input_schema={"workflow_id": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=query_handoff_handler,
            ),
            ToolSpec(
                name="read_knowledge",
                description="read recommended knowledge bundle",
                input_schema={},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=read_knowledge_handler,
            ),
        ]
    )
