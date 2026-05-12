# 控制平面真实任务批次入口接线设计

## 1. 背景

当前仓库级控制平面已经具备以下能力：

- `tasks.py` 提供结构化的 `TaskCard` 任务注册表。
- `TaskStore` 负责状态快照、事件日志和乐观并发门禁。
- `ControlPlaneExecutor` 负责单任务执行和终态 CAS 写入。
- `ControlPlaneOrchestrator` 负责高层多任务并行调度、冲突解释和直接依赖阻塞传播。

但这些能力还没有被接到“真实任务批次入口”上。当前问题是：

- 控制平面没有一个统一的批量执行入口，`TASKS` 仍停留在静态定义层。
- 旧调度框架的 `team-cli.py` 也还没有复用控制平面的 orchestrator 路径。
- 如果分别在控制平面和 `team-cli.py` 里重复装配 store、executor、orchestrator，会造成入口分叉和状态语义漂移。

因此，下一阶段的目标是为控制平面增加一个共享的任务批次入口，并让控制平面自有入口与 `team-cli.py` 共用这条执行链。

## 2. 目标与非目标

### 2.1 目标

- 新增控制平面的共享批次执行入口。
- 让该入口直接消费 `tasks.py` 中的 `TASKS`。
- 新增控制平面自有脚本入口，用于直接运行仓库级任务批次。
- 在 `team-cli.py` 中新增桥接命令，复用同一个共享入口。
- 保持两条入口最终都通过 `ControlPlaneOrchestrator` 执行，确保 CAS 语义一致。

### 2.2 非目标

- 本阶段不把旧调度框架的 `dispatch`、`workflow` 等原有命令全部迁移到控制平面。
- 本阶段不做分布式调度或跨进程状态共享。
- 本阶段不引入 `OpenClaw` 运行时执行。
- 本阶段不扩展审批流、人工审核流或 Web UI 入口。

## 3. 方案比较

### 方案 A：共享 runner，控制平面入口与 team-cli 复用

新增控制平面的共享 runner 模块，由它统一完成：

- 读取 `TASKS`
- 注册初始快照
- 装配 `TaskStore`、`ControlPlaneExecutor`、`ControlPlaneOrchestrator`
- 触发批次执行
- 返回结构化摘要

然后：

- 控制平面新增一个脚本入口调用该 runner
- `team-cli.py` 新增桥接命令，复用该 runner

优点：

- 入口统一，状态语义稳定
- 控制平面主导架构，`team-cli.py` 只是桥接方
- 更适合后续继续演进为标准批次入口

缺点：

- 需要新增 runner 层和两组入口测试

### 方案 B：双入口分别直连 orchestrator

控制平面脚本和 `team-cli.py` 各自直接装配 orchestrator 并执行。

优点：

- 初看实现更快

缺点：

- 装配逻辑重复
- 更容易出现参数、状态目录、摘要格式不一致
- 后续维护成本更高

### 方案 C：先让 team-cli 主导，再反向调用控制平面

把 `team-cli.py` 作为上层主入口，再由它决定是否调用控制平面。

优点：

- 贴近旧调度框架的使用方式

缺点：

- 会让旧调度框架反向定义控制平面接口
- 容易破坏控制平面的独立边界

### 方案选择

本设计采用 **方案 A：共享 runner，双入口复用**。

## 4. 总体设计

### 4.1 新增与更新文件

新增：

- `.hermes/team/control_plane/runner.py`
- `.hermes/team/control_plane/run_batch.py`
- `tests/control_plane/test_runner.py`
- `tests/control_plane/test_framework_team_cli_control_plane.py`

更新：

- `.hermes/team/control_plane/__init__.py`
- `.hermes/team/control_plane/README.md`
- `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`
- `.hermes/team/调度框架/cli/team-cli.py`

### 4.2 核心组件职责

`tasks.py`

- 继续只负责静态任务定义
- 不负责装配、不负责执行

`runner.py`

- 提供共享批次入口
- 负责把 `TASKS` 注册到 `TaskStore`
- 负责装配 `ControlPlaneExecutor` 与 `ControlPlaneOrchestrator`
- 负责调用 orchestrator 并返回摘要

`run_batch.py`

- 提供控制平面自有脚本入口
- 接收最小参数，例如状态目录、并发度
- 调用 `runner.py` 并打印结构化结果

`team-cli.py`

- 新增一个桥接子命令，例如 `control-plane-run`
- 只负责解析 CLI 参数并调用共享 runner
- 不直接复制 orchestrator 或 executor 逻辑

## 5. 共享 runner 接口

建议在 `runner.py` 中提供如下最小接口：

### 5.1 `register_tasks(store, cards)`

