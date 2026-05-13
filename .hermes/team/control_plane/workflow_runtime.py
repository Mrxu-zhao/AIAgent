from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_control_plane_config


class WorkflowRunStore:
    def __init__(self, base_dir: Optional[Path] = None):
        config = load_control_plane_config()
        self.base_dir = Path(base_dir or config.directories["workflow_runtime_dir"])
        self.snapshots_dir = self.base_dir / "snapshots"
        self.events_dir = self.base_dir / "events"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def record_workflow_started(self, workflow_id: str, payload: Dict[str, Any]):
        snapshot = {"workflow_id": workflow_id, "status": "running", "started_at": time.time(), **payload}
        self._write_snapshot(workflow_id, snapshot)

    def record_workflow_completed(self, workflow_id: str, payload: Dict[str, Any]):
        snapshot = self.read_snapshot(workflow_id)
        snapshot.update({"status": payload.get("status", "completed"), "completed_at": time.time(), **payload})
        self._write_snapshot(workflow_id, snapshot)

    def record_step_event(self, workflow_id: str, step_id: str, status: str, payload: Dict[str, Any]):
        event = {
            "workflow_id": workflow_id,
            "step_id": step_id,
            "status": status,
            "timestamp": time.time(),
            "payload": payload,
        }
        with self._events_path(workflow_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_snapshot(self, workflow_id: str) -> Dict[str, Any]:
        path = self._snapshot_path(workflow_id)
        if not path.exists():
            return {"workflow_id": workflow_id, "status": "pending"}
        return json.loads(path.read_text(encoding="utf-8"))

    def list_step_events(self, workflow_id: str) -> List[Dict[str, Any]]:
        path = self._events_path(workflow_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_snapshot(self, workflow_id: str, payload: Dict[str, Any]):
        self._snapshot_path(workflow_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _snapshot_path(self, workflow_id: str) -> Path:
        return self.snapshots_dir / f"{workflow_id}.json"

    def _events_path(self, workflow_id: str) -> Path:
        return self.events_dir / f"{workflow_id}.jsonl"
