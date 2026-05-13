# Agent 能力增强五期设计文档

## 1. 背景

前几期已经把上层协作能力补到了“能发布、能解释、能追踪执行 backend”的阶段：

- `TaskRouter` 能产出结构化 `backend_recommendation`
- `WorkflowEngine` 能生成结构化 `step_contexts`、自动 handoff，并把 handoff 发布到 `message_bus`
- `WorkflowEngine` 在真实执行模式下，已经能把 workflow step 绑定到 control plane 的执行链路
- `MessageBus` 已具备 `HANDOFF` 消息类型、消息订阅、接收，以及 `ack/nack/requeue` 等基础能力

但当前协作链路仍有一个明显缺口：

- handoff 现在只是“发出去”
- 没有稳定的 handoff consumer
- 没有 handoff 的接收、签收、失败状态
- 没有把 handoff 从“消息”提升为“可追踪的协作闭环”

因此本期目标不是继续扩执行器，也不是补治理审计，而是把 handoff 从“发布事件”升级为“最小可消费闭环”。

## 2. 目标与非目标

### 2.1 目标

- 为 handoff 增加最小消费闭环：`sent -> received -> acked/failed`
- 新增基础 `HandoffCoordinator`，负责从 `MessageBus` 接收并处理 `HANDOFF`
- 保持 handoff payload 与现有 `HandoffPayload` 结构兼容，不重做协议
- 让 `WorkflowEngine` 发布的 handoff 消息结构稳定，能直接被 consumer 消费
- 用测试锁定发布、接收、签收、失败处理的核心行为

### 2.2 非目标

- 本期不做 handoff 自动转任务卡或自动触发新 workflow
- 本期不做多级审批、人工签核、权限治理
- 本期不做完整 runtime audit / checkpoint / resume
- 本期不做复杂重试编排或跨进程事件恢复机制
- 本期不改变 CLI 外观，不新增外部服务

## 3. 方案比较

### 方案 A：最小 handoff 消费闭环

新增一个 handoff coordinator，从 `MessageBus` 读取 `HANDOFF` 消息，校验 payload，记录消费状态，并调用 `ack/nack/requeue` 完成最小闭环。

优点：

- 与当前边界最贴合
- 改动集中在消息层和测试层
- 可以直接把“发出去”升级为“接得住”

缺点：

- 还不负责自动创建后续任务
- 协作闭环是“接收确认”级别，不是完整业务编排

### 方案 B：handoff 直接转后续任务

consumer 收到 handoff 后，直接在 control plane 新建 `TaskCard` 或继续驱动 workflow。

优点：

- 业务闭环更强
- 能更快接近真正多 agent 协作编排

缺点：

- 会把消息闭环、任务编排、执行策略耦合在一轮里
- 改动范围明显放大，风险更高

### 方案 C：只增加 handoff 状态记录

只记录 handoff 状态，不实现真实 consumer。

优点：

- 实现最快
- 风险最低

缺点：

- 仍然无法完成“接收”动作
- 本质上还是停留在发布侧增强

### 方案选择

本期选择 **方案 A：最小 handoff 消费闭环**。

理由：

- 当前最缺的是“handoff 接得住”，不是“handoff 自动编排”
- `MessageBus` 已具备消费基础设施，适合先补最小闭环
- 先把闭环打通，再谈治理、审批或自动任务生成，会更稳

## 4. 设计概览

本期只补一条最小消费链：

1. `WorkflowEngine` 继续生成 handoff payload
2. 发布到 `MessageBus` 时，统一成稳定 `Message` 结构，而不是裸字典
3. `HandoffCoordinator` 订阅或轮询 `HANDOFF` 消息
4. 校验 handoff payload
5. 写入 handoff 记录并更新状态
6. 成功则 `ack`，失败则 `nack` 或保留失败记录

最终效果是：

- 发布方知道 handoff 已发出
- 消费方能够收到并确认
- 系统能够查询 handoff 当前处于 `sent/received/acked/failed` 哪个状态

## 5. 详细设计

### 5.1 MessageBus：稳定 handoff 消息结构

当前 `WorkflowEngine` 调用 `self.message_bus.send({"type": "handoff", "payload": handoff_payload})`，这是一种轻量写法，但对真正 consumer 不够稳定。

本期改为统一使用 `MessageBus.create_handoff_message(...)` 或等价标准结构，保证 handoff 消息具备：

- `id`
- `type == "handoff"`
- `from`
- `to`
- `content.task_id`
- `content.context`
- `timestamp`
- `reply_to`

其中：

- `from` 使用 `source_agent`
- `to` 使用 `target_agent`
- `content` 中保留完整 handoff payload

