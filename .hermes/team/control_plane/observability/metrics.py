from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from threading import RLock
from typing import Dict


class MetricsRegistry:
    def __init__(self):
        self._gauges: Dict[str, float] = {}
        self._counters = defaultdict(float)
        self._lock = RLock()

    def set_gauge(self, name: str, value: float):
        with self._lock:
            self._gauges[name] = float(value)

    def inc_counter(self, name: str, amount: float = 1.0):
        with self._lock:
            self._counters[name] += float(amount)

    def record_ratio(self, name: str, numerator: float, denominator: float):
        with self._lock:
            value = 0.0 if denominator == 0 else float(numerator) / float(denominator)
            self._gauges[name] = value
            return value

    def render_prometheus_text(self) -> str:
        lines = []
        with self._lock:
            for name, value in sorted(self._gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
            for name, value in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


_registry = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    return _registry


def refresh_repository_metrics(root: Path | None = None, registry: MetricsRegistry | None = None):
    active_root = Path(root) if root is not None else Path(__file__).resolve().parents[4]
    active_registry = registry or get_metrics_registry()

    tests_dir = active_root / "tests" / "control_plane"
    test_files_total = len(list(tests_dir.glob("test_*.py"))) if tests_dir.exists() else 0
    active_registry.set_gauge("improvement_test_files_total", float(test_files_total))

    coverage_ratio = _read_core_path_coverage_ratio(active_root)
    if coverage_ratio is not None:
        active_registry.set_gauge("improvement_core_path_coverage_ratio", coverage_ratio)

    active_registry.set_gauge(
        "improvement_doc_impl_gap_total",
        float(_count_doc_impl_gaps(active_root)),
    )

    auto_recovery_ratio = _read_auto_recovery_closure_ratio(active_root)
    if auto_recovery_ratio is not None:
        active_registry.set_gauge("improvement_auto_recovery_closure_ratio", auto_recovery_ratio)

    return active_registry


def _read_core_path_coverage_ratio(root: Path) -> float | None:
    summary_path = root / ".hermes" / "team" / "control_plane" / "artifacts" / "execution-summary-2026-05-12.md"
    if not summary_path.exists():
        return None

    content = summary_path.read_text(encoding="utf-8")
    match = re.search(r"交付关键路径总覆盖率：`?(\d+(?:\.\d+)?)%`?", content)
    if match is None:
        return None
    return float(match.group(1)) / 100.0


def _count_doc_impl_gaps(root: Path) -> int:
    framework_root = root / ".hermes" / "team" / "调度框架"
    readmes = [
        framework_root / "README.md",
        framework_root / "README_v2.md",
    ]
    required_tokens = [
        "P1-1",
        "P1-2",
        "P1-3",
        "P1-4",
        "P1-5",
        "P2-1",
        "P2-2",
        "P2-3",
        "P2-4",
        "P2-5",
        "里程碑-1",
        "里程碑-2",
        "里程碑-3",
        "里程碑-4",
    ]
    missing = 0
    for readme in readmes:
        if not readme.exists():
            missing += len(required_tokens)
            continue
        content = readme.read_text(encoding="utf-8")
        missing += sum(1 for token in required_tokens if token not in content)
    return missing


def _read_auto_recovery_closure_ratio(root: Path) -> float | None:
    validation_path = root / ".hermes" / "team" / "control_plane" / "artifacts" / "real-load-validation.json"
    if not validation_path.exists():
        return None

    payload = json.loads(validation_path.read_text(encoding="utf-8"))
    summary = payload.get("real_load", {}).get("summary", {})
    done = float(len(summary.get("done_tasks", [])))
    failed = float(len(summary.get("failed_tasks", [])))
    blocked = float(len(summary.get("blocked_tasks", [])))
    conflicted = float(len(summary.get("conflicted_tasks", [])))
    total = done + failed + blocked + conflicted
    return 0.0 if total == 0 else done / total
