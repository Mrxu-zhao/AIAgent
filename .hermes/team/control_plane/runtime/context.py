from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

FRAMEWORK_CORE_DIR = Path(__file__).resolve().parents[2] / "调度框架" / "core"
if str(FRAMEWORK_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_CORE_DIR))

from governance.session_security import get_session_security_manager
from runtime.rules import build_knowledge_bundle
from runtime.token_compressor import build_context_summary
from task_router import TaskPriority, TaskRouter  # noqa: E402
from tools.spec import ToolExecutionContext


def build_tool_execution_context(
    task: str,
    router: Optional[TaskRouter] = None,
    requested_agent: Optional[str] = None,
    backend_override: Optional[str] = None,
) -> ToolExecutionContext:
    session_security = get_session_security_manager()
    runtime_router = router or TaskRouter()
    intent = runtime_router.analyze_task_intent(task)
    selected_agent, routing_reason = runtime_router.select_best_agent(intent, TaskPriority.NORMAL)
    agent_id = requested_agent or selected_agent
    if requested_agent and isinstance(routing_reason, dict):
        routing_reason = dict(routing_reason)
        routing_reason["requested_agent"] = requested_agent
    knowledge_recommendation = runtime_router._build_knowledge_recommendation(intent, agent_id)
    backend_recommendation = runtime_router._build_backend_recommendation(intent)
    knowledge_bundle = build_knowledge_bundle(knowledge_recommendation)
    session_id = f"tool-session-{int(time.time() * 1000)}"
    session_security.create_policy(session_id, "main")
    return ToolExecutionContext(
        task_id=f"tool-{int(time.time() * 1000)}",
        agent_id=agent_id,
        backend=backend_override or backend_recommendation["selected_backend"],
        intent={
            "task_type": intent.task_type.value,
            "requested_agent": requested_agent,
            "requested_role": intent.requested_role,
            "collaboration_mode": intent.collaboration_mode,
            "routing_reason": routing_reason,
        },
        knowledge_bundle=knowledge_bundle,
        session_id=session_id,
        compression_meta=build_context_summary(knowledge_bundle),
        security_session_type="main",
    )
