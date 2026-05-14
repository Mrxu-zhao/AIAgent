from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ToolHandler = Callable[["ToolExecutionContext", Dict[str, Any]], "ToolResult"]


@dataclass
class ToolExecutionContext:
    task_id: str
    agent_id: str
    backend: str
    cwd: Optional[str] = None
    intent: Dict[str, Any] = field(default_factory=dict)
    knowledge_bundle: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    content: str = ""
    structured_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)

    @classmethod
    def ok_result(
        cls,
        content: str = "",
        structured_data: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[str]] = None,
    ) -> "ToolResult":
        return cls(
            ok=True,
            content=content,
            structured_data=structured_data,
            error=None,
            artifacts=list(artifacts or []),
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        content: str = "",
        structured_data: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[str]] = None,
    ) -> "ToolResult":
        return cls(
            ok=False,
            content=content,
            structured_data=structured_data,
            error=error,
            artifacts=list(artifacts or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "content": self.content,
            "structured_data": self.structured_data,
            "error": self.error,
            "artifacts": list(self.artifacts),
        }


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    is_read_only: bool
    is_concurrency_safe: bool
    handler: ToolHandler
