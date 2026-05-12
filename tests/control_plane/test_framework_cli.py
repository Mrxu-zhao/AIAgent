import unittest

from tests.control_plane.test_support import load_cli_module


cli_module = load_cli_module("team-cli.py", "team_cli")


class CLILifecycleTests(unittest.TestCase):
    def test_team_cli_starts_monitor_on_init(self):
        cli = cli_module.TeamCLI()

        try:
            self.assertTrue(cli.monitor._running)
        finally:
            cli.monitor.stop()


if __name__ == "__main__":
    unittest.main()

