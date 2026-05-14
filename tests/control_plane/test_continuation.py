import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module


class ContinuationTests(unittest.TestCase):
    def test_resume_workflow_reconstructs_pending_steps_from_snapshot_and_events(self):
        continuation_module = load_control_plane_module("continuation")
        workflow_runtime_module = load_control_plane_module("workflow_runtime")

        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-1", {"name": "demo"})
            store.record_step_event("wf-1", "design", "completed", {"summary": "done"})
            store.record_step_event("wf-1", "implement", "pending", {})

            state = continuation_module.resume_workflow("wf-1", runtime_store=store)

        self.assertEqual(state["workflow_id"], "wf-1")
        self.assertEqual(state["snapshot"]["status"], "running")
        self.assertEqual(state["completed_steps"], ["design"])
        self.assertEqual(state["ready_steps"], ["implement"])

    def test_resume_workflow_reports_failed_steps_without_marking_them_ready(self):
        continuation_module = load_control_plane_module("continuation")
        workflow_runtime_module = load_control_plane_module("workflow_runtime")

        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-2", {"name": "demo"})
            store.record_step_event("wf-2", "design", "completed", {"summary": "done"})
            store.record_step_event("wf-2", "implement", "failed", {"error": "boom"})
            store.record_step_event("wf-2", "implement", "pending", {})

            state = continuation_module.resume_workflow("wf-2", runtime_store=store)

        self.assertEqual(state["completed_steps"], ["design"])
        self.assertEqual(state["failed_steps"], ["implement"])
        self.assertEqual(state["ready_steps"], [])


if __name__ == "__main__":
    unittest.main()
