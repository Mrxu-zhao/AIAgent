from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from governance.approval import ApprovalGate
from governance.rbac import RBACPolicy

if TYPE_CHECKING:
    from tools.spec import ToolExecutionContext, ToolSpec
else:
    ToolExecutionContext = Any
    ToolSpec = Any

ROLE_TOOL_PERMISSIONS = {
    "architect": {
        "read_knowledge",
        "search_code",
        "write_file",
        "dispatch_task",
        "generate_architecture_doc",
        "review_api_design",
        "code_review",
        "code_diagnostics",
        "kanban_summary",
        "kanban_create_task",
        "list_oauth_services",
    },
    "backend-dev": {
        "read_knowledge",
        "search_code",
        "write_file",
        "dispatch_task",
        "generate_controller",
        "generate_service",
        "generate_mapper",
        "run_unit_tests",
        "generate_code",
        "code_review",
        "code_diagnostics",
        "kanban_summary",
    },
    "dba": {
        "read_knowledge",
        "search_code",
        "write_file",
        "dispatch_task",
        "generate_ddl",
        "analyze_slow_query",
    },
    "devops": {
        "read_knowledge",
        "write_file",
        "dispatch_task",
        "generate_dockerfile",
        "generate_k8s_manifests",
    },
    "frontend-dev": {
        "read_knowledge",
        "search_code",
        "write_file",
        "dispatch_task",
        "generate_vue_component",
        "generate_api_client",
        "run_linter",
        "generate_code",
        "run_command",
    },
    "qa-functional": {
        "read_knowledge",
        "write_file",
        "dispatch_task",
        "generate_test_cases",
        "run_api_tests",
        "code_review",
        "kanban_summary",
    },
    "qa-performance": {
        "read_knowledge",
        "write_file",
        "dispatch_task",
        "run_api_tests",
    },
    "requirements-analyst": {
        "read_knowledge",
        "search_code",
        "write_file",
        "dispatch_task",
        "generate_prd",
        "kanban_summary",
    },
    "analyst": {
        "read_knowledge",
        "search_code",
        "write_file",
        "dispatch_task",
        "generate_prd",
    },
    "ucd": {
        "read_knowledge",
        "write_file",
        "dispatch_task",
        "generate_design_spec",
    },
}


def resolve_tool_action(tool: ToolSpec, _payload: Dict[str, object], _context: ToolExecutionContext) -> str:
    if tool.action:
        return tool.action
    if tool.is_read_only:
        return "tool.read.generic"
    return "tool.write.generic"


def check_tool_permission(
    policy: RBACPolicy,
    actor: str,
    tool: ToolSpec,
    payload: Dict[str, object],
    context: ToolExecutionContext,
) -> tuple[bool, str]:
    action = resolve_tool_action(tool, payload, context)
    return policy.is_allowed(actor, action), action


def check_tool_approval(
    approval_gate: ApprovalGate,
    tool: ToolSpec,
    action: str,
) -> bool:
    if not tool.requires_approval:
        return False
    return approval_gate.requires_approval(action)


def is_role_tool_allowed(role: str, tool_name: str) -> bool:
    allowed = ROLE_TOOL_PERMISSIONS.get(role)
    if allowed is None:
        return False
    return tool_name in allowed
