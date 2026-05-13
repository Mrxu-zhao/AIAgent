import unittest

from tests.control_plane.test_support import load_control_plane_module

models = load_control_plane_module("models")
conflicts = load_control_plane_module("conflicts")


class ConflictDetectorTests(unittest.TestCase):
    def test_file_scope_conflict_is_hard_block(self):
        left = models.LockScope(files=["a.py"], modules=["m1"], contracts=[])
        right = models.LockScope(files=["a.py"], modules=["m2"], contracts=[])
        verdict = conflicts.detect_conflict(left, right)

        self.assertEqual(verdict["level"], "hard")
        self.assertIn("files", verdict["conflicts"])

    def test_module_scope_conflict_is_soft_block(self):
        left = models.LockScope(files=["a.py"], modules=["monitor"], contracts=[])
        right = models.LockScope(files=["b.py"], modules=["monitor"], contracts=[])
        verdict = conflicts.detect_conflict(left, right)

        self.assertEqual(verdict["level"], "soft")


if __name__ == "__main__":
    unittest.main()

