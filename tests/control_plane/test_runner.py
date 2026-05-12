import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import load_control_plane_module


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_dir = Path(self.temp_dir.name) / "state"
        self.events_dir = Path(self.temp_dir.name) / "events"
        self.runner = load_control_plane_module("runner")
        self.tasks_module = load_control_plane_module("tasks")

    def test_run_task_batch_registers_default_tasks_and_returns_summary(self):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        result = self.runner.run_task_batch(
            state_dir=self.state_dir,
            events_dir=self.events_dir,
            command_runner=lambda command: Result(),
            max_workers=1,
        )

        self.assertIn("summary", result)
        self.assertIn("store", result)
        self.assertEqual(
            sorted(result["task_ids"]),
            sorted(card.task_id for card in self.tasks_module.TASKS),
        )

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
            expected_version=1,
        )

        self.runner.register_tasks(store, [card])

        snapshot = store.read_snapshot(card.task_id)
        self.assertEqual(snapshot["status"], models.TaskStatus.DONE.value)

    def test_run_batch_main_prints_summary_payload(self):
        run_batch = load_control_plane_module("run_batch")

        calls = {}

        def fake_run_task_batch(**kwargs):
            calls.update(kwargs)
            return {"summary": {"done_tasks": ["WS-A-P0-001"], "rounds": 1}}

        run_batch.runner.run_task_batch = fake_run_task_batch

        with patch("sys.argv", ["run_batch.py", "--max-workers", "3"]):
            with patch("builtins.print") as mock_print:
                run_batch.main()

        self.assertEqual(calls["max_workers"], 3)
        mock_print.assert_called()


class RunnerExportTests(unittest.TestCase):
    def test_control_plane_package_exports_runner_helpers(self):
        package = load_control_plane_module("__init__")
        self.assertTrue(hasattr(package, "run_task_batch"))
        self.assertTrue(hasattr(package, "register_tasks"))


if __name__ == "__main__":
    unittest.main()
