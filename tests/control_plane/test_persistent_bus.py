import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
import persistent_bus as persistent_bus_module  # noqa: E402

message_bus_module = load_framework_module("message_bus")


class PersistentMessageBusTests(unittest.TestCase):
    def test_send_receive_and_ack_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = persistent_bus_module.PersistentMessageBus(base_dir=Path(tmp))
            bus.register_agent("backend-1")
            msg = message_bus_module.Message.create(
                message_bus_module.MessageType.TASK_ASSIGN,
                "architect",
                "backend-1",
                {"task": "implement login"},
            )

            self.assertTrue(bus.send(msg))
            received = bus.receive("backend-1")

            self.assertEqual(received.id, msg.id)
            self.assertTrue(bus.ack("backend-1", msg.id))
            self.assertEqual(bus.list_unacked("backend-1"), [])

    def test_persistent_bus_restores_messages_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = persistent_bus_module.PersistentMessageBus(base_dir=root)
            first.register_agent("backend-1")
            msg = message_bus_module.Message.create(
                message_bus_module.MessageType.TASK_ASSIGN,
                "architect",
                "backend-1",
                {"task": "restore me"},
            )
            first.send(msg)

            second = persistent_bus_module.PersistentMessageBus(base_dir=root)
            second.register_agent("backend-1")
            restored = second.receive("backend-1")

            self.assertEqual(restored.content["task"], "restore me")

    def test_framework_message_bus_exposes_ack_when_persistent_enabled(self):
        bus = message_bus_module.MessageBus()
        self.assertTrue(hasattr(bus, "ack"))

    def test_group_broadcast_requeue_unregister_and_stats_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = persistent_bus_module.PersistentMessageBus(base_dir=Path(tmp))
            bus.register_agent("architect")
            bus.register_agent("backend-1")
            bus.register_agent("backend-2")

            group_msg = message_bus_module.Message.create(
                message_bus_module.MessageType.COLLAB_REQUEST,
                "architect",
                "backend",
                {"task": "pair review"},
            )
            bus.send(group_msg)
            first = bus.receive("backend-1")

            self.assertEqual(first.content["task"], "pair review")
            self.assertTrue(bus.nack("backend-1", first.id))
            self.assertEqual(bus.get_pending_count("backend-1"), 1)

            replayed = bus.receive("backend-1")
            self.assertEqual(replayed.id, first.id)
            self.assertFalse(bus.ack("backend-1", "missing"))
            self.assertTrue(bus.ack("backend-1", replayed.id))

            broadcast = message_bus_module.Message.create(
                message_bus_module.MessageType.BROADCAST,
                "architect",
                None,
                {"message": "sync"},
            )
            bus.send(broadcast)

            stats = bus.stats()
            history = bus.get_history(limit=1)
            bus.unregister_agent("backend-2")

            self.assertEqual(history[0]["content"]["message"], "sync")
            self.assertEqual(stats["registered_agents"], 4)
            self.assertIn("backend", stats["groups"])
            self.assertEqual(bus.stats()["registered_agents"], 3)


if __name__ == "__main__":
    unittest.main()
