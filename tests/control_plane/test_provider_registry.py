import unittest
from pathlib import Path
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import providers.registry as registry_module  # noqa: E402


class ProviderRegistryTests(unittest.TestCase):
    def test_registry_returns_hermes_and_openclaw_providers(self):
        registry = registry_module.build_default_provider_registry()

        self.assertIn("hermes", registry.list_providers())
        self.assertIn("openclaw", registry.list_providers())

    def test_openclaw_provider_supports_dry_run_dispatch(self):
        registry = registry_module.build_default_provider_registry()
        provider = registry.get("openclaw")

        command = provider.build_dispatch_command("backend-1", "implement api")

        self.assertIn("backend-1", " ".join(command))

    def test_openclaw_provider_supports_live_dispatch_when_configured(self):
        fake_config = type(
            "Config",
            (),
            {
                "executors": {
                    "hermes": {"command": "hermes"},
                    "openclaw": {
                        "command": "openclaw-live",
                        "mode": "live",
                        "dispatch_args": ["task", "run"],
                    },
                }
            },
        )()

        with patch.object(registry_module, "load_control_plane_config", return_value=fake_config):
            registry = registry_module.build_default_provider_registry()

        provider = registry.get("openclaw")
        command = provider.build_dispatch_command("backend-2", "ship feature")

        self.assertEqual(command[0], "openclaw-live")
        self.assertIn("--execute", command)
        self.assertEqual(command[1:3], ["task", "run"])

    def test_hermes_provider_prefers_detected_chat_command(self):
        fake_config = type(
            "Config",
            (),
            {
                "executors": {
                    "hermes": {
                        "command": "hermes",
                        "mode": "live",
                        "auto_detect": True,
                        "preferred_commands": ["chat", "team"],
                        "dispatch_profiles": {
                            "team": ["team", "dispatch", "-a", "{agent}", "-t", "{task}"],
                            "chat": ["chat", "-q", "[agent:{agent}] {task}", "-Q", "--source", "tool"],
                        },
                    },
                    "openclaw": {"command": "openclaw", "mode": "dry-run"},
                }
            },
        )()

        with patch.object(registry_module, "load_control_plane_config", return_value=fake_config):
            registry = registry_module.build_default_provider_registry()

        provider = registry.get("hermes")
        with patch.object(
            registry_module.HermesProvider,
            "_probe_available_commands",
            return_value={"chat", "status"},
        ):
            command = provider.build_dispatch_command("architect", "ship feature")

        self.assertEqual(command[:3], ["hermes", "chat", "-q"])
        self.assertIn("-Q", command)
        self.assertIn("--source", command)

    def test_hermes_provider_uses_explicit_dispatch_args_over_detection(self):
        fake_config = type(
            "Config",
            (),
            {
                "executors": {
                    "hermes": {
                        "command": "hermes",
                        "mode": "live",
                        "dispatch_args": ["chat", "-q", "[agent:{agent}] {task}", "-Q", "--source", "tool"],
                        "auto_detect": True,
                        "preferred_commands": ["chat", "team"],
                        "dispatch_profiles": {
                            "chat": ["chat", "-q", "[agent:{agent}] {task}", "-Q", "--source", "tool"],
                        },
                    },
                    "openclaw": {"command": "openclaw", "mode": "dry-run"},
                }
            },
        )()

        with patch.object(registry_module, "load_control_plane_config", return_value=fake_config):
            registry = registry_module.build_default_provider_registry()

        provider = registry.get("hermes")
        with patch.object(
            registry_module.HermesProvider,
            "_probe_available_commands",
            return_value={"chat"},
        ):
            command = provider.build_dispatch_command("architect", "ship feature")

        self.assertEqual(command[:3], ["hermes", "chat", "-q"])


    def test_hermes_provider_default_command_is_hermes(self):
        with patch("config._default_override_config_path", return_value=Path("Z:/__missing__/config.json")):
            registry_module.load_control_plane_config.cache_clear()
            registry = registry_module.build_default_provider_registry()

        provider = registry.get("hermes")
        self.assertEqual(provider.command, "hermes")

if __name__ == "__main__":
    unittest.main()
