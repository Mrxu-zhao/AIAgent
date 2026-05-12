from models import LockScope, RetryPolicy, RollbackPolicy, TaskCard, TaskPriority


TASKS = [
    TaskCard(
        task_id="WS-A-P0-001",
        title="修复监控死锁",
        goal="让 dashboard 查询在锁竞争下仍可返回",
        scope=[".hermes/team/调度框架/core/monitor.py"],
        lock_scope=LockScope(
            files=[".hermes/team/调度框架/core/monitor.py"],
            modules=["monitor"],
            contracts=[],
        ),
        inputs=["assessment_report_2026-05-12.md"],
        outputs=["monitor deadlock fix", "unit test output"],
        dependencies=[],
        owner_agent="backend-1",
        review_agent="architect",
        priority=TaskPriority.P0,
        timeout_seconds=1800,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=[0, 60]),
        rollback_policy=RollbackPolicy(mode="code"),
        acceptance_criteria=["dashboard 调用 100 次均返回"],
    ),
    TaskCard(
        task_id="WS-B-P1-005",
        title="Hermes 执行适配",
        goal="为控制平面提供 Hermes 直接执行命令装配能力",
        scope=[".hermes/team/control_plane/adapters.py", ".hermes/team/control_plane/executor.py"],
        lock_scope=LockScope(
            files=[
                ".hermes/team/control_plane/adapters.py",
                ".hermes/team/control_plane/executor.py",
            ],
            modules=["control_plane"],
            contracts=["executor-adapter"],
        ),
        inputs=["team README", "team-dispatch.sh"],
        outputs=["adapter implementation", "executor dispatch command"],
        dependencies=[],
        owner_agent="backend-2",
        review_agent="architect",
        priority=TaskPriority.P1,
        timeout_seconds=1800,
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=[0]),
        rollback_policy=RollbackPolicy(mode="code"),
        acceptance_criteria=["可生成 hermes team dispatch 命令"],
    ),
]
