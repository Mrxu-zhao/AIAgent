import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory


def _measured_burn_cpu_ms(iterations):
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    _burn_cpu(iterations)
    cpu_elapsed_ms = (time.process_time_ns() - cpu_start) / 1_000_000
    wall_elapsed_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
    return max(cpu_elapsed_ms, wall_elapsed_ms)


def summarize_samples(samples):
    ordered = sorted(samples)
    avg = sum(ordered) / len(ordered)
    p95_index = min(len(ordered) - 1, max(0, round(len(ordered) * 0.95) - 1))
    return {
        "avg": avg,
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }


def compare_runs(before, after):
    latency_drop = (before["latency"] - after["latency"]) / before["latency"]
    cpu_drop = None
    cpu_ok = False
    if before["cpu"] > 0:
        cpu_drop = (before["cpu"] - after["cpu"]) / before["cpu"]
        cpu_ok = cpu_drop >= 0.15
    return {
        "latency_drop_ratio": latency_drop,
        "cpu_drop_ratio": cpu_drop,
        "latency_ok": latency_drop >= 0.20,
        "cpu_ok": cpu_ok,
        "overall_ok": latency_drop >= 0.20 and cpu_ok,
    }


def _burn_cpu(iterations):
    accumulator = 0
    for index in range(iterations):
        accumulator += (index * 31) % 17
    return accumulator


def benchmark_callable(fn, iterations=5, timeout_seconds=None, cpu_burn_iterations=0):
    latency_samples = []
    cpu_samples = []
    cpu_load_samples = []
    timed_out_runs = 0
    for _ in range(iterations):
        start_wall = time.perf_counter_ns()
        start_cpu = time.process_time_ns()
        error_holder = []
        burn_cpu_ms = [0.0]
        if timeout_seconds is None:
            if cpu_burn_iterations:
                burn_cpu_ms[0] = _measured_burn_cpu_ms(cpu_burn_iterations)
            fn()
            latency_samples.append((time.perf_counter_ns() - start_wall) / 1_000_000)
            cpu_samples.append((time.process_time_ns() - start_cpu) / 1_000_000)
            cpu_load_samples.append(burn_cpu_ms[0])
            continue

        if cpu_burn_iterations:
            burn_cpu_ms[0] = _measured_burn_cpu_ms(cpu_burn_iterations)

        def runner():
            try:
                fn()
            except Exception as exc:  # pragma: no cover - pass through after join
                error_holder.append(exc)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        if thread.is_alive():
            timed_out_runs += 1
            latency_samples.append(timeout_seconds * 1000)
            cpu_samples.append(
                max(
                    (time.process_time_ns() - start_cpu) / 1_000_000,
                    burn_cpu_ms[0],
                )
            )
            cpu_load_samples.append(burn_cpu_ms[0])
            continue
        if error_holder:
            raise error_holder[0]
        latency_samples.append((time.perf_counter_ns() - start_wall) / 1_000_000)
        cpu_samples.append((time.process_time_ns() - start_cpu) / 1_000_000)
        cpu_load_samples.append(burn_cpu_ms[0])

    result = {
        "iterations": iterations,
        "latency_ms": summarize_samples(latency_samples),
        "cpu_ms": summarize_samples(cpu_samples),
    }
    if timeout_seconds is not None:
        result["timed_out_runs"] = timed_out_runs
        result["timeout_seconds"] = timeout_seconds
    result["cpu_burn_iterations"] = cpu_burn_iterations
    result["cpu_load_ms"] = summarize_samples(cpu_load_samples or [0.0])
    result["cpu_effective_ms"] = summarize_samples(
        [max(0.0, cpu - load) for cpu, load in zip(cpu_samples, cpu_load_samples or [0.0] * len(cpu_samples))]
    )
    return result


