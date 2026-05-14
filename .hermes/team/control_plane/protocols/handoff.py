from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

VALID_BACKENDS = {"hermes", "openclaw"}


@dataclass
class HandoffPayload:
    source_backend: str
    target_backend: str
    task_id: str
    summary: str
    context: Dict[str, Any]
    created_at: float
    source_agent: Optional[str] = None
    target_agent: Optional[str] = None
    source_step: Optional[str] = None
    target_step: Optional[str] = None
    reason: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    selected_backend: Optional[str] = None
    backend_candidates: List[str] = field(default_factory=list)
    backend_reason: Optional[str] = None
    review_policy: Optional[str] = None
    knowledge_recommendation: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        source_backend: str,
        target_backend: str,
        task_id: str,
        summary: str,
        context: Dict[str, Any],
        source_agent: Optional[str] = None,
        target_agent: Optional[str] = None,
        source_step: Optional[str] = None,
        target_step: Optional[str] = None,
        reason: Optional[str] = None,
        artifacts: Optional[List[str]] = None,
        open_questions: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        selected_backend: Optional[str] = None,
        backend_candidates: Optional[List[str]] = None,
        backend_reason: Optional[str] = None,
        review_policy: Optional[str] = None,
        knowledge_recommendation: Optional[Dict[str, Any]] = None,
    ):
        return cls(
            source_backend=source_backend,
            target_backend=target_backend,
            task_id=task_id,
            summary=summary,
            context=context,
            created_at=time.time(),
            source_agent=source_agent,
            target_agent=target_agent,
            source_step=source_step,
            target_step=target_step,
            reason=reason,
            artifacts=list(artifacts or []),
            open_questions=list(open_questions or []),
            risks=list(risks or []),
            selected_backend=selected_backend,
            backend_candidates=list(backend_candidates or []),
            backend_reason=backend_reason,
            review_policy=review_policy,
            knowledge_recommendation=dict(knowledge_recommendation or {}) or None,
        )

    def to_dict(self):
        return {
            "source_backend": self.source_backend,
            "target_backend": self.target_backend,
            "task_id": self.task_id,
            "summary": self.summary,
            "context": self.context,
            "created_at": self.created_at,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "source_step": self.source_step,
            "target_step": self.target_step,
            "reason": self.reason,
            "artifacts": list(self.artifacts),
            "open_questions": list(self.open_questions),
            "risks": list(self.risks),
            "selected_backend": self.selected_backend,
            "backend_candidates": list(self.backend_candidates),
            "backend_reason": self.backend_reason,
            "review_policy": self.review_policy,
            "knowledge_recommendation": dict(self.knowledge_recommendation or {}) or None,
        }


def validate_handoff_payload(payload: Dict[str, Any]) -> bool:
    required = {"source_backend", "target_backend", "task_id", "summary", "context", "created_at"}
    if not required.issubset(payload.keys()):
        return False
    if payload["source_backend"] not in VALID_BACKENDS or payload["target_backend"] not in VALID_BACKENDS:
        return False
    if not isinstance(payload["context"], dict):
        return False
    optional_strings = (
        "source_agent",
        "target_agent",
        "source_step",
        "target_step",
        "reason",
        "selected_backend",
        "backend_reason",
        "review_policy",
    )
    for field_name in optional_strings:
        if field_name in payload and payload[field_name] is not None and not isinstance(payload[field_name], str):
            return False
    for field_name in ("artifacts", "open_questions", "risks", "backend_candidates"):
        if field_name in payload and not isinstance(payload[field_name], list):
            return False
    if (
        "knowledge_recommendation" in payload
        and payload["knowledge_recommendation"] is not None
        and not isinstance(payload["knowledge_recommendation"], dict)
    ):
        return False
    return True
