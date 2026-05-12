import argparse
import types
import unittest

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


if __name__ == "__main__":
    unittest.main()
