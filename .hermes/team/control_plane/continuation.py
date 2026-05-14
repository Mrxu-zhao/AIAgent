from __future__ import annotations

from typing import Any, Dict, List

READY_STATUSES = {
    "pending",
    "handoff_materialized",
    "handoff_dispatched",
    "workflow_resumed",
    "workflow_continued",
}
FAILED_STATUSES = {"failed", "workflow_resume_failed"}


def _unique(values: List[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def resume_workflow(workflow_id: str, runtime_store) -> Dict[str, Any]:
    snapshot = runtime_store.read_snapshot(workflow_id)
    step_statuses = (
        runtime_store.get_step_statuses(workflow_id)
        if hasattr(runtime_store, "get_step_statuses")
        else {}
    )
    events = runtime_store.list_step_events(workflow_id)

    step_histories: Dict[str, List[str]] = {}
    for event in events:
        step_id = str(event.get("step_id", "")).strip()
        status = str(event.get("status", "")).strip()
        if not step_id or not status or step_id == "__workflow__":
            continue
        step_histories.setdefault(step_id, []).append(status)
    for step_id, status in step_statuses.items():
        if not step_id or not status:
            continue
        step_histories.setdefault(step_id, []).append(status)

    completed_steps = [
        step_id
        for step_id, statuses in step_histories.items()
        if "completed" in statuses
    ]
    failed_steps = [
        step_id
        for step_id, statuses in step_histories.items()
        if step_id not in completed_steps and any(status in FAILED_STATUSES for status in statuses)
    ]
    ready_steps = [
        step_id
        for step_id, statuses in step_histories.items()
        if step_id not in completed_steps
        and step_id not in failed_steps
        and any(status in READY_STATUSES for status in statuses)
    ]

    return {
        "workflow_id": workflow_id,
        "snapshot": snapshot,
        "completed_steps": _unique(completed_steps),
        "failed_steps": _unique(failed_steps),
        "ready_steps": _unique(ready_steps),
    }
