# Agent 能力收口与 Continuation 联合设计文档

## 1. 背景

当前这条 agent 能力提升线已经完成了核心主路径：

- `TaskRouter` 已具备任务画像、`backend_recommendation` 与知识装载建议
- `WorkflowEngine` 已支持 workflow step 与 control plane 执行链路绑定
- handoff 已具备稳定 payload、标准 `MessageBus` 传输结构与最小消费闭环
- `HandoffCoordinator` 已支持 handoff 物化为 `TaskCard`
- `HandoffRunStore`、`query handoff/workflow/audit`、`RBAC` 与 `Audit` 已具备最小治理闭环

但从“工程正式封口”和“系统继续做强”的角度看，仍有两块工作没有统一收口：

1. **正式封口**
   - phase1-7 的能力边界还分散在多份设计/计划文档中
   - 运行时产物仍有“样本与真实运行混存”的问题
   - Hermes/OpenClaw 调用契约、handoff 契约、query 契约仍未形成统一对外说明

2. **继续做强**
   - handoff 当前停在“物化为 `TaskCard`”这一层
   - 尚未自动推进到 control plane 执行
   - 尚未形成真正的 workflow continuation / resume

因此本次设计合并成一个大 spec，但顺序明确为：

- **A：正式封口**
- **B：handoff continuation**

## 2. 目标与非目标

### 2.1 总目标

- 用一轮连续工作把 agent 能力线正式封口
- 在封口后继续把系统推进到 `handoff -> TaskCard -> 自动执行 -> workflow continuation`
- 让外部 Hermes/OpenClaw 调用方看到稳定文档、稳定契约、稳定查询面

### 2.2 A 段目标：正式封口

- 形成单一总览文档，收口 phase1-7 的当前能力和边界
- 固化外部调用契约，包括：
  - handoff payload / schema
  - provider 调度契约
  - query / audit 查询约定
  - continuation 状态说明
- 治理运行时产物目录，区分：
  - 仓库固定样本
  - 真实运行或测试执行产物
- 为 runtime/handoff store 提供最小治理能力：
  - 清理
  - 归档
  - 查询

### 2.3 B 段目标：继续做强

- handoff 成功消费并物化为 `TaskCard` 后，自动进入 control plane 执行
- 在此基础上补最小 workflow continuation / resume
- 让 workflow 能从 `snapshot + step events` 恢复尚未完成的下游执行
- continuation 具备最小幂等和失败回退能力

### 2.4 非目标

- 本次不做完整审批工作流、多级签核或人工任务中心
- 不做分布式消息一致性、跨进程强恢复或事件总线集群化
- 不做 Web UI 或外部服务化控制台
- 不做完整性能平台，只做必要验证与治理接口
- 不改 Hermes/OpenClaw 的底层命令语义，只固化和复用现有契约

## 3. 方案比较

### 方案 A：合并大 spec，先 A 后 B

先做文档/治理/契约封口，再继续做 handoff continuation。

优点：

- 顺序自然，契约与状态面先稳定，后续 continuation 不易返工
- 适合当前代码状态，能最大复用既有 `handoff_coordinator/runtime/query`
- 文档、治理与 continuation 共用同一套状态语义

缺点：

- spec 较长，需要在任务拆分时明确 A/B 边界

### 方案 B：先 continuation，最后再补封口

先补 `handoff -> 自动执行 -> workflow resume`，最后再收口文档与治理。

优点：

- 能更快看到系统能力提升

缺点：

- continuation 的状态、目录和契约可能与后续封口文档冲突
- 很容易做完后再回头改协议和目录结构

### 方案 C：A 和 B 完全拆成两个独立项目

把封口和 continuation 分成两次完整 spec/plan/实现循环。

优点：

- 文档与实现边界非常清楚

缺点：

- 用户已明确希望合并成一个大 spec
- 实际上两者状态面高度共享，拆得过细会增加重复设计

### 方案选择

本次选择 **方案 A：合并大 spec，先 A 后 B**。

## 4. 当前基线

### 4.1 已有能力

- `handoff.py` 已定义 handoff payload 的代码级协议
- `handoff.schema.json` 已提供机器可校验 schema，但字段仍偏瘦
- `providers/hermes.py` 与 `providers/openclaw.py` 已提供两类 provider 调度契约
- `handoff_coordinator.py` 已支持 handoff 消费、校验、物化与持久记录
- `handoff_runtime.py` 已支持最小 `record/read/list`
- `workflow_runtime.py` 已支持 workflow snapshot 与 step events
- unified CLI 已支持 `query workflow/handoff/audit`

### 4.2 现存缺口

- `docs/superpowers/specs/plans` 是演进档案，不是最终对外说明
- `workflow_runtime`、`handoffs`、`tool-runtime` 目录还没有清理和分层治理
- `handoff.schema.json` 与 `handoff.py` 字段不完全对齐
- handoff 物化后没有自动执行
- workflow 只有查询状态，没有 `resume_workflow()` 能力

