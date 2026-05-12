import json
import tempfile
import time
from pathlib import Path
import unittest

from tests.control_plane.test_support import load_control_plane_module


baseline_module = load_control_plane_module("baseline")


class BaselineTests(unittest.TestCase):
    def test_summary_includes_avg_p95_and_max(self):
        summary = baseline_module.summarize_samples([10, 20, 30, 40, 50])

        self.assertEqual(summary["avg"], 30.0)
        self.assertEqual(summary["max"], 50)
        self.assertIn("p95", summary)

    def test_performance_goal_requires_latency_and_cpu_reduction(self):
        verdict = baseline_module.compare_runs(
            before={"latency": 100.0, "cpu": 40.0},
            after={"latency": 75.0, "cpu": 32.0},
        )

        self.assertTrue(verdict["latency_ok"])
        self.assertTrue(verdict["cpu_ok"])
        self.assertTrue(verdict["overall_ok"])

    def test_compare_runs_handles_zero_cpu_baseline(self):
        verdict = baseline_module.compare_runs(
            before={"latency": 100.0, "cpu": 0.0},
            after={"latency": 70.0, "cpu": 0.0},
        )

        self.assertTrue(verdict["latency_ok"])
        self.assertFalse(verdict["cpu_ok"])
        self.assertIsNone(verdict["cpu_drop_ratio"])

    def test_benchmark_callable_collects_latency_and_cpu(self):
        result = baseline_module.benchmark_callable(lambda: sum(range(100)), iterations=3)

        self.assertEqual(result["iterations"], 3)
        self.assertIn("latency_ms", result)
        self.assertIn("cpu_ms", result)

    def test_benchmark_callable_supports_cpu_burn_iterations(self):
        result = baseline_module.benchmark_callable(
            lambda: None,
            iterations=2,
            cpu_burn_iterations=50000,
        )

        self.assertEqual(result["cpu_burn_iterations"], 50000)
        self.assertGreaterEqual(result["cpu_ms"]["max"], 0.0)

    def test_benchmark_callable_applies_cpu_burn_even_when_timed_out(self):
        result = baseline_module.benchmark_callable(
            lambda: time.sleep(0.05),
            iterations=1,
            timeout_seconds=0.01,
            cpu_burn_iterations=50000,
        )

        self.assertEqual(result["timed_out_runs"], 1)
        self.assertEqual(result["cpu_burn_iterations"], 50000)
        self.assertGreater(result["cpu_ms"]["max"], 0.0)

    def test_capture_framework_baseline_contains_three_scenarios(self):
        baseline = baseline_module.capture_framework_baseline(
            iterations=1,
            load_profile={"cpu_burn_iterations": 25000},
        )

        self.assertIn("dispatch", baseline["scenarios"])
        self.assertIn("dashboard", baseline["scenarios"])
        self.assertIn("workflow", baseline["scenarios"])
        self.assertEqual(baseline["load_profile"]["cpu_burn_iterations"], 25000)

    def test_capture_framework_baseline_exposes_workflow_correctness_signal(self):
        baseline = baseline_module.capture_framework_baseline(
            iterations=1,
            load_profile={"cpu_burn_iterations": 0},
        )

        workflow = baseline["scenarios"]["workflow"]
        self.assertEqual(workflow["goal_type"], "correctness")
        self.assertFalse(workflow["counts_toward_overall"])
        self.assertEqual(workflow["correctness"]["check"], "step_agent_override")
        self.assertTrue(workflow["correctness"]["all_runs_passed"])

    def test_capture_framework_baseline_supports_custom_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            framework_root = Path(tmp)
            core_dir = framework_root / "core"
            core_dir.mkdir(parents=True, exist_ok=True)
            (core_dir / "task_router.py").write_text(
                "class TaskRouter:\n"
                "    def route_task(self, content):\n"
                "        return 'architect', object()\n",
                encoding="utf-8",
            )
            (core_dir / "monitor.py").write_text(
                "class Monitor:\n"
                "    def __init__(self):\n"
                "        self.metrics = []\n"
                "    def record_agent_metric(self, agent_id, metric_type, value):\n"
                "        self.metrics.append((agent_id, metric_type, value))\n"
                "    def get_dashboard_data(self):\n"
                "        return {'summary': {'total_alerts': 0}}\n",
                encoding="utf-8",
            )
            (core_dir / "workflow_engine.py").write_text(
                "class WorkflowEngine:\n"
                "    def __init__(self, task_router=None, message_bus=None):\n"
                "        self.task_router = task_router\n"
                "    def create_workflow(self, workflow_id, name, description, steps):\n"
                "        class Workflow:\n"
                "            def __init__(self, workflow_id):\n"
                "                self.id = workflow_id\n"
                "        return Workflow(workflow_id)\n"
                "    def execute_workflow(self, workflow_id):\n"
                "        return {'success': True}\n",
                encoding="utf-8",
            )

            baseline = baseline_module.capture_framework_baseline(
                iterations=1,
                framework_root=framework_root,
                label="before",
            )

            self.assertEqual(baseline["label"], "before")
            self.assertIn("dispatch", baseline["scenarios"])

    def test_persist_benchmark_run_writes_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "baseline.json"
            payload = {
                "label": "current",
                "scenarios": {
                    "dispatch": {"latency_ms": {"avg": 1.0, "p95": 1.0, "max": 1.0}, "cpu_ms": {"avg": 1.0, "p95": 1.0, "max": 1.0}},
                },
            }

            baseline_module.persist_benchmark_run(target, payload)

            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["label"], "current")

    def test_export_git_revision_framework_writes_source_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "exported"

            class Result:
                def __init__(self, stdout):
                    self.stdout = stdout
                    self.returncode = 0

            def fake_runner(command, cwd, capture_output, text, check):
                path_spec = command[-1]
                if path_spec.endswith("task_router.py"):
                    return Result("class TaskRouter:\n    pass\n")
                if path_spec.endswith("monitor.py"):
                    return Result("class Monitor:\n    pass\n")
                return Result("class WorkflowEngine:\n    pass\n")

            exported = baseline_module.export_git_revision_framework(
                repo_root=Path(tmp),
                revision="HEAD",
                runner=fake_runner,
                temp_dir=target,
            )

            self.assertTrue((exported / "core" / "task_router.py").exists())
            self.assertTrue((exported / "core" / "monitor.py").exists())
            self.assertTrue((exported / "core" / "workflow_engine.py").exists())

    def test_export_reconstructed_before_framework_reverts_known_fixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            exported = baseline_module.export_reconstructed_before_framework(
                repo_root=Path(r"d:\KIMIK2.5\AIAgent"),
                temp_dir=Path(tmp),
            )

            monitor_source = (exported / "core" / "monitor.py").read_text(encoding="utf-8")
            workflow_source = (exported / "core" / "workflow_engine.py").read_text(encoding="utf-8")

            self.assertIn("threading.Lock()", monitor_source)
            self.assertNotIn("task.assigned_agent = step.agent", workflow_source)

    def test_capture_reconstructed_before_baseline_marks_timeout_prone_scenarios(self):
        baseline = baseline_module.capture_reconstructed_before_baseline(
            repo_root=Path(r"d:\KIMIK2.5\AIAgent"),
            iterations=1,
        )

        self.assertEqual(baseline["label"], "reconstructed-before")
        self.assertIn("dashboard", baseline["scenarios"])
        self.assertIn("timed_out_runs", baseline["scenarios"]["dashboard"])
        self.assertFalse(baseline["scenarios"]["workflow"]["correctness"]["all_runs_passed"])


if __name__ == "__main__":
    unittest.main()

