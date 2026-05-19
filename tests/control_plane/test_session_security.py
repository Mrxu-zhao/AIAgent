import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from governance.session_security import SessionSecurityManager


class SessionSecurityTests(unittest.TestCase):
    def test_pairing_roundtrip(self):
        manager = SessionSecurityManager()
        manager.create_policy("session-1", "main")
        code = manager.generate_pairing_code("session-1")
        self.assertTrue(manager.verify_pairing("session-1", code))

    def test_untrusted_session_denies_write_tool(self):
        manager = SessionSecurityManager()
        manager.create_policy("session-2", "untrusted")
        allowed, reason = manager.check_permission(
            "session-2",
            "write_file",
            {"file_path": "demo.txt"},
            toolset="write",
        )
        self.assertFalse(allowed)
        self.assertIn("denied", reason.lower())


if __name__ == "__main__":
    unittest.main()
