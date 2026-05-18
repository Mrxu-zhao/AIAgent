import unittest
from unittest.mock import patch

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import hermes_health as hermes_health_module  # noqa: E402


class HermesHealthTests(unittest.TestCase):
    @patch("hermes_health.subprocess.run")
    def test_check_hermes_health_marks_missing_command(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        report = hermes_health_module.check_hermes_health("missing-hermes")

        self.assertFalse(report.ok)
        self.assertEqual(report.status, "command_missing")

    @patch("hermes_health.subprocess.run")
    def test_check_hermes_health_marks_not_configured(self, mock_run):
        mock_run.side_effect = [
            type("R", (), {"stdout": "chat team", "stderr": "", "returncode": 0})(),
            type("R", (), {"stdout": "Model: (not set)", "stderr": "not configured", "returncode": 1})(),
        ]

        report = hermes_health_module.check_hermes_health("hermes")

        self.assertFalse(report.ok)
        self.assertEqual(report.status, "not_configured")
        self.assertIn("not configured", report.message.lower())


if __name__ == "__main__":
    unittest.main()
