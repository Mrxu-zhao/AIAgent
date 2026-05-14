# Agent 能力增强六七期设计文档

## 1. 背景

当前这条提升线已经完成了以下能力：

- `TaskRouter` 能输出 `backend_recommendation` 与知识装载建议
- `WorkflowEngine` 能把 workflow step 绑定到 control plane 执行链路
- workflow 自动 handoff 已具备稳定 payload、标准 `MessageBus` 消息结构与真实 provider 感知
- `HandoffCoordinator` 已能消费 `HANDOFF` 消息，并完成最小 `received -> acked/failed` 闭环

但这条线仍没有真正收口，因为 handoff 还停留在“协作事件”层：

- handoff 被消费后不会自动转成可执行对象
- `workflow / handoff / TaskCard` 三层之间没有稳定关联
- 失败 handoff 可见，但没有最小治理闭环
- 外部通过 Hermes/OpenClaw 调这个框架时，仍需要手工接 handoff 后续动作

因此 phase6/phase7 的目标，是把这条线从“可协作”收成“可编排、可查询、可治理”。

## 2. 目标与非目标

### 2.1 目标

- phase6：让成功消费的 handoff 自动物化为 control plane `TaskCard`
- phase6：为 handoff 增加 `materialized` 状态，并避免重复物化
- phase7：为 handoff 增加持久查询能力，可按 `workflow_id / task_id / message_id / target_agent` 查询
- phase7：把 handoff 查询接到统一 CLI，形成最小治理入口
- phase7：查询与导出走 `RBAC + Audit`，敏感导出保留 `ApprovalGate` 钩子
- 用测试锁定物化、去重、查询、审计与 CLI 行为

### 2.2 非目标

- 本期不做复杂审批流或人工签核流程
- 本期不做跨进程恢复、游标恢复、重放编排系统
- 本期不做 handoff 自动续跑完整 workflow continuation 引擎
- 本期不做大规模外部 API 或 Web UI
- 本期不改变 Hermes/OpenClaw 自身协议，只增强本框架内部闭环

## 3. 方案比较

### 方案 A：handoff 先物化为 TaskCard，再补治理闭环

消费成功的 handoff 先物化为 control plane `TaskCard`，并登记到 `TaskStore`；随后再为 handoff 增加持久记录、查询与治理。

优点：

- 与当前 `WorkflowEngine -> HandoffCoordinator -> TaskStore -> Executor` 链路最贴合
- 每一步都能单独测试，回归风险可控
- 最快把“协作事件”变成“可执行对象”

缺点：

- 第一版不会自动执行物化出来的任务
- workflow continuation 暂时仍以 TaskCard 桥接为主

### 方案 B：handoff 直接驱动 workflow continuation

handoff 消费后直接定位下游 workflow step，驱动 workflow 继续执行，而不是先转 TaskCard。

优点：

- 更接近纯 workflow 语义
- 少一层 TaskCard 映射

缺点：

- 会把 workflow 生命周期和 handoff 消费强耦合
- 对现有 control plane 执行链路复用较少，风险更高

### 方案 C：先做治理查询，再最后接物化

先补 handoff 持久记录、查询、CLI，再最后把 handoff 接到任务物化。

优点：

- 可观测性先起来
- 行为变化较小

缺点：

- 中间态价值有限，因为 handoff 仍不能自动推进后续动作

### 方案选择

本期选择 **方案 A**。

理由：

- 当前最缺的是 handoff 后续动作自动承接
- control plane 已经具备 `TaskCard / TaskStore / Executor` 这些可复用入口
- 先把协作事件物化为任务，再补治理查询，是最自然的收口顺序

## 4. 终态设计

### 4.1 Phase6：handoff 自动物化

当 `HandoffCoordinator` 成功消费一条合法 handoff 后：

1. 校验 payload
2. 生成 `HandoffRecord`
3. 基于 handoff 构造最小 `TaskCard`
4. 将 `TaskCard` 注册到 `TaskStore`
5. 更新 `HandoffRecord.status = "materialized"`
6. 为物化结果建立稳定关联：
   - `message_id`
   - `handoff_task_id`
   - `workflow_id`
   - `materialized_task_id`
   - `target_agent`