兼容原则：

- 若 `message_bus` 仍是测试中的简化 FakeBus，允许接受字典形式
- 正式 `MessageBus` 路径优先使用 `Message` 对象

### 5.2 HandoffRecord：handoff 消费态

新增轻量数据结构 `HandoffRecord`，至少包含：

- `message_id`
- `task_id`
- `source_agent`
- `target_agent`
- `source_step`
- `target_step`
- `status`
- `created_at`
- `received_at`
- `acked_at`
- `error`

状态只定义最小集合：

- `sent`
- `received`
- `acked`
- `failed`

### 5.3 HandoffCoordinator：最小 consumer

新增 `HandoffCoordinator`，职责只包含：

- 从 `MessageBus` 接收 `HANDOFF`
- 校验 handoff payload
- 生成或更新 `HandoffRecord`
- 成功消费时调用 `bus.ack(agent_id, message_id)`
- 失败消费时记录错误并调用 `bus.nack(...)` 或保留失败记录

建议提供以下最小接口：

- `consume_for(agent_id: str) -> Optional[Dict[str, Any]]`
  - 拉取目标 agent 的一条 handoff
  - 若无消息返回 `None`
- `handle_message(agent_id: str, message) -> Dict[str, Any]`
  - 校验、记录状态并返回处理结果
- `get_records(task_id: Optional[str] = None) -> List[Dict[str, Any]]`
  - 供测试和后续 CLI/治理查询使用

### 5.4 校验与失败语义

handoff consumer 的失败分两类：

1. **协议失败**
   - payload 缺字段
   - `validate_handoff_payload()` 不通过
   - 记录 `failed`
   - 不继续业务处理

2. **消费失败**
   - consumer 内部异常
   - 记录 `failed`
   - 可调用 `nack`

本期不做复杂重试，只要求失败可见、状态稳定。

### 5.5 WorkflowEngine：发布侧调整

`WorkflowEngine._record_followup_handoffs()` 继续是 handoff 生成入口，但发布逻辑要升级：

- 若 `message_bus` 是正式 `MessageBus`，发送标准 `MessageType.HANDOFF` 消息
- 若 `message_bus` 是简单测试替身，允许回退到当前字典写法，保持已有测试轻量性

这样可以避免一次性改坏现有测试，同时给 coordinator 提供正式消费输入。

## 6. 文件落点

- `\.hermes/team/调度框架/core/message_bus.py`
  - 补稳定 handoff message 创建/发送辅助
- `\.hermes/team/调度框架/core/workflow_engine.py`
  - 调整 handoff 发布为标准消息结构
- `\.hermes/team/调度框架/core/handoff_coordinator.py`
  - 新增最小 handoff consumer
- `tests/control_plane/test_workflow_runtime.py`
  - 补发布侧结构测试
- `tests/control_plane/test_message_bus.py` 或现有总线测试文件
  - 补 handoff message 发送/接收/ack 行为测试
- `tests/control_plane/test_handoff_coordinator.py`
  - 新增 handoff coordinator 测试

## 7. 测试策略

### 7.1 Workflow 发布测试

覆盖：

- handoff 发布时能形成标准消息结构
- `source_agent/target_agent/task_id/payload` 均可被消费侧读取

### 7.2 HandoffCoordinator 测试

覆盖：

- 成功消费 handoff 后状态从 `sent` 变为 `received` 再到 `acked`
- 非法 payload 会进入 `failed`
- `ack/nack` 调用符合预期
- 无消息时返回 `None`

### 7.3 MessageBus 回归

覆盖：

- `HANDOFF` 类型消息能点对点发送
- pending / receive / ack 的统计不回退

## 8. 风险与缓解

### 风险 1：改坏现有 FakeBus 测试

缓解：

- 发布侧保留对简单 `send(dict)` 的兼容
- 仅在正式 `MessageBus` 路径使用标准 `Message`

### 风险 2：persistent bus 语义不完整

缓解：

- 本期只依赖最小 `receive/ack/nack` 能力
- 不建立在 cursor / 持久订阅完整语义之上

### 风险 3：handoff 状态与 workflow 结果重复

缓解：

- `workflow.handoffs` 仍保留发布事实
- `HandoffRecord` 只描述消费态，不替代原 payload

## 9. 完成判定

满足以下条件，视为本期完成：

- handoff 能以稳定消息结构发布到 `MessageBus`
- 至少有一个 `HandoffCoordinator` 能成功消费并签收 handoff
- handoff 消费失败时有明确 `failed` 状态
- 相关测试通过，且无新增诊断错误