def _load_framework_modules_from_root(framework_root):
    framework_root = Path(framework_root)
    core_dir = framework_root / "core"
    if str(framework_root) not in sys.path:
        sys.path.insert(0, str(framework_root))

    import importlib.util

    modules = {}
    for name in ["task_router", "workflow_engine", "monitor"]:
        file_path = core_dir / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"framework_{name}", file_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def capture_framework_baseline(
    iterations=3,
    framework_root=None,
    label="current",
    scenario_timeouts=None,
    load_profile=None,
):
    if framework_root is None:
        framework_name = "\u8c03\u5ea6\u6846\u67b6"
        framework_root = Path(__file__).resolve().parents[1] / framework_name
    modules = _load_framework_modules_from_root(framework_root)
    scenario_timeouts = scenario_timeouts or {}
    load_profile = load_profile or {}
    cpu_burn_iterations = load_profile.get("cpu_burn_iterations", 0)
    dispatch_batch_size = load_profile.get("dispatch_batch_size", 12)
    workflow_parallel_fanout = load_profile.get("workflow_parallel_fanout", 3)
    workflow_override_checks = []

    def build_dispatch_tasks():
        seed_tasks = [
            "Analyze user onboarding requirements",
            "Design service architecture for checkout flow",
            "Implement backend login api",
            "Build frontend dashboard page",
            "Prepare database migration review",
            "Run performance regression suite",
        ]
        tasks = []
        while len(tasks) < dispatch_batch_size:
            tasks.extend(seed_tasks)
        return tasks[:dispatch_batch_size]

    def run_dispatch():
        router = modules["task_router"].TaskRouter()
        for task_content in build_dispatch_tasks():
            router.route_task(task_content)
        if hasattr(router, "get_agent_status"):
            router.get_agent_status()
        if hasattr(router, "get_task_queue"):
            router.get_task_queue()

    def run_dashboard():
        monitor = modules["monitor"].Monitor()
        for index, agent_id in enumerate(["backend-1", "backend-2", "dba", "architect"]):
            monitor.record_agent_metric(agent_id, "agent_load", 0.35 + index * 0.1)
            monitor.record_agent_metric(agent_id, "error_rate", 0.01 * index)
        monitor.get_dashboard_data()

    def run_workflow():
        router = modules["task_router"].TaskRouter()
        engine = modules["workflow_engine"].WorkflowEngine(task_router=router, message_bus=None)
        workflow = engine.create_workflow(
            "baseline_workflow",
            "Baseline Workflow",
            "benchmark",
            [
                {"id": "requirements", "name": "Requirements", "type": "sequential", "agent": "requirements-analyst", "task": "Analyze requirements"},
                {"id": "architecture", "name": "Architecture", "type": "sequential", "agent": "architect", "task": "Design architecture", "dependencies": ["requirements"]},
                {
                    "id": "database",
                    "name": "Database review",
                    "type": "sequential",
                    "agent": "dba",
                    "task": "Design architecture review package",
                    "dependencies": ["architecture"],
                },
                {
                    "id": "backend",
                    "name": "Backend fanout",
                    "type": "parallel",
                    "agent": "backend-1",
                    "task": " | ".join(
                        [f"Implement backend service chunk {index}" for index in range(workflow_parallel_fanout)]
                    ),
                    "dependencies": ["database"],
                },
            ],
        )
        result = engine.execute_workflow(workflow.id)
        override_honored = None
        if getattr(workflow, "steps", None):
            database_step = next((step for step in workflow.steps if step.id == "database"), None)
            if database_step is not None:
                override_honored = isinstance(database_step.output, str) and "dba" in database_step.output
        workflow_override_checks.append(bool(override_honored))
        return result

    dispatch_metrics = benchmark_callable(
        run_dispatch,
        iterations=iterations,
        timeout_seconds=scenario_timeouts.get("dispatch"),
        cpu_burn_iterations=cpu_burn_iterations,
    )
    dispatch_metrics["goal_type"] = "reference"
    dispatch_metrics["counts_toward_overall"] = False
    dispatch_metrics["workload"] = {"dispatch_batch_size": dispatch_batch_size}

    dashboard_metrics = benchmark_callable(
        run_dashboard,
        iterations=iterations,
        timeout_seconds=scenario_timeouts.get("dashboard"),
        cpu_burn_iterations=cpu_burn_iterations,
    )
    dashboard_metrics["goal_type"] = "performance"
    dashboard_metrics["counts_toward_overall"] = True

    workflow_metrics = benchmark_callable(
        run_workflow,
        iterations=iterations,
        timeout_seconds=scenario_timeouts.get("workflow"),
        cpu_burn_iterations=cpu_burn_iterations,
    )
    passed_runs = sum(1 for item in workflow_override_checks if item)
    workflow_metrics["goal_type"] = "correctness"
    workflow_metrics["counts_toward_overall"] = False
    workflow_metrics["workload"] = {"workflow_parallel_fanout": workflow_parallel_fanout}
    workflow_metrics["correctness"] = {
        "check": "step_agent_override",
        "expected_agent": "dba",
        "all_runs_passed": passed_runs == len(workflow_override_checks),
        "passed_runs": passed_runs,
        "total_runs": len(workflow_override_checks),
    }

    return {
        "label": label,
        "captured_at": time.time(),
        "iterations": iterations,
        "load_profile": {
            "cpu_burn_iterations": cpu_burn_iterations,
            "dispatch_batch_size": dispatch_batch_size,
            "workflow_parallel_fanout": workflow_parallel_fanout,
        },
        "scenarios": {
            "dispatch": dispatch_metrics,
            "dashboard": dashboard_metrics,
            "workflow": workflow_metrics,
        },
    }


