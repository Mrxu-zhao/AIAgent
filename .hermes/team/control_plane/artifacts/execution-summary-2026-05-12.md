# 控制平面实施阶段执行摘要

## 已完成范围
- 已建立 `.hermes/team/control_plane/` 最小控制平面目录。
- 已实现任务模型、任务注册表、状态仓、事件日志、冲突检测、失败重试判断、报告生成与基线比较。
- 已为 `TaskStore` 增加乐观并发保护：支持 `expected_version` 冲突拒绝与快照校验。
- 已打通 `Hermes` 调度命令装配与执行器事件回写路径，并为关键状态迁移接入最小 compare-and-swap 保护。
- 已新增 `ControlPlaneOrchestrator`，支持多任务并行调度、`VERSION_CONFLICT` 解释和直接依赖阻塞传播。
- 已为 `OpenClaw` 预留适配接口，当前返回 `NotImplementedError`。
- 已修复调度框架三项 P0 问题：
  - `monitor.py` 仪表盘死锁
  - `workflow_engine.py` 忽略显式 `step.agent`
  - `team-cli.py` 未启动监控生命周期

## 当前验证结果
- 导出验证：`python -m unittest tests.control_plane.test_orchestrator.OrchestratorExportTests -v`
- 导出结果：`1 test, OK`
- 控制平面全量测试：`python -m unittest tests.control_plane.test_adapters tests.control_plane.test_aggregator tests.control_plane.test_baseline tests.control_plane.test_benchmark_runner tests.control_plane.test_conflicts tests.control_plane.test_executor tests.control_plane.test_framework_cli tests.control_plane.test_framework_monitor tests.control_plane.test_framework_workflow tests.control_plane.test_models tests.control_plane.test_orchestrator tests.control_plane.test_store tests.control_plane.test_tasks -v`
- 测试结果：`46 tests, OK`
- 发现模式检查：`python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
- 发现模式结果：`46 tests, OK`
- 覆盖范围：
  - 控制平面模型与适配器
  - 状态仓与冲突检测
  - 版本冲突拒绝与快照校验
  - 执行器、Hermes 命令装配、事件回写与版本冲突检测
  - 高层 orchestrator 调度、ready 任务选择、冲突解释与直接依赖阻塞传播
  - 基线比较、真实基准采样辅助与性能报告生成
  - 独立 benchmark runner 与基线产物重建
  - workflow 显式 `step.agent` 正确性基线与报告渲染
  - 调度框架 P0 回归

## 当前基线产物
- 近似修复前基线：`.hermes/team/control_plane/artifacts/before-baseline.json`
- 当前基线数据：`.hermes/team/control_plane/artifacts/current-baseline.json`
- 当前性能报告：`.hermes/team/control_plane/artifacts/performance-report.md`
- 当前已采样场景：
  - `dispatch`
  - `dashboard`
  - `workflow`
- 当前统一负载口径：`before/current` 均使用 `cpu_burn_iterations = 2000000`
- 当前场景负载：`dispatch_batch_size = 12`、`workflow_parallel_fanout = 3`
- 说明：由于仓库没有历史框架源码，本次 `before` 采用“可重复重建的修复前近似基线”，它会自动回退已知三处修复中的两处核心运行时变更：`monitor` 锁修复与 `workflow` 显式 `step.agent` 修复。

## 当前对比结论
- 延迟目标：仅 `dashboard` 场景达到，整体未达成。`dispatch` 是参考场景，不计入性能目标；`workflow` 主要体现正确性恢复而非提速。
- 关键数据：
- `dispatch`: `62.55238 ms -> 64.02816 ms`
- `dashboard`: `200.0 ms -> 63.2296 ms`
- `workflow`: `63.8902 ms -> 63.53394 ms`
- CPU 目标：未达成。`dashboard` 的 CPU 从 `66.46562 ms` 下降到 `62.5 ms`，但未达到 `>= 15%` 目标。
- 正确性目标：`workflow` 已恢复。`step.agent` 显式指定场景在 `reconstructed-before` 为 `0/5` 通过，在当前版本为 `5/5` 通过。
- 额外证据：`reconstructed-before` 中 `dashboard` 场景 `5/5` 次触发 `0.2s` 超时，符合修复前死锁风险的预期表现。

## 当前边界
- 已满足“`Hermes` 可直接执行”的第一阶段要求，控制平面执行器已具备调用适配器、执行命令、回写 started/completed/failed 事件的最小运行时能力。
- `OpenClaw` 目前只有接口保留，没有执行实现。
- 当前已经产出真实“当前基线”数据和“可重复重建的近似 before 基线”，且两者已统一负载口径；报告也已区分参考场景、性能场景和正确性场景。状态仓、执行器与 orchestrator 已具备最小 compare-and-swap 语义。

## 建议下一步
1. 如果你后续拿到真实旧版本，再补一份真实 `before` 基线，替换当前近似对照。
2. 为 `dashboard` 设计更接近生产状态量级的指标注入和告警密度，继续验证 CPU 降幅是否能稳定达到目标。
3. 如果要继续追性能，优先增加真正存在代码差异的场景，不再把 `dispatch` 这类参考场景纳入优化 KPI。
4. 在真实负载下继续验证 orchestrator 的并发调度、冲突处理与依赖阻塞行为。
