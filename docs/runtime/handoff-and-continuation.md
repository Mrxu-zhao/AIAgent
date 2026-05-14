# Handoff And Continuation

## 状态链路

- handoff payload 先经校验，再进入 message bus 与运行时记录。
- handoff 被消费后，记录会进入 `materialized` 状态，并物化为 `TaskCard`。
- `TaskCard` 物化后会自动进入调度与执行链路，当前最小主状态链路为 `received -> acked -> materialized -> dispatched`。
- handoff 若带有 `workflow_id/target_step`，消费端会继续尝试最小 continuation，并补 `continued` 或 `noop` 的 continuation 结果。
- handoff 现会同时携带 `knowledge_recommendation`、`knowledge_summary` 与 `next_read`，用于目标 agent 的知识消费确认。

## workflow continuation 语义

- `workflow continuation` 指基于 workflow snapshot 与 step events 恢复尚未完成的下游执行。
- 第一版 continuation 聚焦最小 resume，不承诺完整 checkpoint rollback 或跨进程强恢复。
- continuation 当前基于 `resume_workflow(workflow_id, runtime_store)` 重建 `ready_steps`、`completed_steps`、`failed_steps`。
- 若 continuation 条件不满足，handoff 主链至少仍应保留 `TaskCard` 物化与执行能力。
- continuation 失败时，handoff 主状态会回退到 continuation 之前的主状态，避免把主链错误覆盖成失败终态。

## 查询面

- `query handoff`：查看 handoff 运行记录、交接目标、主状态和 continuation 元数据
- `query workflow`：查看 workflow snapshot、step events 与 workflow 级事件
- `query audit`：查看 dispatch、query 与治理操作的审计记录

## 关联字段

- handoff 侧重点字段：`message_id`、`workflow_id`、`target_agent`、`status`
- continuation 侧重点字段：`target_step`、`continuation_status`、`continuation_ready_steps`、`continuation_completed_steps`、`continuation_failed_steps`
- provider 侧重点字段：`selected_backend`、`target_backend`、`backend_reason`
- 知识侧重点字段：`knowledge_recommendation`、`knowledge_summary`、`next_read`

## 运行时事件

- handoff 相关 step 事件包括：`handoff_materialized`、`handoff_dispatched`
- workflow 级事件包括：`workflow_resumed`、`workflow_continued`、`workflow_resume_failed`
- continuation 是否真正找到了可续跑步骤，由 `continuation_ready_steps` 是否为空来区分 `continued` 与 `noop`

## 推荐阅读顺序

- 先读 `docs/architecture/control-plane-overview.md`
- 再读 `docs/contracts/handoff-contract.md`
- 最后结合 `docs/runtime/runtime-governance.md` 看 handoff 与 continuation 的状态边界