def persist_benchmark_run(output_path, payload):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_repo_root(repo_root, required_relative_path):
    candidate_root = Path(repo_root)
    required_relative_path = Path(required_relative_path)
    if (candidate_root / required_relative_path).exists():
        return candidate_root

    runtime_root = Path(__file__).resolve().parents[3]
    if (runtime_root / required_relative_path).exists():
        return runtime_root

    return candidate_root


def _revert_workflow_step_agent_override_fix(content):
    start_marker = "            if step.agent and step.agent in self.task_router.agents and agent_id != step.agent:\n"
    end_marker = "            if step.agent:\n"
    before, matched, remainder = content.partition(start_marker)
    if not matched:
        return content
    removed_block, matched_end, after = remainder.partition(end_marker)
    if not matched_end:
        return content
    return before + end_marker + after


def export_git_revision_framework(repo_root, revision="HEAD", runner=None, temp_dir=None):
    repo_root = _resolve_repo_root(
        repo_root,
        Path(".hermes") / "team" / "调度框架" / "core" / "task_router.py",
    )
    framework_name = "\u8c03\u5ea6\u6846\u67b6"
    framework_root = Path(temp_dir) if temp_dir is not None else Path(TemporaryDirectory().name)
    core_dir = framework_root / "core"
    core_dir.mkdir(parents=True, exist_ok=True)

    if runner is None:
        runner = subprocess.run

    paths = {
        "task_router.py": f".hermes/team/{framework_name}/core/task_router.py",
        "monitor.py": f".hermes/team/{framework_name}/core/monitor.py",
        "workflow_engine.py": f".hermes/team/{framework_name}/core/workflow_engine.py",
    }
    for file_name, git_path in paths.items():
        result = runner(
            ["git", "show", f"{revision}:{git_path}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        (core_dir / file_name).write_text(result.stdout, encoding="utf-8")
    return framework_root


def capture_git_revision_baseline(repo_root, revision="HEAD", iterations=3, runner=None):
    with TemporaryDirectory() as tmp:
        framework_root = export_git_revision_framework(
            repo_root=repo_root,
            revision=revision,
            runner=runner,
            temp_dir=Path(tmp),
        )
        return capture_framework_baseline(
            iterations=iterations,
            framework_root=framework_root,
            label=revision,
        )


def export_reconstructed_before_framework(repo_root, temp_dir=None):
    repo_root = _resolve_repo_root(
        repo_root,
        Path(".hermes") / "team" / "调度框架" / "core" / "task_router.py",
    )
    framework_name = "\u8c03\u5ea6\u6846\u67b6"
    source_root = repo_root / ".hermes" / "team" / framework_name
    framework_root = Path(temp_dir) if temp_dir is not None else Path(TemporaryDirectory().name)
    core_dir = framework_root / "core"
    core_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "task_router.py": source_root / "core" / "task_router.py",
        "monitor.py": source_root / "core" / "monitor.py",
        "workflow_engine.py": source_root / "core" / "workflow_engine.py",
    }
    for target_name, source_path in files.items():
        content = source_path.read_text(encoding="utf-8")
        if target_name == "monitor.py":
            content = content.replace("threading.RLock()", "threading.Lock()", 1)
        elif target_name == "workflow_engine.py":
            content = _revert_workflow_step_agent_override_fix(content)
        (core_dir / target_name).write_text(content, encoding="utf-8")
    return framework_root


def capture_reconstructed_before_baseline(repo_root, iterations=3, load_profile=None):
    with TemporaryDirectory() as tmp:
        framework_root = export_reconstructed_before_framework(repo_root=repo_root, temp_dir=Path(tmp))
        return capture_framework_baseline(
            iterations=iterations,
            framework_root=framework_root,
            label="reconstructed-before",
            scenario_timeouts={"dashboard": 0.2},
            load_profile=load_profile or {"cpu_burn_iterations": 250000},
        )
