import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from workflows.team_runner import TeamWorkflowRunner  # noqa: E402


class TeamWorkflowRunnerTests(unittest.TestCase):
    def test_run_full_delivery_flow_includes_devops_stage(self):
        stage_results = {
            "requirements-analysis": {"ok": True, "workflow_id": "requirements-analysis", "role": "requirements-analyst", "quality_report": {"summary": {"failed": 0}}},
            "architect-design-review": {"ok": True, "workflow_id": "architect-design-review", "role": "architect", "quality_report": {"summary": {"failed": 0}}},
            "dba-table-design": {"ok": True, "workflow_id": "dba-table-design", "role": "dba", "quality_report": {"summary": {"failed": 0}}},
            "ucd-interaction-design": {"ok": True, "workflow_id": "ucd-interaction-design", "role": "ucd", "quality_report": {"summary": {"failed": 0}}},
            "backend-api-development": {"ok": True, "workflow_id": "backend-api-development", "role": "backend-dev", "quality_report": {"summary": {"failed": 1}}},
            "frontend-page-development": {"ok": True, "workflow_id": "frontend-page-development", "role": "frontend-dev", "quality_report": {"summary": {"failed": 1}}},
            "qa-test-case-design": {"ok": True, "workflow_id": "qa-test-case-design", "role": "qa-functional", "quality_report": {"summary": {"failed": 0}}},
            "devops-deployment": {"ok": True, "workflow_id": "devops-deployment", "role": "devops", "quality_report": {"summary": {"failed": 0}}},
        }

        runner = TeamWorkflowRunner()
        with patch("workflows.team_runner.execute_role_workflow", side_effect=lambda workflow_id, context_values=None, cwd=None, knowledge_root=None: stage_results[workflow_id]):
            result = runner.run(
                feature="supplier-onboarding",
                context_values={"feature": "supplier-onboarding", "Feature": "SupplierOnboarding"},
            )

        self.assertEqual(result["stages"][-1]["workflow_id"], "devops-deployment")
        self.assertEqual(result["stages"][-1]["role"], "devops")
        self.assertIn("devops", [item["role"] for item in result["stages"]])
        self.assertGreaterEqual(result["summary"]["total_stages"], 8)


if __name__ == "__main__":
    unittest.main()
