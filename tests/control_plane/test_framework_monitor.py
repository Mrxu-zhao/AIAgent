import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
monitor_module = load_framework_module("monitor")


class MonitorRegressionTests(unittest.TestCase):
    def test_dashboard_returns_without_deadlock(self):
        monitor = monitor_module.Monitor()
        result = {"done": False}

        def run():
            monitor.get_dashboard_data()
            result["done"] = True

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(1.0)

        self.assertTrue(result["done"], "dashboard 璋冪敤搴斿湪 1 绉掑唴杩斿洖")

    def test_dashboard_exposes_recommended_knowledge_and_recent_feedback(self):
        router_module = load_framework_module("task_router")
        router = router_module.TaskRouter()
        router.route_task("请 backend-1 处理 redis cache 一致性问题")

        with tempfile.TemporaryDirectory() as tmp:
            workflow_runtime_dir = Path(tmp) / "workflow_runtime"
            snapshots_dir = workflow_runtime_dir / "snapshots"
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            (snapshots_dir / "wf-1.json").write_text(
                json.dumps(
                    {
                        "workflow_id": "wf-1",
                        "status": "completed",
                        "knowledge_feedback": {
                            "appended_decisions": ["d1"],
                            "appended_risks": ["r1"],
                        },
                        "knowledge_usage": {
                            "summary": {
                                "consumed_paths": [".hermes/team/knowledge/status.md"],
                                "unused_paths": [],
                                "feedback_score": 0.6,
                            },
                            "steps": [{"step_id": "implement"}],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_config = type(
                "Config",
                (),
                {
                    "thresholds": {"agent_load_high": 0.8, "error_rate_high": 0.1},
                    "directories": {"workflow_runtime_dir": str(workflow_runtime_dir)},
                },
            )()

            with patch.object(monitor_module, "load_control_plane_config", return_value=fake_config):
                monitor = monitor_module.Monitor(task_router=router)
                dashboard = monitor.get_dashboard_data()

        self.assertIn("recommended_knowledge", dashboard)
        self.assertTrue(dashboard["recommended_knowledge"])
        self.assertIn("recent_knowledge_feedback", dashboard)
        self.assertEqual(dashboard["recent_knowledge_feedback"][0]["workflow_id"], "wf-1")
        self.assertIn("knowledge_effectiveness_report", dashboard)
        self.assertEqual(dashboard["knowledge_effectiveness_report"]["average_feedback_score"], 0.6)

    def test_dashboard_includes_hermes_health_summary(self):
        fake_config = type(
            "Config",
            (),
            {
                "thresholds": {"agent_load_high": 0.8, "error_rate_high": 0.1},
                "directories": {"workflow_runtime_dir": ""},
                "executors": {"hermes": {"command": "hermes"}},
            },
        )()

        with patch.object(monitor_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                monitor_module,
                "check_hermes_health",
                return_value=type(
                    "Report",
                    (),
                    {
                        "ok": True,
                        "status": "healthy",
                        "message": "ok",
                        "available_commands": ["chat", "team"],
                    },
                )(),
            ):
                monitor = monitor_module.Monitor()
                dashboard = monitor.get_dashboard_data()

        self.assertIn("hermes_health", dashboard)
        self.assertEqual(dashboard["hermes_health"]["status"], "healthy")
        self.assertEqual(dashboard["hermes_health"]["available_commands"], ["chat", "team"])


if __name__ == "__main__":
    unittest.main()
