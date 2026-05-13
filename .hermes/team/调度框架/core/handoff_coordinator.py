import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

CONTROL_PLANE_DIR = Path(__file__).resolve().parents[2] / "control_plane"
if str(CONTROL_PLANE_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_DIR))

from protocols.handoff import validate_handoff_payload


@dataclass
class HandoffRecord:
    message_id: str
    task_id: str
    source_agent: Optional[str]
    target_agent: Optional[str]
    source_step: Optional[str]
    target_step: Optional[str]
    status: str
    created_at: float
    received_at: Optional[float] = None
    acked_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HandoffCoordinator:
    def __init__(self, bus):
        self.bus = bus
        self.records: List[HandoffRecord] = []

    def consume_for(self, agent_id: str) -> Optional[Dict[str, Any]]:
        message = self.bus.receive(agent_id)
        if not message:
            return None
        return self.handle_message(agent_id, message)

    def handle_message(self, agent_id: str, message) -> Dict[str, Any]:
        payload = self._extract_payload(message)
        record = HandoffRecord(
            message_id=getattr(message, "id", ""),
            task_id=str(payload.get("task_id", "")),
            source_agent=payload.get("source_agent"),
            target_agent=payload.get("target_agent"),
            source_step=payload.get("source_step"),
            target_step=payload.get("target_step"),
            status="received",
            created_at=float(payload.get("created_at", time.time())),
            received_at=time.time(),
        )

        if validate_handoff_payload(payload):
            if hasattr(self.bus, "ack"):
                self.bus.ack(agent_id, record.message_id)
            record.status = "acked"
            record.acked_at = time.time()
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

    def _extract_payload(self, message) -> Dict[str, Any]:
        content = getattr(message, "content", {})
        if isinstance(content, dict):
            payload = content.get("context", {})
            if isinstance(payload, dict):
                return payload
        return {}
