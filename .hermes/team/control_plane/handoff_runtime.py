from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import load_control_plane_config


class HandoffRunStore:
    def __init__(self, base_dir: Optional[Path] = None):
        config = load_control_plane_config()
        root = Path(base_dir) if base_dir is not None else Path(config.directories["handoff_runtime_dir"])
        self.base_dir = root
        self.records_dir = self.base_dir / "records"
        self.archive_dir = self.base_dir / "archive"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

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
        message_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        records = [
            record
            for _path, record in self._matching_records(
                workflow_id=workflow_id,
                target_agent=target_agent,
                status=status,
                message_id=message_id,
            )
        ]
        return sorted(records, key=lambda item: item["message_id"])

    def delete_records(
        self,
        workflow_id: Optional[str] = None,
        target_agent: Optional[str] = None,
        status: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> int:
        matches = self._matching_records(
            workflow_id=workflow_id,
            target_agent=target_agent,
            status=status,
            message_id=message_id,
        )
        for path, _record in matches:
            path.unlink(missing_ok=True)
        return len(matches)

    def prune_records(
        self,
        workflow_id: Optional[str] = None,
        target_agent: Optional[str] = None,
        status: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> int:
        return self.delete_records(
            workflow_id=workflow_id,
            target_agent=target_agent,
            status=status,
            message_id=message_id,
        )

    def archive_records(
        self,
        workflow_id: Optional[str] = None,
        target_agent: Optional[str] = None,
        status: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        matches = self._matching_records(
            workflow_id=workflow_id,
            target_agent=target_agent,
            status=status,
            message_id=message_id,
        )
        archive_path = self.archive_dir / f"records-{int(time.time() * 1000)}"
        archive_path.mkdir(parents=True, exist_ok=True)
        for path, _record in matches:
            shutil.move(str(path), str(archive_path / path.name))
        return {
            "archive_path": str(archive_path),
            "archived_files": len(matches),
        }

    def _matching_records(
        self,
        workflow_id: Optional[str] = None,
        target_agent: Optional[str] = None,
        status: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> List[Tuple[Path, Dict[str, Any]]]:
        matches = [
            (path, json.loads(path.read_text(encoding="utf-8")))
            for path in self.records_dir.glob("*.json")
        ]
        if workflow_id is not None:
            matches = [item for item in matches if item[1].get("workflow_id") == workflow_id]
        if target_agent is not None:
            matches = [item for item in matches if item[1].get("target_agent") == target_agent]
        if status is not None:
            matches = [item for item in matches if item[1].get("status") == status]
        if message_id is not None:
            matches = [item for item in matches if item[1].get("message_id") == message_id]
        return sorted(matches, key=lambda item: item[1]["message_id"])

    def _record_path(self, message_id: str) -> Path:
        return self.records_dir / f"{message_id}.json"
