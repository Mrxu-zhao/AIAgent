"""Tests for knowledge closed-loop system."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# Import directly from file path to avoid __init__.py issues
import importlib.util

_extractor_path = os.path.join(
    os.path.dirname(__file__), "../../.hermes/team/control_plane/knowledge_loop/extractor.py"
)
_updater_path = os.path.join(
    os.path.dirname(__file__), "../../.hermes/team/control_plane/knowledge_loop/updater.py"
)

_spec_ext = importlib.util.spec_from_file_location("extractor", _extractor_path)
_extractor = importlib.util.module_from_spec(_spec_ext)
sys.modules["extractor"] = _extractor
_spec_ext.loader.exec_module(_extractor)

_spec_upd = importlib.util.spec_from_file_location("updater", _updater_path)
_updater = importlib.util.module_from_spec(_spec_upd)
sys.modules["updater"] = _updater
_spec_upd.loader.exec_module(_updater)

ExperienceExtractor = _extractor.ExperienceExtractor
ExperienceRecord = _extractor.ExperienceRecord
KnowledgeUpdater = _updater.KnowledgeUpdater


class TestExperienceExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = ExperienceExtractor()

    def test_extract_from_quality_report_fail(self):
        report = {
            "results": [
                {"gate_name": "单测覆盖", "status": "fail", "message": "Coverage 50% < 80%"},
            ]
        }
        records = self.extractor.extract_from_quality_report("backend", "wf-1", report)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].category, "pitfall")
        self.assertIn("Coverage 50%", records[0].description)

    def test_extract_from_quality_report_pass(self):
        report = {
            "results": [
                {"gate_name": "代码评审", "status": "pass", "message": "Passed"},
            ]
        }
        records = self.extractor.extract_from_quality_report("backend", "wf-1", report)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].category, "pattern")

    def test_extract_from_code(self):
        code = "# Best practice: use immutable data\ndef foo(): pass\n// Avoid: global state\n"
        records = self.extractor.extract_from_code("backend", "wf-1", code, "test.py")
        self.assertGreaterEqual(len(records), 2)
        categories = [r.category for r in records]
        self.assertIn("pattern", categories)
        self.assertIn("pitfall", categories)

    def test_extract_from_review(self):
        comments = [
            {"body": "Should use dependency injection", "severity": "info", "title": "DI"},
            {"body": "Avoid hardcoded values", "severity": "error", "title": "Hardcode"},
        ]
        records = self.extractor.extract_from_review("backend", "wf-1", comments)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1].category, "pitfall")

    def test_extract_from_decisions(self):
        decisions = [
            {"summary": "Use Redis cache", "rationale": "Reduce DB load", "scope": "backend"},
        ]
        records = self.extractor.extract_from_decisions("architect", "wf-1", decisions)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].category, "decision")

    def test_deduplicate(self):
        records = [
            ExperienceRecord("", "backend", "pattern", "A", "desc", "wf-1"),
            ExperienceRecord("", "backend", "pattern", "A", "desc", "wf-1"),
            ExperienceRecord("", "backend", "pitfall", "B", "desc2", "wf-1"),
        ]
        unique = self.extractor.deduplicate(records)
        self.assertEqual(len(unique), 2)

    def test_record_id_generation(self):
        r = ExperienceRecord("", "backend", "pattern", "Title", "Desc", "wf-1")
        self.assertTrue(r.record_id)
        self.assertEqual(len(r.record_id), 16)


class TestKnowledgeUpdater(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.knowledge_root = Path(self.tmpdir.name) / "agents"
        self.knowledge_root.mkdir()
        # Create role dirs
        for role in ["backend-dev", "frontend-dev"]:
            (self.knowledge_root / role / "patterns").mkdir(parents=True)
            (self.knowledge_root / role / "pitfalls").mkdir(parents=True)
        self.updater = KnowledgeUpdater(knowledge_root=str(self.knowledge_root))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_update_role_knowledge_pattern(self):
        records = [
            ExperienceRecord("", "backend-dev", "pattern", "Use DI", "Dependency injection", "wf-1"),
        ]
        result = self.updater.update_role_knowledge("backend-dev", records)
        self.assertEqual(result["record_count"], 1)
        self.assertTrue(len(result["updated_files"]) > 0)
        path = Path(result["updated_files"][0])
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("Use DI", content)

    def test_update_role_knowledge_pitfall(self):
        records = [
            ExperienceRecord("", "backend-dev", "pitfall", "N+1", "Avoid N+1 query", "wf-1"),
        ]
        result = self.updater.update_role_knowledge("backend-dev", records)
        path = Path(result["updated_files"][0])
        content = path.read_text(encoding="utf-8")
        self.assertIn("N+1", content)

    def test_deduplication(self):
        records = [
            ExperienceRecord("id1", "backend-dev", "pattern", "Same", "Desc", "wf-1"),
        ]
        self.updater.update_role_knowledge("backend-dev", records)
        self.updater.update_role_knowledge("backend-dev", records)
        path = self.knowledge_root / "backend-dev" / "patterns" / "preferred-patterns.md"
        content = path.read_text(encoding="utf-8")
        self.assertEqual(content.count("id1"), 1)

    def test_update_team_knowledge(self):
        records = [
            ExperienceRecord("", "backend-dev", "pattern", "Shared", "Shared pattern", "wf-1"),
            ExperienceRecord("", "frontend-dev", "pitfall", "Shared", "Shared pitfall", "wf-1"),
        ]
        result = self.updater.update_team_knowledge(records)
        self.assertEqual(result["record_count"], 2)

    def test_build_knowledge_index(self):
        records = [
            ExperienceRecord("idx1", "backend-dev", "pattern", "Idx", "Desc", "wf-1"),
        ]
        self.updater.update_role_knowledge("backend-dev", records)
        index = self.updater.build_knowledge_index()
        self.assertIn("backend-dev", index)


if __name__ == "__main__":
    unittest.main()
