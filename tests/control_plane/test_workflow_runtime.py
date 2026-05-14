import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
import config as config_module  # noqa: E402
import protocols.handoff as handoff_module  # noqa: E402
import workflow_runtime as workflow_runtime_module  # noqa: E402

message_bus_module = load_framework_module("message_bus")
workflow_module = load_framework_module("workflow_engine")
router_module = load_framework_module("task_router")


class WorkflowRuntimeTests(unittest.TestCase):
    def setUp(self):
        config_module.load_control_plane_config.cache_clear()

    def test_default_runtime_directories_use_runs_subtree(self):
        config = config_module.load_control_plane_config()

        self.assertIn(
            "state/runs/workflow_runtime",
            config.directories["workflow_runtime_dir"].replace("\\", "/"),
        )

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

    def test_workflow_engine_returns_step_contexts_and_handoffs(self):
        router = router_module.TaskRouter()
        engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-handoff",
            "handoff",
            "demo",
            [
                {
                    "id": "design",
                    "name": "设计",
                    "type": "sequential",
                    "agent": "architect",
                    "task": "产出接口 spec",
                },
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "根据 {design_summary} 完成代码",
                },
            ],
        )

        result = engine.execute_workflow(workflow.id)

        self.assertTrue(result["success"])
        self.assertIn("step_contexts", result)
        self.assertIn("design", result["step_contexts"])
        self.assertEqual(result["step_contexts"]["design"]["agent"], "architect")
        self.assertEqual(len(result["handoffs"]), 1)
        self.assertEqual(result["handoffs"][0]["source_step"], "design")
        self.assertEqual(result["handoffs"][0]["target_step"], "implement")

    def test_workflow_engine_threads_knowledge_recommendation_from_router(self):
        router = router_module.TaskRouter()
        engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-knowledge-pack",
            "knowledge-pack",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现接口并补测试",
                },
            ],
        )

        result = engine.execute_workflow(workflow.id)

        self.assertTrue(result["success"])
        self.assertIn("knowledge_recommendations", result)
        self.assertIn("implement", result["knowledge_recommendations"])
        knowledge = result["step_contexts"]["implement"]["knowledge_recommendation"]
        self.assertEqual(knowledge["load_order"], ["team", "role", "instance"])
        self.assertIn(".hermes/team/knowledge/status.md", knowledge["team"])
        self.assertIn(".hermes/agents/backend-dev/knowledge/status.md", knowledge["role"])
        self.assertIn(".hermes/team/agents/backend-1/knowledge/expertise.md", knowledge["instance"])

    def test_workflow_engine_accumulates_collaboration_context(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-collab",
            "collab",
            "demo",
            [
                {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                {
                    "id": "review",
                    "name": "评审",
                    "type": "sequential",
                    "agent": "qa-functional",
                    "task": "评审 {design_summary}",
                    "dependencies": ["design"],
                },
            ],
        )

        engine._execute_agent_task = lambda step, task_content: {
            "success": True,
            "output": f"{step.id}:{task_content}",
            "agent": step.agent,
            "artifacts": [f"{step.id}.md"],
            "open_questions": [f"{step.id}-q"],
            "risks": [f"{step.id}-risk"],
            "decisions": [{"summary": f"{step.id}-decision"}],
        }
        result = engine.execute_workflow(workflow.id)

        self.assertIn("collaboration_context", result)
        self.assertEqual(result["collaboration_context"]["artifacts"], ["design.md", "review.md"])
        self.assertEqual(len(result["collaboration_context"]["decisions"]), 2)

    def test_workflow_engine_compresses_decision_summaries(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-decision-summary",
            "decision-summary",
            "demo",
            [
                {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                {
                    "id": "review",
                    "name": "评审",
                    "type": "sequential",
                    "agent": "qa-functional",
                    "task": "评审 {design_summary}",
                    "dependencies": ["design"],
                },
            ],
        )

        engine._execute_agent_task = lambda step, task_content: {
            "success": True,
            "output": f"{step.id}:{task_content}",
            "agent": step.agent,
            "decisions": [
                {
                    "summary": f"{step.id}-decision",
                    "rationale": "因为需要统一执行口径",
                    "impact": "影响后续实现与验收",
                    "next_action": "同步到 handoff",
                }
            ],
        }
        result = engine.execute_workflow(workflow.id)
        decision = result["collaboration_context"]["decisions"][0]

        self.assertEqual(
            decision["decision_summary"],
            "[design] design-decision | rationale: 因为需要统一执行口径 | impact: 影响后续实现与验收 | next: 同步到 handoff",
        )
        self.assertNotIn("rationale", decision)
        self.assertNotIn("impact", decision)
        self.assertNotIn("next_action", decision)

    def test_workflow_handoff_contains_backend_reason(self):
        fake_registry = type(
            "Registry",
            (),
            {
                "list_providers": lambda self: ["hermes", "openclaw"],
                "get": lambda self, name: type(
                    "Provider",
                    (),
                    {"name": name, "dry_run": name == "openclaw"},
                )(),
            },
        )()

        with patch.object(workflow_module, "build_default_provider_registry", return_value=fake_registry):
            engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
            workflow = engine.create_workflow(
                "wf-backend",
                "backend",
                "demo",
                [
                    {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                    {
                        "id": "implement",
                        "name": "实现",
                        "type": "sequential",
                        "agent": "backend-1",
                        "task": "实现代码",
                        "dependencies": ["design"],
                    },
                ],
            )

            def fake_execute(step, task_content):
                result = {"success": True, "output": f"{step.id}:{task_content}", "agent": step.agent}
                if step.id == "design":
                    result["backend_recommendation"] = {
                        "selected_backend": "openclaw",
                        "backend_candidates": ["hermes", "openclaw"],
                        "backend_reason": "needs external execution",
                    }
                return result

            engine._execute_agent_task = fake_execute
            result = engine.execute_workflow(workflow.id)

        self.assertEqual(result["handoffs"][0]["selected_backend"], "openclaw")
        self.assertEqual(result["handoffs"][0]["target_backend"], "openclaw")
        self.assertEqual(result["handoffs"][0]["backend_candidates"], ["hermes", "openclaw"])
        self.assertIn("needs external execution", result["handoffs"][0]["backend_reason"])
        self.assertIn("provider=openclaw", result["handoffs"][0]["backend_reason"])
        self.assertIn("mode=dry-run", result["handoffs"][0]["backend_reason"])

    def test_workflow_handoff_tracks_real_source_backend(self):
        fake_registry = type(
            "Registry",
            (),
            {
                "list_providers": lambda self: ["hermes", "openclaw"],
                "get": lambda self, name: type(
                    "Provider",
                    (),
                    {"name": name, "dry_run": False},
                )(),
            },
        )()

        with patch.object(workflow_module, "build_default_provider_registry", return_value=fake_registry):
            engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
            engine.config.default_executor = "openclaw"
            workflow = engine.create_workflow(
                "wf-source-backend",
                "source-backend",
                "demo",
                [
                    {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                    {
                        "id": "implement",
                        "name": "实现",
                        "type": "sequential",
                        "agent": "backend-1",
                        "task": "实现代码",
                        "dependencies": ["design"],
                    },
                ],
            )

            def fake_execute(step, task_content):
                result = {"success": True, "output": f"{step.id}:{task_content}", "agent": step.agent}
                if step.id == "design":
                    result["backend_recommendation"] = {
                        "selected_backend": "hermes",
                        "backend_reason": "return to local execution",
                    }
                return result

            engine._execute_agent_task = fake_execute
            result = engine.execute_workflow(workflow.id)

        self.assertEqual(result["handoffs"][0]["source_backend"], "openclaw")
        self.assertEqual(result["handoffs"][0]["target_backend"], "hermes")

    def test_workflow_step_inherits_backend_recommendation(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-backend-inherit",
            "backend-inherit",
            "demo",
            [
                {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                    "dependencies": ["design"],
                },
            ],
        )

        def fake_execute(step, task_content):
            result = {"success": True, "output": f"{step.id}:{task_content}", "agent": step.agent}
            if step.id == "design":
                result["backend_recommendation"] = {"selected_backend": "openclaw"}
            return result

        engine._execute_agent_task = fake_execute
        result = engine.execute_workflow(workflow.id)

        self.assertEqual(
            result["step_contexts"]["design"]["backend_recommendation"]["selected_backend"],
            "openclaw",
        )
        self.assertEqual(result["step_contexts"]["implement"]["inherited_backend"], "openclaw")

    def test_workflow_emits_handoff_to_message_bus(self):
        events = []

        class FakeBus:
            def send(self, payload):
                events.append(payload)

        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=FakeBus(), runtime_store=None)
        workflow = engine.create_workflow(
            "wf-bus-handoff",
            "bus-handoff",
            "demo",
            [
                {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                    "dependencies": ["design"],
                },
            ],
        )

        engine._execute_agent_task = lambda step, task_content: {
            "success": True,
            "output": "ok",
            "agent": step.agent,
        }
        engine.execute_workflow(workflow.id)

        self.assertTrue(any(event.get("type") == "handoff" for event in events), "no handoff event")

    def test_workflow_publishes_standard_handoff_message_when_bus_supports_factory(self):
        published = {}

        class FakeBus:
            def create_handoff_message(self, from_agent, to_agent, task_id, context, priority=None):
                published["factory"] = {
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "task_id": task_id,
                    "context": context,
                    "priority": priority,
                }
                return {"kind": "handoff-message", "task_id": task_id, "context": context}

            def send(self, message):
                published["message"] = message
                return True

        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=FakeBus(), runtime_store=None)
        workflow = engine.create_workflow(
            "wf-standard-handoff",
            "standard-handoff",
            "demo",
            [
                {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                    "dependencies": ["design"],
                },
            ],
        )
        engine._execute_agent_task = lambda step, task_content: {
            "success": True,
            "output": "ok",
            "agent": step.agent,
        }

        engine.execute_workflow(workflow.id)

        self.assertEqual(published["factory"]["from_agent"], "architect")
        self.assertEqual(published["factory"]["to_agent"], "backend-1")
        self.assertEqual(published["factory"]["task_id"], "wf-standard-handoff:design->implement")
        self.assertEqual(published["message"]["kind"], "handoff-message")
        self.assertTrue(handoff_module.validate_handoff_payload(published["factory"]["context"]))

    def test_workflow_published_handoff_round_trips_through_message_bus(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = message_bus_module.load_control_plane_config()
            override = {
                **config.directories,
                "message_bus_dir": str(Path(tmp) / "message_bus"),
            }

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
                engine = workflow_module.WorkflowEngine(task_router=None, message_bus=bus, runtime_store=None)
                workflow = engine.create_workflow(
                    "wf-bus-roundtrip",
                    "bus-roundtrip",
                    "demo",
                    [
                        {"id": "design", "name": "设计", "type": "sequential", "agent": "architect", "task": "设计方案"},
                        {
                            "id": "implement",
                            "name": "实现",
                            "type": "sequential",
                            "agent": "backend-1",
                            "task": "实现代码",
                            "dependencies": ["design"],
                        },
                    ],
                )
                engine._execute_agent_task = lambda step, task_content: {
                    "success": True,
                    "output": "ok",
                    "agent": step.agent,
                }

                result = engine.execute_workflow(workflow.id)
                received = bus.receive("backend-1")

            self.assertEqual(received.type, message_bus_module.MessageType.HANDOFF)
            self.assertEqual(received.content["task_id"], result["handoffs"][0]["task_id"])
            self.assertEqual(received.content["context"], result["handoffs"][0])
            self.assertTrue(handoff_module.validate_handoff_payload(received.content["context"]))

    def test_workflow_engine_passes_upstream_agent_and_role_into_review_route(self):
        router = router_module.TaskRouter()
        engine = workflow_module.WorkflowEngine(task_router=router, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-review-routing",
            "review-routing",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现接口",
                },
                {
                    "id": "review",
                    "name": "评审",
                    "type": "sequential",
                    "agent": None,
                    "task": "请 review {implement_summary}",
                    "dependencies": ["implement"],
                },
            ],
        )
        observed = {}
        original_route_task = router.route_task

        def observing_route_task(content, priority=router_module.TaskPriority.NORMAL, **kwargs):
            if "review" in content.lower():
                observed.update(kwargs)
            return original_route_task(content, priority=priority, **kwargs)

        router.route_task = observing_route_task

        result = engine.execute_workflow(workflow.id)

        self.assertTrue(result["success"])
        self.assertEqual(observed["upstream_agent"], "backend-1")
        self.assertEqual(observed["upstream_role"], "后端开发")

    def test_workflow_uses_control_plane_executor_when_dependencies_are_provided(self):
        events = []

        class FakeExecutor:
            def execute_task(self, card, adapter, command_runner):
                events.append(
                    {
                        "task_id": card.task_id,
                        "goal": card.goal,
                        "owner_agent": card.owner_agent,
                        "executor_backend": card.executor_backend,
                    }
                )
                return {
                    "success": True,
                    "command": ["openclaw-live", "task", "run"],
                    "stdout": "ok",
                    "stderr": "",
                }

        engine = workflow_module.WorkflowEngine(
            task_router=None,
            message_bus=None,
            runtime_store=None,
            control_plane_store=object(),
            control_plane_executor=FakeExecutor(),
            control_plane_adapter=object(),
            command_runner=lambda command: None,
        )
        workflow = engine.create_workflow(
            "wf-exec-bind",
            "exec-bind",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                }
            ],
        )
        workflow.variables["backend_recommendation"] = {"selected_backend": "openclaw"}

        result = engine.execute_workflow(workflow.id)

        self.assertEqual(events[0]["executor_backend"], "openclaw")
        self.assertEqual(
            result["step_contexts"]["implement"]["execution"]["command"],
            ["openclaw-live", "task", "run"],
        )

    def test_workflow_real_execution_success_preserves_execution_and_backend_shapes(self):
        class FakeExecutor:
            def execute_task(self, card, adapter, command_runner):
                return {
                    "success": True,
                    "command": ["openclaw-live", "task", "run"],
                    "stdout": "done",
                    "stderr": "",
                }

        engine = workflow_module.WorkflowEngine(
            task_router=None,
            message_bus=None,
            runtime_store=None,
            control_plane_store=object(),
            control_plane_executor=FakeExecutor(),
            control_plane_adapter=object(),
            command_runner=lambda command: None,
        )
        workflow = engine.create_workflow(
            "wf-real-exec-success-shape",
            "real-exec-success-shape",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                }
            ],
        )
        workflow.variables["backend_recommendation"] = {"selected_backend": "hermes"}
        workflow.steps[0].backend = "openclaw"

        result = engine.execute_workflow(workflow.id)
        step_context = result["step_contexts"]["implement"]

        self.assertTrue(result["success"])
        self.assertEqual(
            step_context["execution"],
            {
                "command": ["openclaw-live", "task", "run"],
                "stdout": "done",
                "stderr": "",
                "executor_backend": "openclaw",
            },
        )
        self.assertEqual(
            step_context["backend_recommendation"],
            {"selected_backend": "openclaw"},
        )
        self.assertEqual(step_context["inherited_backend"], "hermes")

    def test_workflow_builds_task_card_with_inherited_backend(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-card-map",
            "card-map",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                }
            ],
        )
        workflow.variables["backend_recommendation"] = {"selected_backend": "openclaw"}
        step = workflow.steps[0]

        card = engine._build_task_card_for_step(workflow, step, "实现代码", "backend-1", "openclaw")

        self.assertEqual(card.task_id, "wf-wf-card-map-implement")
        self.assertEqual(card.owner_agent, "backend-1")
        self.assertEqual(card.review_agent, "backend-1")
        self.assertEqual(card.executor_backend, "openclaw")
        self.assertEqual(card.goal, "实现代码")
        self.assertEqual(card.scope, ["wf-card-map", "implement"])
        self.assertEqual(card.title, "Workflow step implement")
        self.assertEqual(card.timeout_seconds, 300)

    def test_step_backend_override_beats_routing_and_inherited_backend_on_control_plane_failure(self):
        events = []

        class FakeTask:
            def __init__(self, routing_reason):
                self.routing_reason = routing_reason
                self.assigned_agent = "backend-1"

        class FakeRouter:
            agents = {
                "backend-1": type("Agent", (), {"current_tasks": 0, "role": "后端开发"})(),
            }

            def route_task(self, content, **kwargs):
                return (
                    "backend-1",
                    FakeTask({"backend_recommendation": {"selected_backend": "openclaw"}}),
                )

        class FakeExecutor:
            def execute_task(self, card, adapter, command_runner):
                events.append(
                    {
                        "task_id": card.task_id,
                        "executor_backend": card.executor_backend,
                    }
                )
                return {
                    "success": False,
                    "command": ["hermes", "team", "dispatch"],
                    "stdout": "",
                    "stderr": "provider failed",
                    "error": "provider failed",
                }

        engine = workflow_module.WorkflowEngine(
            task_router=FakeRouter(),
            message_bus=None,
            runtime_store=None,
            control_plane_store=object(),
            control_plane_executor=FakeExecutor(),
            control_plane_adapter=object(),
            command_runner=lambda command: None,
        )
        workflow = engine.create_workflow(
            "wf-backend-priority-failure",
            "backend-priority-failure",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                }
            ],
        )
        workflow.variables["backend_recommendation"] = {"selected_backend": "hermes"}
        workflow.steps[0].backend = "openclaw"

        result = engine.execute_workflow(workflow.id)

        self.assertFalse(result["success"])
        self.assertEqual(events[0]["executor_backend"], "openclaw")
        self.assertEqual(
            result["step_contexts"]["implement"]["execution"]["executor_backend"],
            "openclaw",
        )
        self.assertEqual(
            result["step_contexts"]["implement"]["execution"]["stderr"],
            "provider failed",
        )
        self.assertEqual(result["step_contexts"]["implement"]["error"], "provider failed")

    def test_routing_backend_recommendation_beats_inherited_backend_on_control_plane_failure(self):
        events = []

        class FakeTask:
            def __init__(self, routing_reason):
                self.routing_reason = routing_reason
                self.assigned_agent = "backend-1"

        class FakeRouter:
            agents = {
                "backend-1": type("Agent", (), {"current_tasks": 0, "role": "后端开发"})(),
            }

            def route_task(self, content, **kwargs):
                return (
                    "backend-1",
                    FakeTask({"backend_recommendation": {"selected_backend": "openclaw"}}),
                )

        class FakeExecutor:
            def execute_task(self, card, adapter, command_runner):
                events.append(
                    {
                        "task_id": card.task_id,
                        "executor_backend": card.executor_backend,
                    }
                )
                return {
                    "success": False,
                    "command": ["openclaw-live", "task", "run"],
                    "stdout": "",
                    "stderr": "openclaw failed",
                    "error": "openclaw failed",
                }

        engine = workflow_module.WorkflowEngine(
            task_router=FakeRouter(),
            message_bus=None,
            runtime_store=None,
            control_plane_store=object(),
            control_plane_executor=FakeExecutor(),
            control_plane_adapter=object(),
            command_runner=lambda command: None,
        )
        workflow = engine.create_workflow(
            "wf-routing-priority-failure",
            "routing-priority-failure",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                }
            ],
        )
        workflow.variables["backend_recommendation"] = {"selected_backend": "hermes"}

        result = engine.execute_workflow(workflow.id)

        self.assertFalse(result["success"])
        self.assertEqual(events[0]["executor_backend"], "openclaw")
        self.assertEqual(
            result["step_contexts"]["implement"]["execution"]["executor_backend"],
            "openclaw",
        )
        self.assertEqual(
            result["step_contexts"]["implement"]["execution"]["command"],
            ["openclaw-live", "task", "run"],
        )
        self.assertEqual(result["step_contexts"]["implement"]["error"], "openclaw failed")

    def test_workflow_keeps_simulated_execution_without_control_plane_dependencies(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-simulated",
            "simulated",
            "demo",
            [
                {
                    "id": "implement",
                    "name": "实现",
                    "type": "sequential",
                    "agent": "backend-1",
                    "task": "实现代码",
                }
            ],
        )

        result = engine.execute_workflow(workflow.id)
        step_context = result["step_contexts"]["implement"]

        self.assertTrue(result["success"])
        self.assertEqual(
            step_context,
            {
                "step_id": "implement",
                "agent": "backend-1",
                "summary": "模拟执行: 实现代码",
                "artifacts": [],
                "open_questions": [],
                "risks": [],
                "decisions": [],
                "handoff_hint": None,
                "backend_recommendation": None,
                "inherited_backend": None,
            },
        )
        self.assertNotIn("execution", step_context)
        self.assertNotIn("error", step_context)
        self.assertNotIn("knowledge_recommendation", step_context)


if __name__ == "__main__":
    unittest.main()