## 5. A 段设计：正式封口

### 5.1 文档收口结构

新增并维护以下文档层次：

- `docs/architecture/control-plane-overview.md`
  - 作为控制平面与 agent 能力现行总入口
  - 收口 phase1-7 的当前能力、边界、推荐入口
- `docs/contracts/handoff-contract.md`
  - 解释 handoff payload、schema、bus message 结构
- `docs/contracts/provider-contracts.md`
  - 固化 Hermes/OpenClaw provider 的调用约定
- `docs/runtime/runtime-governance.md`
  - 说明 runtime 目录、样本目录、清理规则、保留策略
- `docs/runtime/handoff-and-continuation.md`
  - 统一说明 handoff、TaskCard 物化、自动执行、workflow continuation 的状态语义

保留：

- `docs/superpowers/specs`
- `docs/superpowers/plans`

作为设计与实施档案，不作为最终契约源。

### 5.2 外部契约固化

#### Handoff 契约

以以下两处为统一真实来源：

- 代码真源：`control_plane/protocols/handoff.py`
- 机器真源：`control_plane/protocols/handoff.schema.json`

要求：

- schema 字段与 `handoff.py` 对齐
- 至少覆盖：
  - `source_backend`
  - `target_backend`
  - `task_id`
  - `summary`
  - `context`
  - `source_agent`
  - `target_agent`
  - `source_step`
  - `target_step`
  - `selected_backend`
  - `backend_candidates`
  - `backend_reason`
  - `review_policy`

#### Provider 契约

以以下两处为统一真实来源：

- `providers/hermes.py`
- `providers/openclaw.py`

要求：

- 文档中明确两类 provider 的调度命令格式
- 明确 `executor_backend` 如何映射到 provider
- 明确 `selected_backend/target_backend` 的优先级

#### Query / Audit 契约

以以下两处为统一真实来源：

- unified CLI `query` 子命令
- `governance/audit.py`

要求：

- 文档中明确支持的资源类型
- 明确过滤参数
- 明确 audit 字段结构：
  - `resource`
  - `filters`
  - `result_count`

### 5.3 运行时产物治理

当前问题：

- 仓库已提交的样本与真实运行写入目录混在一起
- `WorkflowRunStore` 和 `HandoffRunStore` 只有写/读/列举，没有生命周期治理

目标目录分层：

- `state/fixtures/`
  - 仓库保留的基线样本、回归样本
- `state/runs/workflow_runtime/`
  - workflow 真实运行与测试运行快照
- `state/runs/handoffs/`
  - handoff 持久记录
- `state/runs/tool-runtime/`
  - tool session / tool transcript

为兼容现有实现，第一版允许：

- 通过配置把 runtime 写路径从旧目录切到新目录
- 提供迁移脚本或最小 copy/move 工具
- 保留旧目录只读样本，不在新运行中继续写入

### 5.4 Store 治理接口

扩展 `WorkflowRunStore` / `HandoffRunStore`：

- `delete_*`
- `prune_*`
- `archive_*`

CLI 增加治理子命令或扩展 `query` 子命令，支持：

- 查询
- 清理
- 归档

治理规则：

- `viewer` 只读
- `operator/admin` 才能做清理/归档
- 清理与归档动作必须写 audit
- 清理/导出等敏感动作预留 `ApprovalGate` 钩子

### 5.5 A 段完成判定

满足以下条件，视为 A 段完成：

- phase1-7 已有统一总览文档
- handoff/provider/query 契约文档已落地
- schema 与代码协议对齐
- runtime 样本与运行产物有清晰目录边界
- store/CLI 具备最小治理能力

## 6. B 段设计：handoff continuation

### 6.1 目标分层

B 段分两层推进：

1. `handoff -> TaskCard -> 自动执行`
2. `handoff -> workflow continuation/resume`

两层都要做，但仍保持回退机制：

- 如果 workflow continuation 条件不满足
- 系统至少仍能完成 `TaskCard` 物化和自动执行

### 6.2 自动执行物化 TaskCard

当前 handoff 成功消费后只做：

- 校验
- 物化 `TaskCard`
- 注册到 `TaskStore`

新增 continuation dispatcher：

- handoff 物化成功后，自动把 `TaskCard` 提交给 control plane 执行链
- 执行结果回写到：
  - `HandoffRecord`
  - `WorkflowRunStore`
  - `TaskStore`

新增或扩展状态：

- `materialized`
- `dispatched`
- `continued`
- `failed`

幂等规则：

- 同一 `message_id` 不重复 dispatch
- 同一 `materialized_task_id` 不重复执行

### 6.3 Workflow continuation / resume

新增最小 `resume_workflow(workflow_id)` 语义：

