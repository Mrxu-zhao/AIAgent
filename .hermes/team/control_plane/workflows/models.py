from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RoleWorkflowStep:
    step_id: str
    name: str
    tool: str
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoleWorkflowStep":
        return cls(
            step_id=str(data.get("step_id", "")),
            name=str(data.get("name", data.get("step_id", ""))),
            tool=str(data.get("tool", "")),
            input=dict(data.get("input") or {}),
            output=dict(data.get("output") or {}),
        )


@dataclass
class RoleWorkflow:
    workflow_id: str
    name: str
    role: str
    description: str = ""
    scene: Optional[str] = None
    stack_selection: Dict[str, Any] = field(default_factory=dict)
    steps: List[RoleWorkflowStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoleWorkflow":
        return cls(
            workflow_id=str(data.get("workflow_id", "")),
            name=str(data.get("name", data.get("workflow_id", ""))),
            role=str(data.get("role", "")),
            description=str(data.get("description", "")),
            scene=data.get("scene"),
            stack_selection=dict(data.get("stack_selection") or {}),
            steps=[RoleWorkflowStep.from_dict(item) for item in list(data.get("steps") or [])],
        )
