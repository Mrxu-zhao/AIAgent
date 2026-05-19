from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

from adapters import get_executor_adapter
from collaboration.kanban import KanbanBoard
from collaboration.kanban import TaskPriority as KanbanTaskPriority
from config import load_control_plane_config
from handoff_runtime import HandoffRunStore
from integrations.oauth import OAuthManager
from intelligence.code_intelligence import CodeReviewer, detect_language, get_code_hub
from knowledge.consumer import expand_excerpt_content
from knowledge.query import query_knowledge_records
from persistent_bus import PersistentMessageBus
from runtime.rules import repository_root
from tools.common_tools import (
    generate_code_handler,
    run_command_handler,
    search_code_handler,
    write_file_handler,
)
from tools.registry import ToolRegistry
from tools.role_tools.architect_tools import (
    generate_architecture_doc_handler,
    review_api_design_handler,
)
from tools.role_tools.backend_tools import (
    generate_controller_handler,
    generate_mapper_handler,
    generate_service_handler,
    run_unit_tests_handler,
)
from tools.role_tools.dba_tools import analyze_slow_query_handler, generate_ddl_handler
from tools.role_tools.devops_tools import (
    generate_dockerfile_handler,
    generate_k8s_manifests_handler,
)
from tools.role_tools.frontend_tools import (
    generate_api_client_handler,
    generate_vue_component_handler,
    run_linter_handler,
)
from tools.role_tools.qa_tools import generate_test_cases_handler, run_api_tests_handler
from tools.role_tools.requirements_tools import generate_prd_handler
from tools.role_tools.ucd_tools import generate_design_spec_handler
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


