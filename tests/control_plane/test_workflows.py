import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from workflows.loader import WorkflowLoader


class WorkflowLoaderTests(unittest.TestCase):
    def test_load_backend_api_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("backend-api-development")
        self.assertEqual(workflow["role"], "backend-dev")
        self.assertTrue(len(workflow["steps"]) > 0)
        self.assertEqual(workflow["steps"][0]["step_id"], "read_requirement")

    def test_load_frontend_page_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("frontend-page-development")
        self.assertEqual(workflow["role"], "frontend-dev")
        self.assertIn("generate_vue_component", [s["tool"] for s in workflow["steps"]])

    def test_load_architect_design_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("architect-design-review")
        self.assertEqual(workflow["role"], "architect")
        self.assertIn("generate_architecture_doc", [s["tool"] for s in workflow["steps"]])

    def test_load_dba_table_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("dba-table-design")
        self.assertEqual(workflow["role"], "dba")
        self.assertIn("generate_ddl", [s["tool"] for s in workflow["steps"]])

    def test_load_qa_test_case_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("qa-test-case-design")
        self.assertEqual(workflow["role"], "qa-functional")
        self.assertIn("generate_test_cases", [s["tool"] for s in workflow["steps"]])

    def test_load_devops_deployment_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("devops-deployment")
        self.assertEqual(workflow["role"], "devops")
        self.assertIn("generate_dockerfile", [s["tool"] for s in workflow["steps"]])

    def test_load_ucd_interaction_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("ucd-interaction-design")
        self.assertEqual(workflow["role"], "ucd")
        self.assertIn("generate_design_spec", [s["tool"] for s in workflow["steps"]])

    def test_load_requirements_analysis_workflow(self):
        loader = WorkflowLoader()
        workflow = loader.load("requirements-analysis")
        self.assertEqual(workflow["role"], "requirements-analyst")
        self.assertIn("generate_prd", [s["tool"] for s in workflow["steps"]])

    def test_load_nested_workflow_by_workflow_id(self):
        loader = WorkflowLoader()
        workflow = loader.load("web-backend-api")
        self.assertEqual(workflow["role"], "backend-dev")
        self.assertEqual(workflow["scene"], "web")
        self.assertEqual(
            workflow["stack_selection"]["options"],
            ["java-spring", "go-gin", "python-fastapi"],
        )
        self.assertEqual(
            workflow["steps"][0]["input"]["paths"],
            ["api/{feature}.md"],
        )

    def test_list_workflows(self):
        loader = WorkflowLoader()
        workflows = loader.list_workflows()
        self.assertIn("backend-api-development", workflows)
        self.assertIn("frontend-page-development", workflows)
        self.assertIn("architect-design-review", workflows)
        self.assertIn("web-backend-api", workflows)
        self.assertIn("mobile-page", workflows)
        self.assertGreaterEqual(len(workflows), 12)

    def test_load_nonexistent_workflow_raises(self):
        loader = WorkflowLoader()
        with self.assertRaises(FileNotFoundError):
            loader.load("nonexistent-workflow")
