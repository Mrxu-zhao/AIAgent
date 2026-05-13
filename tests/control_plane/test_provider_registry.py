import unittest
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


if __name__ == "__main__":
    unittest.main()
