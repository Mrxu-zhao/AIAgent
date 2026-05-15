import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

import cli as unified_cli_module  # noqa: E402
from workflows.executor import build_role_workflow_executor  # noqa: E402
from workflows.loader import WorkflowLoader  # noqa: E402
from workflows.models import RoleWorkflow  # noqa: E402
from workflows.resolver import WorkflowValueResolver  # noqa: E402


class RoleWorkflowModelTests(unittest.TestCase):
    def test_role_workflow_model_from_definition(self):
        definition = {
            "workflow_id": "backend-api-development",
            "name": "demo",
            "role": "backend-dev",
            "steps": [
                {
                    "step_id": "read_requirement",
                    "name": "读取需求",
                    "tool": "read_knowledge",
                    "input": {},
                }
            ],
        }

        workflow = RoleWorkflow.from_dict(definition)

        self.assertEqual(workflow.workflow_id, "backend-api-development")
        self.assertEqual(workflow.steps[0].tool, "read_knowledge")


class WorkflowValueResolverTests(unittest.TestCase):
    def test_resolve_feature_placeholder(self):
        resolver = WorkflowValueResolver({"feature": "user", "Feature": "User"})

        self.assertEqual(resolver.resolve_value("/api/{feature}"), "/api/user")

    def test_resolve_step_output_reference(self):
        resolver = WorkflowValueResolver(
            {
                "step_outputs": {
                    "generate_prd": {
                        "output": "# user 产品需求文档",
                    }
                }
            }
        )

        self.assertEqual(
            resolver.resolve_value("${generate_prd.output}"),
            "# user 产品需求文档",
        )


class RoleWorkflowExecutorTests(unittest.TestCase):
    def test_execute_requirements_role_workflow_generates_deliverables(self):
        loader = WorkflowLoader()
        definition = loader.load("requirements-analysis")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "interviews").mkdir()
            (tmp_path / "interviews" / "user.md").write_text("# notes", encoding="utf-8")
            knowledge_root = tmp_path / "agents"
            role_root = knowledge_root / "requirements-analyst" / "knowledge" / "pitfalls"
            role_root.mkdir(parents=True)

            executor = build_role_workflow_executor(
                cwd=tmp_path,
                knowledge_root=knowledge_root,
            )
            result = executor.execute_from_definition(
                definition,
                {
                    "feature": "user",
                    "Feature": "User",
                    "background": "需要支持用户管理",
                },
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["workflow_id"], "requirements-analysis")
            self.assertEqual(result["role"], "requirements-analyst")
            self.assertTrue((tmp_path / "requirements" / "user_prd.md").exists())
            self.assertIn("quality_report", result)
            self.assertEqual(result["quality_report"]["role"], "analyst")
            self.assertIn("knowledge_feedback", result)
            self.assertGreaterEqual(len(result["knowledge_feedback"]["records"]), 1)

    def test_execute_web_backend_workflow_exposes_selected_stack(self):
        loader = WorkflowLoader()
        definition = loader.load("web-backend-api")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "api").mkdir()
            (tmp_path / "api" / "user.md").write_text("# contract", encoding="utf-8")
            knowledge_root = tmp_path / "agents"
            (knowledge_root / "backend-dev" / "knowledge" / "pitfalls").mkdir(parents=True)

            executor = build_role_workflow_executor(
                cwd=tmp_path,
                knowledge_root=knowledge_root,
            )
            result = executor.execute_from_definition(
                definition,
                {
                    "feature": "user",
                    "Feature": "User",
                    "stack": "go-gin",
                },
            )

            self.assertEqual(result["stack"]["stack_id"], "go-gin")
            self.assertEqual(result["stack"]["category"], "backend")


class RoleWorkflowCliTests(unittest.TestCase):
    def test_build_parser_exposes_role_workflow_subcommand(self):
        parser = unified_cli_module.build_parser()
        help_text = parser.format_help()

        self.assertIn("role-workflow", help_text)

    def test_cli_role_workflow_command_returns_workflow_result(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)
        fake_result = {
            "ok": True,
            "workflow_id": "requirements-analysis",
            "role": "requirements-analyst",
            "steps": [],
        }

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                unified_cli_module,
                "build_default_rbac_policy",
                return_value=SimpleNamespace(is_allowed=lambda *_: True),
            ):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(
                            unified_cli_module,
                            "execute_role_workflow",
                            return_value=fake_result,
                            create=True,
                        ) as execute_mock:
                            stream = io.StringIO()
                            with redirect_stdout(stream):
                                result = unified_cli_module.main(
                                    [
                                        "role-workflow",
                                        "--workflow-id",
                                        "requirements-analysis",
                                        "--feature",
                                        "user",
                                    ]
                                )

        self.assertEqual(result["workflow_id"], "requirements-analysis")
        self.assertIn('"workflow_id": "requirements-analysis"', stream.getvalue())
        execute_mock.assert_called_once()

    def test_load_role_workflow_context_reads_context_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            context_path = Path(tmp) / "context.json"
            context_path.write_text(
                json.dumps({"feature": "user", "background": "demo"}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = unified_cli_module._load_role_workflow_context(str(context_path))

        self.assertEqual(result["feature"], "user")
        self.assertEqual(result["background"], "demo")


if __name__ == "__main__":
    unittest.main()
