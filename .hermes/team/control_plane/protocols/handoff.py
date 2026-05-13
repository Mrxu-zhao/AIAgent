from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

VALID_BACKENDS = {"hermes", "openclaw"}


@dataclass
class HandoffPayload:
    source_backend: str
    target_backend: str
    task_id: str
    summary: str
    context: Dict[str, Any]
    created_at: float

    @classmethod
    def create(cls, source_backend: str, target_backend: str, task_id: str, summary: str, context: Dict[str, Any]):
        return cls(source_backend=source_backend, target_backend=target_backend, task_id=task_id, summary=summary, context=context, created_at=time.time())

    def to_dict(self):
        return {
            "source_backend": self.source_backend,
            "target_backend": self.target_backend,
            "task_id": self.task_id,
            "summary": self.summary,
            "context": self.context,
            "created_at": self.created_at,
        }


def validate_handoff_payload(payload: Dict[str, Any]) -> bool:
    required = {"source_backend", "target_backend", "task_id", "summary", "context", "created_at"}
    if not required.issubset(payload.keys()):
        return False
    if payload["source_backend"] not in VALID_BACKENDS or payload["target_backend"] not in VALID_BACKENDS:
        return False
    return isinstance(payload["context"], dict)
