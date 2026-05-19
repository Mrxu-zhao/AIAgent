import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()

from governance.tool_permissions import is_role_tool_allowed
from tools.builtin import build_default_tool_registry


class EnhancedToolRegistryTests(unittest.TestCase):
    def test_registry_exposes_enhanced_tools(self):
        registry = build_default_tool_registry()
        names = registry.names()
        self.assertIn("code_review", names)
        self.assertIn("code_diagnostics", names)
        self.assertIn("kanban_summary", names)
        self.assertIn("kanban_create_task", names)
        self.assertIn("list_oauth_services", names)

    def test_role_permissions_allow_enhanced_tools(self):
        self.assertTrue(is_role_tool_allowed("architect", "code_review"))
        self.assertTrue(is_role_tool_allowed("backend-dev", "code_review"))
        self.assertTrue(is_role_tool_allowed("architect", "kanban_summary"))


if __name__ == "__main__":
    unittest.main()