第一版不要求自动执行物化任务，只要求它进入 control plane 可执行队列。

### 4.2 Phase7：治理闭环

在 phase6 的基础上补齐最小治理能力：

1. handoff 记录持久化
2. 按 `workflow_id / task_id / message_id / target_agent / status` 查询
3. CLI 查询入口
4. 查询动作审计
5. 基于角色的查询权限控制
6. 为后续审批保留导出钩子

最终系统应支持：

- 看见某个 workflow 产生了哪些 handoff
- 看见每个 handoff 是否已 `materialized`
- 查到它物化成了哪个 `TaskCard`
- 查到失败 handoff 的错误原因
- 通过 CLI 安全地查询与导出这些信息

## 5. 详细设计

### 5.1 Handoff 物化模型

新增 `HandoffMaterialization` 或等价字典结构，至少包含：

- `materialized_task_id`
- `owner_agent`
- `executor_backend`
- `source_workflow_id`
- `source_step`
- `target_step`

`materialized_task_id` 采用稳定命名，建议：

- `handoff-{workflow_id}-{source_step}-{target_step}`

这样可以天然支持幂等注册与重复消费去重。

### 5.2 HandoffRecord 扩展

在现有 `HandoffRecord` 基础上新增字段：

- `workflow_id`
- `materialized_task_id`
- `materialized_at`
- `source_backend`
- `target_backend`
- `selected_backend`

状态集合扩为：

- `received`
- `acked`
- `failed`
- `materialized`

其中：

- `acked` 表示消息级成功消费
- `materialized` 表示已成功落成 `TaskCard`

### 5.3 HandoffCoordinator 扩展

`HandoffCoordinator` 新增可选依赖：

- `task_store`
- `runtime_store`
- `audit_logger`

新增职责：

- 从 handoff payload 中提取 `workflow_id`
- 根据 handoff 构造最小 `TaskCard`
- 检查该 handoff 是否已物化
- 物化后更新记录状态与关联字段
- 若物化失败，记录 `failed`

建议新增最小接口：

- `materialize_record(record, payload) -> Dict[str, Any]`
- `build_task_card(payload) -> TaskCard`
- `find_record(message_id=None, task_id=None) -> Optional[Dict[str, Any]]`

### 5.4 TaskCard 映射规则

handoff 物化出的 `TaskCard` 采用最小映射：

- `task_id`: `handoff-{workflow_id}-{source_step}-{target_step}`
- `title`: `Handoff follow-up for {target_step}`
- `description`: 使用 handoff `summary`，并附带必要上下文
- `owner_agent`: `target_agent`
- `dependencies`: 空列表
- `acceptance_criteria`: 至少包含“consume handoff context”
- `executor_backend`: 优先 `selected_backend`，否则 `target_backend`

这样能直接复用已有 `ControlPlaneExecutor.resolve_adapter()`。

### 5.5 持久查询存储

新增 `HandoffRunStore`，结构尽量贴近 `WorkflowRunStore`：

- `state/handoffs/records/<message_id>.json`
- `state/handoffs/index/by_workflow/<workflow_id>.json`
- `state/handoffs/index/by_target_agent/<agent_id>.json`

至少提供：

- `record_handoff(record)`
- `read_record(message_id)`
- `list_records(workflow_id=None, target_agent=None, status=None)`

第一版可以通过简单 JSON 文件 + 追加索引实现，不需要数据库。

### 5.6 Workflow runtime 关联

为了把 workflow 与 handoff 查询打通：

- 在 `WorkflowEngine` 发布 handoff 时，继续保留 `workflow.handoffs`
- `HandoffCoordinator` 物化时把 `workflow_id` 回写到持久记录
- 若 `runtime_store` 可用，则记录一条 handoff materialization 事件，便于以后从 workflow runtime 侧追踪

### 5.7 CLI 查询与治理

