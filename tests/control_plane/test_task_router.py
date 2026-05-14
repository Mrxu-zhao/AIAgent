import unittest
import tempfile
from pathlib import Path

from tests.control_plane.test_support import load_framework_module

task_router_module = load_framework_module("task_router")


class TaskRouterIntentTests(unittest.TestCase):
    def test_route_task_prefers_explicit_alias_and_records_reason(self):
        router = task_router_module.TaskRouter()

        agent_id, task = router.route_task("请后端 review 这个接口设计")

        self.assertEqual(agent_id, "backend-1")
        self.assertEqual(task.intent["requested_agent"], "backend-1")
        self.assertEqual(task.intent["collaboration_mode"], "review")
        self.assertEqual(task.routing_reason["strategy"], "explicit-agent")

    def test_analyze_task_intent_detects_role_and_deliverables(self):
        router = task_router_module.TaskRouter()

        intent = router.analyze_task_intent("交给 architect 产出 spec 并评审线上风险")

        self.assertEqual(intent.requested_agent, "architect")
        self.assertEqual(intent.requested_role, "系统架构师")
        self.assertIn("spec", intent.deliverables)
        self.assertIn("critical", intent.risk_flags)

    def test_review_task_prefers_qa_pool(self):
        router = task_router_module.TaskRouter()

        agent_id, task = router.route_task("请 review 这个接口变更，给出回归建议")

        self.assertEqual(agent_id, "qa-functional")
        self.assertEqual(task.routing_reason["review_policy"], "soft-prefer-reviewer")
        self.assertFalse(task.routing_reason["fallback_used"])

    def test_review_task_falls_back_when_qa_pool_is_full(self):
        router = task_router_module.TaskRouter()
        router.agents["qa-functional"].current_tasks = router.agents["qa-functional"].max_tasks
        router.agents["qa-performance"].current_tasks = router.agents["qa-performance"].max_tasks

        agent_id, task = router.route_task("请 review 这个接口变更，给出回归建议")

        self.assertNotIn(agent_id, {"qa-functional", "qa-performance"})
        self.assertTrue(task.routing_reason["fallback_used"])

    def test_review_task_supports_explicit_upstream_avoidance(self):
        router = task_router_module.TaskRouter()

        agent_id, task = router.route_task(
            "请 review 这个接口变更，给出回归建议",
            upstream_agent="qa-functional",
            upstream_role="功能测试",
        )

        self.assertEqual(agent_id, "qa-performance")
        self.assertEqual(task.intent["upstream_agent"], "qa-functional")
        self.assertEqual(task.intent["upstream_role"], "功能测试")
        self.assertEqual(task.routing_reason["excluded_agents"], ["qa-functional"])
        self.assertEqual(task.routing_reason["excluded_roles"], ["功能测试"])

    def test_route_task_emits_backend_recommendation(self):
        router = task_router_module.TaskRouter()

        agent_id, task = router.route_task("需要外部执行的 review 任务")

        self.assertIn("backend_recommendation", task.routing_reason)
        self.assertIn(
            task.routing_reason["backend_recommendation"]["selected_backend"],
            {"hermes", "openclaw"},
        )

    def test_route_task_emits_knowledge_recommendation(self):
        router = task_router_module.TaskRouter()

        agent_id, task = router.route_task("请 backend-1 实现接口并补测试")

        self.assertEqual(agent_id, "backend-1")
        self.assertIn("knowledge_recommendation", task.routing_reason)
        knowledge = task.routing_reason["knowledge_recommendation"]
        self.assertEqual(
            knowledge["load_order"],
            ["team", "role", "instance"],
        )
        self.assertIn(".hermes/team/knowledge/status.md", knowledge["team"])
        self.assertIn(".hermes/agents/backend-dev/knowledge/status.md", knowledge["role"])
        self.assertIn(".hermes/team/agents/backend-1/knowledge/expertise.md", knowledge["instance"])

    def test_knowledge_recommendation_prefers_recent_lessons_when_keyword_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".hermes/team/knowledge/status.md").parent.mkdir(parents=True, exist_ok=True)
            (root / ".hermes/team/knowledge/status.md").write_text("status", encoding="utf-8")
            (root / ".hermes/team/knowledge/project-overview.md").write_text("overview", encoding="utf-8")
            (root / ".hermes/team/knowledge/workflow-playbook.md").write_text("workflow", encoding="utf-8")
            (root / ".hermes/agents/backend-dev/knowledge/status.md").parent.mkdir(parents=True, exist_ok=True)
            (root / ".hermes/agents/backend-dev/knowledge/status.md").write_text("role", encoding="utf-8")
            (root / ".hermes/agents/backend-dev/knowledge/overview.md").write_text("overview", encoding="utf-8")
            (root / ".hermes/agents/backend-dev/knowledge/playbooks/common-tasks.md").parent.mkdir(parents=True, exist_ok=True)
            (root / ".hermes/agents/backend-dev/knowledge/playbooks/common-tasks.md").write_text("common", encoding="utf-8")
            (root / ".hermes/agents/backend-dev/knowledge/checklists/delivery-checklist.md").parent.mkdir(parents=True, exist_ok=True)
            (root / ".hermes/agents/backend-dev/knowledge/checklists/delivery-checklist.md").write_text("delivery", encoding="utf-8")
            (root / ".hermes/team/agents/backend-1/knowledge/expertise.md").parent.mkdir(parents=True, exist_ok=True)
            (root / ".hermes/team/agents/backend-1/knowledge/expertise.md").write_text("backend", encoding="utf-8")
            (root / ".hermes/team/agents/backend-1/knowledge/owned-modules.md").write_text("orders", encoding="utf-8")
            (root / ".hermes/team/agents/backend-1/knowledge/delivery-style.md").write_text("style", encoding="utf-8")
            (root / ".hermes/team/agents/backend-1/knowledge/recent-lessons.md").write_text(
                "redis cache invalidation checklist",
                encoding="utf-8",
            )

            router = task_router_module.TaskRouter(knowledge_root=root / ".hermes")

            agent_id, task = router.route_task("请 backend-1 处理 redis cache 一致性问题")

        self.assertEqual(agent_id, "backend-1")
        knowledge = task.routing_reason["knowledge_recommendation"]
        self.assertEqual(
            knowledge["instance"][0],
            ".hermes/team/agents/backend-1/knowledge/recent-lessons.md",
        )
        self.assertGreater(knowledge["path_scores"]["instance"]["recent-lessons.md"]["score"], 0)


if __name__ == "__main__":
    unittest.main()
