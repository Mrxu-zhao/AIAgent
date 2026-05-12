import unittest

from tests.control_plane.test_support import load_framework_module


workflow_module = load_framework_module("workflow_engine")
router_module = load_framework_module("task_router")


class WorkflowRegressionTests(unittest.TestCase):
    def test_step_agent_overrides_auto_routing(self):
        router = router_module.TaskRouter()
        engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None)
        step = workflow_module.WorkflowStep(
            id="database",
            name="Database design",
            type=workflow_module.StepType.SEQUENTIAL,
            agent="dba",
            task_template="Design database schema",
        )

        result = engine._execute_agent_task(step, "Design database schema")

        self.assertEqual(result["agent"], "dba")


if __name__ == "__main__":
    unittest.main()

