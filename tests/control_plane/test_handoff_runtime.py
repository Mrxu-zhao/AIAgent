import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module


class HandoffRunStoreTests(unittest.TestCase):
    def test_handoff_run_store_records_and_filters_records(self):
        runtime_module = load_control_plane_module("handoff_runtime")

        with tempfile.TemporaryDirectory() as tmp:
            store = runtime_module.HandoffRunStore(Path(tmp))
            store.record_handoff(
                {
                    "message_id": "msg-1",
                    "workflow_id": "wf-1",
                    "target_agent": "backend-1",
                    "status": "materialized",
                }
            )
            store.record_handoff(
                {
                    "message_id": "msg-2",
                    "workflow_id": "wf-1",
                    "target_agent": "qa",
                    "status": "failed",
                }
            )

            self.assertEqual(store.read_record("msg-1")["status"], "materialized")
            self.assertEqual(len(store.list_records(workflow_id="wf-1")), 2)
            self.assertEqual(len(store.list_records(target_agent="backend-1")), 1)
            self.assertEqual(len(store.list_records(status="failed")), 1)

    def test_handoff_run_store_supports_composed_filters_and_stable_order(self):
        runtime_module = load_control_plane_module("handoff_runtime")

        with tempfile.TemporaryDirectory() as tmp:
            store = runtime_module.HandoffRunStore(Path(tmp))
            store.record_handoff(
                {
                    "message_id": "msg-2",
                    "workflow_id": "wf-1",
                    "target_agent": "backend-1",
                    "status": "materialized",
                }
            )
            store.record_handoff(
                {
                    "message_id": "msg-1",
                    "workflow_id": "wf-1",
                    "target_agent": "backend-1",
                    "status": "materialized",
                }
            )
            store.record_handoff(
                {
                    "message_id": "msg-3",
                    "workflow_id": "wf-2",
                    "target_agent": "backend-1",
                    "status": "failed",
                }
            )

            records = store.list_records(
                workflow_id="wf-1",
                target_agent="backend-1",
                status="materialized",
            )

            self.assertEqual([record["message_id"] for record in records], ["msg-1", "msg-2"])


if __name__ == "__main__":
    unittest.main()
