import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import file_lock as file_lock_module  # noqa: E402


class FileLockTests(unittest.TestCase):
    def test_atomic_write_text_replaces_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("old", encoding="utf-8")

            file_lock_module.atomic_write_text(path, "new")

            self.assertEqual(path.read_text(encoding="utf-8"), "new")


if __name__ == "__main__":
    unittest.main()
