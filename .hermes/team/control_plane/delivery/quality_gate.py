"""Quality Gate Checker for delivery contracts."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


def _split_yaml_mapping(text: str) -> Tuple[str, str]:
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _parse_yaml_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_yaml_scalar(part.strip()) for part in inner.split(",")]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _parse_yaml_block(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, content = lines[index]
    if current_indent < indent:
        return {}, index
    if content.startswith("- "):
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_dict(lines, index, indent)


def _parse_yaml_dict(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Dict[str, Any], int]:
    data: Dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent or current_indent != indent or content.startswith("- "):
            break
        key, raw_value = _split_yaml_mapping(content)
        index += 1
        if raw_value:
            data[key] = _parse_yaml_scalar(raw_value)
            continue
        if index < len(lines) and lines[index][0] > current_indent:
            value, index = _parse_yaml_block(lines, index, current_indent + 2)
            data[key] = value
        else:
            data[key] = {}
    return data, index


def _parse_yaml_list(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[List[Any], int]:
    items: List[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent or current_indent != indent or not content.startswith("- "):
            break
        remainder = content[2:].strip()
        index += 1
        if not remainder:
            if index < len(lines) and lines[index][0] > current_indent:
                value, index = _parse_yaml_block(lines, index, current_indent + 2)
            else:
                value = None
            items.append(value)
            continue
        if ":" in remainder:
            key, raw_value = _split_yaml_mapping(remainder)
            item: Dict[str, Any] = {}
            if raw_value:
                item[key] = _parse_yaml_scalar(raw_value)
            elif index < len(lines) and lines[index][0] > current_indent:
                value, index = _parse_yaml_block(lines, index, current_indent + 2)
                item[key] = value
            else:
                item[key] = {}
            if index < len(lines) and lines[index][0] > current_indent:
                nested, index = _parse_yaml_block(lines, index, current_indent + 2)
                if isinstance(nested, dict):
                    item.update(nested)
            items.append(item)
            continue
        items.append(_parse_yaml_scalar(remainder))
    return items, index


def _simple_yaml_load(text: str) -> Dict[str, Any]:
    lines: List[Tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        lines.append((indent, stripped))
    if not lines:
        return {}
    data, _ = _parse_yaml_block(lines, 0, lines[0][0])
    return data if isinstance(data, dict) else {}


class GateStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


@dataclass
class GateResult:
    gate_name: str
    status: GateStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    role: str
    overall_status: GateStatus
    results: List[GateResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "overall_status": self.overall_status.value,
            "results": [
                {
                    "gate_name": r.gate_name,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ],
            "summary": self.summary,
        }


class QualityGateChecker:
    """Check deliverables against quality gates defined in delivery contracts."""

    def __init__(self, contracts_dir: Optional[str] = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.contracts_dir = contracts_dir or os.path.join(base, "contracts")
        self.quality_gates_dir = os.path.join(base, "quality_gates")

    def _load_contract(self, role: str) -> Dict[str, Any]:
        path = os.path.join(self.contracts_dir, f"{role}.yaml")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Contract not found for role: {role}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        try:
            import yaml
        except ModuleNotFoundError:
            return _simple_yaml_load(content)
        return yaml.safe_load(content) or {}

    def check(self, role: str, deliverables: Dict[str, Any]) -> QualityReport:
        """Run all quality gates for a role's deliverables."""
        contract = self._load_contract(role)
        gates = contract.get("delivery_contract", {}).get("quality_gates", [])
        results: List[GateResult] = []

        for gate in gates:
            gate_name = gate.get("gate", "")
            tool = gate.get("tool", "")
            required = gate.get("required", False)
            result = self._run_gate(tool, gate_name, gate, deliverables, required)
            results.append(result)

        overall = self._compute_overall(results)
        summary = self._build_summary(results, contract)
        return QualityReport(role=role, overall_status=overall, results=results, summary=summary)

    def _run_gate(
        self,
        tool: str,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        handler = getattr(self, f"_check_{tool}", None)
        if handler is None:
            msg = f"Unknown gate tool: {tool}"
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message=msg,
            )
        return handler(gate_name, gate_config, deliverables, required)

    def _compute_overall(self, results: List[GateResult]) -> GateStatus:
        if any(r.status == GateStatus.FAIL for r in results):
            return GateStatus.FAIL
        if any(r.status == GateStatus.WARN for r in results):
            return GateStatus.WARN
        if all(r.status in (GateStatus.PASS, GateStatus.SKIP) for r in results):
            return GateStatus.PASS
        return GateStatus.FAIL

    def _build_summary(self, results: List[GateResult], contract: Dict[str, Any]) -> Dict[str, Any]:
        total = len(results)
        passed = sum(1 for r in results if r.status == GateStatus.PASS)
        failed = sum(1 for r in results if r.status == GateStatus.FAIL)
        skipped = sum(1 for r in results if r.status == GateStatus.SKIP)
        warnings = sum(1 for r in results if r.status == GateStatus.WARN)
        return {
            "total_gates": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "warnings": warnings,
            "role_name": contract.get("name", ""),
        }

    # ------------------------------------------------------------------
    # Built-in gate checkers
    # ------------------------------------------------------------------

    def _check_coverage_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        threshold = gate_config.get("threshold", 80)
        coverage = deliverables.get("coverage", 0)
        if coverage is None:
            coverage = 0
        if coverage >= threshold:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message=f"Coverage {coverage}% >= threshold {threshold}%",
                details={"coverage": coverage, "threshold": threshold},
            )
        msg = f"Coverage {coverage}% < threshold {threshold}%"
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=msg,
            details={"coverage": coverage, "threshold": threshold},
        )

    def _check_code_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        code = deliverables.get("code", "")
        if not code:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="No code provided for review",
            )
        issues = self._review_code(code)
        if not issues:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="Code review passed",
                details={"issues": []},
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"Code review found {len(issues)} issue(s)",
            details={"issues": issues},
        )

    def _check_api_doc_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        doc = deliverables.get("api_doc", "")
        if not doc:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="API doc not provided",
            )
        missing = []
        for keyword in ["Endpoint", "Method", "Request", "Response"]:
            if keyword.lower() not in doc.lower():
                missing.append(keyword)
        if not missing:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="API doc structure valid",
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"API doc missing sections: {', '.join(missing)}",
            details={"missing_sections": missing},
        )

    def _check_self_checklist(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        checklist = deliverables.get("self_checklist", [])
        if not checklist:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="Self-checklist not provided",
            )
        unchecked = [item for item in checklist if not item.get("checked", False)]
        if not unchecked:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="All self-checklist items passed",
                details={"total": len(checklist)},
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"{len(unchecked)} self-checklist item(s) unchecked",
            details={"unchecked": [u.get("text", "") for u in unchecked]},
        )

    def _check_lint_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        code = deliverables.get("code", "")
        if not code:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="No code provided for lint",
            )
        issues = self._lint_code(code)
        if not issues:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="Lint check passed",
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"Lint found {len(issues)} issue(s)",
            details={"issues": issues},
        )

    def _check_test_execution(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        tests = deliverables.get("tests", [])
        if not tests:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="No tests provided",
            )
        failed = [t for t in tests if not t.get("passed", False)]
        if not failed:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message=f"All {len(tests)} test(s) passed",
                details={"total": len(tests), "failed": 0},
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"{len(failed)}/{len(tests)} test(s) failed",
            details={"total": len(tests), "failed": len(failed), "failures": [f.get("name", "") for f in failed]},
        )

    def _check_performance_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        metrics = deliverables.get("performance_metrics", {})
        threshold = gate_config.get("threshold", {})
        failures = []
        for key, limit in threshold.items():
            actual = metrics.get(key)
            if actual is None:
                failures.append(f"{key}: missing")
            elif actual > limit:
                failures.append(f"{key}: {actual} > {limit}")
        if not failures:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="Performance check passed",
                details={"metrics": metrics},
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"Performance check failed: {', '.join(failures)}",
            details={"failures": failures, "metrics": metrics},
        )

    def _check_security_scan(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        code = deliverables.get("code", "")
        if not code:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="No code provided for security scan",
            )
        issues = self._scan_security(code)
        if not issues:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="Security scan passed",
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"Security scan found {len(issues)} issue(s)",
            details={"issues": issues},
        )

    def _check_design_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        design = deliverables.get("design_doc", "")
        if not design:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="Design doc not provided",
            )
        missing = []
        for keyword in ["Overview", "Architecture", "Data Model", "Interface"]:
            if keyword.lower() not in design.lower():
                missing.append(keyword)
        if not missing:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="Design review passed",
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"Design doc missing sections: {', '.join(missing)}",
            details={"missing_sections": missing},
        )

    def _check_db_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        ddl = deliverables.get("ddl", "")
        if not ddl:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="DDL not provided",
            )
        issues = []
        if "index" not in ddl.lower():
            issues.append("Missing indexes")
        if "created_at" not in ddl.lower() and "updated_at" not in ddl.lower():
            issues.append("Missing timestamp columns")
        if not issues:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="DB review passed",
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"DB review found {len(issues)} issue(s)",
            details={"issues": issues},
        )

    def _check_pr_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        pr = deliverables.get("pr_description", "")
        if not pr:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.FAIL if required else GateStatus.SKIP,
                message="PR description not provided",
            )
        missing = []
        for keyword in ["Summary", "Changes", "Testing"]:
            if keyword.lower() not in pr.lower():
                missing.append(keyword)
        if not missing:
            return GateResult(
                gate_name=gate_name,
                status=GateStatus.PASS,
                message="PR review passed",
            )
        return GateResult(
            gate_name=gate_name,
            status=GateStatus.FAIL if required else GateStatus.WARN,
            message=f"PR description missing sections: {', '.join(missing)}",
            details={"missing_sections": missing},
        )

    def _check_review_meeting(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        minutes = str(deliverables.get("review_minutes", "")).strip()
        if not minutes:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Review minutes not provided")
        keywords = ["结论", "通过", "参与", "review"]
        missing = [kw for kw in keywords if kw.lower() not in minutes.lower()]
        if len(missing) < len(keywords):
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Review meeting evidence present")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Review minutes missing decision evidence")

    def _check_acceptance_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        criteria = deliverables.get("acceptance_criteria", [])
        if not criteria:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Acceptance criteria not provided")
        invalid = []
        for item in criteria:
            description = str(item.get("description", "") if isinstance(item, dict) else item).strip()
            if len(description) < 6:
                invalid.append(description)
        if not invalid:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Acceptance criteria are testable", details={"count": len(criteria)})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"{len(invalid)} acceptance criteria invalid", details={"invalid": invalid})

    def _check_scope_confirm(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        boundary = deliverables.get("scope_boundary", {})
        in_scope = list(boundary.get("in_scope", [])) if isinstance(boundary, dict) else []
        out_scope = list(boundary.get("out_of_scope", [])) if isinstance(boundary, dict) else []
        if in_scope and out_scope:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Scope boundary confirmed", details={"in_scope": len(in_scope), "out_of_scope": len(out_scope)})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Scope boundary missing in/out scope sections")

    def _check_tech_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        return self._check_design_review(gate_name, gate_config, deliverables, required)

    def _check_adr_archive(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        adr_doc = str(deliverables.get("adr_doc", "")).strip()
        if not adr_doc:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="ADR not provided")
        required_sections = ["ADR", "Status", "Decision"]
        missing = [kw for kw in required_sections if kw.lower() not in adr_doc.lower()]
        if not missing:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="ADR archived")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"ADR missing sections: {', '.join(missing)}", details={"missing_sections": missing})

    def _check_api_publish(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        deliverables = dict(deliverables)
        if not deliverables.get("api_doc") and deliverables.get("api_contract"):
            deliverables["api_doc"] = deliverables["api_contract"]
        return self._check_api_doc_check(gate_name, gate_config, deliverables, required)

    def _check_table_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        return self._check_db_review(gate_name, gate_config, deliverables, required)

    def _check_explain_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        explain_report = deliverables.get("explain_report", [])
        if not explain_report:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="EXPLAIN report not provided")
        risky = []
        for item in explain_report:
            scan_type = str(item.get("type", "")).lower()
            rows = int(item.get("rows", 0))
            if scan_type in {"all", "full scan"} or rows > 10000:
                risky.append({"sql": item.get("sql", ""), "type": scan_type, "rows": rows})
        if not risky:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Explain analysis passed", details={"queries": len(explain_report)})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"Explain analysis found {len(risky)} risky query(s)", details={"issues": risky})

    def _check_index_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        index_plan = deliverables.get("index_plan", {})
        indexes = list(index_plan.get("indexes", [])) if isinstance(index_plan, dict) else []
        if indexes:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Index review passed", details={"index_count": len(indexes)})
        ddl = str(deliverables.get("ddl", ""))
        if "create index" in ddl.lower() or " index " in ddl.lower():
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Indexes found in DDL")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Index plan not provided")

    def _check_linter(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        return self._check_lint_check(gate_name, gate_config, deliverables, required)

    def _check_test_runner(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        return self._check_test_execution(gate_name, gate_config, deliverables, required)

    def _check_handoff_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        handoff_doc = str(deliverables.get("handoff_doc", "")).strip()
        if not handoff_doc:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Handoff document not provided")
        keywords = ["页面", "状态", "资源", "交接", "标注"]
        matched = [kw for kw in keywords if kw.lower() in handoff_doc.lower()]
        if len(matched) >= 3:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Handoff information complete", details={"matched_keywords": matched})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Handoff document missing key sections", details={"matched_keywords": matched})

    def _check_usability_plan_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        plan = str(deliverables.get("usability_plan", "")).strip()
        if not plan:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Usability plan not provided")
        keywords = ["用户", "场景", "成功", "观察"]
        missing = [kw for kw in keywords if kw.lower() not in plan.lower()]
        if not missing:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Usability plan is actionable")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"Usability plan missing sections: {', '.join(missing)}", details={"missing_sections": missing})

    def _check_case_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        cases = deliverables.get("test_cases", [])
        if not cases:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Test cases not provided")
        invalid = []
        for case in cases:
            if not isinstance(case, dict):
                invalid.append(case)
                continue
            if not case.get("title") or not case.get("steps") or not case.get("expected"):
                invalid.append(case.get("title", "unnamed"))
        if not invalid:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Test case review passed", details={"count": len(cases)})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"{len(invalid)} test case(s) incomplete", details={"invalid": invalid})

    def _check_bug_format_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        bug_reports = deliverables.get("bug_reports", [])
        if not bug_reports:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Bug reports not provided")
        invalid = []
        for report in bug_reports:
            missing = [field for field in ("title", "steps", "expected", "actual") if not report.get(field)]
            if missing:
                invalid.append({"title": report.get("title", ""), "missing": missing})
        if not invalid:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Bug report format valid", details={"count": len(bug_reports)})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"{len(invalid)} bug report(s) incomplete", details={"invalid": invalid})

    def _check_perf_plan_review(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        plan = str(deliverables.get("perf_plan", "")).strip()
        if not plan:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Performance plan not provided")
        keywords = ["目标", "场景", "并发", "数据", "指标"]
        matched = [kw for kw in keywords if kw.lower() in plan.lower()]
        if len(matched) >= 4:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Performance plan review passed", details={"matched_keywords": matched})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Performance plan missing key sections", details={"matched_keywords": matched})

    def _check_metrics_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        metrics = deliverables.get("performance_metrics", {})
        required_keys = ["tps", "p95_ms", "error_rate"]
        missing = [key for key in required_keys if key not in metrics]
        if missing:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"Missing metrics: {', '.join(missing)}", details={"missing": missing})
        if metrics.get("error_rate", 1) > 0.05:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Error rate exceeds threshold", details={"metrics": metrics})
        return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Metrics check passed", details={"metrics": metrics})

    def _check_bottleneck_confirm(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        analysis = deliverables.get("bottleneck_analysis", {})
        bottlenecks = list(analysis.get("bottlenecks", [])) if isinstance(analysis, dict) else []
        confirmed = bool(analysis.get("confirmed")) if isinstance(analysis, dict) else False
        evidence_missing = [item for item in bottlenecks if not item.get("evidence")]
        if confirmed and bottlenecks and not evidence_missing:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Bottleneck confirmed", details={"count": len(bottlenecks)})
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message="Bottleneck analysis missing confirmation or evidence")

    def _check_deploy_script_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        deployment_config = str(deliverables.get("deployment_config", "")).strip()
        if not deployment_config:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Deployment config not provided")
        keywords = ["rollback", "healthcheck", "strategy"]
        missing = [kw for kw in keywords if kw.lower() not in deployment_config.lower()]
        if not missing:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Deployment config validated")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"Deployment config missing sections: {', '.join(missing)}", details={"missing_sections": missing})

    def _check_monitoring_check(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        monitoring_config = str(deliverables.get("monitoring_config", "")).strip()
        if not monitoring_config:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Monitoring config not provided")
        keywords = ["alert", "dashboard"]
        missing = [kw for kw in keywords if kw.lower() not in monitoring_config.lower()]
        if not missing:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Monitoring config validated")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"Monitoring config missing sections: {', '.join(missing)}", details={"missing_sections": missing})

    def _check_emergency_drill(
        self,
        gate_name: str,
        gate_config: Dict[str, Any],
        deliverables: Dict[str, Any],
        required: bool,
    ) -> GateResult:
        emergency_plan = str(deliverables.get("emergency_plan", "")).strip()
        if not emergency_plan:
            return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.SKIP, message="Emergency plan not provided")
        keywords = ["drill", "rollback", "owner"]
        missing = [kw for kw in keywords if kw.lower() not in emergency_plan.lower()]
        if not missing:
            return GateResult(gate_name=gate_name, status=GateStatus.PASS, message="Emergency drill evidence present")
        return GateResult(gate_name=gate_name, status=GateStatus.FAIL if required else GateStatus.WARN, message=f"Emergency plan missing sections: {', '.join(missing)}", details={"missing_sections": missing})

    # ------------------------------------------------------------------
    # Static analysis helpers
    # ------------------------------------------------------------------

    def _review_code(self, code: str) -> List[Dict[str, Any]]:
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "TODO" in stripped and "FIXME" not in stripped:
                issues.append({"line": i, "type": "todo", "message": "Unresolved TODO"})
            if re.search(r"password\s*=\s*['\"]", stripped, re.IGNORECASE):
                issues.append({"line": i, "type": "secret", "message": "Possible hardcoded password"})
        return issues

    def _lint_code(self, code: str) -> List[Dict[str, Any]]:
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({"line": i, "type": "line_length", "message": "Line exceeds 120 chars"})
            if line.endswith(" ") or line.endswith("\t"):
                issues.append({"line": i, "type": "trailing_whitespace", "message": "Trailing whitespace"})
        return issues

    def _scan_security(self, code: str) -> List[Dict[str, Any]]:
        issues = []
        lines = code.splitlines()
        dangerous = ["eval(", "exec(", "os.system(", "subprocess.call("]
        for i, line in enumerate(lines, 1):
            for d in dangerous:
                if d in line:
                    issues.append({"line": i, "type": "dangerous_call", "message": f"Dangerous call: {d}"})
        return issues
