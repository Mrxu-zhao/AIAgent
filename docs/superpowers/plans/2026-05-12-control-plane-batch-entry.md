# Control Plane Batch Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared control-plane batch runner that executes `TASKS` through `ControlPlaneOrchestrator`, expose it via a control-plane script entrypoint, and bridge it from `team-cli.py`.

**Architecture:** Add a focused `runner.py` that owns task registration and orchestration assembly, then layer two thin entrypoints on top: `run_batch.py` for direct control-plane execution and a new `team-cli.py` subcommand that forwards to the same runner. Keep terminal task state writes inside `ControlPlaneExecutor` and keep CLI glue free of orchestration logic.

**Tech Stack:** Python, `unittest`, `argparse`, file-backed `TaskStore`, existing control-plane orchestrator/executor/adapter modules

---

## File Map

- Create: `.hermes/team/control_plane/runner.py`
  - Shared batch registration and execution entrypoint for the control plane
- Create: `.hermes/team/control_plane/run_batch.py`
  - Thin script wrapper around `runner.run_task_batch(...)`
- Create: `tests/control_plane/test_runner.py`
  - TDD coverage for registration, idempotency, and batch summary behavior
- Create: `tests/control_plane/test_framework_team_cli_control_plane.py`
  - TDD coverage for `team-cli.py` bridge command
- Modify: `.hermes/team/control_plane/__init__.py`
  - Export runner helpers for package-level access
- Modify: `.hermes/team/control_plane/README.md`
  - Document the shared runner and both entrypoints
- Modify: `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`
  - Record the new batch-entry capabilities and verification results
- Modify: `.hermes/team/调度框架/cli/team-cli.py`
  - Add a control-plane bridge subcommand that forwards to the shared runner

### Task 1: Add Runner Registration and Batch Summary Core

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_runner.py`
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runner.py`

- [ ] **Step 1: Write the failing test for default registration and summary**

```python
import tempfile
import unittest
from pathlib import Path

from test_support import load_control_plane_module


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name) / "state"
        self.events_dir = Path(self.temp_dir.name) / "events"
        self.runner = load_control_plane_module("runner")
        self.tasks_module = load_control_plane_module("tasks")

    def test_run_task_batch_registers_default_tasks_and_returns_summary(self):
        def fake_command_runner(command):
            return {"success": True, "exit_code": 0, "stdout": "ok", "stderr": ""}

        result = self.runner.run_task_batch(
            state_dir=self.state_dir,
            events_dir=self.events_dir,
            command_runner=fake_command_runner,
            max_workers=1,
        )

        self.assertIn("summary", result)
        self.assertIn("store", result)
        self.assertEqual(sorted(result["task_ids"]), sorted(card.task_id for card in self.tasks_module.TASKS))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.control_plane.test_runner.RunnerTests.test_run_task_batch_registers_default_tasks_and_returns_summary -v`

Expected: FAIL with `FileNotFoundError` or `AttributeError` because `runner.py` and `run_task_batch(...)` do not exist yet.

- [ ] **Step 3: Write the minimal runner implementation**

```python
from pathlib import Path

from adapters import HermesExecutorAdapter
from executor import ControlPlaneExecutor
from orchestrator import ControlPlaneOrchestrator
from store import TaskStore
from tasks import TASKS


def register_tasks(store, cards):
    for card in cards:
        try:
            store.register_task(card)
        except FileExistsError:
            continue


def run_registered_batch(store, cards, adapter, command_runner, max_workers=2):
    executor = ControlPlaneExecutor(store=store)
    orchestrator = ControlPlaneOrchestrator(store=store, executor=executor)
    return orchestrator.run(cards, adapter=adapter, command_runner=command_runner, max_workers=max_workers)


def run_task_batch(cards=None, state_dir=None, events_dir=None, adapter=None, command_runner=None, max_workers=2):
    cards = cards or TASKS
    state_dir = Path(state_dir) if state_dir else Path(__file__).resolve().parent / "state"
    events_dir = Path(events_dir) if events_dir else Path(__file__).resolve().parent / "events"
    store = TaskStore(state_dir=state_dir, events_dir=events_dir)
    register_tasks(store, cards)
    adapter = adapter or HermesExecutorAdapter()
    summary = run_registered_batch(store, cards, adapter, command_runner, max_workers=max_workers)
    return {
        "task_ids": [card.task_id for card in cards],
        "summary": summary,
        "state_dir": str(state_dir),
        "events_dir": str(events_dir),
        "store": store,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.control_plane.test_runner.RunnerTests.test_run_task_batch_registers_default_tasks_and_returns_summary -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/control_plane/test_runner.py .hermes/team/control_plane/runner.py
git commit -m "feat: add control plane batch runner core"
```

