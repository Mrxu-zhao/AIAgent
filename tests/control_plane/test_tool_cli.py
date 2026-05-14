import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli as unified_cli_module  # noqa: E402


class ToolCLITests(unittest.TestCase):
    def test_build_parser_exposes_tool_run_subcommand(self):
        parser = unified_cli_module.build_parser()
        self.assertIn("tool-run", parser.format_help())

    def test_tool_run_executes_registered_tool(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl", "state_dir": "state"},
        )
        fake_audit = SimpleNamespace(log=lambda *args, **kwargs: None)
        fake_policy = SimpleNamespace(is_allowed=lambda *_: True)
        fake_result = {"ok": True, "content": "done", "structured_data": {"tool": "read_knowledge"}}

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(unified_cli_module, "run_tool_command", return_value=fake_result):
                            result = unified_cli_module.main(
                                ["tool-run", "read_knowledge", "查看团队知识", "--actor", "admin"]
                            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "done")
        self.assertEqual(result["structured_data"]["tool"], "read_knowledge")


if __name__ == "__main__":
    unittest.main()