- 从 `WorkflowRunStore.read_snapshot(workflow_id)` 读取当前状态
- 从 `list_step_events(workflow_id)` 重建 step 状态图
- 找出：
  - 已完成步骤
  - 已失败步骤
  - 尚未执行但依赖已满足的步骤
- continuation 只推进：
  - 由 handoff 新承接的目标 step
  - 或 continuation graph 上依赖已满足的后续 step

第一版不做：

- 完整 checkpoint rollback
- 任意时点从中间恢复任意 step
- 分布式并发恢复

### 6.4 Handoff 与 Continuation 的连接方式

为避免把 workflow 和 handoff 强耦合成一团，采用两段式连接：

1. handoff 先物化为 `TaskCard`
2. 若 payload 中包含可解析的 `workflow_id/target_step`
   - 则在 dispatch 或完成后尝试触发 `resume_workflow(workflow_id)`

这样做的好处：

- 最小保障路径永远存在：至少生成并执行任务卡
- workflow continuation 失败时不会拖垮 handoff 主链

### 6.5 Continuation 状态与事件

在 `WorkflowRunStore` 中新增 continuation 相关事件：

- `handoff_materialized`
- `handoff_dispatched`
- `workflow_resumed`
- `workflow_continued`
- `workflow_resume_failed`

在 `HandoffRecord` 中新增：

- `dispatched_at`
- `continued_at`
- `continuation_workflow_id`
- `continuation_status`

### 6.6 B 段完成判定

满足以下条件，视为 B 段完成：

- handoff 物化后能自动执行 `TaskCard`
- workflow 能基于 snapshot + events 进行最小 continuation
- continuation 具备最小幂等与失败回退
- workflow/handoff/task 三层关联可查询

## 7. 文件落点

### 7.1 A 段

- `docs/architecture/control-plane-overview.md`
- `docs/contracts/handoff-contract.md`
- `docs/contracts/provider-contracts.md`
- `docs/runtime/runtime-governance.md`
- `docs/runtime/handoff-and-continuation.md`
- `.hermes/team/control_plane/protocols/handoff.schema.json`
- `.hermes/team/control_plane/workflow_runtime.py`
- `.hermes/team/control_plane/handoff_runtime.py`
- `.hermes/team/control_plane/cli.py`

### 7.2 B 段

- `.hermes/team/调度框架/core/handoff_coordinator.py`
- `.hermes/team/调度框架/core/workflow_engine.py`
- `.hermes/team/control_plane/runner.py`
- `.hermes/team/control_plane/executor.py`
- `.hermes/team/control_plane/workflow_runtime.py`
- 视实现复杂度，可能新增：
  - `.hermes/team/control_plane/continuation.py`

### 7.3 测试

- `tests/control_plane/test_handoff_coordinator.py`
- `tests/control_plane/test_handoff_runtime.py`
- `tests/control_plane/test_workflow_runtime.py`
- `tests/control_plane/test_unified_cli.py`
- `tests/control_plane/test_governance.py`
- 若新增 continuation 模块：
  - `tests/control_plane/test_continuation.py`

## 8. 测试策略

### 8.1 A 段

覆盖：

- schema 与 payload 对齐
- query / prune / archive / delete 行为
- 样本目录与运行目录分离
- 文档引用与 CLI 行为一致

### 8.2 B 段

覆盖：

- handoff 物化后自动 dispatch
- dispatch 幂等
- workflow resume 成功路径
- workflow resume 失败回退路径
- handoff/task/workflow 三层关联查询

## 9. 风险与缓解

### 风险 1：目录迁移影响现有测试样本

缓解：

- 第一版保留旧目录只读
- 新运行写新目录
- 通过配置迁移，不一次硬切

### 风险 2：workflow continuation 语义过重

缓解：

- 第一版 continuation 只做最小 resume
- 不承诺跨进程强恢复
- continuation 失败时回退为仅执行 TaskCard

### 风险 3：schema 与代码再次漂移

缓解：

- 增加协议一致性测试
- 把对外文档直接锚定到代码真源

### 风险 4：治理命令误删产物

缓解：

- 删除前要求明确过滤条件
- 保留 archive 优先策略
- 敏感操作预留审批钩子

## 10. 实施顺序

### 阶段 A：正式封口

1. 文档总览与契约文档
2. schema 对齐
3. runtime 目录分层
4. store 治理接口
5. CLI 治理命令与审计

### 阶段 B：handoff continuation

1. handoff 自动 dispatch `TaskCard`
2. dispatch 幂等与事件回写
3. `resume_workflow(workflow_id)` 最小实现
4. continuation 查询与失败回退

## 11. 最终完成判定

满足以下全部条件，视为这轮“大 spec”完成：

- A 段已完成：
  - 文档收口
  - 产物治理
  - 外部契约固化
- B 段已完成：
  - handoff 自动执行 `TaskCard`
  - workflow continuation / resume
- 查询、治理、审计与回归测试均通过
