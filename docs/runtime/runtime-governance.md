# Runtime Governance

## 目录分层目标

- `state/fixtures/`：仓库固定样本、基线样本与回归夹具
- `state/runs/workflow_runtime/`：workflow 真实运行与测试运行快照、事件
- `state/runs/handoffs/`：handoff 持久记录
- `state/runs/tool-runtime/`：tool session 与 transcript

## 当前实现与迁移原则

- 当前默认 workflow runtime 已写入 `state/runs/workflow_runtime/`。
- 当前默认 handoff runtime 已写入 `state/handoffs/`，后续治理上按 `state/runs/handoffs/` 目标继续收敛。
- 当前默认 tool runtime 已写入 `state/tool-runtime/`。
- 新增运行时写路径时，优先切到 `state/runs/*` 子树。
- 已提交样本保留在 `state/fixtures/` 或历史只读目录，不与真实运行产物混写。
- 已确认的运行生成目录应加入 `.gitignore`，避免把可重建产物再次提交到仓库。

## 治理动作

- 查询：按资源类型和过滤条件读取运行时记录
- 清理：删除临时或失效运行产物
- 归档：把需保留的运行产物迁移到归档区
- workflow store 当前支持：`delete_workflow()`、`prune_workflows()`、`archive_workflow()`
- handoff store 当前支持：`delete_records()`、`prune_records()`、`archive_records()`
- knowledge 治理当前支持：按 `entry_id` 执行 `accept/reject/archive`，并将动作写入审计轨迹

## 权限边界

- `viewer` 只允许读取
- `operator/admin` 才能执行清理、归档等治理动作
- 敏感动作应写入 audit，并预留审批钩子
- 当前默认权限动作名为 `query.workflow.manage` 与 `query.handoff.manage`

## 查询与审计面

- workflow 查询入口：`query workflow`
- handoff 查询入口：`query handoff`
- audit 查询入口：`query audit`
- knowledge 查询入口：`query audit --search/--agent/--role/--task-type/--risk-tag/--review-status`
- 审计日志真源：`.hermes/team/control_plane/governance/audit.py`
- workflow 治理入口：`query workflow --archive|--delete|--prune`
- handoff 治理入口：`query handoff --archive|--delete|--prune`

## 提交策略

- `state/runs/workflow_runtime/` 属于可重建运行产物，默认不应作为长期提交物。
- `state/tool-runtime/` 属于会话与 transcript 运行产物，默认不应作为长期提交物。
- 若某批运行产物需要保留为夹具或金样本，应先迁移到 `state/fixtures/` 或测试专用目录，再提交。
