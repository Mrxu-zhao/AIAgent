import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.common_tools import (
    generate_code_handler,
    run_command_handler,
    search_code_handler,
    write_file_handler,
)
from tools.spec import ToolExecutionContext


class CommonToolsTests(unittest.TestCase):
    def test_write_file_creates_file_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = ToolExecutionContext(
                task_id="test-1", agent_id="backend-dev", backend="hermes", cwd=str(root)
            )
            result = write_file_handler(
                context,
                {
                    "path": "src/main/java/com/example/Test.java",
                    "content": "public class Test {}",
                },
            )
            self.assertTrue(result.ok)
            written = root / "src" / "main" / "java" / "com" / "example" / "Test.java"
            self.assertTrue(written.exists())
            self.assertEqual(written.read_text(encoding="utf-8"), "public class Test {}")

    def test_write_file_rejects_path_outside_repo(self):
        context = ToolExecutionContext(task_id="test-2", agent_id="backend-dev", backend="hermes")
        result = write_file_handler(
            context,
            {"path": "../../../etc/passwd", "content": "hack"},
        )
        self.assertFalse(result.ok)
        self.assertIn("path must stay within", result.error.lower())

    def test_search_code_finds_matching_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / "UserService.java").write_text("public class UserService {}", encoding="utf-8")
            (src / "OrderService.java").write_text("public class OrderService {}", encoding="utf-8")
            context = ToolExecutionContext(
                task_id="test-3", agent_id="backend-dev", backend="hermes", cwd=str(root)
            )
            result = search_code_handler(context, {"pattern": "UserService", "glob": "*.java"})
            self.assertTrue(result.ok)
            self.assertEqual(len(result.structured_data["matches"]), 1)
            self.assertIn("UserService.java", result.structured_data["matches"][0]["path"])

    def test_run_command_allows_whitelisted_command(self):
        context = ToolExecutionContext(task_id="test-4", agent_id="backend-dev", backend="hermes")
        result = run_command_handler(context, {"command": "echo hello"})
        self.assertTrue(result.ok)
        self.assertIn("hello", result.content)

    def test_run_command_rejects_dangerous_command(self):
        context = ToolExecutionContext(task_id="test-5", agent_id="backend-dev", backend="hermes")
        result = run_command_handler(context, {"command": "rm -rf /"})
        self.assertFalse(result.ok)
        self.assertIn("not allowed", result.error.lower())

    def test_generate_code_from_template(self):
        context = ToolExecutionContext(task_id="test-6", agent_id="backend-dev", backend="hermes")
        result = generate_code_handler(
            context,
            {
                "template": "spring_controller",
                "variables": {
                    "class_name": "UserController",
                    "package": "com.example.controller",
                    "endpoint": "/api/users",
                },
            },
        )
        self.assertTrue(result.ok)
        self.assertIn("UserController", result.content)
        self.assertIn("@RestController", result.content)
