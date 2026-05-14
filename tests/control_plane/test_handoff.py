import json
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import protocols.handoff as handoff_module  # noqa: E402


class HandoffTests(unittest.TestCase):
    def test_handoff_schema_covers_extended_payload_fields(self):
        schema_path = (
            Path(__file__).resolve().parents[2]
            / ".hermes"
            / "team"
            / "control_plane"
            / "protocols"
            / "handoff.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = handoff_module.HandoffPayload.create(
            source_backend="hermes",
            target_backend="openclaw",
            task_id="task-schema",
            summary="handoff",
            context={"files": ["a.py"]},
            source_agent="architect",
            target_agent="backend-1",
            source_step="design",
            target_step="implement",
            reason="role transition",
            artifacts=["spec.md"],
            open_questions=["接口是否分页"],
            risks=["需求变更"],
            selected_backend="openclaw",
            backend_candidates=["hermes", "openclaw"],
            backend_reason="needs external execution",
            review_policy="soft-prefer-reviewer",
        ).to_dict()

        self.assertTrue(set(payload).issubset(schema["properties"]))

    def test_handoff_payload_contains_backend_and_context(self):
        payload = handoff_module.HandoffPayload.create(
            source_backend="hermes",
            target_backend="openclaw",
            task_id="task-1",
            summary="handoff",
            context={"files": ["a.py"]},
        )

        self.assertTrue(handoff_module.validate_handoff_payload(payload.to_dict()))
        self.assertEqual(payload.target_backend, "openclaw")

    def test_handoff_payload_supports_extended_metadata(self):
        payload = handoff_module.HandoffPayload.create(
            source_backend="hermes",
            target_backend="openclaw",
            task_id="task-1",
            summary="handoff",
            context={"files": ["a.py"]},
            source_agent="architect",
            target_agent="backend-1",
            source_step="design",
            target_step="implement",
            reason="role transition",
            artifacts=["spec.md"],
            open_questions=["接口是否分页"],
            risks=["需求变更"],
        )

        data = payload.to_dict()

        self.assertEqual(data["source_agent"], "architect")
        self.assertEqual(data["artifacts"], ["spec.md"])
        self.assertEqual(data["open_questions"], ["接口是否分页"])
        self.assertTrue(handoff_module.validate_handoff_payload(data))

    def test_handoff_payload_supports_backend_explanation_fields(self):
        payload = handoff_module.HandoffPayload.create(
            source_backend="hermes",
            target_backend="openclaw",
            task_id="task-2",
            summary="handoff",
            context={},
            selected_backend="openclaw",
            backend_candidates=["hermes", "openclaw"],
            backend_reason="needs external execution",
            review_policy="soft-prefer-reviewer",
        )

        data = payload.to_dict()

        self.assertEqual(data["selected_backend"], "openclaw")
        self.assertEqual(data["backend_candidates"], ["hermes", "openclaw"])
        self.assertTrue(handoff_module.validate_handoff_payload(data))

    def test_handoff_payload_supports_knowledge_recommendation(self):
        payload = handoff_module.HandoffPayload.create(
            source_backend="hermes",
            target_backend="openclaw",
            task_id="task-3",
            summary="handoff",
            context={},
            knowledge_recommendation={
                "load_order": ["team", "role", "instance"],
                "team": [".hermes/team/knowledge/status.md"],
                "role": [".hermes/agents/backend-dev/knowledge/status.md"],
                "instance": [".hermes/team/agents/backend-1/knowledge/expertise.md"],
            },
        )

        data = payload.to_dict()

        self.assertEqual(
            data["knowledge_recommendation"]["role"],
            [".hermes/agents/backend-dev/knowledge/status.md"],
        )
        self.assertTrue(handoff_module.validate_handoff_payload(data))


if __name__ == "__main__":
    unittest.main()
