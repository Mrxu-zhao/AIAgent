# 控制平面并行调度 CAS 上推设计

## 1. 背景

当前仓库级控制平面已经具备以下基础能力：

- `TaskStore` 支持 `append_event(expected_version=...)` 的乐观并发拒绝。
- `ControlPlaneExecutor` 已在 `READY -> RUNNING -> DONE/FAILED` 的关键状态迁移中消费 `expected_version`。
- `TaskStore.validate_snapshot(...)` 可用于读取后校验快照版本和 `last_event_id`。

但当前多任务并行调度仍主要停留在更低层的调度框架内部，控制平面自身还没有一个统一的并行编排入口。结果是：

- 控制平面 CAS 语义只保护单任务执行路径。
- 高层“哪些任务可以并发启动、谁来阻塞下游、谁来跳过版本冲突”还没有统一规则。
- 如果后续直接把并行逻辑塞进 `workflow_engine.py`，会让控制平面与旧调度框架发生过深耦合。

本设计的目标，是把 CAS 语义上推到“控制平面编排层”，让控制平面自己成为仓库级多任务并行调度的入口。

## 2. 目标与非目标

### 2.1 目标

- 新增仓库级控制平面并行调度器，统一管理多任务并发启动。
- 把 `expected_version` 语义从单任务执行上推到高层调度决策。
- 明确 `ready / running / blocked / done / failed` 的调度层流转规则。
- 在多任务并行执行时，保证竞争写入不会被静默覆盖。
- 保持现有 `TaskStore`、`ControlPlaneExecutor`、`aggregator` 的职责清晰。

### 2.2 非目标

- 本阶段不重写 `.hermes/team/调度框架/core/workflow_engine.py`。
- 本阶段不引入分布式锁、数据库事务或跨进程一致性协议。
- 本阶段不新增 `OpenClaw` 运行时能力。
- 本阶段不把所有任务状态强制扩展到 `reviewing -> done` 完整审批流。

## 3. 方案比较

### 方案 A：控制平面编排层

新增 `orchestrator.py`，由控制平面统一执行高层并发调度；单任务状态迁移继续交给 `ControlPlaneExecutor`。

优点：

- 与现有控制平面分层一致，边界最清晰。
- 可以直接复用 `TaskStore` 与 `ControlPlaneExecutor` 的 CAS 能力。
- 避免深度侵入旧调度框架。

缺点：

- 需要新增一层编排器与对应测试。

### 方案 B：直接改调度框架并行执行

把 `TaskStore` 和 `expected_version` 直接接入 `workflow_engine.py` 内部并行路径。

优点：

- 旧工作流路径可直接受控。

缺点：

- 控制平面和旧调度框架职责混杂。
- 调度框架会被迫理解控制平面状态仓细节。

### 方案选择

本设计采用 **方案 A：控制平面编排层**。

## 4. 总体设计

### 4.1 新增组件

新增：

- `.hermes/team/control_plane/orchestrator.py`
- `tests/control_plane/test_orchestrator.py`

必要时小幅更新：

- `.hermes/team/control_plane/__init__.py`
- `.hermes/team/control_plane/README.md`
- `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`

### 4.2 职责边界

`TaskStore`

- 保存任务快照和事件日志。
- 负责版本校验与快照拒绝覆盖。

`ControlPlaneExecutor`

- 负责单任务执行。
- 负责单任务启动、完成、失败路径的 CAS 状态迁移。

`ControlPlaneOrchestrator`

- 负责读取任务集合和依赖图。
- 负责找出当前轮次的 `ready` 任务。
- 负责并发提交单任务执行。
- 负责解释 `VERSION_CONFLICT`、失败阻塞和轮次推进。

`aggregator`

- 只做汇总，不参与调度决策。

## 5. 核心运行模型

### 5.1 任务输入

调度器以一组 `TaskCard` 为输入，并从中构建：

- `task_by_id`
- `dependency_graph`
- `reverse_dependency_graph`

### 5.2 就绪判定

任务满足以下条件时，才允许进入 `ready` 候选集：

- 当前状态不属于 `done / failed / blocked / cancelled`
- 所有直接依赖任务都处于 `done`

如果任务没有依赖，且当前状态为 `planned` 或 `ready`，则可被调度器纳入当前轮次。

### 5.3 并发执行

调度器提供固定并发度，例如 `max_workers`。

每一轮：

