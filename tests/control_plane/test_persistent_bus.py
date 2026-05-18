import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
import persistent_bus as persistent_bus_module  # noqa: E402
import protocols.handoff as handoff_module  # noqa: E402

message_bus_module = load_framework_module("message_bus")


class PersistentMessageBusTests(unittest.TestCase):
    def test_persistent_message_accepts_already_normalized_payload(self):
        message = persistent_bus_module.PersistentMessage.from_message(
            {
                "id": "msg-1",
                "type": "task_assign",
                "from_agent": "architect",
                "to_agent": "backend-1",
                "content": {"task": "implement"},
                "priority": 1,
                "timestamp": 123.0,
                "reply_to": None,
            }
        )

        self.assertEqual(message.from_agent, "architect")
        self.assertEqual(message.to_agent, "backend-1")
        self.assertEqual(message.content["task"], "implement")

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

    def test_message_bus_create_handoff_message_round_trips_through_receive(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = message_bus_module.load_control_plane_config()
            override = {
                **config.directories,
                "message_bus_dir": str(Path(tmp) / "message_bus"),
            }
            payload = handoff_module.HandoffPayload.create(
                source_backend="hermes",
                target_backend="openclaw",
                task_id="wf-1:design->implement",
                summary="handoff",
                context={"workflow_id": "wf-1"},
                source_agent="architect",
                target_agent="backend-1",
                source_step="design",
                target_step="implement",
            ).to_dict()

            with patch.object(
                message_bus_module,
                "load_control_plane_config",
                return_value=type(
                    "Config",
                    (),
                    {
                        **config.to_dict(),
                        "directories": override,
                    },
                )(),
            ):
                bus = message_bus_module.MessageBus()
                bus.register_agent("architect")
                bus.register_agent("backend-1")

                msg = bus.create_handoff_message(
                    "architect",
                    "backend-1",
                    payload["task_id"],
                    payload,
                )
                bus.send(msg)
                received = bus.receive("backend-1")

            self.assertEqual(received.type, message_bus_module.MessageType.HANDOFF)
            self.assertEqual(received.from_agent, "architect")
            self.assertEqual(received.to_agent, "backend-1")
            self.assertEqual(received.content["task_id"], payload["task_id"])
            self.assertEqual(received.content["context"], payload)

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

    def test_receive_and_requeue_return_falsey_results_when_message_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = persistent_bus_module.PersistentMessageBus(base_dir=Path(tmp))
            bus.register_agent("backend-1")

            self.assertIsNone(bus.receive("backend-1"))
            self.assertFalse(bus.requeue("backend-1", "missing"))

    def test_send_swallow_metrics_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = persistent_bus_module.PersistentMessageBus(base_dir=Path(tmp))
            bus.register_agent("backend-1")
            msg = message_bus_module.Message.create(
                message_bus_module.MessageType.TASK_ASSIGN,
                "architect",
                "backend-1",
                {"task": "keep going"},
            )

            with patch("observability.metrics.get_metrics_registry", side_effect=RuntimeError("boom")):
                self.assertTrue(bus.send(msg))

    def test_multiple_bus_instances_merge_registered_agents_in_shared_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = persistent_bus_module.PersistentMessageBus(base_dir=root)
            second = persistent_bus_module.PersistentMessageBus(base_dir=root)

            first.register_agent("architect")
            second.register_agent("backend-1")

            third = persistent_bus_module.PersistentMessageBus(base_dir=root)
            stats = third.stats()

        self.assertIn("architect", stats["pending_counts"])
        self.assertIn("backend-1", stats["pending_counts"])


if __name__ == "__main__":
    unittest.main()
