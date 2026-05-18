import json
import os
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

    def test_default_agents_include_project_manager_virtual_role(self):
        config = config_module.load_control_plane_config()

        self.assertIn("project-manager", config.agents)
        self.assertEqual(config.agents["project-manager"].name, "Hermes")
        self.assertEqual(config.agents["project-manager"].role, "项目经理")
        self.assertEqual(config.aliases["项目经理"], "project-manager")
        self.assertEqual(config.aliases["Hermes"], "project-manager")

    def test_default_standard_workflow_loads_from_workflow_directory(self):
        steps = workflow_module.create_standard_project_workflow()

        self.assertTrue(any(step["id"] == "requirement_confirmation" for step in steps))
        self.assertTrue(any(step["id"] == "ucd_design" for step in steps))
        manager_steps = [
            step for step in steps if (step.get("entry_checks") or {}).get("approval_role") == "项目经理"
        ]
        self.assertTrue(manager_steps)
        self.assertTrue(all(step["agent"] == "project-manager" for step in manager_steps))

    def test_workflow_engine_can_load_workflow_definition_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project_delivery.json"
            path.write_text(
                json.dumps(
                    {
                        "workflow_id": "project_delivery",
                        "name": "demo",
                        "description": "demo workflow",
                        "steps": [{"id": "step-1", "name": "步骤1", "type": "sequential", "agent": "architect", "task": "设计"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            workflow = workflow_module.load_workflow_definition(path)

        self.assertEqual(workflow["workflow_id"], "project_delivery")
        self.assertEqual(workflow["steps"][0]["id"], "step-1")

    def test_workflow_engine_loads_existing_repo_relative_definition_without_rebasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            try:
                os.chdir(tmp)
                path = Path(".hermes") / "team" / "调度框架" / "workflows" / "demo.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "workflow_id": "demo",
                            "name": "demo",
                            "description": "demo workflow",
                            "steps": [{"id": "step-1", "name": "步骤1", "type": "sequential", "agent": "architect", "task": "设计"}],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                workflow = workflow_module.load_workflow_definition(str(path))
            finally:
                os.chdir(previous)

        self.assertEqual(workflow["workflow_id"], "demo")

    def test_human_project_manager_review_defaults_to_virtual_agent(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-pm-default",
            "pm-default",
            "demo",
            [
                {
                    "id": "milestone_review",
                    "name": "里程碑评审",
                    "type": "human",
                    "task": "项目经理审批里程碑",
                    "entry_checks": {
                        "approval_required": True,
                        "approval_role": "项目经理",
                    },
                }
            ],
        )

        self.assertEqual(workflow.steps[0].agent, "project-manager")

    def test_workflow_run_store_persists_snapshot_and_step_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-1", {"name": "demo"})
            store.record_step_event("wf-1", "step-1", "running", {"agent": "architect"})

            snapshot = store.read_snapshot("wf-1")
            events = store.list_step_events("wf-1")

            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(events[0]["step_id"], "step-1")

    def test_workflow_run_store_returns_latest_step_statuses_for_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-1", {"name": "demo"})
            store.record_step_event("wf-1", "design", "running", {})
            store.record_step_event("wf-1", "design", "completed", {"summary": "done"})
            store.record_step_event("wf-1", "implement", "pending", {})

            statuses = store.get_step_statuses("wf-1")

            self.assertEqual(
                statuses,
                {
                    "design": "completed",
                    "implement": "pending",
                },
            )

    def test_workflow_run_store_returns_pending_defaults_for_unknown_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))

            self.assertEqual(
                store.read_snapshot("wf-missing"),
                {"workflow_id": "wf-missing", "status": "pending"},
            )
            self.assertEqual(store.list_step_events("wf-missing"), [])

    def test_workflow_run_store_filters_workflow_and_blank_events_from_step_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-1", {"name": "demo"})
            store.record_workflow_event("wf-1", "running", {"phase": "boot"})
            store.record_step_event("wf-1", "design", "completed", {"summary": "ok"})
            store.record_step_event("wf-1", "  ", "completed", {})
            store.record_step_event("wf-1", "implement", " ", {})

            self.assertEqual(
                store.get_step_statuses("wf-1"),
                {"design": "completed"},
            )

    def test_workflow_run_store_can_delete_prune_and_archive_workflows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = workflow_runtime_module.WorkflowRunStore(Path(tmp))
            store.record_workflow_started("wf-delete", {"name": "delete"})
            store.record_step_event("wf-delete", "step-1", "running", {})
            delete_result = store.delete_workflow("wf-delete")

            self.assertEqual(delete_result["deleted_files"], 2)
            self.assertEqual(store.delete_workflow("wf-delete")["deleted_files"], 0)

            store.record_workflow_started("wf-running", {"name": "running"})
            store.record_step_event("wf-running", "step-1", "running", {})
            store.record_workflow_started("wf-done", {"name": "done"})
            store.record_workflow_completed("wf-done", {"status": "completed"})
            store.record_step_event("wf-done", "step-1", "completed", {})

            prune_result = store.prune_workflows(status="completed")

            self.assertEqual(
                prune_result,
                {"deleted_workflows": 1, "deleted_files": 2},
            )
            self.assertTrue(store._snapshot_path("wf-running").exists())
            self.assertFalse(store._snapshot_path("wf-done").exists())

            store.record_workflow_started("wf-archive", {"name": "archive"})
            store.record_step_event("wf-archive", "step-1", "running", {})
            first_archive = store.archive_workflow("wf-archive")

            self.assertEqual(first_archive["archived_files"], 2)
            self.assertTrue((Path(first_archive["archive_path"]) / "wf-archive.json").exists())
            self.assertTrue((Path(first_archive["archive_path"]) / "wf-archive.jsonl").exists())

            store.record_workflow_started("wf-archive", {"name": "archive"})
            store.record_step_event("wf-archive", "step-2", "completed", {})
            second_archive = store.archive_workflow("wf-archive")

            self.assertEqual(second_archive["archived_files"], 2)
            self.assertTrue((Path(second_archive["archive_path"]) / "wf-archive.json").exists())

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
            self.assertIn("knowledge_usage", snapshot)
            self.assertGreaterEqual(
                snapshot["knowledge_usage"]["summary"]["feedback_score"],
                0.0,
            )

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

    def test_workflow_handoff_contains_target_knowledge_recommendation(self):
        engine = workflow_module.WorkflowEngine(task_router=router_module.TaskRouter(), message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-handoff-knowledge",
            "handoff-knowledge",
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

        knowledge = result["handoffs"][0]["knowledge_recommendation"]
        self.assertEqual(knowledge["load_order"], ["team", "role", "instance"])
        self.assertIn(".hermes/team/knowledge/status.md", knowledge["team"])
        self.assertIn(".hermes/agents/backend-dev/knowledge/status.md", knowledge["role"])
        self.assertIn(".hermes/team/agents/backend-1/knowledge/expertise.md", knowledge["instance"])

    def test_workflow_engine_writes_decisions_and_risks_back_to_team_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_root = Path(tmp) / ".hermes" / "team" / "knowledge"
            knowledge_root.mkdir(parents=True, exist_ok=True)
            (knowledge_root / "decision-log.md").write_text(
                "# 关键决策记录\n\n| 日期 | 决策 | 理由 | 影响范围 |\n|------|------|------|----------|\n",
                encoding="utf-8",
            )
            (knowledge_root / "risk-register.md").write_text(
                "# 风险登记册\n\n| 风险 | 影响范围 | 预警信号 | 缓解策略 |\n|------|----------|----------|----------|\n",
                encoding="utf-8",
            )

            engine = workflow_module.WorkflowEngine(
                task_router=router_module.TaskRouter(),
                message_bus=None,
                runtime_store=None,
                knowledge_root=knowledge_root,
            )
            workflow = engine.create_workflow(
                "wf-knowledge-sync",
                "knowledge-sync",
                "demo",
                [
                    {
                        "id": "implement",
                        "name": "实现",
                        "type": "sequential",
                        "agent": "backend-1",
                        "task": "实现接口",
                    }
                ],
            )
            engine._execute_agent_task = lambda step, task_content: {
                "success": True,
                "output": "ok",
                "agent": step.agent,
                "risks": ["接口变更影响现有调用方"],
                "decisions": [
                    {
                        "summary": "采用接口版本化",
                        "rationale": "降低兼容性风险",
                        "impact": "接口层",
                        "next_action": "同步前端联调",
                    }
                ],
            }

            result = engine.execute_workflow(workflow.id)
            decision_log = (knowledge_root / "decision-log.md").read_text(encoding="utf-8")
            risk_register = (knowledge_root / "risk-register.md").read_text(encoding="utf-8")

        self.assertTrue(result["success"])
        self.assertIn("采用接口版本化", decision_log)
        self.assertIn("wf-knowledge-sync", decision_log)
        self.assertIn("接口变更影响现有调用方", risk_register)
        self.assertIn("workflow: wf-knowledge-sync", risk_register)

    def test_workflow_feedback_writes_metadata_and_deduplicates_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_root = Path(tmp) / ".hermes" / "team" / "knowledge"
            engine = workflow_module.WorkflowEngine(
                task_router=router_module.TaskRouter(),
                message_bus=None,
                runtime_store=None,
                knowledge_root=knowledge_root,
            )
            workflow = engine.create_workflow(
                "wf-knowledge-dedupe",
                "knowledge-dedupe",
                "demo",
                [
                    {
                        "id": "implement",
                        "name": "实现",
                        "type": "sequential",
                        "agent": "backend-1",
                        "task": "实现接口",
                    }
                ],
            )
            engine._execute_agent_task = lambda step, task_content: {
                "success": True,
                "output": "ok",
                "agent": step.agent,
                "risks": ["缓存一致性风险"],
                "decisions": [
                    {
                        "summary": "采用接口版本化",
                        "rationale": "降低兼容性风险",
                        "impact": "接口层",
                        "next_action": "同步前端联调",
                    }
                ],
            }

            first = engine.execute_workflow(workflow.id)
            workflow.status = "pending"
            workflow.completed_at = None
            workflow.started_at = None
            workflow.steps[0].status = workflow_module.StepStatus.PENDING
            second = engine.execute_workflow(workflow.id)
            decision_log = (knowledge_root / "decision-log.md").read_text(encoding="utf-8")
            risk_register = (knowledge_root / "risk-register.md").read_text(encoding="utf-8")

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertIn("owner: control-plane", decision_log)
        self.assertIn("last_reviewed:", decision_log)
        self.assertEqual(decision_log.count("采用接口版本化"), 1)
        self.assertEqual(risk_register.count("缓存一致性风险"), 1)

    def test_workflow_engine_writes_team_lessons_from_step_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_root = Path(tmp) / ".hermes" / "team" / "knowledge"
            engine = workflow_module.WorkflowEngine(
                task_router=router_module.TaskRouter(),
                message_bus=None,
                runtime_store=None,
                knowledge_root=knowledge_root,
            )
            workflow = engine.create_workflow(
                "wf-team-lessons",
                "team-lessons",
                "demo",
                [
                    {
                        "id": "implement",
                        "name": "实现",
                        "type": "sequential",
                        "agent": "backend-1",
                        "task": "实现接口",
                    }
                ],
            )
            engine._execute_agent_task = lambda step, task_content: {
                "success": True,
                "output": "以 markdown 项目上下文启动 workflow",
                "agent": step.agent,
                "risks": ["上下文文件格式不稳定"],
                "decisions": [
                    {
                        "summary": "非 JSON context-file 按文本注入 project_context",
                        "rationale": "避免 workflow 启动阶段崩溃",
                        "impact": "workflow 输入装载",
                        "next_action": "补齐 CLI 使用说明",
                    }
                ],
            }

            result = engine.execute_workflow(workflow.id)
            lesson_files = sorted((knowledge_root / "lessons").glob("workflow-lessons-*-*-*.md"))
            lesson_text = lesson_files[0].read_text(encoding="utf-8")

        self.assertTrue(result["success"])
        self.assertEqual(len(lesson_files), 1)
        self.assertRegex(lesson_files[0].name, r"^workflow-lessons-\d{4}-\d{2}-\d{2}\.md$")
        self.assertIn("source: wf-team-lessons", lesson_text)
        self.assertIn("workflow: wf-team-lessons", lesson_text)
        self.assertIn("step: implement", lesson_text)
        self.assertIn("agent: backend-1", lesson_text)
        self.assertIn("非 JSON context-file 按文本注入 project_context", lesson_text)

    def test_workflow_engine_writes_recent_lessons_for_agent_and_deduplicates_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_root = Path(tmp) / ".hermes" / "team" / "knowledge"
            engine = workflow_module.WorkflowEngine(
                task_router=router_module.TaskRouter(),
                message_bus=None,
                runtime_store=None,
                knowledge_root=knowledge_root,
            )
            workflow = engine.create_workflow(
                "wf-instance-lessons",
                "instance-lessons",
                "demo",
                [
                    {
                        "id": "review",
                        "name": "评审",
                        "type": "sequential",
                        "agent": "qa-functional",
                        "task": "评审交付物",
                    }
                ],
            )
            engine._execute_agent_task = lambda step, task_content: {
                "success": True,
                "output": "交付前先复核终态 snapshot",
                "agent": step.agent,
                "risks": ["VERSION_CONFLICT 会误报失败"],
                "decisions": [
                    {
                        "summary": "终态写入冲突后先复核 snapshot",
                        "rationale": "避免已完成任务被误判失败",
                        "impact": "dispatch 与 workflow 收口",
                        "next_action": "统一用于并发完成写入",
                    }
                ],
            }

            first = engine.execute_workflow(workflow.id)
            workflow.status = "pending"
            workflow.completed_at = None
            workflow.started_at = None
            workflow.steps[0].status = workflow_module.StepStatus.PENDING
            second = engine.execute_workflow(workflow.id)
            recent_lessons = (
                knowledge_root.parent / "agents" / "qa-functional" / "knowledge" / "recent-lessons.md"
            ).read_text(encoding="utf-8")

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertIn("# qa-functional - 最近经验", recent_lessons)
        self.assertIn("## ", recent_lessons)
        self.assertEqual(
            recent_lessons.count("### 经验：终态写入冲突后先复核 snapshot"),
            1,
        )
        self.assertIn("workflow: wf-instance-lessons", recent_lessons)

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

    def test_workflow_builds_task_card_with_entry_checks(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-card-gates",
            "card-gates",
            "demo",
            [
                {
                    "id": "functional_test",
                    "name": "功能测试",
                    "type": "sequential",
                    "agent": "qa-functional",
                    "task": "执行功能测试",
                    "entry_checks": {
                        "required_deliverables": ["后端单元测试报告.md"],
                        "coverage_threshold": {"backend": 70},
                        "test_pass_rate": 100,
                    },
                }
            ],
        )
        step = workflow.steps[0]

        card = engine._build_task_card_for_step(workflow, step, "执行功能测试", "qa-functional", "hermes")

        self.assertEqual(card.entry_checks["coverage_threshold"]["backend"], 70)
        self.assertIn("后端单元测试报告.md", card.required_deliverables)
        self.assertFalse(card.approval_required)

    def test_human_review_blocks_without_approval(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-blocked-approval",
            "blocked-approval",
            "demo",
            [
                {
                    "id": "requirements_review",
                    "name": "需求评审",
                    "type": "human",
                    "agent": "architect",
                    "task": "评审需求",
                    "entry_checks": {
                        "required_deliverables": ["PRD.md"],
                        "approval_required": True,
                        "approval_role": "项目经理",
                    },
                }
            ],
            {"deliverables": ["PRD.md"], "approvals": {}},
        )

        result = engine.execute_workflow(workflow.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["blocked_steps"], ["requirements_review"])
        self.assertIn("approval required", result["error"])

    def test_entry_checks_block_on_missing_quality_gates(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-quality-gate",
            "quality-gate",
            "demo",
            [
                {
                    "id": "functional_test",
                    "name": "功能测试",
                    "type": "sequential",
                    "agent": "qa-functional",
                    "task": "执行功能测试",
                    "entry_checks": {
                        "required_deliverables": ["后端单元测试报告.md"],
                        "coverage_threshold": {"backend": 70},
                        "test_pass_rate": 100,
                    },
                }
            ],
            {
                "deliverables": ["后端单元测试报告.md"],
                "quality_gates": {"coverage": {"backend": 60}, "test_pass_rate": 100},
            },
        )

        result = engine.execute_workflow(workflow.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["blocked_steps"], ["functional_test"])
        self.assertIn("coverage gate failed", result["error"])

    def test_entry_checks_block_on_missing_deliverables(self):
        engine = workflow_module.WorkflowEngine(task_router=None, message_bus=None, runtime_store=None)
        workflow = engine.create_workflow(
            "wf-missing-deliverable",
            "missing-deliverable",
            "demo",
            [
                {
                    "id": "closure_confirmation",
                    "name": "闭环确认",
                    "type": "human",
                    "agent": "qa-functional",
                    "task": "确认闭环",
                    "entry_checks": {
                        "required_deliverables": ["功能测试报告.md", "回归测试报告.md"],
                        "approval_required": True,
                        "approval_role": "项目经理",
                    },
                }
            ],
            {"deliverables": ["功能测试报告.md"]},
        )

        result = engine.execute_workflow(workflow.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["blocked_steps"], ["closure_confirmation"])
        self.assertIn("missing required deliverables", result["error"])

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
