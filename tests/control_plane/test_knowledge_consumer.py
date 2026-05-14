import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
from knowledge.consumer import (  # noqa: E402
    build_excerpt_bundle,
    build_excerpt_record,
    expand_excerpt_content,
)


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


if __name__ == "__main__":
    unittest.main()
