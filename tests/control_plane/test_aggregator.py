import tempfile
import unittest
from pathlib import Path

from tests.control_plane.test_support import load_control_plane_module

models = load_control_plane_module("models")
aggregator_module = load_control_plane_module("aggregator")
store_module = load_control_plane_module("store")
reporting_module = load_control_plane_module("reporting")


class AggregatorTests(unittest.TestCase):
    def test_aggregator_builds_final_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = aggregator_module.build_report(
                output_dir=Path(tmp),
                task_summary={"done": 3, "failed": 0, "blocked": 1},
                performance_summary={"overall_ok": True},
            )

            self.assertIn("done: 3", report)
            self.assertIn("overall_ok: True", report)

    def test_reporting_renders_section(self):
        section = reporting_module.render_bullet_section("Execution Summary", ["done: 3", "failed: 0"])

        self.assertIn("## Execution Summary", section)
        self.assertIn("- done: 3", section)

    def test_aggregator_summarizes_store_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")

            done_card = models.TaskCard(
                task_id="WS-A-P0-001",
                title="Done task",
                goal="done",
                scope=[],
                lock_scope=models.LockScope(files=[], modules=[], contracts=[]),
                inputs=[],
                outputs=[],
                dependencies=[],
                owner_agent="backend-1",
                review_agent="architect",
                priority=models.TaskPriority.P0,
                timeout_seconds=1,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["done"],
                status=models.TaskStatus.DONE,
            )
            failed_card = models.TaskCard(
                task_id="WS-B-P1-001",
                title="Failed task",
                goal="failed",
                scope=[],
                lock_scope=models.LockScope(files=[], modules=[], contracts=[]),
                inputs=[],
                outputs=[],
                dependencies=[],
                owner_agent="backend-2",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["failed"],
                status=models.TaskStatus.FAILED,
            )
            store.register_task(done_card)
            store.register_task(failed_card)

            summary = aggregator_module.summarize_store(store)

            self.assertEqual(summary["done"], 1)
            self.assertEqual(summary["failed"], 1)

    def test_build_report_from_store_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = store_module.TaskStore(base / "state", base / "events")
            done_card = models.TaskCard(
                task_id="WS-C-P1-001",
                title="Done report task",
                goal="done",
                scope=[],
                lock_scope=models.LockScope(files=[], modules=[], contracts=[]),
                inputs=[],
                outputs=[],
                dependencies=[],
                owner_agent="backend-1",
                review_agent="architect",
                priority=models.TaskPriority.P1,
                timeout_seconds=1,
                retry_policy=models.RetryPolicy(max_attempts=1, backoff_seconds=[0]),
                rollback_policy=models.RollbackPolicy(mode="code"),
                acceptance_criteria=["done"],
                status=models.TaskStatus.DONE,
            )
            store.register_task(done_card)

            summary = aggregator_module.summarize_store(store)
            report = aggregator_module.build_report(
                output_dir=base / "artifacts",
                task_summary=summary,
                performance_summary={"overall_ok": True},
            )

            self.assertIn("done: 1", report)
            self.assertTrue((base / "artifacts" / "final-report.md").exists())

    def test_build_performance_report_renders_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = aggregator_module.build_performance_report(
                output_dir=base,
                current_run={
                    "label": "after",
                    "scenarios": {
                        "dispatch": {
                            "latency_ms": {"avg": 80.0, "p95": 90.0, "max": 100.0},
                            "cpu_ms": {"avg": 20.0, "p95": 22.0, "max": 25.0},
                            "goal_type": "reference",
                            "counts_toward_overall": False,
                        },
                        "workflow": {
                            "latency_ms": {"avg": 40.0, "p95": 42.0, "max": 45.0},
                            "cpu_ms": {"avg": 15.0, "p95": 16.0, "max": 17.0},
                            "goal_type": "correctness",
                            "counts_toward_overall": False,
                            "correctness": {
                                "check": "step_agent_override",
                                "expected_agent": "dba",
                                "all_runs_passed": True,
                                "passed_runs": 3,
                                "total_runs": 3,
                            },
                        }
                    },
                },
                previous_run={
                    "label": "before",
                    "scenarios": {
                        "dispatch": {
                            "latency_ms": {"avg": 100.0, "p95": 120.0, "max": 150.0},
                            "cpu_ms": {"avg": 30.0, "p95": 32.0, "max": 35.0},
                            "goal_type": "reference",
                            "counts_toward_overall": False,
                        },
                        "workflow": {
                            "latency_ms": {"avg": 45.0, "p95": 48.0, "max": 50.0},
                            "cpu_ms": {"avg": 16.0, "p95": 17.0, "max": 18.0},
                            "goal_type": "correctness",
                            "counts_toward_overall": False,
                            "correctness": {
                                "check": "step_agent_override",
                                "expected_agent": "dba",
                                "all_runs_passed": False,
                                "passed_runs": 0,
                                "total_runs": 3,
                            },
                        }
                    },
                },
            )

            self.assertIn("dispatch", report)
            self.assertIn("latency_ok: True", report)
            self.assertIn("goal_type: correctness", report)
            self.assertIn("correctness_before_passed: False", report)
            self.assertIn("correctness_after_passed: True", report)
            self.assertTrue((base / "performance-report.md").exists())

    def test_build_performance_report_prefers_effective_cpu_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = aggregator_module.build_performance_report(
                output_dir=base,
                current_run={
                    "label": "after",
                    "scenarios": {
                        "dashboard": {
                            "latency_ms": {"avg": 60.0, "p95": 62.0, "max": 64.0},
                            "cpu_ms": {"avg": 62.5, "p95": 62.5, "max": 62.5},
                            "cpu_effective_ms": {"avg": 4.0, "p95": 4.0, "max": 4.0},
                            "goal_type": "performance",
                            "counts_toward_overall": True,
                        }
                    },
                },
                previous_run={
                    "label": "before",
                    "scenarios": {
                        "dashboard": {
                            "latency_ms": {"avg": 100.0, "p95": 100.0, "max": 100.0},
                            "cpu_ms": {"avg": 80.0, "p95": 80.0, "max": 80.0},
                            "cpu_effective_ms": {"avg": 10.0, "p95": 10.0, "max": 10.0},
                            "goal_type": "performance",
                            "counts_toward_overall": True,
                        }
                    },
                },
            )

            self.assertIn("cpu_before_avg_ms: 10.0", report)
            self.assertIn("cpu_after_avg_ms: 4.0", report)
            self.assertIn("cpu_ok: True", report)


if __name__ == "__main__":
    unittest.main()

