import json
from dataclasses import asdict
from pathlib import Path


class VersionConflictError(RuntimeError):
    pass


class SnapshotValidationError(RuntimeError):
    pass


class TaskStore:
    def __init__(self, state_dir: Path, events_dir: Path):
        self.state_dir = Path(state_dir)
        self.events_dir = Path(events_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def register_task(self, card):
        snapshot = asdict(card)
        snapshot["priority"] = card.priority.value
        snapshot["status"] = card.status.value
        snapshot["version"] = 1
        snapshot["last_event_id"] = None
        snapshot["updated_at"] = None
        snapshot["updated_by"] = None
        self._write_json(self.state_dir / f"{card.task_id}.json", snapshot)

    def append_event(self, event, expected_version=None):
        snapshot = self.read_snapshot(event.task_id)
        if expected_version is not None and snapshot["version"] != expected_version:
            raise VersionConflictError(
                f"snapshot version mismatch for {event.task_id}: "
                f"expected {expected_version}, got {snapshot['version']}"
            )
        event_path = self.events_dir / f"{event.task_id}.jsonl"
        with event_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n")
        snapshot["status"] = event.status_after.value
        snapshot["version"] += 1
        snapshot["last_event_id"] = event.event_id
        snapshot["updated_at"] = event.timestamp
        snapshot["updated_by"] = event.agent_id
        self._write_json(self.state_dir / f"{event.task_id}.json", snapshot)

    def read_snapshot(self, task_id: str):
        return json.loads((self.state_dir / f"{task_id}.json").read_text(encoding="utf-8"))

    def validate_snapshot(self, task_id: str, expected_version=None, expected_last_event_id=None):
        snapshot = self.read_snapshot(task_id)
        if expected_version is not None and snapshot["version"] != expected_version:
            raise SnapshotValidationError(
                f"snapshot version mismatch for {task_id}: "
                f"expected {expected_version}, got {snapshot['version']}"
            )
        if (
            expected_last_event_id is not None
            and snapshot["last_event_id"] != expected_last_event_id
        ):
            raise SnapshotValidationError(
                f"snapshot last_event_id mismatch for {task_id}: "
                f"expected {expected_last_event_id}, got {snapshot['last_event_id']}"
            )
        return snapshot

    def list_events(self, task_id: str):
        event_path = self.events_dir / f"{task_id}.jsonl"
        if not event_path.exists():
            return []
        return [
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_json(self, path: Path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
