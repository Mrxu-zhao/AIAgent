import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli as unified_cli_module  # noqa: E402
import governance.audit as audit_module  # noqa: E402


class UnifiedCLITests(unittest.TestCase):
    def test_build_parser_exposes_required_subcommands(self):
        parser = unified_cli_module.build_parser()
        help_text = parser.format_help()

        self.assertIn("dispatch", help_text)
        self.assertIn("workflow", help_text)
        self.assertIn("query", help_text)
        self.assertIn("monitor", help_text)
        self.assertIn("control-plane-run", help_text)
        self.assertIn("validate", help_text)

    def test_dispatch_command_routes_task_and_audits(self):
        observed = {"registered": [], "audit": []}

        class FakeBus:
            def register_agent(self, agent_id):
                observed["registered"].append(agent_id)

            def create_task_message(self, actor, agent_id, task_id, task):
                return {
                    "actor": actor,
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "task": task,
                }

            def send(self, payload):
                observed["sent"] = payload

        class FakeRouter:
            agents = {"architect": object(), "backend-1": object()}

            def route_task(self, task, priority):
                observed["priority"] = priority.name
                return "architect", SimpleNamespace(id="task-1")

        fake_audit = SimpleNamespace(log=lambda action, payload: observed["audit"].append((action, payload)))
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        fake_policy = SimpleNamespace(is_allowed=lambda actor, action: True)

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(unified_cli_module, "TaskRouter", return_value=FakeRouter()):
                            with patch.object(unified_cli_module, "get_bus", return_value=FakeBus()):
                                payload = unified_cli_module.main(
                                    ["dispatch", "设计接口", "--actor", "admin", "--priority", "high"]
                                )

        self.assertEqual(payload["agent"], "architect")
        self.assertEqual(payload["task_id"], "task-1")
        self.assertEqual(observed["registered"], ["architect", "backend-1"])
        self.assertEqual(observed["sent"]["task"], "设计接口")
        self.assertEqual(observed["priority"], "HIGH")
        self.assertEqual(observed["audit"][0][0], "dispatch")

    def test_monitor_prometheus_command_returns_exported_text(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                unified_cli_module,
                "build_default_rbac_policy",
                return_value=SimpleNamespace(is_allowed=lambda *_: True),
            ):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger"):
                        with patch.object(unified_cli_module, "refresh_repository_metrics") as refresh_mock:
                            with patch.object(
                                unified_cli_module,
                                "export_metrics_text",
                                return_value="metric 1\n",
                            ):
                                result = unified_cli_module.main(["monitor", "--prometheus"])

        self.assertEqual(result, "metric 1\n")
        refresh_mock.assert_called_once_with()

    def test_control_plane_run_command_calls_shared_runner(self):
        observed = {}
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        fake_audit = SimpleNamespace(log=lambda action, payload: observed.update({"action": action, **payload}))

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
                            "run_task_batch",
                            return_value={"summary": {"done_tasks": ["WS-A-P0-001"]}},
                        ):
                            result = unified_cli_module.main(
                                ["control-plane-run", "--max-workers", "3"]
                            )

        self.assertEqual(result["summary"]["done_tasks"], ["WS-A-P0-001"])
        self.assertEqual(observed["action"], "control-plane-run")
        self.assertEqual(observed["max_workers"], 3)

    def test_validate_command_calls_real_load_validation(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)

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
                            "run_real_load_validation",
                            return_value={"replicas": 2, "success": True},
                        ) as validation_mock:
                            result = unified_cli_module.main(
                                ["validate", "--replicas", "2", "--max-workers", "5"]
                            )

        self.assertEqual(result["replicas"], 2)
        validation_mock.assert_called_once_with(replicas=2, max_workers=5)

    def test_workflow_command_returns_engine_result(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)
        fake_engine = SimpleNamespace(
            create_workflow=lambda *args: SimpleNamespace(id="wf-1"),
            execute_workflow=lambda workflow_id: {
                "success": True,
                "workflow_id": workflow_id,
                "step_contexts": {"step-1": {"summary": "done"}},
                "handoffs": [],
            },
        )

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                unified_cli_module,
                "build_default_rbac_policy",
                return_value=SimpleNamespace(is_allowed=lambda *_: True),
            ):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(unified_cli_module, "TaskRouter"):
                            with patch.object(unified_cli_module, "WorkflowEngine", return_value=fake_engine):
                                with patch.object(
                                    unified_cli_module,
                                    "create_standard_project_workflow",
                                    return_value=[{"id": "step-1"}],
                                ):
                                    result = unified_cli_module.main(
                                        ["workflow", "--name", "demo-project"]
                                    )

        self.assertTrue(result["success"])
        self.assertEqual(result["workflow_id"], "wf-1")
        self.assertIn("step_contexts", result)
        self.assertIn("handoffs", result)

    def test_query_handoff_returns_filtered_records(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: action == "query.handoff" and actor == "viewer"
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)
        fake_records = [
            {"message_id": "msg-1", "workflow_id": "wf-1", "target_agent": "backend-1"},
            {"message_id": "msg-2", "workflow_id": "wf-2", "target_agent": "backend-2"},
        ]

        class FakeHandoffStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def list_records(self, workflow_id=None, target_agent=None, status=None):
                records = list(fake_records)
                if workflow_id is not None:
                    records = [record for record in records if record["workflow_id"] == workflow_id]
                if target_agent is not None:
                    records = [record for record in records if record["target_agent"] == target_agent]
                if status is not None:
                    records = [record for record in records if record.get("status") == status]
                return records

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(
                            unified_cli_module,
                            "HandoffRunStore",
                            FakeHandoffStore,
                            create=True,
                        ):
                            result = unified_cli_module.main(
                                ["query", "handoff", "--workflow-id", "wf-1", "--actor", "viewer"]
                            )

        self.assertEqual([record["message_id"] for record in result["records"]], ["msg-1"])

    def test_query_handoff_supports_message_id_and_status_filters(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: action == "query.handoff" and actor == "viewer"
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)
        fake_records = [
            {
                "message_id": "msg-1",
                "workflow_id": "wf-1",
                "target_agent": "backend-1",
                "status": "materialized",
            },
            {
                "message_id": "msg-1",
                "workflow_id": "wf-1",
                "target_agent": "backend-1",
                "status": "failed",
            },
            {
                "message_id": "msg-2",
                "workflow_id": "wf-1",
                "target_agent": "backend-1",
                "status": "materialized",
            },
        ]

        class FakeHandoffStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def list_records(self, workflow_id=None, target_agent=None, status=None):
                del workflow_id, target_agent, status
                return list(fake_records)

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(
                            unified_cli_module,
                            "HandoffRunStore",
                            FakeHandoffStore,
                            create=True,
                        ):
                            result = unified_cli_module.main(
                                [
                                    "query",
                                    "handoff",
                                    "--workflow-id",
                                    "wf-1",
                                    "--message-id",
                                    "msg-1",
                                    "--status",
                                    "materialized",
                                    "--target-agent",
                                    "backend-1",
                                    "--actor",
                                    "viewer",
                                ]
                            )

        self.assertEqual(
            result["records"],
            [
                {
                    "message_id": "msg-1",
                    "workflow_id": "wf-1",
                    "target_agent": "backend-1",
                    "status": "materialized",
                }
            ],
        )

    def test_query_handoff_rejects_unauthorized_actor(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(is_allowed=lambda *_: False)

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger"):
                        with self.assertRaises(PermissionError):
                            unified_cli_module.main(
                                ["query", "handoff", "--workflow-id", "wf-1", "--actor", "guest"]
                            )

    def test_query_workflow_returns_snapshot_and_events(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: action == "query.workflow" and actor == "viewer"
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)

        class FakeWorkflowStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def read_snapshot(self, workflow_id):
                return {"workflow_id": workflow_id, "status": "completed"}

            def list_step_events(self, workflow_id):
                return [{"workflow_id": workflow_id, "event": "handoff_materialized"}]

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(
                            unified_cli_module,
                            "WorkflowRunStore",
                            FakeWorkflowStore,
                            create=True,
                        ):
                            result = unified_cli_module.main(
                                ["query", "workflow", "--id", "wf-1", "--actor", "viewer"]
                            )

        self.assertEqual(result["snapshot"]["workflow_id"], "wf-1")
        self.assertEqual(result["events"][0]["event"], "handoff_materialized")

    def test_query_audit_returns_filtered_records_and_writes_audit_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            logger = audit_module.AuditLogger(audit_path)
            logger.log("dispatch", {"actor": "admin"})
            logger.log("workflow", {"workflow_id": "wf-1"})
            fake_config = SimpleNamespace(
                sensitive_actions=[],
                directories={
                    "audit_log": str(audit_path),
                    "state_dir": str(Path(tmp) / "state"),
                    "workflow_runtime_dir": str(Path(tmp) / "workflow-runtime"),
                },
            )
            fake_policy = SimpleNamespace(
                is_allowed=lambda actor, action: action == "query.audit.read" and actor == "viewer"
            )

            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(
                    unified_cli_module,
                    "build_default_rbac_policy",
                    return_value=fake_policy,
                ):
                    with patch.object(unified_cli_module, "ApprovalGate"):
                        result = unified_cli_module.main(
                            ["query", "audit", "--action", "dispatch", "--actor", "viewer"]
                        )

            self.assertEqual([record["action"] for record in result["records"]], ["dispatch"])
            logged_actions = [entry["action"] for entry in audit_module.AuditLogger(audit_path).read_all()]
            self.assertIn("query", logged_actions)

    def test_query_handoff_writes_structured_audit_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            fake_config = SimpleNamespace(
                sensitive_actions=[],
                directories={
                    "audit_log": str(audit_path),
                    "state_dir": str(Path(tmp) / "state"),
                    "workflow_runtime_dir": str(Path(tmp) / "workflow-runtime"),
                },
            )
            fake_policy = SimpleNamespace(
                is_allowed=lambda actor, action: action == "query.handoff" and actor == "viewer"
            )

            class FakeHandoffStore:
                def __init__(self, *_args, **_kwargs):
                    pass

                def list_records(self, workflow_id=None, target_agent=None, status=None):
                    del workflow_id, target_agent, status
                    return [
                        {
                            "message_id": "msg-1",
                            "workflow_id": "wf-1",
                            "target_agent": "backend-1",
                            "status": "materialized",
                        },
                        {
                            "message_id": "msg-1",
                            "workflow_id": "wf-1",
                            "target_agent": "backend-1",
                            "status": "failed",
                        },
                    ]

            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(
                    unified_cli_module,
                    "build_default_rbac_policy",
                    return_value=fake_policy,
                ):
                    with patch.object(unified_cli_module, "ApprovalGate"):
                        with patch.object(
                            unified_cli_module,
                            "HandoffRunStore",
                            FakeHandoffStore,
                            create=True,
                        ):
                            unified_cli_module.main(
                                [
                                    "query",
                                    "handoff",
                                    "--workflow-id",
                                    "wf-1",
                                    "--message-id",
                                    "msg-1",
                                    "--status",
                                    "materialized",
                                    "--target-agent",
                                    "backend-1",
                                    "--actor",
                                    "viewer",
                                ]
                            )

            query_events = [
                entry
                for entry in audit_module.AuditLogger(audit_path).read_all()
                if entry["action"] == "query"
            ]
            self.assertEqual(len(query_events), 1)
            self.assertEqual(
                query_events[0]["filters"],
                {
                    "id": None,
                    "workflow_id": "wf-1",
                    "message_id": "msg-1",
                    "target_agent": "backend-1",
                    "status": "materialized",
                    "action": None,
                },
            )
            self.assertEqual(query_events[0]["result_count"], 1)

    def test_main_without_command_prints_help(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = unified_cli_module.main([])

        self.assertIsNone(result)
        self.assertIn("control-plane-run", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
