import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.test_support import load_cli_module


cli_module = load_cli_module("team-cli.py", "team_cli")


class CLILifecycleTests(unittest.TestCase):
    def test_team_cli_starts_monitor_on_init(self):
        cli = cli_module.TeamCLI()

        try:
            self.assertTrue(cli.monitor._running)
        finally:
            cli.monitor.stop()

    def test_team_cli_shutdown_stops_monitor_when_running(self):
        cli = cli_module.TeamCLI()

        try:
            cli.shutdown()
            self.assertFalse(cli.monitor._running)
        finally:
            if cli.monitor._running:
                cli.monitor.stop()

    def test_main_stops_monitor_after_command_dispatch(self):
        observed = {"stop_calls": 0, "status_calls": 0}

        class FakeCLI:
            def __init__(self):
                self.monitor = SimpleNamespace(
                    _running=True,
                    stop=lambda: observed.__setitem__("stop_calls", observed["stop_calls"] + 1),
                )

            def cmd_status(self, args):
                observed["status_calls"] += 1

            def print_banner(self):
                raise AssertionError("print_banner should not be called")

            def shutdown(self):
                if self.monitor._running:
                    self.monitor.stop()
                    self.monitor._running = False

        with patch.object(cli_module, "TeamCLI", FakeCLI):
            with patch("sys.argv", ["team-cli.py", "status"]):
                cli_module.main()

        self.assertEqual(observed["status_calls"], 1)
        self.assertEqual(observed["stop_calls"], 1)


if __name__ == "__main__":
    unittest.main()

