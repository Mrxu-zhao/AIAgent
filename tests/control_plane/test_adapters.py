﻿import unittest
from unittest.mock import patch

from tests.control_plane.test_support import load_control_plane_module

adapters_module = load_control_plane_module("adapters")


class AdapterTests(unittest.TestCase):
    def test_hermes_adapter_builds_dispatch_command(self):
        adapter = adapters_module.HermesExecutorAdapter(
            hermes_command="hermes",
            dispatch_script=".hermes/team/璋冨害妗嗘灦/scripts/team-dispatch.sh",
        )

        command = adapter.build_dispatch_command("architect", "鍒嗘瀽浠诲姟")

        self.assertEqual(
            command,
            [
                "hermes",
                "team",
                "dispatch",
                "-a",
                "architect",
                "-t",
                "鍒嗘瀽浠诲姟",
            ],
        )

    def test_openclaw_adapter_builds_dry_run_dispatch_command(self):
        adapter = adapters_module.OpenClawExecutorAdapter()

        command = adapter.build_dispatch_command("architect", "鍒嗘瀽浠诲姟")

        self.assertIn("openclaw", command[0])
        self.assertIn("--dry-run", command)
        self.assertIn("architect", command)

    def test_default_adapter_preserves_openclaw_live_dispatch_args(self):
        fake_provider = type(
            "Provider",
            (),
            {
                "name": "openclaw",
                "command": "openclaw-live",
                "dry_run": False,
                "dispatch_args": ["task", "run"],
            },
        )()
        fake_registry = type("Registry", (), {"get": lambda self, name: fake_provider})()
        fake_config = type("Config", (), {"default_executor": "openclaw"})()

        with patch.object(adapters_module, "load_control_plane_config", return_value=fake_config):
            with patch.object(
                adapters_module,
                "build_default_provider_registry",
                return_value=fake_registry,
            ):
                adapter = adapters_module.get_default_executor_adapter()

        command = adapter.build_dispatch_command("architect", "ship feature")
        self.assertEqual(command[:3], ["openclaw-live", "task", "run"])
        self.assertIn("--execute", command)


if __name__ == "__main__":
    unittest.main()

