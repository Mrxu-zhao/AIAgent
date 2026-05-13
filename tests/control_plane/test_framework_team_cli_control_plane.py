import argparse
import io
import types
import unittest
from contextlib import redirect_stdout

from tests.control_plane.test_support import load_cli_module


class TeamCLIControlPlaneTests(unittest.TestCase):
    def test_control_plane_run_command_forwards_to_shared_runner(self):
        module = load_cli_module("team-cli.py", "framework_team_cli")
        cli = module.TeamCLI()

        observed = {}

        def fake_run_task_batch(**kwargs):
            observed.update(kwargs)
            return {"summary": {"done_tasks": ["WS-A-P0-001"], "rounds": 1}}

        module.control_plane_runner = types.SimpleNamespace(run_task_batch=fake_run_task_batch)
        try:
            cli.cmd_control_plane_run(argparse.Namespace(max_workers=4))
        finally:
            cli.monitor.stop()

        self.assertEqual(observed["max_workers"], 4)

    def test_control_plane_run_output_is_ascii_safe(self):
        module = load_cli_module("team-cli.py", "framework_team_cli_ascii")
        cli = module.TeamCLI()

        module.control_plane_runner = types.SimpleNamespace(
            run_task_batch=lambda **_: {"summary": {"done_tasks": ["WS-A-P0-001"], "rounds": 1}}
        )
        stream = io.StringIO()
        try:
            with redirect_stdout(stream):
                cli.cmd_control_plane_run(argparse.Namespace(max_workers=1))
        finally:
            cli.monitor.stop()

        output = stream.getvalue()
        self.assertIn("[OK]", output)
        self.assertNotIn("✓", output)
        self.assertNotIn("✗", output)


if __name__ == "__main__":
    unittest.main()
