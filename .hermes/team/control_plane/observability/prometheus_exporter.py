from pathlib import Path

from observability.metrics import get_metrics_registry


def export_metrics_text(registry=None) -> str:
    active_registry = registry or get_metrics_registry()
    return active_registry.render_prometheus_text()


def write_metrics_file(path: Path, registry=None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(export_metrics_text(registry=registry), encoding="utf-8")
    return target
