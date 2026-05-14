import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path, load_framework_module

ensure_control_plane_path()
import config as config_module  # noqa: E402

task_router_module = load_framework_module("task_router")
monitor_module = load_framework_module("monitor")


class ConfigCenterTests(unittest.TestCase):
    def setUp(self):
        config_module.load_control_plane_config.cache_clear()

    def test_default_config_exposes_agents_groups_thresholds_and_executors(self):
        config = config_module.load_control_plane_config()

        self.assertIn("architect", config.agents)
        self.assertIn("backend", config.groups)
        self.assertIn("agent_load_high", config.thresholds)
        self.assertIn("hermes", config.executors)
        self.assertEqual(config.default_executor, "hermes")

    def test_task_router_uses_centralized_agent_config(self):
        router = task_router_module.TaskRouter()

        self.assertIn("architect", router.agents)
        self.assertEqual(router.agents["architect"].name, "张欣怡")

    def test_monitor_uses_centralized_thresholds(self):
        monitor = monitor_module.Monitor()

        self.assertAlmostEqual(monitor.thresholds["agent_load_high"], 0.8)

    def test_override_config_deep_merges_agents_thresholds_and_executor(self):
        with tempfile.TemporaryDirectory() as tmp:
            override_path = Path(tmp) / "control-plane-config.json"
            override_path.write_text(
                json.dumps(
                    {
                        "thresholds": {"agent_load_high": 0.9},
                        "executors": {"openclaw": {"mode": "live"}},
                        "feature_flags": {"metrics_enabled": False},
                        "default_executor": "openclaw",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            config = config_module.load_control_plane_config(str(override_path))

        self.assertAlmostEqual(config.thresholds["agent_load_high"], 0.9)
        self.assertEqual(config.executors["openclaw"]["mode"], "live")
        self.assertFalse(config.feature_flags["metrics_enabled"])
        self.assertEqual(config.default_executor, "openclaw")

    def test_to_dict_contains_directory_alias_and_agent_metadata(self):
        config = config_module.load_control_plane_config()

        payload = config.to_dict()

        self.assertIn("state_dir", payload["directories"])
        self.assertEqual(payload["aliases"]["后端"], "backend-1")
        self.assertEqual(payload["agents"]["architect"]["name"], "张欣怡")

    def test_load_control_plane_config_ignores_metrics_failures(self):
        config_module.load_control_plane_config.cache_clear()

        with patch("observability.metrics.get_metrics_registry", side_effect=RuntimeError("boom")):
            config = config_module.load_control_plane_config()

        self.assertIn("architect", config.agents)


if __name__ == "__main__":
    unittest.main()
