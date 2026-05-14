from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_control_plane_config


class HandoffRunStore:
    def __init__(self, base_dir: Optional[Path] = None):
        config = load_control_plane_config()
        state_dir = Path(config.directories["state_dir"])
        self.base_dir = Path(base_dir or (state_dir / "handoffs"))
        self.records_dir = self.base_dir / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def record_handoff(self, record: Dict[str, Any]) -> Dict[str, Any]:
        message_id = record["message_id"]
        self._record_path(message_id).write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def read_record(self, message_id: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(message_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_records(
        self,
        workflow_id: Optional[str] = None,
        target_agent: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        records = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.records_dir.glob("*.json")
        ]
        if workflow_id is not None:
            records = [record for record in records if record.get("workflow_id") == workflow_id]
        if target_agent is not None:
            records = [record for record in records if record.get("target_agent") == target_agent]
        if status is not None:
            records = [record for record in records if record.get("status") == status]
        return sorted(records, key=lambda item: item["message_id"])

    def _record_path(self, message_id: str) -> Path:
        return self.records_dir / f"{message_id}.json"