### Task 2: Add Runner Idempotency Protection

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_runner.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runner.py`

- [ ] **Step 1: Write the failing idempotency test**

```python
    def test_register_tasks_does_not_reset_existing_terminal_snapshot(self):
        store_module = load_control_plane_module("store")
        models = load_control_plane_module("models")
        store = store_module.TaskStore(state_dir=self.state_dir, events_dir=self.events_dir)
        card = self.tasks_module.TASKS[0]
        store.register_task(card)

        store.append_event(
            models.TaskEvent(
                event_id="evt-finished",
                task_id=card.task_id,
                event_type=models.EventType.TASK_COMPLETED,
                agent_id="tester",
                timestamp=0.0,
                attempt=1,
                status_before=models.TaskStatus.PLANNED,
                status_after=models.TaskStatus.DONE,
                summary="finished",
                artifact_refs=[],
                lock_scope={"files": [], "modules": [], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            ),
            expected_version=0,
        )

        self.runner.register_tasks(store, [card])

        snapshot = store.read_snapshot(card.task_id)
        self.assertEqual(snapshot["status"], models.TaskStatus.DONE.value)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.control_plane.test_runner.RunnerTests.test_register_tasks_does_not_reset_existing_terminal_snapshot -v`

Expected: FAIL if `register_tasks(...)` tries to overwrite or reinitialize the existing snapshot.

- [ ] **Step 3: Tighten registration behavior to stay idempotent**

```python
def register_tasks(store, cards):
    for card in cards:
        snapshot_path = store._snapshot_path(card.task_id)
        if snapshot_path.exists():
            continue
        store.register_task(card)
```

- [ ] **Step 4: Run focused and file-level tests**

Run: `python -m unittest tests.control_plane.test_runner -v`

Expected: PASS for both the original runner test and the new idempotency test.

- [ ] **Step 5: Commit**

```bash
git add tests/control_plane/test_runner.py .hermes/team/control_plane/runner.py
git commit -m "feat: make control plane batch registration idempotent"
```

### Task 3: Add the Control-Plane Script Entrypoint

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\run_batch.py`
- Modify: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_runner.py`

- [ ] **Step 1: Write the failing script entrypoint test**

```python
    def test_run_batch_main_prints_summary_payload(self):
        run_batch = load_control_plane_module("run_batch")

        calls = {}

        def fake_run_task_batch(**kwargs):
            calls.update(kwargs)
            return {"summary": {"done_tasks": ["WS-A-P0-001"], "rounds": 1}}

        run_batch.runner.run_task_batch = fake_run_task_batch

        with unittest.mock.patch("sys.argv", ["run_batch.py", "--max-workers", "3"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                run_batch.main()

        self.assertEqual(calls["max_workers"], 3)
        mock_print.assert_called()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.control_plane.test_runner.RunnerTests.test_run_batch_main_prints_summary_payload -v`

Expected: FAIL because `run_batch.py` and `main()` do not exist yet.

- [ ] **Step 3: Implement the thin script wrapper**

```python
import argparse
import json

import runner


def build_parser():
    parser = argparse.ArgumentParser(description="Run control-plane task batch")
    parser.add_argument("--max-workers", type=int, default=2)
    return parser


def main():
    args = build_parser().parse_args()
    result = runner.run_task_batch(max_workers=args.max_workers)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run file-level tests**

Run: `python -m unittest tests.control_plane.test_runner -v`

Expected: PASS including the new script-wrapper test.

- [ ] **Step 5: Commit**

```bash
git add tests/control_plane/test_runner.py .hermes/team/control_plane/run_batch.py
git commit -m "feat: add control plane batch script entrypoint"
```

### Task 4: Bridge the Shared Runner from team-cli

**Files:**
- Create: `d:\KIMIK2.5\AIAgent\tests\control_plane\test_framework_team_cli_control_plane.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\cli\team-cli.py`

- [ ] **Step 1: Write the failing bridge test**

```python
import argparse
import unittest

from tests.control_plane.test_support import load_cli_module


class TeamCLIControlPlaneTests(unittest.TestCase):
    def test_control_plane_run_command_forwards_to_shared_runner(self):
        module = load_cli_module("team-cli.py", "framework_team_cli")
        cli = module.TeamCLI()

        observed = {}

        def fake_run_task_batch(**kwargs):
            observed.update(kwargs)
            return {"summary": {"done_tasks": ["WS-A-P0-001"], "rounds": 1}}

        module.control_plane_runner.run_task_batch = fake_run_task_batch
        cli.cmd_control_plane_run(argparse.Namespace(max_workers=4))

        self.assertEqual(observed["max_workers"], 4)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.control_plane.test_framework_team_cli_control_plane.TeamCLIControlPlaneTests.test_control_plane_run_command_forwards_to_shared_runner -v`

Expected: FAIL because there is no control-plane bridge command in `team-cli.py`.

- [ ] **Step 3: Add the bridge command and parser wiring**

```python
import control_plane.runner as control_plane_runner


class TeamCLI:
    def cmd_control_plane_run(self, args):
        result = control_plane_runner.run_task_batch(max_workers=args.max_workers)
        print(f"{Colors.GREEN}✓ 控制平面批次执行完成{Colors.NC}")
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


def main():
    ...
    control_plane_parser = subparsers.add_parser("control-plane-run", help="运行控制平面任务批次")
    control_plane_parser.add_argument("--max-workers", type=int, default=2, help="并发执行数")
    ...
    elif args.command == "control-plane-run":
        cli.cmd_control_plane_run(args)
```

- [ ] **Step 4: Run the new bridge test**

Run: `python -m unittest tests.control_plane.test_framework_team_cli_control_plane -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/control_plane/test_framework_team_cli_control_plane.py .hermes/team/调度框架/cli/team-cli.py
git commit -m "feat: bridge control plane batch runner from team cli"
```

### Task 5: Export the Runner and Update Docs

**Files:**
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\__init__.py`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\README.md`
- Modify: `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\artifacts\execution-summary-2026-05-12.md`

- [ ] **Step 1: Write the failing export test**

```python
class RunnerExportTests(unittest.TestCase):
    def test_control_plane_package_exports_runner_helpers(self):
        package = load_control_plane_module("__init__")
        self.assertTrue(hasattr(package, "run_task_batch"))
        self.assertTrue(hasattr(package, "register_tasks"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.control_plane.test_runner.RunnerExportTests -v`

Expected: FAIL because `__init__.py` does not export runner helpers yet.

- [ ] **Step 3: Export helpers and update docs**

```python
from runner import register_tasks, run_registered_batch, run_task_batch

__all__ = [
    ...,
    "register_tasks",
    "run_registered_batch",
    "run_task_batch",
]
```

```md
- `runner.py` 负责共享批次入口：注册任务、装配 store/executor/orchestrator、返回结构化摘要。
- `run_batch.py` 是控制平面自有脚本入口。
- `team-cli.py control-plane-run` 通过桥接方式复用同一 runner，不复制调度逻辑。
```

```md
- 控制平面已新增共享 batch runner，并同时接通控制平面脚本入口与 `team-cli.py` 桥接入口。
- 新增验证：`python -m unittest tests.control_plane.test_runner -v`
- 新增验证：`python -m unittest tests.control_plane.test_framework_team_cli_control_plane -v`
```

- [ ] **Step 4: Run doc-adjacent tests and package export tests**

Run: `python -m unittest tests.control_plane.test_runner -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .hermes/team/control_plane/__init__.py .hermes/team/control_plane/README.md .hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md tests/control_plane/test_runner.py
git commit -m "docs: publish control plane batch runner usage"
```

### Task 6: Run Full Verification and Fix Integration Gaps

**Files:**
- Verify:
  - `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\runner.py`
  - `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\run_batch.py`
  - `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\cli\team-cli.py`
  - `d:\KIMIK2.5\AIAgent\tests\control_plane\test_runner.py`
  - `d:\KIMIK2.5\AIAgent\tests\control_plane\test_framework_team_cli_control_plane.py`

- [ ] **Step 1: Run focused integration tests**

Run: `python -m unittest tests.control_plane.test_runner tests.control_plane.test_framework_team_cli_control_plane -v`

Expected: PASS

- [ ] **Step 2: Run control-plane full regression**

Run: `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`

Expected: PASS for all control-plane tests

- [ ] **Step 3: Run diagnostics on touched files**

Run diagnostics for:

- `file:///d:/KIMIK2.5/AIAgent/.hermes/team/control_plane/runner.py`
- `file:///d:/KIMIK2.5/AIAgent/.hermes/team/control_plane/run_batch.py`
- `file:///d:/KIMIK2.5/AIAgent/.hermes/team/调度框架/cli/team-cli.py`
- `file:///d:/KIMIK2.5/AIAgent/tests/control_plane/test_runner.py`
- `file:///d:/KIMIK2.5/AIAgent/tests/control_plane/test_framework_team_cli_control_plane.py`

Expected: no diagnostics, or only pre-existing unrelated diagnostics

- [ ] **Step 4: If any verification command fails, stop and return to the owning task**

Run: revisit Task 1-5 based on the failing file instead of inventing new behavior in Task 6

Expected: no ad-hoc code is added in Task 6; all fixes are applied by updating the specific task that owns the failing file

- [ ] **Step 5: Final commit**

```bash
git add .hermes/team/control_plane/runner.py .hermes/team/control_plane/run_batch.py .hermes/team/调度框架/cli/team-cli.py tests/control_plane/test_runner.py tests/control_plane/test_framework_team_cli_control_plane.py .hermes/team/control_plane/__init__.py .hermes/team/control_plane/README.md .hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md
git commit -m "feat: wire control plane batch entrypoints"
```
