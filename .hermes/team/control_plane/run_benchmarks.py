from pathlib import Path

import aggregator
import baseline


def run_benchmarks(
    repo_root: Path,
    artifacts_dir: Path,
    iterations: int = 5,
    load_profile=None,
    capture_current=None,
    capture_before=None,
):
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    load_profile = load_profile or {"cpu_burn_iterations": 2_000_000}
    capture_current = capture_current or baseline.capture_framework_baseline
    capture_before = capture_before or baseline.capture_reconstructed_before_baseline

    current_run = capture_current(
        iterations=iterations,
        label="current",
        load_profile=load_profile,
    )
    before_run = capture_before(
        repo_root=repo_root,
        iterations=iterations,
        load_profile=load_profile,
    )

    baseline.persist_benchmark_run(artifacts_dir / "current-baseline.json", current_run)
    baseline.persist_benchmark_run(artifacts_dir / "before-baseline.json", before_run)
    aggregator.build_performance_report(
        artifacts_dir,
        current_run=current_run,
        previous_run=before_run,
    )
    return artifacts_dir / "performance-report.md"


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[3]
    artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    report_path = run_benchmarks(repo_root=repo_root, artifacts_dir=artifacts_dir)
    print(report_path)
