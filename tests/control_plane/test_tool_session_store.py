import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from tools.session_store import SessionStore  # noqa: E402


class ToolSessionStoreTests(unittest.TestCase):
    def test_create_and_resume_session_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions")
            snapshot = store.create_session(
                task="请 architect review",
                agent_id="architect",
                backend="hermes",
                knowledge_bundle={"paths": [".hermes/team/knowledge/status.md"]},
                intent={"task_type": "architecture"},
            )

            updated = store.update_session(
                snapshot["session_id"],
                last_tool_name="read_knowledge",
                last_tool_result={"ok": True, "content_preview": "knowledge:1"},
                history_entry={"tool_name": "read_knowledge", "ok": True},
            )
            resumed = store.read_session(snapshot["session_id"])

            self.assertEqual(updated["session_id"], snapshot["session_id"])
            self.assertEqual(resumed["last_tool_name"], "read_knowledge")
            self.assertEqual(updated["history"][0]["tool_name"], "read_knowledge")


if __name__ == "__main__":
    unittest.main()
