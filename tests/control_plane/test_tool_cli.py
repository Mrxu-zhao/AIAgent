import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli as unified_cli_module  # noqa: E402


class ToolCLITests(unittest.TestCase):
    def test_build_parser_exposes_tool_run_subcommand(self):
        parser = unified_cli_module.build_parser()
        self.assertIn("tool-run", parser.format_help())
        self.assertIn("tool-session", parser.format_help())

    def test_tool_run_executes_registered_tool(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "state/workflow-runtime",
                "message_bus_dir": "state/message-bus",
            },
        )
        fake_audit = SimpleNamespace(log=lambda *args, **kwargs: None)
        fake_policy = SimpleNamespace(is_allowed=lambda *_: True)
        fake_result = {
            "ok": True,
            "content": "done",
            "structured_data": {"tool": "read_knowledge"},
            "session_id": "session-1",
        }

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
        self.assertEqual(result["session_id"], "session-1")

    def test_run_tool_command_route_task_returns_structured_route(self):
        state_dir = Path("d:/KIMIK2.5/AIAgent/.hermes/team/control_plane/state")
        fake_config = SimpleNamespace(
            sensitive_actions=["provider.openclaw.live"],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": str(state_dir),
                "workflow_runtime_dir": str(state_dir / "workflow_runtime"),
                "message_bus_dir": str(state_dir / "message_bus"),
            },
        )

        result = unified_cli_module.run_tool_command(
            tool_name="route_task",
            task="请 architect review 接口设计",
            actor="operator",
            config=fake_config,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["structured_data"]["agent_id"], "architect")
        self.assertIn("routing_reason", result["structured_data"])
        self.assertIn("session_id", result)

    def test_tool_run_resume_reuses_previous_session(self):
        state_dir = Path("d:/KIMIK2.5/AIAgent/.hermes/team/control_plane/state")
        fake_config = SimpleNamespace(
            sensitive_actions=["provider.openclaw.live"],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": str(state_dir),
                "workflow_runtime_dir": str(state_dir / "workflow_runtime"),
                "message_bus_dir": str(state_dir / "message_bus"),
            },
        )

        first = unified_cli_module.run_tool_command(
            tool_name="read_knowledge",
            task="请 architect review 接口设计",
            actor="operator",
            config=fake_config,
        )
        resumed = unified_cli_module.run_tool_command(
            tool_name="find_knowledge_files",
            task="ignored when resumed",
            actor="operator",
            config=fake_config,
            session_id=first["session_id"],
            resume=True,
        )

        self.assertEqual(resumed["session_id"], first["session_id"])
        self.assertTrue(resumed["ok"])
        self.assertIn(".hermes/team/knowledge/status.md", resumed["structured_data"]["paths"])


if __name__ == "__main__":
    unittest.main()
