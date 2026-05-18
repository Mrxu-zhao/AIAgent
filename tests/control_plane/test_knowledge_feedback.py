import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import knowledge_feedback as knowledge_feedback_module  # noqa: E402


class KnowledgeFeedbackTests(unittest.TestCase):
    def test_record_knowledge_usage_calculates_feedback_score(self):
        usage = knowledge_feedback_module.record_knowledge_usage(
            workflow_id="wf-1",
            knowledge_recommendations={
                "implement": {
                    "team": [".hermes/team/knowledge/status.md"],
                    "role": [".hermes/agents/backend-dev/knowledge/status.md"],
                    "instance": [".hermes/team/agents/backend-1/knowledge/expertise.md"],
                }
            },
            knowledge_bundles={
                "implement": {
                    "paths": [
                        ".hermes/team/knowledge/status.md",
                        ".hermes/agents/backend-dev/knowledge/status.md",
                    ],
                    "next_read": [".hermes/team/knowledge/status.md"],
                }
            },
            step_contexts={
                "implement": {
                    "agent": "backend-1",
                    "decisions": [{"summary": "use versioned api"}],
                    "risks": ["cache consistency"],
                }
            },
        )

        self.assertEqual(usage["workflow_id"], "wf-1")
        self.assertEqual(len(usage["steps"]), 1)
        self.assertEqual(usage["summary"]["recommended_paths"][0], ".hermes/team/knowledge/status.md")
        self.assertEqual(usage["summary"]["consumed_paths"][0], ".hermes/team/knowledge/status.md")
        self.assertEqual(usage["summary"]["unused_paths"][0], ".hermes/team/agents/backend-1/knowledge/expertise.md")
        self.assertGreater(usage["summary"]["feedback_score"], 0.0)

    def test_sync_workflow_feedback_promotes_instance_lessons_to_role_and_team_project_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_root = Path(tmp) / ".hermes" / "team" / "knowledge"
            feedback = knowledge_feedback_module.sync_workflow_feedback(
                knowledge_root=knowledge_root,
                workflow_id="children-literacy-game",
                collaboration_context={},
                step_contexts={
                    "frontend_impl": {
                        "agent": "frontend-1",
                        "summary": "儿童识字游戏首屏需要优先加载拼音卡片与离线素材",
                        "risks": ["小游戏素材过大时首屏会卡顿"],
                        "decisions": [
                            {
                                "summary": "儿童识字游戏首屏采用离线素材预热",
                                "rationale": "降低拼音关卡首屏等待时间",
                                "impact": "前端加载体验",
                                "next_action": "沉淀为小游戏加载模式",
                            }
                        ],
                    }
                },
            )
            team_project_lessons = (knowledge_root / "project-lessons.md").read_text(encoding="utf-8")
            role_project_lessons = (
                knowledge_root.parents[1]
                / "agents"
                / "frontend-dev"
                / "knowledge"
                / "project-lessons.md"
            ).read_text(encoding="utf-8")

        self.assertIn("team_project_lessons_path", feedback)
        self.assertIn("role_project_lessons", feedback)
        self.assertIn("children-literacy-game", team_project_lessons)
        self.assertIn("儿童识字游戏首屏采用离线素材预热", team_project_lessons)
        self.assertIn("儿童识字游戏首屏采用离线素材预热", role_project_lessons)
        self.assertIn("project_type: children-literacy-game", role_project_lessons)


if __name__ == "__main__":
    unittest.main()
