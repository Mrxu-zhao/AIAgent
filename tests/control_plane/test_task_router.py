import unittest

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


if __name__ == "__main__":
    unittest.main()