统一 CLI 新增 `query` 子命令，第一版支持：

- `query workflow --id <workflow_id>`
- `query handoff --workflow-id <workflow_id>`
- `query handoff --message-id <message_id>`
- `query handoff --target-agent <agent_id>`
- `query audit --action <action>`

治理规则：

- `viewer` 可读 `monitor.read` 与新增只读查询
- `operator/admin` 可读全部 query
- `handoff.export` 或未来导出类操作走 `ApprovalGate.requires_approval(...)`
- 所有 query 都写 `audit.log("query", ...)`

### 5.8 RBAC 与 Approval 扩展

`RBACPolicy` 默认规则增加：

- `viewer`: `query.workflow`, `query.handoff`, `query.audit.read`
- `operator`: 在 viewer 基础上增加 `query.handoff.export`
- `admin`: 保持全量查询与导出权限

`ApprovalGate` 第一版不拦截普通查询，只拦截未来导出动作。为保持兼容，本期只预留钩子，不强制新增审批交互。

## 6. 文件落点

- `\.hermes/team/调度框架/core/handoff_coordinator.py`
  - 扩展物化、去重、状态推进与查询辅助
- `\.hermes/team/control_plane/store.py`
  - 继续复用 `TaskStore.register_task()` 作为物化落点
- `\.hermes/team/control_plane/workflow_runtime.py`
  - 若需要，补 handoff materialization 事件记录
- `\.hermes/team/control_plane/handoff_runtime.py`
  - 新增 handoff 持久存储
- `\.hermes/team/control_plane/cli.py`
  - 新增 `query` 子命令，并接 RBAC/Audit
- `\.hermes/team/control_plane/governance/rbac.py`
  - 扩展 query 权限
- `tests/control_plane/test_handoff_coordinator.py`
  - 补物化、去重、失败、查询测试
- `tests/control_plane/test_handoff_runtime.py`
  - 新增持久查询测试
- `tests/control_plane/test_unified_cli.py`
  - 补 `query` 子命令、RBAC、审计测试
- `tests/control_plane/test_governance.py`
  - 补 query 权限与审计钩子回归

## 7. 测试策略

### 7.1 Phase6 物化测试

覆盖：

- 合法 handoff 被消费后生成稳定 `TaskCard`
- `executor_backend` 正确继承 `selected_backend`
- 重复消费同一 handoff 不会重复注册任务
- 物化成功后 `status == "materialized"`

### 7.2 Handoff 持久查询测试

覆盖：

- 记录可以按 `message_id` 读取
- 可以按 `workflow_id`、`target_agent`、`status` 过滤
- 记录包含 `materialized_task_id`

### 7.3 CLI 与治理测试

覆盖：

- `query workflow`、`query handoff`、`query audit` 都能返回结构化数据
- query 行为会写审计日志
- 未授权角色访问受限查询时报错
- 普通 query 不触发审批

## 8. 风险与缓解

### 风险 1：重复消费导致重复物化

缓解：

- 采用稳定 `materialized_task_id`
- 注册前检查现有 handoff record 或 `TaskStore.read_snapshot()`

### 风险 2：handoff payload 不足以构造高质量 TaskCard

缓解：

- 第一版只映射最小字段
- description 以 `summary + context` 为主，不强求完整任务语义

### 风险 3：CLI query 扩展影响现有命令

缓解：

- 新增独立 `query` subparser，不改现有命令行为
- 用 `test_unified_cli.py` 锁定回归

### 风险 4：治理模块过于轻量

缓解：

- 本期只用 `RBAC + Audit + Approval hook`
- 不把轻量治理件误当成完整审批系统

## 9. 完成判定

满足以下条件，视为这条提升线完成：

- handoff 成功消费后能自动物化成 `TaskCard`
- 物化结果与 workflow/handoff 存在稳定关联
- handoff 记录可持久查询
- CLI 能查询 workflow、handoff、audit
- query 行为具备最小 RBAC 与审计保护
- 相关测试通过，且无新增 diagnostics
