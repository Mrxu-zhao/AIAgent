import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import cli as unified_cli_module  # noqa: E402


class EnhancedCliTests(unittest.TestCase):
    def test_code_review_command_prints_score(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            unified_cli_module.main(["code-review", "--inline-code", "eval(user_input)"])
        payload = json.loads(buffer.getvalue())
        self.assertIn("score", payload)
        self.assertGreaterEqual(len(payload["security"]), 1)

    def test_kanban_summary_command_prints_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "kanban.db")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                unified_cli_module.main(["kanban", "summary", "--db-path", db_path])
            payload = json.loads(buffer.getvalue())
            self.assertIn("total", payload)

    def test_oauth_list_command_marks_deferred(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            unified_cli_module.main(["oauth", "list"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["exchange_mode"], "deferred")
        self.assertIn("github", payload["services"])


if __name__ == "__main__":
    unittest.main()
