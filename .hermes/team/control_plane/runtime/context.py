from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

FRAMEWORK_CORE_DIR = Path(__file__).resolve().parents[2] / "调度框架" / "core"
if str(FRAMEWORK_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_CORE_DIR))

from task_router import TaskPriority, TaskRouter  # noqa: E402

from runtime.rules import build_knowledge_bundle
from tools.spec import ToolExecutionContext


def build_tool_execution_context(
    task: str,
    router: Optional[TaskRouter] = None,
    requested_agent: Optional[str] = None,
    backend_override: Optional[str] = None,
) -> ToolExecutionContext:
    runtime_router = router or TaskRouter()
    intent = runtime_router.analyze_task_intent(task)
    selected_agent, routing_reason = runtime_router.select_best_agent(intent, TaskPriority.NORMAL)
    agent_id = requested_agent or selected_agent
    knowledge_recommendation = runtime_router._build_knowledge_recommendation(intent, agent_id)
    backend_recommendation = runtime_router._build_backend_recommendation(intent)
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
        knowledge_bundle=build_knowledge_bundle(knowledge_recommendation),
    )