def echo_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    message = str(payload.get("task", ""))
    return ToolResult.ok_result(
        content=message,
        structured_data={"message": message},
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
    preloaded_items = list(context.knowledge_bundle.get("items", []))
    if preloaded_items:
        expand = bool(_payload.get("expand"))
        for item in preloaded_items:
            record = dict(item)
            if expand:
                record = expand_excerpt_content(record)
            records.append(record)
        handoff_message_id = _payload.get("handoff_message_id")
        if handoff_message_id:
            HandoffRunStore().mark_knowledge_consumed(
                str(handoff_message_id),
                consumer=context.agent_id,
                failure_reason=None,
            )
        return ToolResult.ok_result(
            content=f"knowledge:{len(records)}",
            structured_data={"items": records},
            artifacts=[item["path"] for item in records],
        )
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


def query_knowledge_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    root = repository_root() / ".hermes" / "team" / "knowledge"
    result = query_knowledge_records(
        root=root,
        query_text=payload.get("search"),
        filters={
            "agent": payload.get("agent"),
            "role": payload.get("role"),
            "task_type": payload.get("task_type"),
            "risk_tag": payload.get("risk_tag"),
            "review_status": payload.get("review_status"),
            "workflow_id": payload.get("workflow_id"),
        },
    )
    return ToolResult.ok_result(
        content=f"knowledge-query:{len(result['records'])}",
        structured_data=result,
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


def _kanban_db_path(payload: Dict[str, object]) -> str:
    if payload.get("db_path"):
        return str(payload["db_path"])
    config = load_control_plane_config()
    return str(Path(config.directories["state_dir"]) / "kanban.db")


def code_review_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    reviewer = CodeReviewer()
    source = str(payload.get("source") or payload.get("task") or "")
    result = reviewer.review(source)
    return ToolResult.ok_result(
        content=f"score:{result.score}",
        structured_data={
            "score": result.score,
            "issues": result.issues,
            "security_concerns": result.security_concerns,
            "suggestions": result.suggestions,
        },
    )


def code_diagnostics_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    file_path = str(payload.get("file_path") or payload.get("path") or "")
    language = str(payload.get("language") or detect_language(file_path) or "python")
    diagnostics = []
    if file_path:
        hub = get_code_hub()
        client = hub.get_lsp(language, str(repository_root()))
        diagnostics = client.get_diagnostics(file_path) if client else []
    return ToolResult.ok_result(
        content=f"diagnostics:{len(diagnostics)}",
        structured_data={"diagnostics": diagnostics, "language": language, "file_path": file_path},
    )


def kanban_summary_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    board = KanbanBoard(_kanban_db_path(payload))
    summary = board.get_board_summary()
    return ToolResult.ok_result(content=json.dumps(summary, ensure_ascii=False), structured_data=summary)


def kanban_create_task_handler(_context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    board = KanbanBoard(_kanban_db_path(payload))
    task = board.create_task(
        title=str(payload.get("title") or payload.get("task") or "Untitled Task"),
        description=str(payload.get("description") or ""),
        assignee=str(payload.get("assignee") or ""),
        priority=KanbanTaskPriority(int(payload.get("priority", 2))),
        tags=list(payload.get("tags") or []),
    )
    return ToolResult.ok_result(
        content=f"kanban:{task.id}",
        structured_data={"id": task.id, "title": task.title, "status": task.status.value},
    )


def list_oauth_services_handler(_context: ToolExecutionContext, _payload: Dict[str, object]) -> ToolResult:
    manager = OAuthManager()
    return ToolResult.ok_result(
        content="oauth-services",
        structured_data={"services": manager.list_services(), "exchange_mode": manager.exchange_mode},
    )


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolSpec(
                name="echo",
                description="echo the provided task text",
                input_schema={"task": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=echo_handler,
                action="tool.read.generic",
            ),
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
            ToolSpec(
                name="query_knowledge",
                description="query governed knowledge records",
                input_schema={},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=query_knowledge_handler,
                action="tool.read.knowledge",
            ),
            ToolSpec(
                name="write_file",
                description="write or update a file within the repository",
                input_schema={"path": "str", "content": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=write_file_handler,
                action="tool.write.file",
            ),
            ToolSpec(
                name="search_code",
                description="search code in the repository",
                input_schema={"pattern": "str", "glob": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=search_code_handler,
                action="tool.read.search",
            ),
            ToolSpec(
                name="run_command",
                description="run a whitelisted shell command",
                input_schema={"command": "str", "timeout": "int"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=run_command_handler,
                action="tool.execute.command",
            ),
            ToolSpec(
                name="generate_code",
                description="generate code from a template",
                input_schema={"template": "str", "variables": "dict"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_code_handler,
                action="tool.generate.code",
            ),
            ToolSpec(
                name="generate_controller",
                description="generate Spring Boot Controller code",
                input_schema={"class_name": "str", "package": "str", "endpoint": "str", "entity_name": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_controller_handler,
                action="tool.generate.controller",
            ),
            ToolSpec(
                name="generate_service",
                description="generate Spring Boot Service code",
                input_schema={"class_name": "str", "package": "str", "entity_name": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_service_handler,
                action="tool.generate.service",
            ),
            ToolSpec(
                name="generate_mapper",
                description="generate MyBatis Mapper code",
                input_schema={"class_name": "str", "package": "str", "entity_name": "str", "table_name": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_mapper_handler,
                action="tool.generate.mapper",
            ),
            ToolSpec(
                name="run_unit_tests",
                description="run JUnit tests via Maven",
                input_schema={"test_path": "str", "timeout": "int"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=run_unit_tests_handler,
                action="tool.execute.tests",
            ),
            ToolSpec(
                name="generate_vue_component",
                description="generate Vue3 component code",
                input_schema={"component_name": "str", "props": "list", "emits": "list"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_vue_component_handler,
                action="tool.generate.vue",
            ),
            ToolSpec(
                name="generate_api_client",
                description="generate frontend API client code",
                input_schema={"api_name": "str", "endpoint": "str", "methods": "list"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_api_client_handler,
                action="tool.generate.apiclient",
            ),
            ToolSpec(
                name="run_linter",
                description="run ESLint on frontend code",
                input_schema={"file_path": "str", "timeout": "int"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=run_linter_handler,
                action="tool.execute.linter",
            ),
            ToolSpec(
                name="generate_architecture_doc",
                description="generate architecture design document",
                input_schema={"system_name": "str", "requirements": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_architecture_doc_handler,
                action="tool.generate.archdoc",
            ),
            ToolSpec(
                name="review_api_design",
                description="review API design and provide feedback",
                input_schema={"api_spec": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=review_api_design_handler,
                action="tool.review.api",
            ),
            ToolSpec(
                name="generate_ddl",
                description="generate MySQL DDL statement",
                input_schema={"table_name": "str", "columns": "list", "table_comment": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_ddl_handler,
                action="tool.generate.ddl",
            ),
            ToolSpec(
                name="analyze_slow_query",
                description="analyze slow SQL query",
                input_schema={"sql": "str", "explain": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=analyze_slow_query_handler,
                action="tool.analyze.sql",
            ),
            ToolSpec(
                name="generate_test_cases",
                description="generate test case document",
                input_schema={"requirement": "str", "feature": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_test_cases_handler,
                action="tool.generate.testcases",
            ),
            ToolSpec(
                name="run_api_tests",
                description="run API tests via Newman",
                input_schema={"collection": "str", "timeout": "int"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=run_api_tests_handler,
                action="tool.execute.apitests",
            ),
            ToolSpec(
                name="generate_dockerfile",
                description="generate Dockerfile for application",
                input_schema={"app_type": "str", "app_name": "str", "port": "int"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_dockerfile_handler,
                action="tool.generate.dockerfile",
            ),
            ToolSpec(
                name="generate_k8s_manifests",
                description="generate Kubernetes manifests",
                input_schema={"service_name": "str", "image": "str", "port": "int", "replicas": "int"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_k8s_manifests_handler,
                action="tool.generate.k8s",
            ),
            ToolSpec(
                name="generate_design_spec",
                description="generate UI/UX design specification",
                input_schema={"feature": "str", "platform": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_design_spec_handler,
                action="tool.generate.designspec",
            ),
            ToolSpec(
                name="generate_prd",
                description="generate Product Requirements Document",
                input_schema={"feature": "str", "background": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=generate_prd_handler,
                action="tool.generate.prd",
            ),
            ToolSpec(
                name="code_review",
                description="review code and report security/style/performance findings",
                input_schema={"source": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=code_review_handler,
                action="tool.read.code_review",
            ),
            ToolSpec(
                name="code_diagnostics",
                description="inspect diagnostics for a source file using optional LSP support",
                input_schema={"file_path": "str", "language": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=code_diagnostics_handler,
                action="tool.read.code_diagnostics",
            ),
            ToolSpec(
                name="kanban_summary",
                description="read collaboration board summary",
                input_schema={"db_path": "str"},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=kanban_summary_handler,
                action="tool.read.kanban",
            ),
            ToolSpec(
                name="kanban_create_task",
                description="create a task in the collaboration board",
                input_schema={"title": "str", "description": "str", "assignee": "str"},
                is_read_only=False,
                is_concurrency_safe=False,
                handler=kanban_create_task_handler,
                action="tool.write.kanban",
            ),
            ToolSpec(
                name="list_oauth_services",
                description="list OAuth services reserved for future integration",
                input_schema={},
                is_read_only=True,
                is_concurrency_safe=True,
                handler=list_oauth_services_handler,
                action="tool.read.oauth",
            ),
        ]
    )