1. 扫描所有任务快照
2. 选出可执行任务
3. 使用线程池并发调用 `ControlPlaneExecutor.execute_task(...)`
4. 收集每个任务的执行结果
5. 根据结果更新调度层视图
6. 进入下一轮，直到没有可推进任务

### 5.4 CAS 冲突语义

如果 `ControlPlaneExecutor.execute_task(...)` 返回：

- `success = False`
- `error_code = "VERSION_CONFLICT"`

则调度器必须将该结果解释为：

- 本轮未拿到该任务的执行权
- 该任务当前快照不能被调度器二次覆盖
- 该任务不应被误标记为 `failed`
- 调度器应重新读取快照，并在下一轮重新判断是否还需要调度

这使得高层调度与低层单任务执行共享同一套 CAS 语义。

### 5.5 失败阻塞传播

如果某任务执行结果是普通失败（非 `VERSION_CONFLICT`）：

- 当前任务状态由 `ControlPlaneExecutor` 自己写成 `failed`
- 调度器只负责把其直接依赖者标记为 `blocked`
- 与失败任务无依赖关系的任务可继续执行

阻塞传播必须只沿直接依赖图向下游传播，不允许全局停机。

## 6. 调度器接口设计

建议提供以下最小接口：

### 6.1 `build_dependency_graph(cards)`

输入 `TaskCard` 列表，输出：

- 正向依赖图
- 反向依赖图

### 6.2 `get_ready_tasks(cards)`

基于当前快照和依赖关系，返回当前轮次可调度的任务列表。

### 6.3 `run(cards, adapter, command_runner, max_workers=2)`

执行完整的多任务并行调度流程，并返回结构化摘要，例如：

- `done_tasks`
- `failed_tasks`
- `blocked_tasks`
- `conflicted_tasks`
- `rounds`

### 6.4 `block_dependents(task_id)`

在某任务失败后，将直接依赖者写为 `blocked`，并记录对应事件。

## 7. 事件与状态约束

调度层新增的关键约束如下：

- 调度器不直接写 `done` 或 `failed` 终态，终态仍由 `ControlPlaneExecutor` 写入。
- 调度器可以写入高层协调事件，例如 `task_ready`、`task_blocked`、`task_conflict_detected`。
- 调度器写协调事件时，也必须消费 `expected_version`，不能绕过状态仓门禁。

推荐新增或明确使用以下事件：

- `task_ready`
- `task_blocked`
- `task_conflict_detected`

## 8. 测试设计

新增 `tests/control_plane/test_orchestrator.py`，至少覆盖以下场景：

### 8.1 并行就绪任务可同时推进

- 两个无依赖任务在同一轮进入执行
- 最终都能进入 `done`

### 8.2 失败只阻塞直接依赖者

- `A -> B`，`C` 无依赖
- 若 `A` 失败，则 `B` 进入 `blocked`
- `C` 不受影响，可继续执行

### 8.3 版本冲突不会被误判为失败

- 某任务在执行中被外部事件抢先推进版本
- 执行器返回 `VERSION_CONFLICT`
- 调度器应把它记入 `conflicted_tasks`
- 快照不能被误写为 `failed`

### 8.4 调度轮次可收敛

- 多轮推进后，当没有 `ready` 任务时，调度器退出
- 输出的摘要与最终快照一致

## 9. 风险与约束

- 当前 `TaskStore.append_event(...)` 仍是文件级读写，不是原子事务；本设计只提供“单机乐观并发保护”，不声称提供强一致事务。
- 若调度器和外部进程同时对同一任务写入，`VERSION_CONFLICT` 将变成正常路径之一，因此摘要必须显式展示冲突任务。
- 如果调度层直接写终态，会与 `ControlPlaneExecutor` 双写冲突，因此必须严格限制职责边界。

## 10. 实施顺序

推荐按以下顺序落地：

1. 先补 `test_orchestrator.py` 的失败测试
2. 实现 `orchestrator.py` 最小能力
3. 接入 `task_conflict_detected` / `task_blocked` 等协调事件
4. 跑控制平面全量测试
5. 更新 README 与执行摘要

## 11. 结论

把 CAS 语义上推到控制平面编排层的关键，不是把所有状态写路径都塞进一个模块，而是让高层调度也遵循“读快照版本 -> 尝试推进 -> 冲突即回退重读”的同一套规则。

本设计通过新增 `ControlPlaneOrchestrator`，把高层并行调度、失败阻塞传播和冲突解释统一收口在控制平面内部，同时保留旧调度框架的边界稳定性。这是下一阶段增强开发中最小、最可验证、也最适合继续演进的方案。
