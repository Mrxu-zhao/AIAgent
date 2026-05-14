from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TaskPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class TaskStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    TASK_REGISTERED = "task_registered"
    TASK_READY = "task_ready"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_BLOCKED = "task_blocked"
    TASK_CONFLICT_DETECTED = "task_conflict_detected"
    TASK_RETRYING = "task_retrying"
    TASK_FAILED = "task_failed"
    TASK_ROLLED_BACK = "task_rolled_back"
    TASK_COMPLETED = "task_completed"
    ARTIFACT_PUBLISHED = "artifact_published"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"


@dataclass
class LockScope:
    files: List[str]
    modules: List[str]
    contracts: List[str]


@dataclass
class RetryPolicy:
    max_attempts: int
    backoff_seconds: List[int]


@dataclass
class RollbackPolicy:
    mode: str


@dataclass
class TaskCard:
    task_id: str
    title: str
    goal: str
    scope: List[str]
    lock_scope: LockScope
    inputs: List[str]
    outputs: List[str]
    dependencies: List[str]
    owner_agent: str
    review_agent: str
    priority: TaskPriority
    timeout_seconds: int
    retry_policy: RetryPolicy
    rollback_policy: RollbackPolicy
    acceptance_criteria: List[str]
    executor_backend: Optional[str] = None
    knowledge_recommendation: Optional[Dict[str, object]] = None
    knowledge_bundle: Optional[Dict[str, object]] = None
    knowledge_summary: Optional[str] = None
    status: TaskStatus = TaskStatus.PLANNED
    evidence: List[str] = field(default_factory=list)


@dataclass
class TaskEvent:
    event_id: str
    task_id: str
    event_type: EventType
    agent_id: str
    timestamp: float
    attempt: int
    status_before: TaskStatus
    status_after: TaskStatus
    summary: str
    artifact_refs: List[str]
    lock_scope: Dict[str, List[str]]
    depends_on: List[str]
    metrics_delta: Dict[str, float]
    error_code: Optional[str]
