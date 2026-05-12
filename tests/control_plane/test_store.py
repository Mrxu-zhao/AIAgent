import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module


models = load_control_plane_module("models")
store_module = load_control_plane_module("store")


class TaskStoreTests(unittest.TestCase):
    def test_append_event_updates_snapshot_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            card = models.TaskCard(
                task_id="WS-B-P1-001",
                title="Define protocol",
                goal="Persist task events",
                scope=[".hermes/team/control_plane/models.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["spec"],
                outputs=["models diff"],
                dependencies=[],
                owner_agent="backend-2",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="state"),
                acceptance_criteria=["state snapshot is written"],
            )
            store.register_task(card)
            event = models.TaskEvent(
                event_id="evt-001",
                task_id=card.task_id,
                event_type=models.EventType.TASK_STARTED,
                agent_id="backend-2",
                timestamp=1.0,
                attempt=1,
                status_before=models.TaskStatus.READY,
                status_after=models.TaskStatus.RUNNING,
                summary="start",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            )
            store.append_event(event)
            snapshot = store.read_snapshot(card.task_id)

            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(snapshot["version"], 2)

    def test_list_events_reads_back_event_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            card = models.TaskCard(
                task_id="WS-B-P1-002",
                title="Store events",
                goal="Read event history",
                scope=[".hermes/team/control_plane/store.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["spec"],
                outputs=["event log"],
                dependencies=[],
                owner_agent="backend-2",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="state"),
                acceptance_criteria=["event history can be queried"],
            )
            store.register_task(card)
            event = models.TaskEvent(
                event_id="evt-002",
                task_id=card.task_id,
                event_type=models.EventType.TASK_COMPLETED,
                agent_id="backend-2",
                timestamp=2.0,
                attempt=1,
                status_before=models.TaskStatus.RUNNING,
                status_after=models.TaskStatus.DONE,
                summary="done",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            )
            store.append_event(event)

            events = store.list_events(card.task_id)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_id"], "evt-002")

    def test_append_event_rejects_stale_snapshot_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            card = models.TaskCard(
                task_id="WS-B-P1-003",
                title="Reject stale writes",
                goal="Protect snapshot version",
                scope=[".hermes/team/control_plane/store.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["spec"],
                outputs=["conflict"],
                dependencies=[],
                owner_agent="backend-2",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="state"),
                acceptance_criteria=["stale writes are rejected"],
            )
            store.register_task(card)
            first_event = models.TaskEvent(
                event_id="evt-003",
                task_id=card.task_id,
                event_type=models.EventType.TASK_STARTED,
                agent_id="backend-2",
                timestamp=3.0,
                attempt=1,
                status_before=models.TaskStatus.READY,
                status_after=models.TaskStatus.RUNNING,
                summary="start",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            )
            store.append_event(first_event, expected_version=1)

            stale_event = models.TaskEvent(
                event_id="evt-004",
                task_id=card.task_id,
                event_type=models.EventType.TASK_COMPLETED,
                agent_id="backend-2",
                timestamp=4.0,
                attempt=1,
                status_before=models.TaskStatus.RUNNING,
                status_after=models.TaskStatus.DONE,
                summary="done",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            )

            with self.assertRaises(store_module.VersionConflictError):
                store.append_event(stale_event, expected_version=1)

    def test_validate_snapshot_checks_version_and_last_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            card = models.TaskCard(
                task_id="WS-B-P1-004",
                title="Validate snapshot",
                goal="Check snapshot guardrails",
                scope=[".hermes/team/control_plane/store.py"],
                lock_scope=models.LockScope(files=[], modules=["control_plane"], contracts=[]),
                inputs=["spec"],
                outputs=["snapshot validation"],
                dependencies=[],
                owner_agent="backend-2",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1200,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="state"),
                acceptance_criteria=["snapshot can be validated"],
            )
            store.register_task(card)
            event = models.TaskEvent(
                event_id="evt-005",
                task_id=card.task_id,
                event_type=models.EventType.TASK_STARTED,
                agent_id="backend-2",
                timestamp=5.0,
                attempt=1,
                status_before=models.TaskStatus.READY,
                status_after=models.TaskStatus.RUNNING,
                summary="start",
                artifact_refs=[],
                lock_scope={"files": [], "modules": ["control_plane"], "contracts": []},
                depends_on=[],
                metrics_delta={},
                error_code=None,
            )
            store.append_event(event)

            validated = store.validate_snapshot(
                card.task_id,
                expected_version=2,
                expected_last_event_id="evt-005",
            )

            self.assertEqual(validated["status"], "running")

            with self.assertRaises(store_module.SnapshotValidationError):
                store.validate_snapshot(card.task_id, expected_version=1)

            with self.assertRaises(store_module.SnapshotValidationError):
                store.validate_snapshot(card.task_id, expected_last_event_id="evt-mismatch")


if __name__ == "__main__":
    unittest.main()

