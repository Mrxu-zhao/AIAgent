import unittest

from tests.control_plane.test_support import load_control_plane_module

models = load_control_plane_module("models")


class TaskModelTests(unittest.TestCase):
    def test_task_card_requires_unique_identity_fields(self):
        card = models.TaskCard(
            task_id="WS-A-P0-001",
            title="Fix monitor deadlock",
            goal="Ensure dashboard calls return",
            scope=[".hermes/team/\u8c03\u5ea6\u6846\u67b6/core/monitor.py"],
            lock_scope=models.LockScope(
                files=[".hermes/team/\u8c03\u5ea6\u6846\u67b6/core/monitor.py"],
                modules=["monitor"],
                contracts=[],
            ),
            inputs=["assessment_report_2026-05-12.md"],
            outputs=["monitor fix diff"],
            dependencies=[],
            owner_agent="backend-1",
            review_agent="architect",
            priority=models.TaskPriority.P0,
            timeout_seconds=1800,
            retry_policy=models.RetryPolicy(max_attempts=2, backoff_seconds=[0, 60]),
            rollback_policy=models.RollbackPolicy(mode="code"),
            acceptance_criteria=["dashboard call returns"],
        )

        self.assertEqual(card.task_id, "WS-A-P0-001")
        self.assertEqual(card.status, models.TaskStatus.PLANNED)
        self.assertEqual(card.priority.value, "P0")

    def test_task_event_captures_state_transition(self):
        event = models.TaskEvent(
            event_id="evt-001",
            task_id="WS-B-P1-001",
            event_type=models.EventType.TASK_STARTED,
            agent_id="backend-2",
            timestamp=1710000000.0,
            attempt=1,
            status_before=models.TaskStatus.READY,
            status_after=models.TaskStatus.RUNNING,
            summary="start protocol modeling",
            artifact_refs=[],
            lock_scope={"files": [], "modules": [], "contracts": []},
            depends_on=[],
            metrics_delta={},
            error_code=None,
        )

        self.assertEqual(event.status_after, models.TaskStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()

