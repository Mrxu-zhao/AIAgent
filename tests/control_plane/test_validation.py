import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module

models = load_control_plane_module("models")
validation_module = load_control_plane_module("validation")
builtin_module = load_control_plane_module("tools/builtin")


def make_card(task_id, dependencies=None):
    return models.TaskCard(
        task_id=task_id,
        title=f"title-{task_id}",
        goal=f"goal-{task_id}",
        scope=[".hermes/team/control_plane/validation.py"],
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
        acceptance_criteria=["validation can run"],
        status=models.TaskStatus.PLANNED,
    )


class ValidationTests(unittest.TestCase):
    def test_replicate_cards_rewrites_ids_and_dependencies_per_replica(self):
        cards = [
            make_card("TASK-1"),
            make_card("TASK-2", dependencies=["TASK-1"]),
        ]

        replicated = validation_module.replicate_cards(cards, replicas=2)

        self.assertEqual(
            [card.task_id for card in replicated],
            ["TASK-1-R01", "TASK-2-R01", "TASK-1-R02", "TASK-2-R02"],
        )
        self.assertEqual(replicated[1].dependencies, ["TASK-1-R01"])
        self.assertEqual(replicated[3].dependencies, ["TASK-1-R02"])

    def test_run_real_load_validation_reports_all_done_for_successful_batch(self):
        cards = [make_card("TASK-1"), make_card("TASK-2", dependencies=["TASK-1"])]

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        with tempfile.TemporaryDirectory() as tmp:
            payload = validation_module.run_real_load_validation(
                cards=cards,
                replicas=3,
                state_dir=Path(tmp) / "state",
                events_dir=Path(tmp) / "events",
                command_runner=lambda command: Result(),
                max_workers=2,
            )

        self.assertEqual(payload["workload"]["replicas"], 3)
        self.assertEqual(payload["workload"]["total_tasks"], 6)
        self.assertEqual(payload["summary"]["failed_tasks"], [])
        self.assertEqual(payload["summary"]["blocked_tasks"], [])
        self.assertTrue(payload["checks"]["all_tasks_done"])

    def test_run_behavior_validation_reports_blocking_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = validation_module.run_behavior_validation(Path(tmp))

        self.assertEqual(payload["dependency_blocking"]["summary"]["failed_tasks"], ["VAL-BLOCK-ROOT"])
        self.assertEqual(payload["dependency_blocking"]["summary"]["blocked_tasks"], ["VAL-BLOCK-LEAF"])
        self.assertEqual(payload["version_conflict"]["summary"]["conflicted_tasks"], ["VAL-CONFLICT-001"])
        self.assertTrue(payload["dependency_blocking"]["checks"]["blocked_dependency_recorded"])
        self.assertTrue(payload["version_conflict"]["checks"]["conflict_recorded"])

    def test_read_file_rejects_path_escape(self):
        with self.assertRaises(ValueError):
            builtin_module.read_file_handler(None, {"path": "../outside.txt"})


if __name__ == "__main__":
    unittest.main()
