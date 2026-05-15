"""Update team knowledge base with extracted experience records."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .extractor import ExperienceRecord
except ImportError:
    from extractor import ExperienceRecord


class KnowledgeUpdater:
    """Update agent knowledge bases with closed-loop experience."""

    def __init__(self, knowledge_root: Optional[str] = None):
        base = Path(__file__).resolve().parent.parent.parent.parent
        self.knowledge_root = Path(knowledge_root) if knowledge_root else base / "agents"
        self.team_knowledge = base / "team" / "control_plane" / "knowledge"

    def update_role_knowledge(
        self,
        role: str,
        records: List[ExperienceRecord],
    ) -> Dict[str, Any]:
        """Append experience records to role's knowledge base."""
        updated: List[str] = []
        for record in records:
            paths = self._target_paths(role, record)
            for path in paths:
                self._append_to_file(path, record)
                updated.append(str(path))
        return {"role": role, "updated_files": list(set(updated)), "record_count": len(records)}

    def update_team_knowledge(
        self,
        records: List[ExperienceRecord],
    ) -> Dict[str, Any]:
        """Append cross-role records to team shared knowledge."""
        team_patterns = self.team_knowledge / "shared_patterns.md"
        team_pitfalls = self.team_knowledge / "shared_pitfalls.md"
        updated: List[str] = []
        for record in records:
            if record.category == "pattern":
                self._append_to_file(team_patterns, record, heading="## Shared Patterns\n\n")
                updated.append(str(team_patterns))
            elif record.category == "pitfall":
                self._append_to_file(team_pitfalls, record, heading="## Shared Pitfalls\n\n")
                updated.append(str(team_pitfalls))
        return {"updated_files": list(set(updated)), "record_count": len(records)}

    def update_templates(
        self,
        role: str,
        records: List[ExperienceRecord],
    ) -> Dict[str, Any]:
        """Update role templates based on patterns."""
        template_dir = self.knowledge_root / role / "templates"
        updated: List[str] = []
        for record in records:
            if record.category != "pattern":
                continue
            template_file = template_dir / "lessons-learned.md"
            self._append_to_file(template_file, record, heading="# Lessons Learned\n\n")
            updated.append(str(template_file))
        return {"role": role, "updated_files": list(set(updated)), "record_count": len(records)}

    def append_lessons(self, role: str, lessons: List[str]) -> Dict[str, Any]:
        lesson_items = [lesson.strip() for lesson in lessons if lesson and lesson.strip()]
        if not lesson_items:
            return {"role": role, "path": None, "lesson_count": 0}
        path = self._role_knowledge_dir(role) / "recent-lessons.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            text = "# Recent Lessons\n\n"
        existing_lines = {line.strip() for line in text.splitlines() if line.strip()}
        additions = [f"- {lesson}" for lesson in lesson_items if f"- {lesson}" not in existing_lines]
        if additions:
            path.write_text(text.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")
        return {"role": role, "path": str(path), "lesson_count": len(lesson_items)}

    def _target_paths(self, role: str, record: ExperienceRecord) -> List[Path]:
        role_dir = self._role_knowledge_dir(role)
        paths: List[Path] = []
        if record.category == "pattern":
            paths.append(role_dir / "patterns" / "preferred-patterns.md")
        elif record.category == "pitfall":
            paths.append(role_dir / "pitfalls" / "common-mistakes.md")
        elif record.category == "optimization":
            paths.append(role_dir / "patterns" / "preferred-patterns.md")
        elif record.category == "decision":
            paths.append(role_dir / "decisions.md")
        return [p for p in paths if p.parent.exists()]

    def _role_knowledge_dir(self, role: str) -> Path:
        role_dir = self.knowledge_root / role
        nested = role_dir / "knowledge"
        if nested.exists():
            return nested
        return role_dir

    def _append_to_file(
        self,
        path: Path,
        record: ExperienceRecord,
        heading: str = "",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = self._format_entry(record)
        if not path.exists():
            path.write_text(heading + entry + "\n", encoding="utf-8")
            return
        text = path.read_text(encoding="utf-8")
        if record.record_id and record.record_id in text:
            return
        path.write_text(text.rstrip() + "\n\n" + entry + "\n", encoding="utf-8")

    def _format_entry(self, record: ExperienceRecord) -> str:
        lines = [
            f"<!-- record_id: {record.record_id} -->",
            f"**[{record.category.upper()}]** {record.title}",
            "",
            f"> {record.description}",
            "",
            f"- Role: {record.role}",
            f"- Source: {record.source_workflow}",
        ]
        if record.tags:
            lines.append(f"- Tags: {', '.join(record.tags)}")
        lines.append(f"- Date: {record.created_at}")
        return "\n".join(lines)

    def build_knowledge_index(self) -> Dict[str, Any]:
        """Build searchable index of all knowledge entries."""
        index: Dict[str, List[Dict[str, Any]]] = {}
        for role_dir in self.knowledge_root.iterdir():
            if not role_dir.is_dir():
                continue
            role = role_dir.name
            index[role] = []
            for md_file in role_dir.rglob("*.md"):
                records = self._parse_records(md_file.read_text(encoding="utf-8"))
                for r in records:
                    index[role].append({
                        "record_id": r.record_id,
                        "category": r.category,
                        "title": r.title,
                        "file": str(md_file.relative_to(self.knowledge_root)),
                    })
        return index

    def _parse_records(self, text: str) -> List[ExperienceRecord]:
        records: List[ExperienceRecord] = []
        for block in text.split("<!-- record_id: ")[1:]:
            parts = block.split("-->", 1)
            if len(parts) < 2:
                continue
            record_id = parts[0].strip()
            body = parts[1].strip()
            title_match = body.split("\n")[0] if body else ""
            records.append(
                ExperienceRecord(
                    record_id=record_id,
                    role="unknown",
                    category="unknown",
                    title=title_match,
                    description=body,
                    source_workflow="index",
                )
            )
        return records
