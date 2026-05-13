import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