- 把 `TaskCard` 批量注册到 `TaskStore`
- 若任务已存在，则保持幂等，不重复覆盖已存在快照

### 5.2 `run_registered_batch(store, cards, adapter, command_runner, max_workers=2)`

- 假设任务已注册
- 调用 `ControlPlaneOrchestrator.run(...)`
- 返回结构化调度摘要

### 5.3 `run_task_batch(cards=None, state_dir=None, events_dir=None, adapter=None, command_runner=None, max_workers=2)`

- 若 `cards` 为空，默认使用 `tasks.py` 中的 `TASKS`
- 创建或装配 `TaskStore`
- 注册任务
- 运行 orchestrator
- 返回包括状态目录、事件目录和调度摘要在内的结果

## 6. 入口设计

### 6.1 控制平面脚本入口

新增 `run_batch.py`：

- 默认读取控制平面内置 `TASKS`
- 默认使用控制平面 `state/` 和 `events/` 目录
- 支持通过命令行覆盖 `--max-workers`
- 执行完成后输出 JSON 或便于阅读的摘要文本

这条入口用于：

- 直接验证控制平面自有任务批次能否被真正执行
- 为后续 benchmark、回归和自动化脚本提供稳定入口

### 6.2 team-cli 桥接入口

在 `team-cli.py` 中新增一个控制平面子命令，例如：

- `control-plane-run`

它负责：

- 解析最小必要参数，例如 `--max-workers`
- 调用共享 runner
- 输出调度摘要

它不负责：

- 重复注册任务
- 自己实现依赖图
- 自己实现并发调度

## 7. 数据流

### 7.1 控制平面入口

1. `run_batch.py`
2. `runner.run_task_batch(...)`
3. `TaskStore`
4. `ControlPlaneOrchestrator.run(...)`
5. `ControlPlaneExecutor.execute_task(...)`
6. 快照与事件回写
7. 返回结构化摘要

### 7.2 team-cli 入口

1. `team-cli.py control-plane-run`
2. `runner.run_task_batch(...)`
3. 后续路径与控制平面入口完全一致

这保证了两条入口只是“触发方式不同”，而不是“两套调度系统并存”。

## 8. 状态与幂等约束

- 共享 runner 注册任务时必须幂等，不能因重复调用而重置已存在任务状态。
- 两条入口都必须通过同一 `TaskStore` / `ControlPlaneOrchestrator` 路径执行。
- 调度摘要至少包含：
  - `done_tasks`
  - `failed_tasks`
  - `blocked_tasks`
  - `conflicted_tasks`
  - `rounds`
- 若某任务已存在终态快照，再次运行批次时应保持终态，不回退成 `planned`。

## 9. 测试设计

### 9.1 `test_runner.py`

至少覆盖：

- runner 能从默认 `TASKS` 装配并注册任务
- runner 能调用 orchestrator 并返回摘要
- 重复注册任务不会覆盖已存在终态快照

### 9.2 `test_framework_team_cli_control_plane.py`

至少覆盖：

- `team-cli.py` 新增的控制平面命令能成功调用共享 runner
- CLI 桥接不会复制调度逻辑，只做参数转发

### 9.3 全量验证

保持以下验证路径可通过：

- `python -m unittest tests.control_plane.test_runner -v`
- `python -m unittest tests.control_plane.test_framework_team_cli_control_plane -v`
- `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`

## 10. 风险与约束

- `team-cli.py` 当前为单文件 CLI，若新增命令时直接在文件内扩散装配逻辑，会重新形成耦合；必须坚持桥接而非复制。
- `tasks.py` 中当前任务集较小，第一版 runner 先满足仓库内置任务批次，不急于支持任意外部任务清单文件。
- 如果 runner 默认直接执行真实 Hermes 命令，测试会变脆；因此需要保持可注入 `adapter` 与 `command_runner`，让测试继续使用假执行器。

## 11. 实施顺序

推荐按以下顺序落地：

1. 先为 runner 补失败测试
2. 实现 `runner.py` 的注册与批次执行最小闭环
3. 新增 `run_batch.py`
4. 为 `team-cli.py` 增加桥接子命令和测试
5. 更新导出、README 和 execution summary
6. 跑控制平面全量回归

## 12. 结论

这轮增强的关键不是“多加一个 CLI 命令”，而是把控制平面的静态任务集真正接到统一的批次执行路径上，并让控制平面自有入口与旧调度框架 CLI 共用同一条 runner 链路。

通过共享 runner：

- 控制平面获得真实可执行的任务批次入口
- `team-cli.py` 获得对控制平面的桥接能力
- 两条入口共享同一套 CAS 语义、状态仓和调度摘要

这为下一步把控制平面能力接入更真实的任务流和自动化入口提供了稳定基础。
