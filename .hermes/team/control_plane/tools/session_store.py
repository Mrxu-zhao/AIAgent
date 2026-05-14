from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List


class SessionStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        task: str,
        agent_id: str,
        backend: str,
        knowledge_bundle: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = time.time()
        snapshot = {
            "session_id": session_id,
            "task": task,
            "agent_id": agent_id,
            "backend": backend,
            "status": "ready",
            "created_at": now,
            "updated_at": now,
            "last_tool_name": None,
            "last_tool_result": None,
            "knowledge_bundle": knowledge_bundle,
            "intent": intent,
            "history": [],
        }
        self._write(session_id, snapshot)
        return snapshot

    def read_session(self, session_id: str) -> Dict[str, Any]:
        path = self._path(session_id)
        if not path.exists():
            raise ValueError(f"unknown session: {session_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def update_session(self, session_id: str, **updates: Any) -> Dict[str, Any]:
        snapshot = self.read_session(session_id)
        history_entry = updates.pop("history_entry", None)
        snapshot.update(updates)
        snapshot["updated_at"] = time.time()
        if history_entry is not None:
            snapshot.setdefault("history", []).append(history_entry)
        self._write(session_id, snapshot)
        return snapshot

    def list_sessions(self) -> List[Dict[str, Any]]:
        snapshots = []
        for path in sorted(self.base_dir.glob("*.json")):
            snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        return sorted(snapshots, key=lambda item: item["updated_at"], reverse=True)

    def _path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def _write(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        self._path(session_id).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
