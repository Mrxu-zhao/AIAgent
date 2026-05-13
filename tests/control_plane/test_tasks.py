import unittest

from tests.control_plane.test_support import load_control_plane_module

tasks_module = load_control_plane_module("tasks")


class TaskRegistryTests(unittest.TestCase):
    def test_registry_contains_framework_p0_task(self):
        ids = [task.task_id for task in tasks_module.TASKS]

        self.assertIn("WS-A-P0-001", ids)

    def test_registry_contains_hermes_execution_task(self):
        registry = {task.task_id: task for task in tasks_module.TASKS}

        self.assertEqual(registry["WS-B-P1-005"].owner_agent, "backend-2")


if __name__ == "__main__":
    unittest.main()

