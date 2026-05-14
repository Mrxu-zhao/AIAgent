# Handoff Contract

## 真源

- 代码真源：`.hermes/team/control_plane/protocols/handoff.py`
- 机器真源：`.hermes/team/control_plane/protocols/handoff.schema.json`

为方便外部调用方检索，代码真源也可写作 `control_plane/protocols/handoff.py`，机器真源也可写作 `control_plane/protocols/handoff.schema.json`。

## payload 结构

- 必填字段：`source_backend`、`target_backend`、`task_id`、`summary`、`context`、`created_at`
- 扩展字段：`source_agent`、`target_agent`、`source_step`、`target_step`、`reason`
- 附件与风险字段：`artifacts`、`open_questions`、`risks`
- backend 选择字段：`selected_backend`、`backend_candidates`、`backend_reason`
- 治理字段：`review_policy`

## bus envelope

- handoff 在 message bus 中使用 `MessageType.HANDOFF`
- 最小信封包含业务 payload 与关联上下文，常见关键位包括 `task_id` 和 `context`
- 消费端应先按 schema 校验，再进入 handoff materialization 与后续运行时记录

## backend 字段语义

- `target_backend` 表示 handoff 目标后端，是业务侧要求的接收方。
- `selected_backend` 表示路由或调度器最终选中的执行后端。
- `backend_candidates` 表示候选后端集合。
- `backend_reason` 说明为何最终选中该后端。

## agent 与 step 字段语义

- `source_agent` / `target_agent` 用于描述交接双方 agent。
- `source_step` / `target_step` 用于把 handoff 与 workflow step 关联起来。
- 若 payload 带有 `target_step` 与关联 `workflow_id`，消费端可以把 handoff 与后续 continuation 建立关联。
