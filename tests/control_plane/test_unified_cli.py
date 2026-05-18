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
import governance.audit as audit_module  # noqa: E402
import runtime.rules as runtime_rules_module  # noqa: E402


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
                return "architect", SimpleNamespace(
                    id="task-1",
                    routing_reason={
                        "knowledge_recommendation": {
                            "load_order": ["team", "role", "instance"],
                            "team": [".hermes/team/knowledge/status.md"],
                            "role": [".hermes/agents/architect/knowledge/status.md"],
                            "instance": [".hermes/team/agents/architect/knowledge/expertise.md"],
                        }
                    },
                )

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
        self.assertEqual(
            payload["knowledge_recommendation"]["load_order"],
            ["team", "role", "instance"],
        )
        self.assertEqual(
            payload["knowledge_bundle"],
            runtime_rules_module.build_knowledge_bundle(payload["knowledge_recommendation"]),
        )

    def test_dispatch_command_execute_calls_execution_helper(self):
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
            agents = {"architect": object()}

            def route_task(self, task, priority):
                return "architect", SimpleNamespace(id="task-2", routing_reason={})

        fake_audit = SimpleNamespace(log=lambda action, payload: observed["audit"].append((action, payload)))
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
            default_executor="hermes",
        )
        fake_policy = SimpleNamespace(is_allowed=lambda actor, action: True)

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(unified_cli_module, "TaskRouter", return_value=FakeRouter()):
                            with patch.object(unified_cli_module, "get_bus", return_value=FakeBus()):
                                with patch.object(
                                    unified_cli_module,
                                    "execute_dispatch_task",
                                    return_value={"success": True, "stdout": "ok"},
                                ) as execute_mock:
                                    payload = unified_cli_module.main(
                                        ["dispatch", "设计接口", "--actor", "admin", "--priority", "high", "--execute"]
                                    )

        self.assertEqual(payload["execution"]["success"], True)
        execute_mock.assert_called_once()

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
                            "_execute_workflow_definition",
                            return_value={"workflow_id": "project_delivery", "success": True},
                        ):
                            with patch.object(
                                unified_cli_module,
                                "default_workflow_definition_path",
                                return_value=Path("/workspace/.hermes/workflows/project_delivery.json"),
                            ):
                                result = unified_cli_module.main(
                                    ["control-plane-run", "--max-workers", "3"]
                                )

        self.assertEqual(result["workflow_id"], "project_delivery")
        self.assertEqual(observed["action"], "control-plane-run")
        self.assertEqual(observed["max_workers"], 3)

    def test_validate_command_calls_real_load_validation(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "artifacts_dir": "artifacts",
            },
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
        validation_mock.assert_called_once()
        self.assertEqual(validation_mock.call_args.kwargs["replicas"], 2)
        self.assertEqual(validation_mock.call_args.kwargs["max_workers"], 5)
        self.assertIn("state_dir", validation_mock.call_args.kwargs)
        self.assertIn("events_dir", validation_mock.call_args.kwargs)

    def test_execute_dispatch_task_persists_successful_state(self):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fake_config = SimpleNamespace(
                directories={
                    "state_dir": str(base / "state"),
                    "events_dir": str(base / "events"),
                },
                default_executor="hermes",
            )

            outcome = unified_cli_module.execute_dispatch_task(
                task_id="task-execute-1",
                task_text="设计接口",
                agent_id="architect",
                backend="hermes",
                config=fake_config,
                command_runner=lambda command: Result(),
            )

            snapshot = json.loads((base / "state" / "task-execute-1.json").read_text(encoding="utf-8"))

        self.assertTrue(outcome["success"])
        self.assertEqual(snapshot["status"], "done")
        self.assertEqual(
            outcome["command"],
            ["hermes", "team", "dispatch", "-a", "architect", "-t", "设计接口"],
        )

    def test_execute_dispatch_task_falls_back_when_command_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fake_config = SimpleNamespace(
                directories={
                    "state_dir": str(base / "state"),
                    "events_dir": str(base / "events"),
                },
                default_executor="hermes",
            )

            with patch.object(
                unified_cli_module.subprocess,
                "run",
                side_effect=FileNotFoundError("missing hermes"),
            ):
                outcome = unified_cli_module.execute_dispatch_task(
                    task_id="task-execute-fallback",
                    task_text="设计接口",
                    agent_id="architect",
                    backend="hermes",
                    config=fake_config,
                )

            snapshot = json.loads((base / "state" / "task-execute-fallback.json").read_text(encoding="utf-8"))

        self.assertTrue(outcome["success"])
        self.assertEqual(snapshot["status"], "done")
        self.assertEqual(outcome["runner_mode"], "dry-run-fallback")

    def test_validate_command_marks_failed_checks_as_unsuccessful(self):
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
                            return_value={
                                "summary": {"done_tasks": [], "failed_tasks": [], "blocked_tasks": [], "conflicted_tasks": [], "rounds": 0},
                                "checks": {
                                    "all_tasks_done": False,
                                    "no_failed_tasks": True,
                                    "no_blocked_tasks": True,
                                    "no_conflicted_tasks": True,
                                },
                            },
                        ):
                            result = unified_cli_module.main(["validate"])

        self.assertFalse(result["success"])

    def test_main_exits_nonzero_when_validate_reports_failure(self):
        with patch.object(unified_cli_module, "main", return_value={"success": False}):
            with self.assertRaises(SystemExit) as exc:
                exec(
                    "if __name__ == '__main__':\n    result = main()\n    raise SystemExit(0 if (result is None or result.get('success', True)) else 1)\n",
                    {"__name__": "__main__", "main": unified_cli_module.main, "SystemExit": SystemExit},
                )

        self.assertEqual(exc.exception.code, 1)

    def test_workflow_command_returns_engine_result(self):
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
                            "_execute_workflow_definition",
                            return_value={
                                "success": True,
                                "workflow_id": "wf-1",
                                "step_contexts": {"step-1": {"summary": "done"}},
                                "handoffs": [],
                            },
                        ):
                            with patch.object(
                                unified_cli_module,
                                "default_workflow_definition_path",
                                return_value=Path("/workspace/.hermes/workflows/project_delivery.json"),
                            ):
                                result = unified_cli_module.main(
                                    ["workflow", "--name", "demo-project"]
                                )

        self.assertTrue(result["success"])
        self.assertEqual(result["workflow_id"], "wf-1")
        self.assertIn("step_contexts", result)
        self.assertIn("handoffs", result)

    def test_workflow_command_uses_prototype_definition_when_requested(self):
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
                            "_execute_workflow_definition",
                            return_value={"success": True, "workflow_id": "wf-prototype"},
                        ) as execute_mock:
                            with patch.object(
                                unified_cli_module,
                                "prototype_workflow_definition_path",
                                return_value=Path("/workspace/.hermes/workflows/prototype_delivery.json"),
                            ):
                                result = unified_cli_module.main(
                                    ["workflow", "--name", "demo-project", "--prototype"]
                                )

        self.assertTrue(result["success"])
        self.assertEqual(result["workflow_id"], "wf-prototype")
        self.assertEqual(
            execute_mock.call_args.kwargs["workflow_path"],
            Path("/workspace/.hermes/workflows/prototype_delivery.json"),
        )

    def test_workflow_command_injects_auto_approvals_for_human_steps(self):
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
                            "_execute_workflow_definition",
                            return_value={"success": True, "workflow_id": "wf-auto"},
                        ) as execute_mock:
                            with patch.object(
                                unified_cli_module,
                                "load_workflow_definition",
                                return_value={
                                    "workflow_id": "project_delivery",
                                    "steps": [
                                        {"id": "requirement_confirmation", "type": "human"},
                                        {"id": "requirements_analysis", "type": "sequential"},
                                    ],
                                },
                            ):
                                with patch.object(
                                    unified_cli_module,
                                    "default_workflow_definition_path",
                                    return_value=Path("/workspace/.hermes/workflows/project_delivery.json"),
                                ):
                                    result = unified_cli_module.main(
                                        ["workflow", "--name", "demo-project", "--auto-approve"]
                                    )

        self.assertTrue(result["success"])
        self.assertEqual(
            execute_mock.call_args.kwargs["context"]["approvals"]["requirement_confirmation"]["approved"],
            True,
        )

    def test_workflow_command_auto_approve_injects_governance_bypass_context(self):
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
                            "_execute_workflow_definition",
                            return_value={"success": True, "workflow_id": "wf-auto"},
                        ) as execute_mock:
                            with patch.object(
                                unified_cli_module,
                                "load_workflow_definition",
                                return_value={
                                    "workflow_id": "project_delivery",
                                    "steps": [
                                        {
                                            "id": "requirements_review",
                                            "type": "human",
                                            "entry_checks": {
                                                "required_deliverables": ["PRD.md"],
                                                "approval_required": True,
                                                "coverage_threshold": {"backend": 70},
                                                "test_pass_rate": 100,
                                            },
                                        }
                                    ],
                                },
                            ):
                                with patch.object(
                                    unified_cli_module,
                                    "default_workflow_definition_path",
                                    return_value=Path("/workspace/.hermes/workflows/project_delivery.json"),
                                ):
                                    unified_cli_module.main(
                                        ["workflow", "--name", "demo-project", "--auto-approve"]
                                    )

        context = execute_mock.call_args.kwargs["context"]
        self.assertIn("PRD.md", context["deliverables"])
        self.assertEqual(context["quality_gates"]["coverage"]["backend"], 70)
        self.assertEqual(context["quality_gates"]["test_pass_rate"], 100)

    def test_workflow_command_surfaces_knowledge_bundles(self):
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
                            "_execute_workflow_definition",
                            return_value={
                                "success": True,
                                "workflow_id": "wf-knowledge",
                                "step_contexts": {"step-1": {"summary": "done"}},
                                "knowledge_recommendations": {
                                    "step-1": {
                                        "load_order": ["team", "role", "instance"],
                                        "team": [".hermes/team/knowledge/status.md"],
                                        "role": [".hermes/agents/architect/knowledge/status.md"],
                                        "instance": [".hermes/team/agents/architect/knowledge/expertise.md"],
                                    }
                                },
                                "knowledge_bundles": {
                                    "step-1": runtime_rules_module.build_knowledge_bundle(
                                        {
                                            "load_order": ["team", "role", "instance"],
                                            "team": [".hermes/team/knowledge/status.md"],
                                            "role": [".hermes/agents/architect/knowledge/status.md"],
                                            "instance": [".hermes/team/agents/architect/knowledge/expertise.md"],
                                        }
                                    )
                                },
                                "handoffs": [],
                            },
                        ):
                            with patch.object(
                                unified_cli_module,
                                "default_workflow_definition_path",
                                return_value=Path("/workspace/.hermes/workflows/project_delivery.json"),
                            ):
                                result = unified_cli_module.main(
                                    ["workflow", "--name", "knowledge-demo"]
                                )

        self.assertIn("knowledge_bundles", result)
        self.assertEqual(
            result["knowledge_bundles"]["step-1"],
            runtime_rules_module.build_knowledge_bundle(
                result["knowledge_recommendations"]["step-1"]
            ),
        )

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

    def test_query_handoff_supports_knowledge_summary_view(self):
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
                "knowledge_recommendation": {
                    "team": [".hermes/team/knowledge/status.md"],
                    "role": [".hermes/agents/backend-dev/knowledge/status.md"],
                    "instance": [".hermes/team/agents/backend-1/knowledge/expertise.md"],
                },
            },
            {
                "message_id": "msg-2",
                "workflow_id": "wf-1",
                "target_agent": "backend-2",
                "status": "materialized",
                "knowledge_recommendation": None,
            },
        ]

        class FakeHandoffStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def list_records(self, workflow_id=None, target_agent=None, status=None, message_id=None):
                del workflow_id, target_agent, status, message_id
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
                                    "--knowledge-only",
                                    "--summary",
                                    "--actor",
                                    "viewer",
                                ]
                            )

        self.assertEqual(result["summary"]["knowledge_record_count"], 1)
        self.assertIn(".hermes/team/knowledge/status.md", result["summary"]["top_knowledge_paths"])

    def test_query_knowledge_uses_dedicated_resource(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: action == "query.knowledge" and actor == "viewer"
        )
        fake_audit = SimpleNamespace(log=lambda *args: None)

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                        with patch.object(
                            unified_cli_module,
                            "query_knowledge_records",
                            return_value={
                                "filters": {"review_status": "pending_review"},
                                "records": [{"entry_id": "gov-1"}],
                                "summary": {"record_count": 1},
                                "aggregations": {"by_review_status": {"pending_review": 1}},
                            },
                        ) as query_mock:
                            result = unified_cli_module.main(
                                [
                                    "query",
                                    "knowledge",
                                    "--search",
                                    "统一批入口",
                                    "--review-status",
                                    "pending_review",
                                    "--actor",
                                    "viewer",
                                ]
                            )

        self.assertEqual(result["summary"]["record_count"], 1)
        query_mock.assert_called_once()

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
                    "continuation_status": None,
                    "continued_at": None,
                    "continuation_workflow_id": None,
                    "continuation_ready_steps": [],
                    "continuation_completed_steps": [],
                    "continuation_failed_steps": [],
                }
            ],
        )

    def test_query_handoff_exposes_continuation_metadata_keys(self):
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
                        "status": "dispatched",
                        "continuation_status": "continued",
                        "continued_at": 456.0,
                    }
                ]

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
                                ["query", "handoff", "--message-id", "msg-1", "--actor", "viewer"]
                            )

        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["continuation_status"], "continued")
        self.assertEqual(result["records"][0]["continuation_workflow_id"], "wf-1")
        self.assertEqual(result["records"][0]["continued_at"], 456.0)
        self.assertEqual(result["records"][0]["continuation_ready_steps"], [])
        self.assertEqual(result["records"][0]["continuation_completed_steps"], [])
        self.assertEqual(result["records"][0]["continuation_failed_steps"], [])

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

    def test_query_workflow_supports_knowledge_only_summary_view(self):
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
                return {
                    "workflow_id": workflow_id,
                    "status": "completed",
                    "knowledge_feedback": {
                        "appended_decisions": ["d1"],
                        "appended_risks": ["r1"],
                    },
                    "knowledge_usage": {
                        "summary": {
                            "recommended_paths": ["a.md", "b.md"],
                            "consumed_paths": ["a.md"],
                            "unused_paths": ["b.md"],
                            "feedback_score": 0.75,
                        }
                    },
                }

            def list_step_events(self, workflow_id):
                return [{"workflow_id": workflow_id, "event": "completed"}]

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
                                [
                                    "query",
                                    "workflow",
                                    "--id",
                                    "wf-1",
                                    "--knowledge-only",
                                    "--summary",
                                    "--actor",
                                    "viewer",
                                ]
                            )

        self.assertEqual(result["summary"]["knowledge_feedback"]["decision_count"], 1)
        self.assertEqual(result["summary"]["knowledge_feedback"]["risk_count"], 1)
        self.assertEqual(result["summary"]["knowledge_usage"]["recommended_count"], 2)
        self.assertEqual(result["summary"]["knowledge_usage"]["consumed_count"], 1)
        self.assertEqual(result["summary"]["knowledge_usage"]["unused_count"], 1)
        self.assertEqual(result["summary"]["knowledge_usage"]["feedback_score"], 0.75)
        self.assertEqual(result["snapshot"]["workflow_id"], "wf-1")

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

    def test_query_handoff_prune_removes_filtered_runtime_records_and_audits(self):
        observed = {"audit": []}
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.handoff", "query.handoff.manage"}
        )
        fake_audit = SimpleNamespace(log=lambda action, payload: observed["audit"].append((action, payload)))

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="handoff",
                    id=None,
                    workflow_id="wf-1",
                    message_id=None,
                    target_agent=None,
                    status="failed",
                    action=None,
                    actor="operator",
                    prune=True,
                    archive=False,
                    delete=False,
                )

            def print_help(self):
                return None

        class FakeHandoffStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def list_records(self, workflow_id=None, target_agent=None, status=None):
                return [
                    {
                        "message_id": "msg-1",
                        "workflow_id": workflow_id,
                        "target_agent": target_agent,
                        "status": status,
                    }
                ]

            def prune_records(self, workflow_id=None, message_id=None, target_agent=None, status=None):
                self.last_prune = {
                    "workflow_id": workflow_id,
                    "message_id": message_id,
                    "target_agent": target_agent,
                    "status": status,
                }
                return 2

            def delete_records(self, workflow_id=None, target_agent=None, status=None):
                self.last_delete = {
                    "workflow_id": workflow_id,
                    "target_agent": target_agent,
                    "status": status,
                }
                return 2

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(
                        unified_cli_module,
                        "ApprovalGate",
                        return_value=SimpleNamespace(requires_approval=lambda *_: False),
                    ):
                        with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                            with patch.object(
                                unified_cli_module,
                                "HandoffRunStore",
                                FakeHandoffStore,
                                create=True,
                            ):
                                result = unified_cli_module.main(["query", "handoff", "--prune"])

        self.assertEqual(result.get("deleted_count"), 2)
        self.assertEqual(observed["audit"][0][0], "handoff.prune")
        self.assertEqual(observed["audit"][0][1]["status"], "failed")

    def test_query_workflow_archive_uses_manage_permission_and_returns_archive_path(self):
        observed = {"audit": []}
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.workflow", "query.workflow.manage"}
        )
        fake_audit = SimpleNamespace(log=lambda action, payload: observed["audit"].append((action, payload)))

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="workflow",
                    id="wf-1",
                    workflow_id=None,
                    message_id=None,
                    target_agent=None,
                    status=None,
                    action=None,
                    actor="operator",
                    prune=False,
                    archive=True,
                    delete=False,
                )

            def print_help(self):
                return None

        class FakeWorkflowStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def read_snapshot(self, workflow_id):
                return {"workflow_id": workflow_id, "status": "running"}

            def list_step_events(self, workflow_id):
                return [{"workflow_id": workflow_id, "event": "running"}]

            def archive_workflow(self, workflow_id):
                self.last_workflow_id = workflow_id
                return {
                    "workflow_id": workflow_id,
                    "archive_path": "archives/wf-1.zip",
                    "archived_files": 2,
                }

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(
                        unified_cli_module,
                        "ApprovalGate",
                        return_value=SimpleNamespace(requires_approval=lambda *_: False),
                    ):
                        with patch.object(unified_cli_module, "AuditLogger", return_value=fake_audit):
                            with patch.object(
                                unified_cli_module,
                                "WorkflowRunStore",
                                FakeWorkflowStore,
                                create=True,
                            ):
                                result = unified_cli_module.main(["query", "workflow", "--archive"])

        self.assertEqual(result.get("archive_path"), "archives/wf-1.zip")
        self.assertEqual(result.get("archived_files"), 2)
        self.assertEqual(observed["audit"][0][0], "workflow.archive")
        self.assertEqual(observed["audit"][0][1]["workflow_id"], "wf-1")

    def test_query_handoff_prune_requires_operator_or_admin(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "viewer" and action == "query.handoff"
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="handoff",
                    id=None,
                    workflow_id=None,
                    message_id=None,
                    target_agent=None,
                    status="failed",
                    action=None,
                    actor="viewer",
                    prune=True,
                    archive=False,
                    delete=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(
                        unified_cli_module,
                        "ApprovalGate",
                        return_value=SimpleNamespace(requires_approval=lambda *_: False),
                    ):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaises(PermissionError):
                                unified_cli_module.main(["query", "handoff", "--prune"])

    def test_extract_knowledge_recommendation_returns_none_for_non_mapping_reason(self):
        task = SimpleNamespace(routing_reason="not-a-dict")

        self.assertIsNone(unified_cli_module._extract_knowledge_recommendation(task))

    def test_build_knowledge_bundles_skips_non_mapping_recommendations(self):
        result = {
            "knowledge_recommendations": {
                "step-1": {
                    "load_order": ["team", "role", "instance"],
                    "team": [".hermes/team/knowledge/status.md"],
                    "role": [".hermes/agents/architect/knowledge/status.md"],
                    "instance": [".hermes/team/agents/architect/knowledge/expertise.md"],
                },
                "step-2": "skip-me",
            }
        }

        bundles = unified_cli_module._build_knowledge_bundles(result)

        self.assertEqual(list(bundles.keys()), ["step-1"])

    def test_workflow_knowledge_payload_keeps_recommendations_and_bundles(self):
        payload = {
            "snapshot": {
                "workflow_id": "wf-1",
                "status": "completed",
                "knowledge_feedback": {"appended_decisions": ["d1"], "appended_risks": []},
                "knowledge_recommendations": {"step-1": {"team": ["a.md"]}},
                "knowledge_bundles": {"step-1": {"paths": ["a.md"]}},
            },
            "events": [{"workflow_id": "wf-1", "event": "completed"}],
        }

        result = unified_cli_module._workflow_knowledge_payload(payload)

        self.assertEqual(result["snapshot"]["knowledge_recommendations"]["step-1"]["team"], ["a.md"])
        self.assertEqual(result["snapshot"]["knowledge_bundles"]["step-1"]["paths"], ["a.md"])

    def test_load_workflow_context_reads_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            context_path = Path(tmp) / "context.json"
            context_path.write_text('{"project_name": "demo"}', encoding="utf-8")

            result = unified_cli_module._load_workflow_context(str(context_path))

        self.assertEqual(result, {"project_name": "demo"})

    def test_run_tool_command_resume_requires_session_id(self):
        with self.assertRaisesRegex(ValueError, "--resume requires --session-id"):
            unified_cli_module.run_tool_command(tool_name="read_knowledge", task="demo", resume=True)

    def test_query_workflow_manage_rejects_multiple_actions(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.workflow", "query.workflow.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="workflow",
                    id="wf-1",
                    workflow_id=None,
                    message_id=None,
                    target_agent=None,
                    status=None,
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=True,
                    archive=True,
                    delete=False,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(unified_cli_module, "ApprovalGate"):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(
                                ValueError, "workflow manage supports one action at a time"
                            ):
                                unified_cli_module.main(["query", "workflow", "--prune", "--archive"])

    def test_query_workflow_manage_requires_id_for_archive(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.workflow", "query.workflow.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="workflow",
                    id=None,
                    workflow_id=None,
                    message_id=None,
                    target_agent=None,
                    status=None,
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=False,
                    archive=True,
                    delete=False,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(unified_cli_module, "ApprovalGate"):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(ValueError, "workflow manage requires --id"):
                                unified_cli_module.main(["query", "workflow", "--archive"])

    def test_query_workflow_prune_requires_approval(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.workflow", "query.workflow.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="workflow",
                    id=None,
                    workflow_id=None,
                    message_id=None,
                    target_agent=None,
                    status="completed",
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=True,
                    archive=False,
                    delete=False,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(
                        unified_cli_module,
                        "ApprovalGate",
                        return_value=SimpleNamespace(
                            requires_approval=lambda action: action == "workflow.prune"
                        ),
                    ):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(
                                PermissionError, "workflow prune requires approval"
                            ):
                                unified_cli_module.main(["query", "workflow", "--prune"])

    def test_query_handoff_manage_rejects_multiple_actions(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.handoff", "query.handoff.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="handoff",
                    id=None,
                    workflow_id="wf-1",
                    message_id=None,
                    target_agent=None,
                    status="failed",
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=True,
                    archive=True,
                    delete=False,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(unified_cli_module, "ApprovalGate"):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(
                                ValueError, "handoff manage supports one action at a time"
                            ):
                                unified_cli_module.main(["query", "handoff", "--prune", "--archive"])

    def test_query_handoff_manage_requires_at_least_one_filter(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.handoff", "query.handoff.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="handoff",
                    id=None,
                    workflow_id=None,
                    message_id=None,
                    target_agent=None,
                    status=None,
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=False,
                    archive=False,
                    delete=True,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(unified_cli_module, "ApprovalGate"):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(
                                ValueError, "handoff manage requires at least one filter"
                            ):
                                unified_cli_module.main(["query", "handoff", "--delete"])

    def test_query_handoff_archive_requires_approval(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.handoff", "query.handoff.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="handoff",
                    id=None,
                    workflow_id="wf-1",
                    message_id=None,
                    target_agent=None,
                    status="materialized",
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=False,
                    archive=True,
                    delete=False,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(
                        unified_cli_module,
                        "ApprovalGate",
                        return_value=SimpleNamespace(
                            requires_approval=lambda action: action == "handoff.archive"
                        ),
                    ):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(
                                PermissionError, "handoff archive requires approval"
                            ):
                                unified_cli_module.main(["query", "handoff", "--archive"])

    def test_query_handoff_delete_requires_approval(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "handoff_runtime_dir": "handoff-runtime",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: actor == "operator"
            and action in {"query.handoff", "query.handoff.manage"}
        )

        class FakeParser:
            def parse_args(self, _argv):
                return SimpleNamespace(
                    command="query",
                    resource="handoff",
                    id=None,
                    workflow_id="wf-1",
                    message_id=None,
                    target_agent=None,
                    status="materialized",
                    action=None,
                    agent=None,
                    role=None,
                    task_type=None,
                    risk_tag=None,
                    review_status=None,
                    search=None,
                    actor="operator",
                    prune=False,
                    archive=False,
                    delete=True,
                    knowledge_only=False,
                    summary=False,
                )

            def print_help(self):
                return None

        with patch.object(unified_cli_module, "build_parser", return_value=FakeParser()):
            with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
                with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                    with patch.object(
                        unified_cli_module,
                        "ApprovalGate",
                        return_value=SimpleNamespace(
                            requires_approval=lambda action: action == "handoff.delete"
                        ),
                    ):
                        with patch.object(unified_cli_module, "AuditLogger"):
                            with self.assertRaisesRegex(
                                PermissionError, "handoff delete requires approval"
                            ):
                                unified_cli_module.main(["query", "handoff", "--delete"])

    def test_query_knowledge_action_applies_governance_directly(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
                "workflow_runtime_dir": "workflow-runtime",
            },
        )
        fake_policy = SimpleNamespace(
            is_allowed=lambda actor, action: action == "query.knowledge" and actor == "viewer"
        )

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(unified_cli_module, "build_default_rbac_policy", return_value=fake_policy):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger"):
                        with patch.object(
                            unified_cli_module,
                            "apply_governance_action",
                            return_value={"ok": True, "entry_id": "gov-1"},
                        ) as action_mock:
                            result = unified_cli_module.main(
                                [
                                    "query",
                                    "knowledge",
                                    "--action",
                                    "accept",
                                    "--id",
                                    "gov-1",
                                    "--actor",
                                    "viewer",
                                ]
                            )

        self.assertEqual(result, {"ok": True, "entry_id": "gov-1"})
        action_mock.assert_called_once()

    def test_monitor_dashboard_enriches_payload_with_knowledge_metrics(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={"audit_log": "audit-log.jsonl"},
        )
        fake_monitor = SimpleNamespace(
            get_dashboard_data=lambda: {"queue_depth": 3},
            task_router="router",
            workflow_runtime_dir="workflow-runtime",
        )

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                unified_cli_module,
                "build_default_rbac_policy",
                return_value=SimpleNamespace(is_allowed=lambda *_: True),
            ):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger"):
                        with patch.object(unified_cli_module, "get_monitor", return_value=fake_monitor):
                            with patch.object(
                                unified_cli_module,
                                "build_knowledge_heat_ranking",
                                return_value=[{"path": "a.md", "count": 2}],
                            ):
                                with patch.object(
                                    unified_cli_module,
                                    "build_consumption_by_agent",
                                    return_value={"architect": 1},
                                ):
                                    with patch.object(
                                        unified_cli_module,
                                        "build_unused_recommendations",
                                        return_value=["unused.md"],
                                    ):
                                        with patch.object(
                                            unified_cli_module,
                                            "build_high_risk_coverage",
                                            return_value={"covered": 2},
                                        ):
                                                with patch.object(
                                                    unified_cli_module,
                                                    "build_knowledge_effectiveness_report",
                                                    return_value={"average_feedback_score": 0.8},
                                                ):
                                                    with patch.object(
                                                        unified_cli_module,
                                                        "build_pending_governance_counts",
                                                        return_value={"pending_review": 1},
                                                    ):
                                                        result = unified_cli_module.main(["monitor", "--dashboard"])

        self.assertEqual(result["queue_depth"], 3)
        self.assertEqual(result["knowledge_heat_ranking"][0]["path"], "a.md")
        self.assertEqual(result["knowledge_consumption_by_agent"]["architect"], 1)
        self.assertEqual(result["unused_recommendations"], ["unused.md"])
        self.assertEqual(result["high_risk_workflow_coverage"]["covered"], 2)
        self.assertEqual(result["knowledge_effectiveness_report"]["average_feedback_score"], 0.8)
        self.assertEqual(result["pending_governance_counts"]["pending_review"], 1)

    def test_tool_session_list_and_default_paths_return_sessions(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
            },
        )

        class FakeSessionStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def list_sessions(self):
                return [{"session_id": "session-1"}]

            def read_session(self, session_id):
                return {"session_id": session_id}

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                unified_cli_module,
                "build_default_rbac_policy",
                return_value=SimpleNamespace(is_allowed=lambda *_: True),
            ):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger"):
                        with patch.object(unified_cli_module, "SessionStore", FakeSessionStore):
                            listed = unified_cli_module.main(["tool-session", "list"])
                            defaulted = unified_cli_module.main(["tool-session"])

        self.assertEqual(listed, {"sessions": [{"session_id": "session-1"}]})
        self.assertEqual(defaulted, {"sessions": [{"session_id": "session-1"}]})

    def test_tool_session_get_reads_target_session(self):
        fake_config = SimpleNamespace(
            sensitive_actions=[],
            directories={
                "audit_log": "audit-log.jsonl",
                "state_dir": "state",
            },
        )

        class FakeSessionStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def list_sessions(self):
                return [{"session_id": "session-1"}]

            def read_session(self, session_id):
                return {"session_id": session_id, "status": "done"}

        with patch.object(unified_cli_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                unified_cli_module,
                "build_default_rbac_policy",
                return_value=SimpleNamespace(is_allowed=lambda *_: True),
            ):
                with patch.object(unified_cli_module, "ApprovalGate"):
                    with patch.object(unified_cli_module, "AuditLogger"):
                        with patch.object(unified_cli_module, "SessionStore", FakeSessionStore):
                            result = unified_cli_module.main(
                                ["tool-session", "get", "--session-id", "session-9"]
                            )

        self.assertEqual(result, {"session_id": "session-9", "status": "done"})

    def test_main_without_command_prints_help(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = unified_cli_module.main([])

        self.assertIsNone(result)
        self.assertIn("control-plane-run", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
