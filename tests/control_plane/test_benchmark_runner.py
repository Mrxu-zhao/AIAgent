import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module

runner_module = load_control_plane_module("run_benchmarks")


class BenchmarkRunnerTests(unittest.TestCase):
    def test_runner_writes_before_and_current_baselines(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observed = {}

            def fake_capture_current(**kwargs):
                observed["current"] = kwargs
                return {
                    "label": "current",
                    "load_profile": {"cpu_burn_iterations": 2_000_000},
                    "scenarios": {
                        "dispatch": {
                            "cpu_ms": {"avg": 10.0, "p95": 10.0, "max": 10.0},
                            "latency_ms": {"avg": 10.0, "p95": 10.0, "max": 10.0},
                        }
                    },
                }

            def fake_capture_before(**kwargs):
                observed["before"] = kwargs
                return {
                    "label": "reconstructed-before",
                    "load_profile": {"cpu_burn_iterations": 2_000_000},
                    "scenarios": {
                        "dispatch": {
                            "cpu_ms": {"avg": 20.0, "p95": 20.0, "max": 20.0},
                            "latency_ms": {"avg": 20.0, "p95": 20.0, "max": 20.0},
                        }
                    },
                }

            report_path = runner_module.run_benchmarks(
                repo_root=base,
                artifacts_dir=base / "artifacts",
                capture_current=fake_capture_current,
                capture_before=fake_capture_before,
            )

            self.assertEqual(
                observed["current"]["load_profile"],
                {"cpu_burn_iterations": 2_000_000},
            )
            self.assertEqual(
                observed["before"]["load_profile"],
                {"cpu_burn_iterations": 2_000_000},
            )
            self.assertTrue((base / "artifacts" / "current-baseline.json").exists())
            self.assertTrue((base / "artifacts" / "before-baseline.json").exists())
            self.assertTrue(report_path.exists())

            report = (base / "artifacts" / "performance-report.md").read_text(encoding="utf-8")
            self.assertIn("dispatch", report)


if __name__ == "__main__":
    unittest.main()
