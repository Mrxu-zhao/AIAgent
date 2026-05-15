import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.hermes/team/control_plane"))

from stacks.registry import get_stack_config, list_stacks


class StackRegistryTests(unittest.TestCase):
    def test_get_java_spring_config(self):
        config = get_stack_config("backend", "java-spring")
        self.assertEqual(config.name, "Java Spring Boot")
        self.assertIn("test", config.commands)

    def test_get_vue3_config(self):
        config = get_stack_config("frontend", "vue3")
        self.assertEqual(config.name, "Vue 3")
        self.assertIn(".vue", config.file_extensions)

    def test_get_mysql_config(self):
        config = get_stack_config("database", "mysql")
        self.assertEqual(config.name, "MySQL")

    def test_list_all_stacks(self):
        stacks = list_stacks()
        self.assertIn("backend", stacks)
        self.assertIn("frontend", stacks)
        self.assertIn("database", stacks)
        self.assertIn("java-spring", stacks["backend"])
        self.assertIn("harmony-arkts", stacks["frontend"])

    def test_list_backend_stacks(self):
        stacks = list_stacks("backend")
        self.assertEqual(len(stacks["backend"]), 3)

    def test_get_unknown_stack_raises(self):
        with self.assertRaises(ValueError):
            get_stack_config("backend", "unknown")
