import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
import knowledge.analytics as analytics_module  # noqa: E402
import knowledge.governance as governance_module  # noqa: E402

router_module = load_framework_module('task_router')


class KnowledgeAnalyticsTests(unittest.TestCase):
    def test_dashboard_helpers_expose_heat_and_pending_counts(self):
        router = router_module.TaskRouter()
        router.route_task('请 backend-1 实现接口并补测试')
        heat = analytics_module.build_knowledge_heat_ranking(router)
        by_agent = analytics_module.build_consumption_by_agent(router)
        unused = analytics_module.build_unused_recommendations(router)
        self.assertTrue(heat)
        self.assertTrue(by_agent)
        self.assertTrue(unused)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            governance_module.append_governance_entry(
                root=root,
                entry_type='decision',
                content='统一批入口',
                owner='architect',
            )
            counts = analytics_module.build_pending_governance_counts(root)
            self.assertEqual(counts['pending_total'], 1)

    def test_effectiveness_report_aggregates_workflow_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp) / "workflow_runtime"
            snapshots_dir = runtime_dir / "snapshots"
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            (snapshots_dir / "wf-1.json").write_text(
                """{
  "workflow_id": "wf-1",
  "status": "completed",
  "knowledge_usage": {
    "summary": {
      "consumed_paths": [".hermes/team/knowledge/status.md"],
      "unused_paths": [".hermes/team/knowledge/risk-register.md"],
      "feedback_score": 0.7
    },
    "steps": [{"step_id": "implement"}]
  }
}""",
                encoding="utf-8",
            )
            report = analytics_module.build_knowledge_effectiveness_report(runtime_dir)

        self.assertEqual(report["workflow_count"], 1)
        self.assertEqual(report["usage_record_count"], 1)
        self.assertEqual(report["average_feedback_score"], 0.7)
        self.assertEqual(report["usage_heat_ranking"][0]["path"], ".hermes/team/knowledge/status.md")
        self.assertEqual(report["unused_path_ranking"][0]["path"], ".hermes/team/knowledge/risk-register.md")


if __name__ == '__main__':
    unittest.main()
