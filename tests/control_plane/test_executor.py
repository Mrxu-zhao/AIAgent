import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import load_control_plane_module

models = load_control_plane_module("models")
store_module = load_control_plane_module("store")
executor_module = load_control_plane_module("executor")
adapters_module = load_control_plane_module("adapters")


class ExecutorTests(unittest.TestCase):
    def test_failed_task_blocks_dependents_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            runner = executor_module.ControlPlaneExecutor(store)
            graph = {
                "WS-A-P0-001": [],
                "WS-A-P0-002": ["WS-A-P0-001"],
                "WS-D-P1-001": [],
            }

            blocked = runner.compute_blocked_tasks("WS-A-P0-001", graph)

            self.assertEqual(blocked, ["WS-A-P0-002"])

    def test_transient_failure_retries_within_limit(self):
        runner = executor_module.ControlPlaneExecutor(store=None)

        self.assertTrue(runner.should_retry(1, 2, "transient"))
        self.assertFalse(runner.should_retry(2, 2, "transient"))
        self.assertFalse(runner.should_retry(1, 2, "deterministic"))

    def test_dispatch_command_uses_hermes_adapter(self):
        runner = executor_module.ControlPlaneExecutor(store=None)
        adapter = adapters_module.HermesExecutorAdapter()
        command = runner.build_dispatch_command(adapter, "architect", "analyze task")

        self.assertEqual(
            command,
            ["hermes", "team", "dispatch", "-a", "architect", "-t", "analyze task"],
        )

    def test_execute_task_records_started_and_completed_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            runner = executor_module.ControlPlaneExecutor(store=store)
            adapter = adapters_module.HermesExecutorAdapter()
            card = models.TaskCard(
                task_id="WS-B-P1-010",
                title="Dispatch via Hermes",
                goal="Run Hermes task",
                scope=[".hermes/team/control_plane/executor.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["task"],
                outputs=["stdout"],
                dependencies=[],
                owner_agent="architect",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["task completes"],
            )
            store.register_task(card)

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            outcome = runner.execute_task(card, adapter, lambda command: Result())

            snapshot = store.read_snapshot(card.task_id)
            events = store.list_events(card.task_id)

            self.assertTrue(outcome["success"])
            self.assertEqual(snapshot["status"], "done")
            self.assertEqual(snapshot["version"], 3)
            self.assertEqual([event["status_after"] for event in events], ["running", "done"])

    def test_execute_task_records_failed_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            runner = executor_module.ControlPlaneExecutor(store=store)
            adapter = adapters_module.HermesExecutorAdapter()
            card = models.TaskCard(
                task_id="WS-B-P1-011",
                title="Fail Hermes task",
                goal="Persist failure state",
                scope=[".hermes/team/control_plane/executor.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["task"],
                outputs=["stderr"],
                dependencies=[],
                owner_agent="architect",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["failure state is written"],
            )
            store.register_task(card)

            class Result:
                returncode = 1
                stdout = ""
                stderr = "boom"

            outcome = runner.execute_task(card, adapter, lambda command: Result())

            snapshot = store.read_snapshot(card.task_id)
            events = store.list_events(card.task_id)

            self.assertFalse(outcome["success"])
            self.assertEqual(snapshot["status"], "failed")
            self.assertEqual(events[-1]["error_code"], "PROCESS_EXIT_1")

    def test_execute_task_detects_version_conflict_before_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            runner = executor_module.ControlPlaneExecutor(store=store)
            adapter = adapters_module.HermesExecutorAdapter()
            card = models.TaskCard(
                task_id="WS-B-P1-012",
                title="Conflict on completion",
                goal="Detect stale completion write",
                scope=[".hermes/team/control_plane/executor.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["task"],
                outputs=["conflict"],
                dependencies=[],
                owner_agent="architect",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["version conflict is surfaced"],
            )
            store.register_task(card)

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            def command_runner(command):
                store.append_event(
                    models.TaskEvent(
                        event_id="evt-external",
                        task_id=card.task_id,
                        event_type=models.EventType.TASK_PROGRESS,
                        agent_id="reviewer",
                        timestamp=2.0,
                        attempt=1,
                        status_before=models.TaskStatus.RUNNING,
                        status_after=models.TaskStatus.RUNNING,
                        summary="external update",
                        artifact_refs=[],
                        lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                        depends_on=[],
                        metrics_delta={},
                        error_code=None,
                    ),
                    expected_version=2,
                )
                return Result()

            outcome = runner.execute_task(card, adapter, command_runner)

            snapshot = store.read_snapshot(card.task_id)
            events = store.list_events(card.task_id)

            self.assertFalse(outcome["success"])
            self.assertEqual(outcome["error_code"], "VERSION_CONFLICT")
            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(snapshot["version"], 3)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[-1]["event_id"], "evt-external")

    def test_execute_task_supports_per_card_executor_backend_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            runner = executor_module.ControlPlaneExecutor(store=store)
            default_adapter = adapters_module.HermesExecutorAdapter()
            card = models.TaskCard(
                task_id="WS-B-P1-013",
                title="Override backend",
                goal="Route via openclaw",
                scope=[".hermes/team/control_plane/executor.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["task"],
                outputs=["stdout"],
                dependencies=[],
                owner_agent="backend-1",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["task uses explicit backend"],
                executor_backend="openclaw",
            )
            store.register_task(card)

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            override_adapter = adapters_module.OpenClawExecutorAdapter(
                openclaw_command="openclaw-live",
                dry_run=False,
                dispatch_args=["task", "run"],
            )

            observed = {}

            def command_runner(command):
                observed["command"] = command
                return Result()

            with patch.object(
                executor_module,
                "get_executor_adapter",
                return_value=override_adapter,
            ) as resolver_mock:
                outcome = runner.execute_task(card, default_adapter, command_runner)

            self.assertTrue(outcome["success"])
            resolver_mock.assert_called_once_with("openclaw")
            self.assertEqual(observed["command"][:3], ["openclaw-live", "task", "run"])
            self.assertIn("--execute", observed["command"])


if __name__ == "__main__":
    unittest.main()

