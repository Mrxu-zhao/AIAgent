# 仓库级控制平面

## 目录
- `models.py`：任务卡、事件、状态与锁域模型
- `tasks.py`：第一批标准任务注册表
- `store.py`：任务快照与事件日志落盘
- `conflicts.py`：文件级、模块级、契约级冲突检测
- `adapters.py`：`Hermes` 直连执行适配器与 `OpenClaw` 预留接口
- `executor.py`：失败隔离、重试判断与命令装配
- `baseline.py`：延迟与 CPU 目标比较
- `reporting.py`：报告片段渲染
- `aggregator.py`：最终 Markdown 报告生成
- `runner.py`：共享批次入口，负责任务注册与调度装配
- `run_batch.py`：控制平面自有任务批次脚本入口
- `run_benchmarks.py`：独立基线重建入口

## 当前边界
- 第一阶段直接支持 `Hermes` 调度命令装配。
- `OpenClaw` 已提供 dry-run MVP 适配接口，真实 live 执行仍留待后续阶段。
- 调度框架的 P0 修复由控制平面的测试集统一验证。
- `TaskStore` 已支持基于 `expected_version` 的乐观并发拒绝，以及基于 `version` / `last_event_id` 的快照校验。
- `ControlPlaneExecutor` 已在关键状态迁移中消费 `expected_version`，对完成态写入提供最小 compare-and-swap 保护。
- `ControlPlaneOrchestrator` 已负责高层多任务并行调度，并把 CAS 语义上推到 ready 任务选择、冲突解释和直接依赖阻塞传播。
- 调度器不直接写 `done` / `failed` 终态，终态仍由 `ControlPlaneExecutor` 负责。
- `runner.py` 已把 `TASKS`、`TaskStore`、`ControlPlaneExecutor` 和 `ControlPlaneOrchestrator` 装配为统一批次执行入口。
- `run_batch.py` 与 `team-cli.py control-plane-run` 共享同一条 runner 链路，不复制调度逻辑。
- `team.sh`、`team-dispatch.sh`、`team-tmux.sh` 已退化为薄适配层，统一转发到控制平面入口或兼容 CLI。

## 推荐执行顺序
1. 使用 `runner.py` 或 `run_batch.py` 注册任务并建立状态仓
2. 通过共享 runner 装配执行器、适配器与 `ControlPlaneOrchestrator`
3. 使用 `ControlPlaneOrchestrator` 选择 ready 任务并执行高层调度
4. 如需从旧 CLI 触发，使用 `team-cli.py control-plane-run`
5. 运行调度框架 P0 回归测试
6. 采集基线并比较优化前后指标
7. 聚合执行结果并生成最终报告

## 基线与性能报告
运行以下命令重建当前基线、近似修复前基线与性能报告：

```bash
python .hermes/team/control_plane/run_benchmarks.py
```

输出产物：
- `.hermes/team/control_plane/artifacts/current-baseline.json`
- `.hermes/team/control_plane/artifacts/before-baseline.json`
- `.hermes/team/control_plane/artifacts/performance-report.md`

说明：
- `run_benchmarks.py` 会对 `current` 与 `reconstructed-before` 使用相同的负载配置，保证性能对比口径一致。
- 当前默认负载会同时记录 `dispatch_batch_size` 与 `workflow_parallel_fanout`，让 `dispatch` 与 `workflow` 更接近真实路径而不是只跑单次调用。
- `performance-report.md` 现在区分 `reference`、`performance`、`correctness` 三类场景，其中 `workflow` 会额外输出显式 `step.agent` 是否被尊重的正确性结论。

## 验证基线
- `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`：`90 tests, OK`
- `python -B -m coverage report --include=".hermes/team/control_plane/config.py,.hermes/team/control_plane/persistent_bus.py,.hermes/team/control_plane/workflow_runtime.py,.hermes/team/control_plane/cli.py"`：`94%`
- `ruff check .hermes/team/control_plane .hermes/team/调度框架/core .hermes/team/调度框架/cli/team-cli.py tests/control_plane --ignore E402,E501,E722,E741`：`All checks passed`
