import unittest

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

    def test_openclaw_adapter_exposes_placeholder_contract(self):
        adapter = adapters_module.OpenClawExecutorAdapter()

        with self.assertRaises(NotImplementedError):
            adapter.build_dispatch_command("architect", "鍒嗘瀽浠诲姟")


if __name__ == "__main__":
    unittest.main()

