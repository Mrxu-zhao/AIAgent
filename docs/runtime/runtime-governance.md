# Runtime Governance

## 目录分层目标

- `state/fixtures/`：仓库固定样本、基线样本与回归夹具
- `state/runs/workflow_runtime/`：workflow 真实运行与测试运行快照、事件
- `state/runs/handoffs/`：handoff 持久记录
- `state/runs/tool-runtime/`：tool session 与 transcript

## 当前实现与迁移原则

- 当前默认实现仍以 `state/` 下的既有目录为主，文档先明确目标治理结构。
- 新增运行时写路径时，优先切到 `state/runs/*` 子树。
- 已提交样本保留在 `state/fixtures/` 或历史只读目录，不与真实运行产物混写。

## 治理动作

- 查询：按资源类型和过滤条件读取运行时记录
- 清理：删除临时或失效运行产物
- 归档：把需保留的运行产物迁移到归档区

## 权限边界

- `viewer` 只允许读取
- `operator/admin` 才能执行清理、归档等治理动作
- 敏感动作应写入 audit，并预留审批钩子

## 查询与审计面

- workflow 查询入口：`query workflow`
- handoff 查询入口：`query handoff`
- audit 查询入口：`query audit`
- 审计日志真源：`.hermes/team/control_plane/governance/audit.py`
