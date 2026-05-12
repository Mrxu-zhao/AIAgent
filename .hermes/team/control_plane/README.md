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
- `run_benchmarks.py`：独立基线重建入口

## 当前边界
- 第一阶段直接支持 `Hermes` 调度命令装配。
- `OpenClaw` 仅保留统一适配接口，不在本阶段实现运行时执行。
- 调度框架的 P0 修复由控制平面的测试集统一验证。
- `TaskStore` 已支持基于 `expected_version` 的乐观并发拒绝，以及基于 `version` / `last_event_id` 的快照校验。

## 推荐执行顺序
1. 注册任务并建立状态仓
2. 使用执行器与适配器装配 `Hermes` 调度命令
3. 运行调度框架 P0 回归测试
4. 采集基线并比较优化前后指标
5. 聚合执行结果并生成最终报告

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
