# Handoff And Continuation

## 状态链路

- handoff payload 先经校验，再进入 message bus 与运行时记录。
- handoff 被消费后，记录会进入 `materialized` 状态，并物化为 `TaskCard`。
- `TaskCard` 可继续进入调度与执行链路，后续状态可扩展为 `dispatched`、`continued`、`failed`。

## workflow continuation 语义

- `workflow continuation` 指基于 workflow snapshot 与 step events 恢复尚未完成的下游执行。
- 第一版 continuation 聚焦最小 resume，不承诺完整 checkpoint rollback 或跨进程强恢复。
- 若 continuation 条件不满足，handoff 主链至少仍应保留 `TaskCard` 物化与执行能力。

## 查询面

- `query handoff`：查看 handoff 运行记录、交接目标与状态
- `query workflow`：查看 workflow snapshot 与 step events
- `query audit`：查看 dispatch、query 与治理操作的审计记录

## 关联字段

- handoff 侧重点字段：`message_id`、`workflow_id`、`target_agent`、`status`
- continuation 侧重点字段：`target_step`、workflow snapshot、step events
- provider 侧重点字段：`selected_backend`、`target_backend`、`backend_reason`

## 推荐阅读顺序

- 先读 `docs/architecture/control-plane-overview.md`
- 再读 `docs/contracts/handoff-contract.md`
- 最后结合 `docs/runtime/runtime-governance.md` 看 handoff 与 continuation 的状态边界
