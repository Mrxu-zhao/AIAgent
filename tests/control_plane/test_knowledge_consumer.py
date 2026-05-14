import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import runtime.rules as runtime_rules_module  # noqa: E402
import tools.builtin as builtin_module  # noqa: E402
from knowledge.consumer import (  # noqa: E402
    build_excerpt_bundle,
    build_excerpt_record,
    expand_excerpt_content,
)
from tools.spec import ToolExecutionContext  # noqa: E402


class KnowledgeConsumerTests(unittest.TestCase):
    def test_build_excerpt_bundle_prioritizes_summary_over_raw_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "delivery-checklist.md"
            file_path.write_text(
                "# Delivery Checklist\n\n- 先补测试\n- 再补回归说明\n- 最后更新 handoff\n",
                encoding="utf-8",
            )
            bundle = build_excerpt_bundle(
                paths=["delivery-checklist.md"],
                resolved_paths=[str(file_path)],
                profile={"task_type": "implementation", "risk_flags": ["regression"]},
            )

        self.assertTrue(bundle["preloaded"])
        self.assertIn("summary", bundle["items"][0])
        self.assertNotIn("content", bundle["items"][0])
        self.assertIn("先补测试", bundle["items"][0]["excerpt"])

    def test_consumer_degrades_on_bad_encoding(self):
        item = build_excerpt_record("bad.md", "bad.md", b"\xff\xfe")
        self.assertEqual(item["degraded_reason"], "decode-error")

    def test_expand_excerpt_content_reads_raw_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            path.write_text("hello knowledge", encoding="utf-8")
            item = {"path": "note.md", "resolved_path": str(path), "expandable": True}
            expanded = expand_excerpt_content(item)

        self.assertEqual(expanded["content"], "hello knowledge")

    def test_preload_knowledge_bundle_reuses_cache_for_same_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            path.write_text("version-1", encoding="utf-8")
            bundle = {
                "paths": ["note.md"],
                "resolved_paths": [str(path)],
                "profile": {"task_type": "implementation"},
                "cache_key": "cache-key-1",
            }
            first = runtime_rules_module.preload_knowledge_bundle(bundle)
            path.write_text("version-2", encoding="utf-8")
            second = runtime_rules_module.preload_knowledge_bundle(bundle)

        self.assertEqual(first["items"][0]["summary"], second["items"][0]["summary"])
        self.assertTrue(second.get("cache_hit"))

    def test_read_knowledge_marks_handoff_consumption_when_message_id_provided(self):
        context = ToolExecutionContext(
            task_id="tool-1",
            agent_id="backend-1",
            backend="hermes",
            knowledge_bundle={
                "items": [
                    {
                        "path": "note.md",
                        "resolved_path": "note.md",
                        "summary": "summary",
                        "excerpt": "excerpt",
                        "expandable": False,
                    }
                ]
            },
        )
        observed = {}

        class FakeStore:
            def __init__(self, *_args, **_kwargs):
                pass

            def mark_knowledge_consumed(self, message_id, consumer=None, failure_reason=None):
                observed["message_id"] = message_id
                observed["consumer"] = consumer
                observed["failure_reason"] = failure_reason
                return {"message_id": message_id, "knowledge_consumed": True}

        original_store = builtin_module.HandoffRunStore
        builtin_module.HandoffRunStore = FakeStore
        try:
            result = builtin_module.read_knowledge_handler(
                context,
                {"handoff_message_id": "msg-1"},
            )
        finally:
            builtin_module.HandoffRunStore = original_store

        self.assertTrue(result.ok)
        self.assertEqual(observed["message_id"], "msg-1")
        self.assertEqual(observed["consumer"], "backend-1")


if __name__ == "__main__":
    unittest.main()
