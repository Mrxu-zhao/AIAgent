import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from knowledge.models import KnowledgeBundle, KnowledgeExcerpt, KnowledgeProfile  # noqa: E402


class KnowledgeModelsTests(unittest.TestCase):
    def test_knowledge_bundle_keeps_profile_excerpt_and_usage(self):
        profile = KnowledgeProfile(
            task_type='implementation',
            deliverables=['code', 'tests'],
            risk_flags=['regression'],
            owner_agent='backend-1',
            role_key='backend-dev',
            collaboration_mode='handoff',
        )
        excerpt = KnowledgeExcerpt(
            path='.hermes/team/knowledge/workflow-playbook.md',
            resolved_path='D:/repo/.hermes/team/knowledge/workflow-playbook.md',
            summary='use the delivery checklist first',
            excerpt='先补测试，再更新交接摘要。',
            priority=90.0,
            matched_by=['task_type', 'risk_flag'],
            tokens_estimate=24,
            expandable=True,
        )
        bundle = KnowledgeBundle(
            profile=profile,
            load_order=['team', 'role', 'instance'],
            team=['.hermes/team/knowledge/workflow-playbook.md'],
            role=['.hermes/agents/backend-dev/knowledge/checklists/delivery-checklist.md'],
            instance=['.hermes/team/agents/backend-1/knowledge/recent-lessons.md'],
            cross_role=['architect+backend-dev+qa-functional'],
            excerpts=[excerpt],
        )
        self.assertEqual(bundle.profile.owner_agent, 'backend-1')
        self.assertEqual(bundle.excerpts[0].priority, 90.0)
        self.assertEqual(bundle.cross_role, ['architect+backend-dev+qa-functional'])


if __name__ == '__main__':
    unittest.main()
