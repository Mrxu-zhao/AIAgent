import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_TEAM_SKILL_DOCS = [
    ROOT / ".hermes" / "skills" / "architect" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "backend-dev" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "dba" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "devops" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "frontend-dev" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "qa-functional" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "qa-performance" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "ucd" / "SKILL.md",
    ROOT / ".hermes" / "skills" / "agent-team" / "requirements-analyst" / "SKILL.md",
]


class SkillDocumentationTests(unittest.TestCase):
    def test_agent_team_skills_use_repository_relative_hermes_paths(self):
        mismatched_files = []
        for skill_doc in AGENT_TEAM_SKILL_DOCS:
            content = skill_doc.read_text(encoding="utf-8")
            if "~/.hermes/" in content:
                mismatched_files.append(str(skill_doc.relative_to(ROOT)))

        self.assertEqual(
            mismatched_files,
            [],
            msg=f"skill docs still point runtime paths to ~/.hermes: {mismatched_files}",
        )


if __name__ == "__main__":
    unittest.main()
