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

    def test_evaluate_condition_supports_boolean_expressions_with_placeholders(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None)

        result = engine._evaluate_condition(
            "{approved} and {score} >= 80 and not {blocked}",
            {"approved": True, "score": 95, "blocked": False},
        )

        self.assertTrue(result)

    def test_evaluate_condition_rejects_attribute_access(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None)

        result = engine._evaluate_condition("({score}).__class__", {"score": 95})

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()

