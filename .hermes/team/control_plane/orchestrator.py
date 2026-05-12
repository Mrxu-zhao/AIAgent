from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from uuid import uuid4

from models import EventType, TaskEvent, TaskStatus
from executor import ControlPlaneExecutor


def build_dependency_graph(cards):
    forward = {card.task_id: list(card.dependencies) for card in cards}
    reverse = defaultdict(list)
    for card in cards:
        for dependency in card.dependencies:
            reverse[dependency].append(card.task_id)
    for card in cards:
        reverse.setdefault(card.task_id, [])
    return {"forward": forward, "reverse": dict(reverse)}


def get_ready_tasks(cards, store):
    snapshots = {card.task_id: store.read_snapshot(card.task_id) for card in cards}
    terminal_statuses = {
        TaskStatus.DONE.value,
        TaskStatus.FAILED.value,
        TaskStatus.BLOCKED.value,
        TaskStatus.CANCELLED.value,
    }
    ready = []
    for card in cards:
        snapshot = snapshots[card.task_id]
        if snapshot["status"] in terminal_statuses:
            continue
        if all(snapshots[dependency]["status"] == TaskStatus.DONE.value for dependency in card.dependencies):
            ready.append(card)
    return ready


class ControlPlaneOrchestrator:
    def __init__(self, store, executor=None):
        self.store = store
        self.executor = executor or ControlPlaneExecutor(store=store)

    def record_conflict(self, card, summary):
        snapshot = self.store.read_snapshot(card.task_id)
        self.store.append_event(
            TaskEvent(
                event_id=f"evt-{uuid4().hex}",
                task_id=card.task_id,
                event_type=EventType.TASK_CONFLICT_DETECTED,
                agent_id="control-plane-orchestrator",
                timestamp=time.time(),
                attempt=1,
                status_before=TaskStatus(snapshot["status"]),
                status_after=TaskStatus(snapshot["status"]),
                summary=summary,
                artifact_refs=[],
                lock_scope={
                    "files": card.lock_scope.files,
                    "modules": card.lock_scope.modules,
                    "contracts": card.lock_scope.contracts,
                },
                depends_on=card.dependencies,
                metrics_delta={},
                error_code="VERSION_CONFLICT",
            ),
            expected_version=snapshot["version"],
        )

    def block_dependents(self, task_id, cards):
        cards_by_id = {card.task_id: card for card in cards}
        blocked = []
        terminal_statuses = {
            TaskStatus.DONE.value,
            TaskStatus.FAILED.value,
            TaskStatus.BLOCKED.value,
            TaskStatus.CANCELLED.value,
        }
        for dependent_id in build_dependency_graph(cards)["reverse"].get(task_id, []):
            snapshot = self.store.read_snapshot(dependent_id)
            if snapshot["status"] in terminal_statuses:
                continue

            dependent_card = cards_by_id[dependent_id]
            self.store.append_event(
                TaskEvent(
                    event_id=f"evt-{uuid4().hex}",
                    task_id=dependent_id,
                    event_type=EventType.TASK_BLOCKED,
                    agent_id="control-plane-orchestrator",
                    timestamp=time.time(),
                    attempt=1,
                    status_before=TaskStatus(snapshot["status"]),
                    status_after=TaskStatus.BLOCKED,
                    summary=f"blocked by failed dependency {task_id}",
                    artifact_refs=[],
                    lock_scope={
                        "files": dependent_card.lock_scope.files,
                        "modules": dependent_card.lock_scope.modules,
                        "contracts": dependent_card.lock_scope.contracts,
                    },
                    depends_on=[task_id],
                    metrics_delta={},
                    error_code="DEPENDENCY_BLOCKED",
                ),
                expected_version=snapshot["version"],
            )
            blocked.append(dependent_id)
        return blocked

    def run(self, cards, adapter, command_runner, max_workers=2):
        done_tasks = []
        failed_tasks = []
        blocked_tasks = []
        conflicted_tasks = []
        rounds = 0

        while True:
            ready_cards = [
                card
                for card in get_ready_tasks(cards, self.store)
                if self.store.read_snapshot(card.task_id)["status"]
                in (TaskStatus.PLANNED.value, TaskStatus.READY.value)
            ]
            if not ready_cards:
                break

            rounds += 1
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(self.executor.execute_task, card, adapter, command_runner): card
                    for card in ready_cards
                }
                for future in as_completed(future_map):
                    card = future_map[future]
                    result = future.result()
                    if result["success"]:
                        done_tasks.append(card.task_id)
                    elif result.get("error_code") == "VERSION_CONFLICT":
                        conflicted_tasks.append(card.task_id)
                        self.record_conflict(card, "orchestrator observed version conflict")
                    else:
                        failed_tasks.append(card.task_id)
                        blocked_tasks.extend(self.block_dependents(card.task_id, cards))

        return {
            "done_tasks": sorted(set(done_tasks)),
            "failed_tasks": sorted(set(failed_tasks)),
            "blocked_tasks": sorted(set(blocked_tasks)),
            "conflicted_tasks": sorted(set(conflicted_tasks)),
            "rounds": rounds,
        }
