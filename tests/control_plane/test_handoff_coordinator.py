import unittest

from tests.control_plane.test_support import FRAMEWORK_DIR, load_framework_module

message_bus_module = load_framework_module("message_bus")


class HandoffCoordinatorTests(unittest.TestCase):
    def test_handoff_coordinator_consumes_and_acks_valid_handoff(self):
        received = []
        framework_file = FRAMEWORK_DIR / "handoff_coordinator.py"

        self.assertTrue(framework_file.exists(), "handoff_coordinator.py should exist")

        coordinator_module = load_framework_module("handoff_coordinator")

        class FakeBus:
            def __init__(self):
                self.messages = [
                    type(
                        "Msg",
                        (),
                        {
                            "id": "msg-1",
                            "type": message_bus_module.MessageType.HANDOFF,
                            "from_agent": "architect",
                            "to_agent": "backend-1",
                            "content": {
                                "task_id": "wf-1:design->implement",
                                "context": {
                                    "source_agent": "architect",
                                    "target_agent": "backend-1",
                                    "source_step": "design",
                                    "target_step": "implement",
                                    "summary": "handoff",
                                    "task_id": "wf-1:design->implement",
                                    "source_backend": "hermes",
                                    "target_backend": "openclaw",
                                    "created_at": 123.0,
                                    "context": {"workflow_id": "wf-1"},
                                },
                            },
                        },
                    )()
                ]

            def receive(self, agent_id, timeout=0.1):
                return self.messages.pop(0) if self.messages else None

            def ack(self, agent_id, message_id):
                received.append((agent_id, message_id))
                return True

        coordinator = coordinator_module.HandoffCoordinator(FakeBus())
        result = coordinator.consume_for("backend-1")

        self.assertEqual(result["status"], "acked")
        self.assertEqual(received, [("backend-1", "msg-1")])
        self.assertEqual(coordinator.get_records("wf-1:design->implement"), [result])

    def test_handoff_coordinator_marks_failed_for_invalid_payload(self):
        framework_file = FRAMEWORK_DIR / "handoff_coordinator.py"

        self.assertTrue(framework_file.exists(), "handoff_coordinator.py should exist")

        coordinator_module = load_framework_module("handoff_coordinator")
        nacked = []

        class FakeBus:
            def receive(self, agent_id, timeout=0.1):
                return type(
                    "Msg",
                    (),
                    {
                        "id": "msg-2",
                        "type": message_bus_module.MessageType.HANDOFF,
                        "from_agent": "architect",
                        "to_agent": "backend-1",
                        "content": {
                            "task_id": "wf-1:design->implement",
                            "context": {"broken": True},
                        },
                    },
                )()

            def ack(self, agent_id, message_id):
                raise AssertionError("ack should not be called for invalid payload")

            def nack(self, agent_id, message_id):
                nacked.append((agent_id, message_id))
                return True

        coordinator = coordinator_module.HandoffCoordinator(FakeBus())
        result = coordinator.consume_for("backend-1")

        self.assertEqual(result["status"], "failed")
        self.assertIn("invalid handoff payload", result["error"])
        self.assertEqual(nacked, [("backend-1", "msg-2")])
        self.assertEqual(coordinator.get_records(""), [result])

    def test_handoff_coordinator_returns_none_when_no_message(self):
        framework_file = FRAMEWORK_DIR / "handoff_coordinator.py"

        self.assertTrue(framework_file.exists(), "handoff_coordinator.py should exist")

        coordinator_module = load_framework_module("handoff_coordinator")

        class FakeBus:
            def receive(self, agent_id, timeout=0.1):
                return None

        coordinator = coordinator_module.HandoffCoordinator(FakeBus())

        self.assertIsNone(coordinator.consume_for("backend-1"))
        self.assertEqual(coordinator.get_records(), [])


if __name__ == "__main__":
    unittest.main()
