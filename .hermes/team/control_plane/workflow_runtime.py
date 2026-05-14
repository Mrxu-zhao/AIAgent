from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_control_plane_config


class WorkflowRunStore:
    def __init__(self, base_dir: Optional[Path] = None):
        config = load_control_plane_config()
        root = Path(base_dir) if base_dir is not None else Path(config.directories["workflow_runtime_dir"])
        self.base_dir = root
        self.snapshots_dir = self.base_dir / "snapshots"
        self.events_dir = self.base_dir / "events"
        self.archive_dir = self.base_dir / "archive"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

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
            "event": status,
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

    def get_step_statuses(self, workflow_id: str) -> Dict[str, str]:
        statuses: Dict[str, str] = {}
        for event in self.list_step_events(workflow_id):
            step_id = str(event.get("step_id", "")).strip()
            status = str(event.get("status", "")).strip()
            if not step_id or not status or step_id == "__workflow__":
                continue
            statuses[step_id] = status
        return statuses

    def record_workflow_event(self, workflow_id: str, status: str, payload: Dict[str, Any]):
        event = {
            "workflow_id": workflow_id,
            "step_id": "__workflow__",
            "event": status,
            "status": status,
            "timestamp": time.time(),
            "payload": payload,
        }
        with self._events_path(workflow_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        targets = self._workflow_paths(workflow_id)
        for path in targets:
            path.unlink(missing_ok=True)
        return {
            "workflow_id": workflow_id,
            "deleted_files": len(targets),
        }

    def prune_workflows(self, status: Optional[str] = None) -> Dict[str, Any]:
        deleted_workflows = 0
        deleted_files = 0
        for snapshot_path in sorted(self.snapshots_dir.glob("*.json")):
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if status is not None and snapshot.get("status") != status:
                continue
            result = self.delete_workflow(snapshot["workflow_id"])
            deleted_workflows += 1
            deleted_files += result["deleted_files"]
        return {
            "deleted_workflows": deleted_workflows,
            "deleted_files": deleted_files,
        }

    def archive_workflow(self, workflow_id: str) -> Dict[str, Any]:
        targets = self._workflow_paths(workflow_id)
        archive_path = self.archive_dir / workflow_id
        if archive_path.exists():
            shutil.rmtree(archive_path)
        archive_path.mkdir(parents=True, exist_ok=True)
        for path in targets:
            shutil.move(str(path), str(archive_path / path.name))
        return {
            "workflow_id": workflow_id,
            "archive_path": str(archive_path),
            "archived_files": len(targets),
        }

    def _write_snapshot(self, workflow_id: str, payload: Dict[str, Any]):
        self._snapshot_path(workflow_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _snapshot_path(self, workflow_id: str) -> Path:
        return self.snapshots_dir / f"{workflow_id}.json"

    def _events_path(self, workflow_id: str) -> Path:
        return self.events_dir / f"{workflow_id}.jsonl"

    def _workflow_paths(self, workflow_id: str) -> List[Path]:
        return [path for path in [self._snapshot_path(workflow_id), self._events_path(workflow_id)] if path.exists()]
