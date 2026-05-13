import unittest

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import protocols.handoff as handoff_module  # noqa: E402


class HandoffTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
