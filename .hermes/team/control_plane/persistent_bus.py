from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from config import load_control_plane_config
from file_lock import FileLock, atomic_write_text


@dataclass
class PersistentMessage:
    id: str
    type: str
    from_agent: str
    to_agent: Optional[str]
    content: Dict[str, Any]
    priority: int
    timestamp: float
    reply_to: Optional[str] = None

    @classmethod
    def from_message(cls, message):
        if hasattr(message, "to_dict"):
            payload = message.to_dict()
            return cls(
                id=payload["id"],
                type=payload["type"],
                from_agent=payload["from"],
                to_agent=payload["to"],
                content=payload["content"],
                priority=payload["priority"],
                timestamp=payload["timestamp"],
                reply_to=payload.get("reply_to"),
            )
        if "from" in message or "to" in message:
            return cls(
                id=message["id"],
                type=message["type"],
                from_agent=message["from"],
                to_agent=message.get("to"),
                content=message["content"],
                priority=message["priority"],
                timestamp=message["timestamp"],
                reply_to=message.get("reply_to"),
            )
        return cls(**message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "from": self.from_agent,
            "to": self.to_agent,
            "content": self.content,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
        }


class PersistentMessageBus:
    def __init__(self, base_dir: Optional[Path] = None):
        config = load_control_plane_config()
        self.base_dir = Path(base_dir or config.directories["message_bus_dir"])
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._messages_path = self.base_dir / "messages.jsonl"
        self._state_path = self.base_dir / "state.json"
        self._file_lock_path = self.base_dir / ".bus.lock"
        self._lock = RLock()
        self._groups = config.groups
        self._registered_agents = set()
        self._history: List[PersistentMessage] = []
        self._pending: Dict[str, List[PersistentMessage]] = {}
        self._unacked: Dict[str, Dict[str, PersistentMessage]] = {}
        self.load_from_disk()

    def register_agent(self, agent_id: str):
        def mutate():
            self._registered_agents.add(agent_id)
            self._pending.setdefault(agent_id, [])
            self._unacked.setdefault(agent_id, {})

        self._mutate_shared_state(mutate)

    def unregister_agent(self, agent_id: str):
        def mutate():
            self._registered_agents.discard(agent_id)
            self._pending.pop(agent_id, None)
            self._unacked.pop(agent_id, None)

        self._mutate_shared_state(mutate)

    def send(self, message) -> bool:
        persistent = PersistentMessage.from_message(message)
        
        def mutate():
            self._history.append(persistent)
            for agent_id in self._resolve_targets(persistent):
                self._pending.setdefault(agent_id, []).append(persistent)
                self._registered_agents.add(agent_id)
            with self._messages_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(persistent.to_dict(), ensure_ascii=False) + "\n")

        self._mutate_shared_state(mutate)
        try:
            from observability.metrics import get_metrics_registry

            registry = get_metrics_registry()
            registry.inc_counter("improvement_cross_process_trace_ratio", 1)
        except Exception:
            pass
        return True

    def receive(self, agent_id: str) -> Optional[PersistentMessage]:
        result = {"message": None}

        def mutate():
            queue = self._pending.setdefault(agent_id, [])
            if not queue:
                return
            message = queue.pop(0)
            self._unacked.setdefault(agent_id, {})[message.id] = message
            result["message"] = message

        self._mutate_shared_state(mutate)
        return result["message"]

    def ack(self, agent_id: str, message_id: str) -> bool:
        result = {"ok": False}

        def mutate():
            unacked = self._unacked.setdefault(agent_id, {})
            if message_id not in unacked:
                return
            del unacked[message_id]
            result["ok"] = True

        self._mutate_shared_state(mutate)
        return result["ok"]

    def nack(self, agent_id: str, message_id: str) -> bool:
        return self.requeue(agent_id, message_id)

    def requeue(self, agent_id: str, message_id: str) -> bool:
        result = {"ok": False}

        def mutate():
            unacked = self._unacked.setdefault(agent_id, {})
            if message_id not in unacked:
                return
            message = unacked.pop(message_id)
            self._pending.setdefault(agent_id, []).insert(0, message)
            result["ok"] = True

        self._mutate_shared_state(mutate)
        return result["ok"]

    def list_unacked(self, agent_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [message.to_dict() for message in self._unacked.setdefault(agent_id, {}).values()]

    def get_pending_count(self, agent_id: str) -> int:
        with self._lock:
            return len(self._pending.setdefault(agent_id, []))

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [message.to_dict() for message in self._history[-limit:]]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "registered_agents": len(self._registered_agents),
                "history_size": len(self._history),
                "pending_counts": {agent_id: len(queue) for agent_id, queue in self._pending.items()},
                "unacked_counts": {agent_id: len(messages) for agent_id, messages in self._unacked.items()},
                "groups": {group_id: list(agent_ids) for group_id, agent_ids in self._groups.items()},
            }

    def load_from_disk(self):
        if self._messages_path.exists():
            self._history = [
                PersistentMessage.from_message(json.loads(line))
                for line in self._messages_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        if self._state_path.exists():
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            self._registered_agents = set(payload.get("registered_agents", []))
            self._pending = {
                agent_id: [PersistentMessage.from_message(item) for item in items]
                for agent_id, items in payload.get("pending", {}).items()
            }
            self._unacked = {
                agent_id: {
                    msg["id"]: PersistentMessage.from_message(msg)
                    for msg in items
                }
                for agent_id, items in payload.get("unacked", {}).items()
            }

    def _mutate_shared_state(self, mutator):
        with self._lock:
            with FileLock(self._file_lock_path):
                self.load_from_disk()
                mutator()
                self._persist_state()

    def _persist_state(self):
        payload = {
            "registered_agents": sorted(self._registered_agents),
            "pending": {
                agent_id: [message.to_dict() for message in messages]
                for agent_id, messages in self._pending.items()
            },
            "unacked": {
                agent_id: [message.to_dict() for message in messages.values()]
                for agent_id, messages in self._unacked.items()
            },
        }
        atomic_write_text(self._state_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _resolve_targets(self, message: PersistentMessage) -> List[str]:
        if message.to_agent is None:
            return sorted(agent_id for agent_id in self._registered_agents if agent_id != message.from_agent)
        if message.to_agent in self._groups:
            return [agent_id for agent_id in self._groups[message.to_agent] if agent_id != message.from_agent]
        return [message.to_agent]
