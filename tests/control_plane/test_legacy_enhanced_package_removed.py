import unittest
from pathlib import Path


class LegacyEnhancedPackageRemovalTests(unittest.TestCase):
    def test_legacy_package_removed_after_migration(self):
        self.assertFalse(Path("aiagent_enhanced/code_intelligence.py").exists())
        self.assertFalse(Path("aiagent_enhanced/security_model.py").exists())


if __name__ == "__main__":
    unittest.main()
