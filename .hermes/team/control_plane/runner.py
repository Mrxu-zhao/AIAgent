from pathlib import Path

from adapters import HermesExecutorAdapter, get_default_executor_adapter
from config import load_control_plane_config
from executor import ControlPlaneExecutor
from orchestrator import ControlPlaneOrchestrator
from store import TaskStore
from tasks import TASKS


def register_tasks(store, cards):
    for card in cards:
        snapshot_path = store.state_dir / f"{card.task_id}.json"
        if snapshot_path.exists():
            continue
        store.register_task(card)


def run_registered_batch(store, cards, adapter, command_runner, max_workers=2):
    executor = ControlPlaneExecutor(store=store)
    orchestrator = ControlPlaneOrchestrator(store=store, executor=executor)
    return orchestrator.run(
        cards,
        adapter=adapter,
        command_runner=command_runner,
        max_workers=max_workers,
    )


def run_task_batch(
    cards=None,
    state_dir=None,
    events_dir=None,
    adapter=None,
    command_runner=None,
    max_workers=2,
):
    config = load_control_plane_config()
    cards = cards or TASKS
    state_dir = Path(state_dir) if state_dir else Path(config.directories["state_dir"])
    events_dir = Path(events_dir) if events_dir else Path(config.directories["events_dir"])
    store = TaskStore(state_dir=state_dir, events_dir=events_dir)
    register_tasks(store, cards)
    adapter = adapter or get_default_executor_adapter() or HermesExecutorAdapter()
    summary = run_registered_batch(
        store,
        cards,
        adapter,
        command_runner,
        max_workers=max_workers,
    )
    return {
        "task_ids": [card.task_id for card in cards],
        "summary": summary,
        "state_dir": str(state_dir),
        "events_dir": str(events_dir),
        "store": store,
    }
