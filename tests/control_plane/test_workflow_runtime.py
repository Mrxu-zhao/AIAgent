import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
import workflow_runtime as workflow_runtime_module  # noqa: E402

workflow_module = load_framework_module("workflow_engine")
router_module = load_framework_module("task_router")


class WorkflowRuntimeTests(unittest.TestCase):
    def test_workflow_run_store_persists_snapshot_and_step_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-1", {"name": "demo"})
            store.record_step_event("wf-1", "step-1", "running", {"agent": "architect"})

            snapshot = store.read_snapshot("wf-1")
            events = store.list_step_events("wf-1")

            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(events[0]["step_id"], "step-1")

    def test_workflow_engine_writes_runtime_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            router = router_module.TaskRouter()
            engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None, runtime_store=runtime)
            workflow = engine.create_workflow(
                "wf-runtime",
                "runtime",
                "demo",
                [{"id": "requirements", "name": "需求", "type": "sequential", "agent": "requirements-analyst", "task": "分析需求"}],
            )

            result = engine.execute_workflow(workflow.id)
            snapshot = runtime.read_snapshot(workflow.id)

            self.assertTrue(result["success"])
            self.assertEqual(snapshot["status"], "completed")


if __name__ == "__main__":
    unittest.main()
