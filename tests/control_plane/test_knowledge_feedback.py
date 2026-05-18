import unittest

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


if __name__ == "__main__":
    unittest.main()
