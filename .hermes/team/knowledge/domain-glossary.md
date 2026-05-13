# 领域术语表

| 术语 | 含义 | 备注 |
|------|------|------|
| Agent | 具体执行任务的团队成员或角色实例 | 如 `backend-1`、`architect` |
| Role | 角色原型 | 如 `backend-dev`、`qa-functional` |
| Profile | 运行时配置与人格入口 | 位于 `.hermes/profiles/*/` |
| Team Knowledge | 团队公共知识层 | 所有 agent 共享 |
| Role Knowledge | 角色知识层 | 同角色实例共享 |
| Instance Knowledge | 实例知识层 | 具体 agent 专属 |
| Workflow | 标准协作步骤编排 | 由 `WorkflowEngine` 执行 |
| Handoff | 跨 agent 交接载荷 | 结构化移交上下文 |
| Control Plane | 控制平面 | 负责任务状态、执行、适配器与 provider |
| Backend Recommendation | 推荐执行后端 | 如 `hermes`、`openclaw` |

## 命名约定
- “团队层”指 `.hermes/team/knowledge/`
- “角色层”指 `.hermes/agents/<role>/knowledge/`
- “实例层”指 `.hermes/team/agents/<agent>/knowledge/`
- “共享记忆”指 `.hermes/memories/`
