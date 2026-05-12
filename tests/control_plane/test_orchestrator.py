import tempfile
import unittest
from pathlib import Path

try:
    from .test_support import load_control_plane_module
except ImportError:
    from test_support import load_control_plane_module

models = load_control_plane_module("models")
store_module = load_control_plane_module("store")
orchestrator_module = load_control_plane_module("orchestrator")


def make_card(task_id, dependencies=None, status=None):
    return models.TaskCard(
        task_id=task_id,
        title=f"title-{task_id}",
        goal=f"goal-{task_id}",
        scope=[".hermes/team/control_plane/orchestrator.py"],
        lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
        inputs=["spec"],
        outputs=["summary"],
        dependencies=dependencies or [],
        owner_agent="backend-2",
        review_agent="architect",
        priority=models.TaskPriority.P1,
        timeout_seconds=1200,
        retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
        rollback_policy=models.RollbackPolicy(mode="state"),
        acceptance_criteria=["orchestrator can schedule task"],
        status=status or models.TaskStatus.PLANNED,
    )


class OrchestratorGraphTests(unittest.TestCase):
    def test_build_dependency_graph_returns_forward_and_reverse_edges(self):
        cards = [
            make_card("WS-B-P1-010"),
            make_card("WS-B-P1-011", dependencies=["WS-B-P1-010"]),
            make_card("WS-B-P1-012", dependencies=["WS-B-P1-010"]),
        ]

        graph = orchestrator_module.build_dependency_graph(cards)

        self.assertEqual(graph["forward"]["WS-B-P1-011"], ["WS-B-P1-010"])
        self.assertEqual(
            sorted(graph["reverse"]["WS-B-P1-010"]),
            ["WS-B-P1-011", "WS-B-P1-012"],
        )

    def test_get_ready_tasks_returns_only_tasks_with_satisfied_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            cards = [
                make_card("WS-B-P1-020"),
                make_card("WS-B-P1-021", dependencies=["WS-B-P1-020"]),
                make_card("WS-B-P1-022"),
            ]
            for card in cards:
                store.register_task(card)

            ready = orchestrator_module.get_ready_tasks(cards, store)

            self.assertEqual(
                [card.task_id for card in ready],
                ["WS-B-P1-020", "WS-B-P1-022"],
            )


class OrchestratorRunTests(unittest.TestCase):
    def test_run_executes_multiple_ready_tasks_and_collects_done_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            cards = [
                make_card("WS-B-P1-030"),
                make_card("WS-B-P1-031"),
            ]
            for card in cards:
                store.register_task(card)

            class Adapter:
                def build_dispatch_command(self, agent_id, task):
                    return ["dispatch", agent_id, task]

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            def command_runner(command):
                return Result()

            executor = orchestrator_module.ControlPlaneExecutor(store=store)
            orchestrator = orchestrator_module.ControlPlaneOrchestrator(store=store, executor=executor)

            summary = orchestrator.run(
                cards,
                adapter=Adapter(),
                command_runner=command_runner,
                max_workers=2,
            )

            self.assertEqual(sorted(summary["done_tasks"]), ["WS-B-P1-030", "WS-B-P1-031"])
            self.assertEqual(summary["failed_tasks"], [])
            self.assertEqual(summary["blocked_tasks"], [])
            self.assertEqual(summary["conflicted_tasks"], [])
            self.assertGreaterEqual(summary["rounds"], 1)

    def test_failed_task_blocks_only_direct_dependents_and_records_task_blocked_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            cards = [
                make_card("WS-B-P1-040"),
                make_card("WS-B-P1-041", dependencies=["WS-B-P1-040"]),
                make_card("WS-B-P1-042"),
            ]
            for card in cards:
                store.register_task(card)

            class Adapter:
                def build_dispatch_command(self, agent_id, task):
                    return ["dispatch", agent_id, task]

            class SuccessResult:
                returncode = 0
                stdout = "ok"
                stderr = ""

            class FailureResult:
                returncode = 1
                stdout = ""
                stderr = "boom"

            def command_runner(command):
                if command[-1] == "goal-WS-B-P1-040":
                    return FailureResult()
                return SuccessResult()

            orchestrator = orchestrator_module.ControlPlaneOrchestrator(store=store)
            summary = orchestrator.run(
                cards,
                adapter=Adapter(),
                command_runner=command_runner,
                max_workers=2,
            )

            blocked_snapshot = store.read_snapshot("WS-B-P1-041")
            independent_snapshot = store.read_snapshot("WS-B-P1-042")
            blocked_events = store.list_events("WS-B-P1-041")

            self.assertEqual(summary["failed_tasks"], ["WS-B-P1-040"])
            self.assertEqual(summary["blocked_tasks"], ["WS-B-P1-041"])
            self.assertEqual(blocked_snapshot["status"], "blocked")
            self.assertEqual(independent_snapshot["status"], "done")
            self.assertEqual(
                [event["event_type"] for event in blocked_events],
                ["task_blocked"],
            )
            self.assertEqual(
                blocked_events[0]["error_code"],
                "DEPENDENCY_BLOCKED",
            )

    def test_version_conflict_is_recorded_without_marking_task_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_module.TaskStore(Path(tmp) / "state", Path(tmp) / "events")
            card = make_card("WS-B-P1-050")
            store.register_task(card)

            class Adapter:
                def build_dispatch_command(self, agent_id, task):
                    return ["dispatch", agent_id, task]

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            def command_runner(command):
                store.append_event(
                    models.TaskEvent(
                        event_id="evt-external-conflict",
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

            orchestrator = orchestrator_module.ControlPlaneOrchestrator(store=store)
            summary = orchestrator.run(
                [card],
                adapter=Adapter(),
                command_runner=command_runner,
                max_workers=1,
            )

            snapshot = store.read_snapshot(card.task_id)
            events = store.list_events(card.task_id)

            self.assertEqual(summary["conflicted_tasks"], ["WS-B-P1-050"])
            self.assertEqual(summary["failed_tasks"], [])
            self.assertEqual(snapshot["status"], "running")
            self.assertIn("task_conflict_detected", [event["event_type"] for event in events])


class OrchestratorExportTests(unittest.TestCase):
    def test_orchestrator_module_exports_control_plane_orchestrator(self):
        package = load_control_plane_module("__init__")

        self.assertTrue(hasattr(package, "ControlPlaneOrchestrator"))
