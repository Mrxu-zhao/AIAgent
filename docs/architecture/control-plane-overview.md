# Control Plane Overview

## 当前推荐入口

- 控制平面主入口：`.hermes/team/control_plane/cli.py`
- 批次执行入口：`.hermes/team/control_plane/runner.py`
- provider 注册与装配入口：`.hermes/team/control_plane/providers/registry.py`
- workflow 运行时入口：`.hermes/team/control_plane/workflow_runtime.py`
- handoff 运行时入口：`.hermes/team/control_plane/handoff_runtime.py`

## phase1-7 能力总览

- phase1-3：建立任务模型、状态仓与基础控制平面调度链路。
- phase4：把 workflow step 与控制平面执行链路绑定，支持 workflow runtime 快照和 step events。
- phase5：固化 handoff payload、schema 和标准 message bus 传输结构。
- phase6-7：补齐 handoff 消费、治理查询、RBAC、audit 与最小统一 CLI 查询面。

## 已支持边界

- 支持 `Hermes` 直连执行与 `OpenClaw` dry-run provider 装配。
- 支持 `query workflow`、`query handoff`、`query audit` 三类最小查询面。
- 支持 workflow snapshot 与 step event 落盘。
- 支持 handoff 记录持久化、按 `workflow_id/target_agent/status` 过滤查询。
- 支持基础治理骨架，包括 RBAC、audit 与审批钩子预留。

## 未支持边界

- 尚未形成完整 checkpoint / resume / continuation 闭环。
- 尚未提供完整持久化 cursor、订阅恢复与分布式消息一致性。
- 尚未形成完整 Web UI、审批流与任务中心。
- `OpenClaw` 真实 live 执行仍保留给后续阶段。

## 推荐查询与治理入口

- CLI 查询入口：`.hermes/team/control_plane/cli.py query`
- 审计真源：`.hermes/team/control_plane/governance/audit.py`
- handoff 契约说明：`docs/contracts/handoff-contract.md`
- provider 契约说明：`docs/contracts/provider-contracts.md`
- 运行时治理说明：`docs/runtime/runtime-governance.md`
- handoff 与 continuation 状态说明：`docs/runtime/handoff-and-continuation.md`
