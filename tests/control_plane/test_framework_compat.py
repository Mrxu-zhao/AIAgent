import unittest

from tests.control_plane.test_support import load_framework_module


message_bus_module = load_framework_module("message_bus")
monitor_module = load_framework_module("monitor")
task_router_module = load_framework_module("task_router")


class FrameworkCompatTests(unittest.TestCase):
    def test_message_bus_stats_exposes_registered_agents_and_history_counts(self):
        bus = message_bus_module.MessageBus()
        bus.register_agent("architect")
        bus.register_agent("backend-1")
        bus.send(
            message_bus_module.Message.create(
                message_bus_module.MessageType.BROADCAST,
                "architect",
                None,
                {"message": "hello"},
            )
        )

        stats = bus.stats()

        self.assertEqual(stats["registered_agents"], 2)
        self.assertEqual(stats["history_size"], 1)
        self.assertEqual(stats["pending_counts"]["backend-1"], 1)

    def test_monitor_agents_returns_router_agents_when_bound(self):
        router = task_router_module.TaskRouter()
        monitor = monitor_module.Monitor(task_router=router)

        self.assertIs(monitor.agents, router.agents)
        self.assertIn("architect", monitor.agents)


if __name__ == "__main__":
    unittest.main()
