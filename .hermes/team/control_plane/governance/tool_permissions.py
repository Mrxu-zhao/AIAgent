from __future__ import annotations

from typing import Dict

from governance.approval import ApprovalGate
from governance.rbac import RBACPolicy
from tools.spec import ToolExecutionContext, ToolSpec


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
