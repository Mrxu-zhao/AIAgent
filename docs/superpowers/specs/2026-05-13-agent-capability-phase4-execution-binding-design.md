# Agent 能力增强四期设计文档

## 1. 背景

前三期已经把上层 agent 能力补到一个可解释、可传递、可观测的状态：

- `TaskRouter` 能输出结构化 `backend_recommendation`
- `WorkflowEngine` 能跨 step 继承 `inherited_backend`
- 跨 agent 步骤会生成 handoff，并把 payload 发布到 `message_bus`
- `ControlPlaneExecutor` 已支持 `TaskCard.executor_backend`，可以按任务级 backend 覆盖默认 provider

但当前仍存在一个关键断点：

- workflow 里的 backend recommendation 还停留在上下文和 handoff 元数据层
- `WorkflowEngine._execute_agent_task()` 仍是模拟执行，不会真正落到 control plane 的执行链路
- 因此当前系统可能出现“workflow 说下一步应走 `openclaw`，但真实执行并未发生 provider 切换”的语义割裂

本期目标就是把这条链真正接通：让 workflow step 在满足条件时生成可执行任务卡，并把 `recommended/inherited backend` 映射到 `TaskCard.executor_backend`，交给 `ControlPlaneExecutor` 做真实 provider 选择。

## 2. 目标与非目标

### 2.1 目标

- 让 `WorkflowEngine` 支持“真实执行模式”，不再只返回模拟字符串结果
- 在 workflow step 执行时，把 backend recommendation 映射为真实 `TaskCard.executor_backend`
- 复用已有 `ControlPlaneExecutor` 与 provider registry，不重写执行底座
- 保持现有 workflow/handoff 结构化返回值，新增的真实执行结果继续沉淀为 `step_context`
- 用最小增量测试覆盖端到端执行绑定

### 2.2 非目标

- 本期不实现 handoff 消费方、签收、审批与状态流转
- 本期不引入新的 provider 类型，仍只支持 `hermes/openclaw`
- 本期不实现 workflow checkpoint/resume/audit 全闭环
- 本期不把所有 workflow step 都强制走 control plane，只对 agent task 路径打通真实执行

## 3. 方案比较

### 方案 A：只在 workflow 结果里记录 executor_backend

只把 `inherited_backend` 和 `backend_recommendation` 写得更完整，但 `_execute_agent_task()` 仍然返回模拟结果。

优点：

- 改动最小
- 风险最低

缺点：

- 不能解决“推荐 backend 和真实执行脱节”的核心问题
- 只是把元数据做得更像真执行

### 方案 B：workflow 直接拼 provider 命令并执行

让 `WorkflowEngine` 直接读 provider registry，自己构造命令并运行。

优点：

- 能最快打通 workflow 到执行

缺点：

- 会复制 `ControlPlaneExecutor` 的命令装配、状态写入与错误处理逻辑
- 破坏现有 control plane 边界

### 方案 C：workflow 生成任务卡，复用 control plane executor

`WorkflowEngine` 在 agent step 执行时生成临时 `TaskCard`，把 backend 绑定到 `executor_backend`，再调用 `ControlPlaneExecutor.execute_task()` 完成真实执行。

优点：

- 最大程度复用现有 control plane
- 与已经实现的 `TaskCard.executor_backend` 完整闭环
- 后续若要补审计、runtime 记录、治理，都有稳定承接点

缺点：

- 需要给 workflow 增加 task card 映射逻辑
- 需要处理 workflow step 与临时任务卡之间的字段映射

### 方案选择

本期选择 **方案 C：workflow 生成任务卡，复用 control plane executor**。

理由：

- 用户已明确选择“真实执行绑定”
- 当前控制平面已经具备最小可运行执行闭环
- 复用已有执行器比在 workflow 层另造一套执行逻辑更稳

## 4. 设计概览

本期只做一条最小执行闭环：

1. `WorkflowEngine` 在执行 agent step 时，解析该 step 的目标 agent、任务内容和 backend recommendation
2. 将 step 映射成临时 `TaskCard`
3. 若 step 自身或继承上下文中存在 backend recommendation，则写入 `TaskCard.executor_backend`
4. 调用 `ControlPlaneExecutor.execute_task()` 做真实命令派发
5. 把执行结果再归一化回当前 workflow 的 `step_context`

这样，workflow 上层继续是“步骤编排器”，control plane 继续是“真实执行器”，两者职责不混。

## 5. 详细设计

### 5.1 WorkflowEngine：增加真实执行入口

#### 新增可选依赖

`WorkflowEngine.__init__()` 增加以下可选依赖：

- `control_plane_store`
- `control_plane_executor`
- `control_plane_adapter`
- `command_runner`

兼容原则：

- 若这些依赖未提供，保持当前模拟执行逻辑
- 只有在依赖齐备时，才进入真实执行路径

