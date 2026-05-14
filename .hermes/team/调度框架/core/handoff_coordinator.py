import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CONTROL_PLANE_DIR = Path(__file__).resolve().parents[2] / "control_plane"
if str(CONTROL_PLANE_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_DIR))

from continuation import resume_workflow
from models import LockScope, RetryPolicy, RollbackPolicy, TaskCard, TaskPriority
from protocols.handoff import validate_handoff_payload


@dataclass
class HandoffRecord:
    message_id: str
    task_id: str
    workflow_id: Optional[str]
    source_agent: Optional[str]
    target_agent: Optional[str]
    source_step: Optional[str]
    target_step: Optional[str]
    status: str
    created_at: float
    source_backend: Optional[str] = None
    target_backend: Optional[str] = None
    selected_backend: Optional[str] = None
    knowledge_recommendation: Optional[Dict[str, Any]] = None
    received_at: Optional[float] = None
    acked_at: Optional[float] = None
    materialized_task_id: Optional[str] = None
    materialized_at: Optional[float] = None
    dispatched_at: Optional[float] = None
    continued_at: Optional[float] = None
    continuation_workflow_id: Optional[str] = None
    continuation_status: Optional[str] = None
    continuation_ready_steps: List[str] = field(default_factory=list)
    continuation_completed_steps: List[str] = field(default_factory=list)
    continuation_failed_steps: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HandoffCoordinator:
    def __init__(
        self,
        bus,
        task_store=None,
        handoff_store=None,
        runtime_store=None,
        dispatcher=None,
        adapter=None,
        command_runner=None,
    ):
        self.bus = bus
        self.task_store = task_store
        self.handoff_store = handoff_store
        self.runtime_store = runtime_store
        self.dispatcher = dispatcher
        self.adapter = adapter
        self.command_runner = command_runner
        self.records: List[HandoffRecord] = []

    def consume_for(self, agent_id: str) -> Optional[Dict[str, Any]]:
        message = self.bus.receive(agent_id)
        if not message:
            return None
        return self.handle_message(agent_id, message)

    def handle_message(self, agent_id: str, message) -> Dict[str, Any]:
        payload = self._extract_payload(message)
        message_id = getattr(message, "id", "")
        task_id = str(payload.get("task_id", ""))
        existing = self.find_record(message_id=message_id, task_id=task_id)
        if existing and existing.materialized_task_id:
            if hasattr(self.bus, "ack"):
                self.bus.ack(agent_id, message_id)
            return existing.to_dict()

        workflow_context = payload.get("context", {})
        workflow_id = workflow_context.get("workflow_id") if isinstance(workflow_context, dict) else None
        record = HandoffRecord(
            message_id=message_id,
            task_id=task_id,
            workflow_id=workflow_id,
            source_agent=payload.get("source_agent"),
            target_agent=payload.get("target_agent"),
            source_step=payload.get("source_step"),
            target_step=payload.get("target_step"),
            source_backend=payload.get("source_backend"),
            target_backend=payload.get("target_backend"),
            selected_backend=payload.get("selected_backend"),
            knowledge_recommendation=payload.get("knowledge_recommendation"),
            status="received",
            created_at=float(payload.get("created_at", time.time())),
            received_at=time.time(),
        )

        if validate_handoff_payload(payload):
            if hasattr(self.bus, "ack"):
                self.bus.ack(agent_id, record.message_id)
            record.status = "acked"
            record.acked_at = time.time()
            if self.task_store is not None:
                self._materialize_task(record, payload)
                self._persist_materialized_record(record)
                self._dispatch_materialized_task(record, payload)
                self._trigger_workflow_continuation(record)
                if self.handoff_store is not None:
                    self.handoff_store.record_handoff(record.to_dict())
        else:
            record.status = "failed"
            record.error = "invalid handoff payload"
            if hasattr(self.bus, "nack"):
                self.bus.nack(agent_id, record.message_id)

        self.records.append(record)
        return record.to_dict()

    def get_records(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if task_id is None:
            return [record.to_dict() for record in self.records]
        return [record.to_dict() for record in self.records if record.task_id == task_id]

    def find_record(
        self,
        message_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Optional[HandoffRecord]:
        for record in self.records:
            if message_id and record.message_id == message_id:
                return record
            if task_id and record.task_id == task_id:
                return record
        return None

    def _extract_payload(self, message) -> Dict[str, Any]:
        content = getattr(message, "content", {})
        if isinstance(content, dict):
            payload = content.get("context", {})
            if isinstance(payload, dict):
                return payload
        return {}

    def _materialize_task(self, record: HandoffRecord, payload: Dict[str, Any]) -> None:
        task_card = self._build_task_card(payload)
        if not self._task_exists(task_card.task_id):
            self.task_store.register_task(task_card)
        record.materialized_task_id = task_card.task_id
        record.materialized_at = time.time()
        record.status = "materialized"

    def _persist_materialized_record(self, record: HandoffRecord) -> None:
        if self.handoff_store is not None:
            self.handoff_store.record_handoff(record.to_dict())
        if self.runtime_store is not None and record.workflow_id:
            self.runtime_store.record_step_event(
                record.workflow_id,
                record.target_step or "handoff",
                "handoff_materialized",
                {
                    "message_id": record.message_id,
                    "materialized_task_id": record.materialized_task_id,
                },
            )

    def _dispatch_materialized_task(self, record: HandoffRecord, payload: Dict[str, Any]) -> None:
        if self.dispatcher is None or not record.materialized_task_id:
            return
        if self._task_already_dispatched(record.materialized_task_id):
            record.status = "dispatched"
            if record.dispatched_at is None:
                record.dispatched_at = time.time()
            return

        task_card = self._build_task_card(payload)
        outcome = self.dispatcher.execute_task(task_card, self.adapter, self.command_runner)
        record.status = "dispatched"
        record.dispatched_at = time.time()
        if isinstance(outcome, dict) and outcome.get("error"):
            record.error = outcome["error"]
        if self.handoff_store is not None:
            self.handoff_store.record_handoff(record.to_dict())
        if self.runtime_store is not None and record.workflow_id:
            self.runtime_store.record_step_event(
                record.workflow_id,
                record.target_step or "handoff",
                "handoff_dispatched",
                {
                    "message_id": record.message_id,
                    "materialized_task_id": record.materialized_task_id,
                },
            )

    def _trigger_workflow_continuation(self, record: HandoffRecord) -> None:
        if self.runtime_store is None or not record.workflow_id:
            return
        record.continuation_workflow_id = record.workflow_id
        fallback_status = record.status
        try:
            continuation = resume_workflow(record.workflow_id, self.runtime_store)
        except Exception as exc:
            record.status = fallback_status
            record.continuation_status = "failed"
            record.continuation_ready_steps = []
            record.continuation_completed_steps = []
            record.continuation_failed_steps = []
            record.error = record.error or str(exc)
            if hasattr(self.runtime_store, "record_workflow_event"):
                self.runtime_store.record_workflow_event(
                    record.workflow_id,
                    "workflow_resume_failed",
                    {
                        "message_id": record.message_id,
                        "target_step": record.target_step,
                        "error": str(exc),
                    },
                )
            return

        record.continuation_ready_steps = list(continuation["ready_steps"])
        record.continuation_completed_steps = list(continuation["completed_steps"])
        record.continuation_failed_steps = list(continuation["failed_steps"])
        record.continued_at = time.time()
        record.continuation_status = "continued" if record.continuation_ready_steps else "noop"
        if hasattr(self.runtime_store, "record_workflow_event"):
            self.runtime_store.record_workflow_event(
                record.workflow_id,
                "workflow_continued" if record.continuation_ready_steps else "workflow_resumed",
                {
                    "message_id": record.message_id,
                    "target_step": record.target_step,
                    "ready_steps": list(record.continuation_ready_steps),
                    "completed_steps": list(record.continuation_completed_steps),
                },
            )

    def _build_task_card(self, payload: Dict[str, Any]) -> TaskCard:
        workflow_context = payload.get("context", {})
        workflow_id = workflow_context.get("workflow_id", "handoff")
        source_step = payload.get("source_step") or "source"
        target_step = payload.get("target_step") or "target"
        target_agent = payload.get("target_agent") or "unknown"
        summary = payload.get("summary") or "consume handoff context"
        target_backend = payload.get("selected_backend") or payload.get("target_backend")
        task_id = f"handoff-{workflow_id}-{source_step}-{target_step}"
        return TaskCard(
            task_id=task_id,
            title=f"Handoff follow-up for {target_step}",
            goal=summary,
            scope=[],
            lock_scope=LockScope(files=[], modules=[], contracts=[]),
            inputs=[],
            outputs=[],
            dependencies=[],
            owner_agent=target_agent,
            review_agent=payload.get("source_agent") or target_agent,
            priority=TaskPriority.P1,
            timeout_seconds=1800,
            retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=[0]),
            rollback_policy=RollbackPolicy(mode="manual"),
            acceptance_criteria=[summary],
            executor_backend=target_backend,
        )

    def _task_exists(self, task_id: str) -> bool:
        try:
            self.task_store.read_snapshot(task_id)
            return True
        except FileNotFoundError:
            return False

    def _task_already_dispatched(self, task_id: str) -> bool:
        if self.task_store is None or not hasattr(self.task_store, "list_events"):
            return False
        return bool(self.task_store.list_events(task_id))
