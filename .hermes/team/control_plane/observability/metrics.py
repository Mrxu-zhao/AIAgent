from __future__ import annotations

from collections import defaultdict
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
