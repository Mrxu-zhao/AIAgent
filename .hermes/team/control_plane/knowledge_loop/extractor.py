"""Extract experience patterns from delivery artifacts and quality reports."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ExperienceRecord:
    record_id: str
    role: str
    category: str  # pattern | pitfall | optimization | decision
    title: str
    description: str
    source_workflow: str
    source_step: str = ""
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.record_id:
            content = f"{self.role}:{self.category}:{self.title}:{self.source_workflow}"
            self.record_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperienceRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ExperienceExtractor:
    """Extract reusable experience from delivery outputs and quality feedback."""

    def __init__(self):
        self._pattern_keywords = {
            "pattern": ["pattern", "最佳实践", "推荐", "should", "preferred", "best practice"],
            "pitfall": ["pitfall", "陷阱", "避免", "注意", "avoid", "do not", "禁止"],
            "optimization": ["optimization", "优化", "性能", "提速", "improve", "faster"],
            "decision": ["decision", "决策", "选择", "trade-off", "权衡", "decided"],
        }

    def extract_from_quality_report(
        self,
        role: str,
        workflow_id: str,
        quality_report: Dict[str, Any],
    ) -> List[ExperienceRecord]:
        """Extract patterns from quality gate results."""
        records: List[ExperienceRecord] = []
        results = quality_report.get("results", [])
        for result in results:
            status = result.get("status", "")
            gate_name = result.get("gate_name", "")
            message = result.get("message", "")
            if status in ("fail", "warn"):
                records.append(
                    ExperienceRecord(
                        record_id="",
                        role=role,
                        category="pitfall",
                        title=f"Quality gate failure: {gate_name}",
                        description=message,
                        source_workflow=workflow_id,
                        tags=["quality-gate", gate_name, status],
                        context={"gate_result": result},
                    )
                )
            elif status == "pass" and gate_name in ("代码评审", "设计评审", "数据库评审"):
                records.append(
                    ExperienceRecord(
                        record_id="",
                        role=role,
                        category="pattern",
                        title=f"Quality gate success: {gate_name}",
                        description=f"Passed {gate_name} successfully",
                        source_workflow=workflow_id,
                        tags=["quality-gate", gate_name, "success"],
                        context={"gate_result": result},
                    )
                )
        return records

    def extract_from_code(
        self,
        role: str,
        workflow_id: str,
        code: str,
        file_path: str = "",
    ) -> List[ExperienceRecord]:
        """Extract patterns from code comments and structure."""
        records: List[ExperienceRecord] = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped.startswith("#") and not stripped.startswith("//") and not stripped.startswith("*"):
                continue
            category = self._classify_comment(stripped)
            if category:
                records.append(
                    ExperienceRecord(
                        record_id="",
                        role=role,
                        category=category,
                        title=f"Code insight at line {i}",
                        description=stripped.lstrip("#*/ ").strip(),
                        source_workflow=workflow_id,
                        source_step=file_path,
                        tags=["code-comment", category],
                        context={"line": i, "file": file_path},
                    )
                )
        return records

    def extract_from_review(
        self,
        role: str,
        workflow_id: str,
        review_comments: List[Dict[str, Any]],
    ) -> List[ExperienceRecord]:
        """Extract patterns from code review comments."""
        records: List[ExperienceRecord] = []
        for comment in review_comments:
            body = comment.get("body", "")
            category = self._classify_comment(body)
            if not category:
                category = "pitfall" if comment.get("severity") in ("error", "critical") else "pattern"
            records.append(
                ExperienceRecord(
                    record_id="",
                    role=role,
                    category=category,
                    title=comment.get("title", "Review comment"),
                    description=body,
                    source_workflow=workflow_id,
                    tags=["review", comment.get("severity", "info"), category],
                    context={"reviewer": comment.get("reviewer", "")},
                )
            )
        return records

    def extract_from_decisions(
        self,
        role: str,
        workflow_id: str,
        decisions: List[Dict[str, Any]],
    ) -> List[ExperienceRecord]:
        """Extract decision records."""
        records: List[ExperienceRecord] = []
        for decision in decisions:
            records.append(
                ExperienceRecord(
                    record_id="",
                    role=role,
                    category="decision",
                    title=decision.get("summary", "Decision"),
                    description=decision.get("rationale", ""),
                    source_workflow=workflow_id,
                    tags=["decision", decision.get("scope", "general")],
                    context={
                        "alternatives": decision.get("alternatives", []),
                        "impact": decision.get("impact", ""),
                    },
                )
            )
        return records

    def _classify_comment(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for category, keywords in self._pattern_keywords.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    return category
        return None

    def deduplicate(self, records: List[ExperienceRecord]) -> List[ExperienceRecord]:
        """Remove duplicate records by content hash."""
        seen: set = set()
        unique: List[ExperienceRecord] = []
        for r in records:
            key = hashlib.sha256(f"{r.role}:{r.category}:{r.title}:{r.description}".encode()).hexdigest()[:16]
            if key not in seen:
                seen.add(key)
                r.record_id = key
                unique.append(r)
        return unique
