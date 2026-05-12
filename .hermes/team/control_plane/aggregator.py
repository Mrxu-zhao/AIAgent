from pathlib import Path

from baseline import compare_runs
from reporting import render_bullet_section


def summarize_store(store):
    summary = {"done": 0, "failed": 0, "blocked": 0}
    for snapshot_file in store.state_dir.glob("*.json"):
        snapshot = store.read_snapshot(snapshot_file.stem)
        status = snapshot.get("status")
        if status == "done":
            summary["done"] += 1
        elif status == "failed":
            summary["failed"] += 1
        elif status == "blocked":
            summary["blocked"] += 1
    return summary


def build_report(output_dir: Path, task_summary, performance_summary):
    output_dir.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "# 控制平面执行报告",
            "",
            render_bullet_section(
                "执行概览",
                [
                    f"done: {task_summary['done']}",
                    f"failed: {task_summary['failed']}",
                    f"blocked: {task_summary['blocked']}",
                ],
            ).rstrip(),
            "",
            render_bullet_section(
                "性能对比报告",
                [f"overall_ok: {performance_summary['overall_ok']}"],
            ).rstrip(),
            "",
        ]
    )
    report_path = output_dir / "final-report.md"
    report_path.write_text(content, encoding="utf-8")
    return content


def build_performance_report(output_dir: Path, current_run, previous_run=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Performance Report", ""]
    for scenario, current_metrics in current_run["scenarios"].items():
        lines.append(f"## {scenario}")
        goal_type = current_metrics.get("goal_type")
        if goal_type:
            lines.append(f"- goal_type: {goal_type}")
        if "counts_toward_overall" in current_metrics:
            lines.append(f"- counts_toward_overall: {current_metrics['counts_toward_overall']}")
        if previous_run and scenario in previous_run.get("scenarios", {}):
            previous_metrics = previous_run["scenarios"][scenario]
            verdict = compare_runs(
                before={
                    "latency": previous_metrics["latency_ms"]["avg"],
                    "cpu": previous_metrics["cpu_ms"]["avg"],
                },
                after={
                    "latency": current_metrics["latency_ms"]["avg"],
                    "cpu": current_metrics["cpu_ms"]["avg"],
                },
            )
            lines.append(f"- latency_before_avg_ms: {previous_metrics['latency_ms']['avg']}")
            lines.append(f"- latency_after_avg_ms: {current_metrics['latency_ms']['avg']}")
            lines.append(f"- cpu_before_avg_ms: {previous_metrics['cpu_ms']['avg']}")
            lines.append(f"- cpu_after_avg_ms: {current_metrics['cpu_ms']['avg']}")
            lines.append(f"- latency_ok: {verdict['latency_ok']}")
            lines.append(f"- cpu_ok: {verdict['cpu_ok']}")
            lines.append(f"- overall_ok: {verdict['overall_ok']}")
            if current_metrics.get("correctness") and previous_metrics.get("correctness"):
                lines.append(f"- correctness_check: {current_metrics['correctness']['check']}")
                lines.append(
                    f"- correctness_expected_agent: {current_metrics['correctness']['expected_agent']}"
                )
                lines.append(
                    f"- correctness_before_passed: {previous_metrics['correctness']['all_runs_passed']}"
                )
                lines.append(
                    f"- correctness_after_passed: {current_metrics['correctness']['all_runs_passed']}"
                )
                lines.append(
                    f"- correctness_before_runs: {previous_metrics['correctness']['passed_runs']}/{previous_metrics['correctness']['total_runs']}"
                )
                lines.append(
                    f"- correctness_after_runs: {current_metrics['correctness']['passed_runs']}/{current_metrics['correctness']['total_runs']}"
                )
        else:
            lines.append("- comparison_available: False")
            lines.append(f"- latency_avg_ms: {current_metrics['latency_ms']['avg']}")
            lines.append(f"- cpu_avg_ms: {current_metrics['cpu_ms']['avg']}")
            if current_metrics.get("correctness"):
                lines.append(f"- correctness_check: {current_metrics['correctness']['check']}")
                lines.append(
                    f"- correctness_after_passed: {current_metrics['correctness']['all_runs_passed']}"
                )
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    report_path = output_dir / "performance-report.md"
    report_path.write_text(content, encoding="utf-8")
    return content
