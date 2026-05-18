from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class KnowledgeProfile:
    task_type: str
    deliverables: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    search_terms: List[str] = field(default_factory=list)
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    owner_agent: Optional[str] = None
    role_key: Optional[str] = None
    collaboration_mode: str = 'single'
    upstream_agent: Optional[str] = None
    upstream_role: Optional[str] = None
    scope_paths: List[str] = field(default_factory=list)
    module_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeExcerpt:
    path: str
    resolved_path: str
    summary: str
    excerpt: str
    priority: float
    matched_by: List[str] = field(default_factory=list)
    tokens_estimate: int = 0
    expandable: bool = True
    degraded_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeUsage:
    recommended_paths: List[str] = field(default_factory=list)
    consumed_paths: List[str] = field(default_factory=list)
    expanded_paths: List[str] = field(default_factory=list)
    unused_paths: List[str] = field(default_factory=list)
    decision_helpful_count: int = 0
    risk_helpful_count: int = 0
    feedback_score: float = 0.0

    def calculate_feedback_score(self) -> float:
        recommended_total = max(1, len({path for path in self.recommended_paths if path}))
        consumed_ratio = len({path for path in self.consumed_paths if path}) / recommended_total
        expanded_ratio = len({path for path in self.expanded_paths if path}) / recommended_total
        unused_ratio = len({path for path in self.unused_paths if path}) / recommended_total
        helpful_total = self.decision_helpful_count + self.risk_helpful_count
        helpful_ratio = min(helpful_total / 3.0, 1.0)
        score = (0.45 * consumed_ratio) + (0.15 * expanded_ratio) + (0.35 * helpful_ratio) - (0.10 * unused_ratio)
        return round(max(0.0, min(score, 1.0)), 4)

    def finalize_feedback_score(self) -> float:
        self.feedback_score = self.calculate_feedback_score()
        return self.feedback_score

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeBundle:
    profile: KnowledgeProfile
    load_order: List[str] = field(default_factory=list)
    team: List[str] = field(default_factory=list)
    role: List[str] = field(default_factory=list)
    instance: List[str] = field(default_factory=list)
    cross_role: List[str] = field(default_factory=list)
    excerpts: List[KnowledgeExcerpt] = field(default_factory=list)
    raw_paths: List[str] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
    cache_key: Optional[str] = None
    usage: KnowledgeUsage = field(default_factory=KnowledgeUsage)
    recommendation_reason: List[str] = field(default_factory=list)
    degradations: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload['profile'] = self.profile.to_dict()
        payload['usage'] = self.usage.to_dict()
        payload['excerpts'] = [item.to_dict() for item in self.excerpts]
        return payload


@dataclass
class GovernanceEntry:
    entry_id: str
    entry_type: str
    content: str
    owner: str
    review_status: str = 'pending_review'
    accepted: bool = False
    rejected: bool = False
    archived: bool = False
    source_workflow_id: Optional[str] = None
    source_step_id: Optional[str] = None
    source_agent: Optional[str] = None
    created_at: Optional[float] = None
    reviewed_at: Optional[float] = None
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
