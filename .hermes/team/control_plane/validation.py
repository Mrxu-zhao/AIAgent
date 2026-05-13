from dataclasses import replace
from pathlib import Path

from models import (
    EventType,
    TaskCard,
    TaskEvent,
    TaskStatus,
)
from orchestrator import ControlPlaneOrchestrator
from runner import run_task_batch
from store import TaskStore
from tasks import TASKS


def replicate_cards(cards, replicas=1):
    replicated = []
    for replica in range(1, replicas + 1):
        suffix = f"R{replica:02d}"
        for card in cards:
            replicated.append(
                replace(
                    card,
                    task_id=f"{card.task_id}-{suffix}",
                    dependencies=[f"{dependency}-{suffix}" for dependency in card.dependencies],
                )
            )
    return replicated


def run_real_load_validation(
    cards=None,
    replicas=3,
    state_dir=None,
    events_dir=None,
    adapter=None,
    command_runner=None,
    max_workers=4,
):
    base_cards = cards or TASKS
    expanded_cards = replicate_cards(base_cards, replicas=replicas)
    result = run_task_batch(
        cards=expanded_cards,
        state_dir=state_dir,
        events_dir=events_dir,
        adapter=adapter,
        command_runner=command_runner,
        max_workers=max_workers,
    )
    summary = result["summary"]
    return {
        "workload": {
            "base_tasks": len(base_cards),
            "replicas": replicas,
            "total_tasks": len(expanded_cards),
            "max_workers": max_workers,
        },
        "paths": {
            "state_dir": str(Path(result["state_dir"])),
            "events_dir": str(Path(result["events_dir"])),
        },
        "summary": summary,
        "checks": {
            "all_tasks_done": len(summary["done_tasks"]) == len(expanded_cards),
            "no_failed_tasks": not summary["failed_tasks"],
            "no_blocked_tasks": not summary["blocked_tasks"],
            "no_conflicted_tasks": not summary["conflicted_tasks"],
        },
    }


def _make_validation_card(template: TaskCard, task_id: str, goal: str, dependencies=None):
    return replace(
        template,
        task_id=task_id,
        title=task_id,
        goal=goal,
        dependencies=dependencies or [],
        status=TaskStatus.PLANNED,
        evidence=[],
    )


def run_behavior_validation(base_dir):
    base_dir = Path(base_dir)

    class Adapter:
        def build_dispatch_command(self, agent_id, task):
            return ["dispatch", agent_id, task]

    success_template = TASKS[0]
    conflict_template = TASKS[1] if len(TASKS) > 1 else TASKS[0]

    block_store = TaskStore(base_dir / "behavior-state" / "block", base_dir / "behavior-events" / "block")
    block_cards = [
        _make_validation_card(success_template, "VAL-BLOCK-ROOT", "block-root"),
        _make_validation_card(success_template, "VAL-BLOCK-LEAF", "block-leaf", dependencies=["VAL-BLOCK-ROOT"]),
    ]
    for card in block_cards:
        block_store.register_task(card)

    def block_runner(command):
        class Result:
            stdout = ""
            stderr = "boom" if command[-1] == "block-root" else ""
            returncode = 1 if command[-1] == "block-root" else 0

        return Result()

    block_summary = ControlPlaneOrchestrator(store=block_store).run(
        block_cards,
        adapter=Adapter(),
        command_runner=block_runner,
        max_workers=2,
    )

    conflict_store = TaskStore(
        base_dir / "behavior-state" / "conflict",
        base_dir / "behavior-events" / "conflict",
    )
    conflict_card = _make_validation_card(conflict_template, "VAL-CONFLICT-001", "conflict-goal")
    conflict_store.register_task(conflict_card)

    def conflict_runner(command):
        snapshot = conflict_store.read_snapshot(conflict_card.task_id)
        conflict_store.append_event(
            TaskEvent(
                event_id="evt-validation-conflict",
                task_id=conflict_card.task_id,
                event_type=EventType.TASK_PROGRESS,
                agent_id="validation",
                timestamp=2.0,
                attempt=1,
                status_before=TaskStatus(snapshot["status"]),
                status_after=TaskStatus(snapshot["status"]),
                summary="external update during validation",
                artifact_refs=[],
                lock_scope={
                    "files": conflict_card.lock_scope.files,
                    "modules": conflict_card.lock_scope.modules,
                    "contracts": conflict_card.lock_scope.contracts,
                },
                depends_on=conflict_card.dependencies,
                metrics_delta={},
                error_code=None,
            ),
            expected_version=snapshot["version"],
        )

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    conflict_summary = ControlPlaneOrchestrator(store=conflict_store).run(
        [conflict_card],
        adapter=Adapter(),
        command_runner=conflict_runner,
        max_workers=1,
    )
    conflict_events = conflict_store.list_events(conflict_card.task_id)

    return {
        "dependency_blocking": {
            "summary": block_summary,
            "checks": {
                "blocked_dependency_recorded": block_summary["blocked_tasks"] == ["VAL-BLOCK-LEAF"],
            },
        },
        "version_conflict": {
            "summary": conflict_summary,
            "checks": {
                "conflict_recorded": any(
                    event["event_type"] == EventType.TASK_CONFLICT_DETECTED.value
                    for event in conflict_events
                ),
            },
        },
    }
