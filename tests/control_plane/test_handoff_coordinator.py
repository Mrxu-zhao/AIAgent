import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import (
    FRAMEWORK_DIR,
    load_control_plane_module,
    load_framework_module,
)

message_bus_module = load_framework_module("message_bus")


def valid_handoff_message(message_id="msg-1"):
    return type(
        "Msg",
        (),
        {
            "id": message_id,
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
                    "selected_backend": "openclaw",
                    "created_at": 123.0,
                    "context": {"workflow_id": "wf-1"},
                },
            },
        },
    )()


class FakeBus:
    def __init__(self, *messages):
        self.messages = list(messages)

    def receive(self, agent_id, timeout=0.1):
        return self.messages.pop(0) if self.messages else None

    def ack(self, agent_id, message_id):
        return True

    def nack(self, agent_id, message_id):
        return True


class HandoffCoordinatorTests(unittest.TestCase):
    def test_handoff_coordinator_materializes_valid_handoff_into_task_card(self):
        framework_file = FRAMEWORK_DIR / "handoff_coordinator.py"
        self.assertTrue(framework_file.exists(), "handoff_coordinator.py should exist")

        coordinator_module = load_framework_module("handoff_coordinator")
        store_module = load_control_plane_module("store")

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
                return True

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")

            coordinator = coordinator_module.HandoffCoordinator(
                FakeBus(),
                task_store=store,
            )
            result = coordinator.consume_for("backend-1")
            snapshot = store.read_snapshot("handoff-wf-1-design-implement")

        self.assertEqual(result["status"], "materialized")
        self.assertEqual(result["materialized_task_id"], "handoff-wf-1-design-implement")
        self.assertEqual(snapshot["owner_agent"], "backend-1")
        self.assertEqual(snapshot["executor_backend"], "openclaw")

    def test_handoff_coordinator_reuses_existing_materialized_task_for_duplicate_message(self):
        coordinator_module = load_framework_module("handoff_coordinator")
        store_module = load_control_plane_module("store")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            bus = FakeBus(valid_handoff_message())
            coordinator = coordinator_module.HandoffCoordinator(bus, task_store=store)

            first = coordinator.consume_for("backend-1")
            bus.messages = [valid_handoff_message()]
            second = coordinator.consume_for("backend-1")

            self.assertEqual(first["materialized_task_id"], second["materialized_task_id"])
            self.assertEqual(len(store.list_events(first["materialized_task_id"])), 0)
            self.assertEqual(len(coordinator.get_records("wf-1:design->implement")), 1)

    def test_handoff_coordinator_records_workflow_and_backend_metadata(self):
        coordinator_module = load_framework_module("handoff_coordinator")
        store_module = load_control_plane_module("store")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            coordinator = coordinator_module.HandoffCoordinator(
                FakeBus(valid_handoff_message()),
                task_store=store,
            )

            result = coordinator.consume_for("backend-1")

        self.assertEqual(result["workflow_id"], "wf-1")
        self.assertEqual(result["source_backend"], "hermes")
        self.assertEqual(result["target_backend"], "openclaw")
        self.assertEqual(result["selected_backend"], "openclaw")

    def test_handoff_coordinator_persists_materialized_record_and_runtime_event(self):
        coordinator_module = load_framework_module("handoff_coordinator")
        runtime_module = load_control_plane_module("handoff_runtime")
        workflow_runtime_module = load_control_plane_module("workflow_runtime")
        store_module = load_control_plane_module("store")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            task_store = store_module.TaskStore(base / "state", base / "events")
            handoff_store = runtime_module.HandoffRunStore(base / "handoffs")
            workflow_store = workflow_runtime_module.WorkflowRunStore(base / "workflows")
            coordinator = coordinator_module.HandoffCoordinator(
                FakeBus(valid_handoff_message()),
                task_store=task_store,
                handoff_store=handoff_store,
                runtime_store=workflow_store,
            )

            result = coordinator.consume_for("backend-1")
            persisted = handoff_store.read_record("msg-1")
            events = workflow_store.list_step_events("wf-1")

        self.assertEqual(persisted["materialized_task_id"], result["materialized_task_id"])
        self.assertTrue(any(event["event"] == "handoff_materialized" for event in events))

    def test_handoff_coordinator_dispatches_materialized_task_once(self):
        coordinator_module = load_framework_module("handoff_coordinator")
        store_module = load_control_plane_module("store")
        dispatched = []

        class FakeDispatcher:
            def execute_task(self, card, adapter, command_runner):
                dispatched.append(
                    {
                        "task_id": card.task_id,
                        "owner_agent": card.owner_agent,
                        "executor_backend": card.executor_backend,
                    }
                )
                return {
                    "success": True,
                    "command": ["openclaw", "dispatch"],
                    "stdout": "ok",
                    "stderr": "",
                }

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            bus = FakeBus(valid_handoff_message())
            coordinator = coordinator_module.HandoffCoordinator(
                bus,
                task_store=store,
                dispatcher=FakeDispatcher(),
                adapter=object(),
                command_runner=lambda command: None,
            )

            first = coordinator.consume_for("backend-1")
            bus.messages = [valid_handoff_message()]
            second = coordinator.consume_for("backend-1")

        self.assertEqual(first["status"], "dispatched")
        self.assertIsNotNone(first["dispatched_at"])
        self.assertEqual(second["status"], "dispatched")
        self.assertEqual(first["materialized_task_id"], second["materialized_task_id"])
        self.assertEqual(first["dispatched_at"], second["dispatched_at"])
        self.assertEqual(
            dispatched,
            [
                {
                    "task_id": "handoff-wf-1-design-implement",
                    "owner_agent": "backend-1",
                    "executor_backend": "openclaw",
                }
            ],
        )

    def test_handoff_dispatch_can_trigger_workflow_resume(self):
        coordinator_module = load_framework_module("handoff_coordinator")
        workflow_runtime_module = load_control_plane_module("workflow_runtime")
        store_module = load_control_plane_module("store")

        class FakeDispatcher:
            def execute_task(self, card, adapter, command_runner):
                return {
                    "success": True,
                    "command": ["openclaw", "dispatch"],
                    "stdout": "ok",
                    "stderr": "",
                }

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            workflow_store = workflow_runtime_module.WorkflowRunStore(base / "workflows")
            workflow_store.record_workflow_started("wf-1", {"name": "demo"})
            workflow_store.record_step_event("wf-1", "design", "completed", {"summary": "done"})
            bus = FakeBus(valid_handoff_message())
            coordinator = coordinator_module.HandoffCoordinator(
                bus,
                task_store=store,
                runtime_store=workflow_store,
                dispatcher=FakeDispatcher(),
                adapter=object(),
                command_runner=lambda command: None,
            )

            result = coordinator.consume_for("backend-1")

        self.assertEqual(result["continuation_workflow_id"], "wf-1")
        self.assertEqual(result["continuation_status"], "continued")
        self.assertIsNotNone(result["continued_at"])
        self.assertEqual(result["continuation_ready_steps"], ["implement"])
        self.assertEqual(result["continuation_completed_steps"], ["design"])
        self.assertEqual(result["continuation_failed_steps"], [])

    def test_continuation_failure_falls_back_to_dispatched_state(self):
        coordinator_module = load_framework_module("handoff_coordinator")
        store_module = load_control_plane_module("store")

        class FakeDispatcher:
            def execute_task(self, card, adapter, command_runner):
                return {
                    "success": True,
                    "command": ["openclaw", "dispatch"],
                    "stdout": "ok",
                    "stderr": "",
                }

        class BrokenRuntimeStore:
            def __init__(self):
                self.workflow_events = []

            def read_snapshot(self, workflow_id):
                raise RuntimeError(f"resume failed for {workflow_id}")

            def list_step_events(self, workflow_id):
                del workflow_id
                return []

            def record_step_event(self, workflow_id, step_id, status, payload):
                del workflow_id, step_id, status, payload

            def record_workflow_event(self, workflow_id, status, payload):
                self.workflow_events.append(
                    {
                        "workflow_id": workflow_id,
                        "status": status,
                        "payload": payload,
                    }
                )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            runtime_store = BrokenRuntimeStore()
            coordinator = coordinator_module.HandoffCoordinator(
                FakeBus(valid_handoff_message()),
                task_store=store,
                runtime_store=runtime_store,
                dispatcher=FakeDispatcher(),
                adapter=object(),
                command_runner=lambda command: None,
            )

            result = coordinator.consume_for("backend-1")

        self.assertEqual(result["status"], "dispatched")
        self.assertEqual(result["continuation_workflow_id"], "wf-1")
        self.assertEqual(result["continuation_status"], "failed")
        self.assertEqual(result["continuation_ready_steps"], [])
        self.assertEqual(result["continuation_completed_steps"], [])
        self.assertEqual(result["continuation_failed_steps"], [])
        self.assertIsNotNone(result["dispatched_at"])
        self.assertIn("resume failed for wf-1", result["error"])
        self.assertEqual(
            runtime_store.workflow_events,
            [
                {
                    "workflow_id": "wf-1",
                    "status": "workflow_resume_failed",
                    "payload": {
                        "message_id": "msg-1",
                        "target_step": "implement",
                        "error": "resume failed for wf-1",
                    },
                }
            ],
        )

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
