from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillCurator:
    def __init__(self, skills_dir: str = ".hermes/skills", storage_backend: str = "file"):
        self.storage_backend = storage_backend
        self.skills_dir = Path(skills_dir)
        if self.storage_backend == "file":
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, Dict[str, Any]] = {}
        if self.storage_backend == "file":
            self._load_skills()

    def _load_skills(self) -> None:
        for file_path in self.skills_dir.glob("*.json"):
            self._skills[file_path.stem] = json.loads(file_path.read_text(encoding="utf-8"))

    def _save_skill(self, name: str) -> None:
        if self.storage_backend != "file":
            return
        file_path = self.skills_dir / f"{name}.json"
        file_path.write_text(json.dumps(self._skills[name], ensure_ascii=False, indent=2), encoding="utf-8")

    def register_skill(
        self,
        name: str,
        description: str,
        handler_code: str,
        usage_count: int = 0,
        archived: bool = False,
    ) -> bool:
        self._skills[name] = {
            "name": name,
            "description": description,
            "handler_code": handler_code,
            "created_at": time.time(),
            "updated_at": time.time(),
            "usage_count": usage_count,
            "archived": archived,
            "version": 1,
        }
        self._save_skill(name)
        return True

    def use_skill(self, name: str) -> Optional[Dict[str, Any]]:
        skill = self._skills.get(name)
        if skill is None or skill.get("archived"):
            return None
        skill["usage_count"] = skill.get("usage_count", 0) + 1
        skill["last_used"] = time.time()
        self._save_skill(name)
        return skill

    def archive_skill(self, name: str) -> bool:
        if name not in self._skills:
            return False
        self._skills[name]["archived"] = True
        self._skills[name]["archived_at"] = time.time()
        self._save_skill(name)
        return True

    def restore_skill(self, name: str) -> bool:
        if name not in self._skills:
            return False
        self._skills[name]["archived"] = False
        self._save_skill(name)
        return True

    def list_skills(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": skill.get("description", ""),
                "usage": skill.get("usage_count", 0),
                "archived": skill.get("archived", False),
            }
            for name, skill in self._skills.items()
            if include_archived or not skill.get("archived")
        ]
