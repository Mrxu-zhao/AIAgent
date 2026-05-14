import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import knowledge.governance as governance_module  # noqa: E402
import knowledge.query as knowledge_query_module  # noqa: E402


class KnowledgeQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        governance_module.append_governance_entry(
            root=self.tmp_path,
            entry_type='decision',
            content='统一批入口',
            owner='architect',
            source_workflow_id='wf-1',
            source_step_id='design',
            source_agent='architect',
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_query_supports_agent_role_and_review_status_filters(self):
        result = knowledge_query_module.query_knowledge_records(
            root=self.tmp_path,
            query_text='统一批入口',
            filters={
                'agent': 'architect',
                'role': 'architect',
                'review_status': 'pending_review',
            },
        )
        self.assertIn('records', result)
        self.assertIn('summary', result)
        self.assertIn('aggregations', result)
        self.assertEqual(result['summary']['record_count'], 1)


if __name__ == '__main__':
    unittest.main()
