import json
import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import ensure_control_plane_path

ensure_control_plane_path()
import observability.metrics as metrics_module  # noqa: E402


class MetricsTests(unittest.TestCase):
    def test_metrics_registry_renders_prometheus_text(self):
        registry = metrics_module.MetricsRegistry()
        registry.set_gauge("improvement_dashboard_availability_ratio", 1.0)
        registry.inc_counter("improvement_test_files_total", 1)

        text = registry.render_prometheus_text()

        self.assertIn("improvement_dashboard_availability_ratio", text)
        self.assertIn("improvement_test_files_total", text)

    def test_refresh_repository_metrics_collects_repo_backed_gauges(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tests_dir = root / "tests" / "control_plane"
            tests_dir.mkdir(parents=True)
            (tests_dir / "test_alpha.py").write_text("import unittest\n", encoding="utf-8")
            (tests_dir / "test_beta.py").write_text("import unittest\n", encoding="utf-8")

            artifacts_dir = root / ".hermes" / "team" / "control_plane" / "artifacts"
            artifacts_dir.mkdir(parents=True)
            (artifacts_dir / "execution-summary-2026-05-12.md").write_text(
                "-  - 交付关键路径总覆盖率：`94%`\n",
                encoding="utf-8",
            )
            (artifacts_dir / "real-load-validation.json").write_text(
                json.dumps(
                    {
                        "real_load": {
                            "summary": {
                                "done_tasks": ["A", "B", "C"],
                                "failed_tasks": [],
                                "blocked_tasks": [],
                                "conflicted_tasks": [],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            framework_dir = root / ".hermes" / "team" / "调度框架"
            framework_dir.mkdir(parents=True)
            readme_tokens = "\n".join(
                [
                    "P1-1",
                    "P1-2",
                    "P1-3",
                    "P1-4",
                    "P1-5",
                    "P2-1",
                    "P2-2",
                    "P2-3",
                    "P2-4",
                    "P2-5",
                    "里程碑-1",
                    "里程碑-2",
                    "里程碑-3",
                    "里程碑-4",
                ]
            )
            (framework_dir / "README.md").write_text(readme_tokens, encoding="utf-8")
            (framework_dir / "README_v2.md").write_text(readme_tokens, encoding="utf-8")

            registry = metrics_module.MetricsRegistry()
            metrics_module.refresh_repository_metrics(root=root, registry=registry)
            text = registry.render_prometheus_text()

        self.assertIn("improvement_test_files_total 2.0", text)
        self.assertIn("improvement_core_path_coverage_ratio 0.94", text)
        self.assertIn("improvement_doc_impl_gap_total 0.0", text)
        self.assertIn("improvement_auto_recovery_closure_ratio 1.0", text)


if __name__ == "__main__":
    unittest.main()