#### 新增辅助方法

- `_resolve_step_backend(step, workflow) -> Optional[str]`

  - 优先级：
    1. step 显式 backend
    2. 当前 step result / routing_reason 给出的 backend recommendation
    3. workflow.variables 中继承下来的 `backend_recommendation.selected_backend`
    4. 无则返回 `None`
- `_build_task_card_for_step(step, task_content, agent_id, executor_backend) -> TaskCard`

  - 为 workflow step 构造临时任务卡
  - `task_id` 使用稳定格式：`wf-{workflow_id}-{step_id}`
  - `goal` 为渲染后的 `task_content`
  - `owner_agent` 为 step 实际执行 agent
  - `executor_backend` 写入解析后的 backend
- `_execute_via_control_plane(step, task_content, agent_id) -> Dict[str, Any]`

  - 构造任务卡
  - 如 store 中不存在同名快照则注册任务
  - 调用 `ControlPlaneExecutor.execute_task()`
  - 把执行结果转成 workflow step 所需的结果字典

### 5.2 TaskCard 映射原则

workflow step 到 `TaskCard` 的映射采用最小字段集：

- `task_id`: `wf-{workflow_id}-{step_id}`
- `title`: `Workflow step {step.id}`
- `goal`: 渲染后的 `task_content`
- `scope`: `[workflow.id, step.id]`
- `owner_agent`: 实际执行 agent
- `review_agent`: 若无更好信息，默认同 `owner_agent`
- `priority`: 映射为 `P1`
- `executor_backend`: 从 backend recommendation 解析得到

不在本期映射的内容：

- 精细 lock scope
- rollback 语义定制
- 复杂 acceptance criteria

这些字段统一采用最小安全默认值，后续再精化。

### 5.3 真实执行与模拟执行并存

`_execute_agent_task()` 调整为双路径：

- **真实执行路径**

  - 条件：`task_router` 存在，且 `control_plane_store/control_plane_executor/command_runner` 已注入
  - 行为：路由 agent 后，走 `_execute_via_control_plane()`
- **模拟执行路径**

  - 条件：依赖不齐备
  - 行为：保持现有 `"任务已分配给 {agent_id}"` 返回形状

这样能保证现有测试和调用方可以渐进迁移。

### 5.4 返回值与上下文沉淀

真实执行路径返回的结果字典统一包含：

- `success`
- `output`
- `agent`
- `backend_recommendation`
- `inherited_backend`
- `execution`

其中 `execution` 至少包含：

- `command`
- `stdout`
- `stderr`
- `executor_backend`

这些字段会继续被 `_build_step_context()` 与 `_merge_step_context_into_variables()` 消费，不改已有 `step_contexts` 和 `handoffs` 的结构契约。

## 6. 测试策略

### 6.1 Workflow 端到端测试

新增测试覆盖：

- 当 workflow step 继承到 `openclaw` backend recommendation 时，真实执行命令应走 `openclaw` adapter
- 当 workflow 未注入 control plane 依赖时，仍保持模拟执行路径
- 当 step 显式 backend 与 inherited backend 冲突时，显式 backend 优先

### 6.2 Executor 兼容性测试

补充测试覆盖：

- workflow 构造出的临时 `TaskCard` 能被 `ControlPlaneExecutor` 正常执行
- `TaskCard.executor_backend` 仍优先于默认 adapter

### 6.3 回归范围

至少回归以下测试集：

- `tests.control_plane.test_task_router`
- `tests.control_plane.test_workflow_runtime`
- `tests.control_plane.test_executor`
- `tests.control_plane.test_adapters`
- `tests.control_plane.test_handoff`
- `tests.control_plane.test_provider_registry`
- `tests.control_plane.test_unified_cli`

## 7. 风险与缓解

### 风险 1：workflow 临时任务卡污染状态仓

缓解：

- 使用稳定且带 `workflow_id/step_id` 前缀的 task_id
- 本期接受 workflow step 在状态仓中留下执行痕迹，这是“真实执行绑定”的一部分

### 风险 2：真实执行破坏现有轻量 workflow 测试

缓解：

- 只有在显式注入 control plane 依赖时才进入真实执行路径
- 默认仍保持模拟执行

### 风险 3：backend recommendation 优先级不清

缓解：

- 明确优先级：显式 step backend > 当前 routing recommendation > inherited backend > default executor
- 用测试锁死该优先级

## 8. 完成判定

满足以下条件，视为本期完成：

- workflow step 能在真实执行模式下调用 `ControlPlaneExecutor`
- backend recommendation 能映射到 `TaskCard.executor_backend`
- `openclaw/hermes` 的真实 provider 选择与 workflow recommendation 一致
- 未注入 control plane 依赖时，原模拟执行路径不回退
- 相关测试通过，且无新增诊断错误
