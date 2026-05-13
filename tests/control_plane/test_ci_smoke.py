import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CISmokeTests(unittest.TestCase):
    def test_pyproject_exists_and_defines_ruff_and_coverage(self):
        pyproject = ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")

        self.assertIn("[tool.ruff]", content)
        self.assertIn("[tool.coverage", content)

    def test_github_actions_workflow_exists(self):
        workflow = ROOT / ".github" / "workflows" / "control-plane-ci.yml"
        content = workflow.read_text(encoding="utf-8")

        self.assertIn("coverage", content)
        self.assertIn("unittest", content)
        self.assertIn("--fail-under=90", content)

    def test_framework_readmes_include_assessment_mapping_table(self):
        readmes = [
            ROOT / ".hermes" / "team" / "调度框架" / "README.md",
            ROOT / ".hermes" / "team" / "调度框架" / "README_v2.md",
        ]

        for readme in readmes:
            content = readme.read_text(encoding="utf-8")
            self.assertIn("评估报告实现对照表", content, readme.name)
            self.assertIn("P1-1", content, readme.name)
            self.assertIn("P1-5", content, readme.name)
            self.assertIn("P2-5", content, readme.name)
            self.assertIn("里程碑-4-观测与CI", content, readme.name)

    def test_legacy_entrypoints_are_thin_adapters(self):
        framework_root = ROOT / ".hermes" / "team" / "调度框架"
        scripts = {
            "team.sh": framework_root / "team.sh",
            "team-dispatch.sh": framework_root / "scripts" / "team-dispatch.sh",
            "team-tmux.sh": framework_root / "tmux" / "team-tmux.sh",
        }

        for name, script in scripts.items():
            content = script.read_text(encoding="utf-8")
            self.assertIn("cli/team-cli.py", content, name)

        self.assertIn(
            "control_plane/cli.py",
            scripts["team.sh"].read_text(encoding="utf-8"),
            "team.sh",
        )
        self.assertIn(
            "dispatch -a",
            scripts["team-dispatch.sh"].read_text(encoding="utf-8"),
            "team-dispatch.sh",
        )
        self.assertIn(
            "interactive",
            scripts["team-tmux.sh"].read_text(encoding="utf-8"),
            "team-tmux.sh",
        )


if __name__ == "__main__":
    unittest.main()
