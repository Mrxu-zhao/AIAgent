# 架构地图

## 关键区域
- `.hermes/team/调度框架/`
  - 面向 team 调度的上层能力，包含任务路由、workflow、message bus、monitor 与 CLI。
- `.hermes/team/control_plane/`
  - 面向执行与状态的底座能力，包含任务模型、状态仓、执行器、provider registry 与 adapters。
- `.hermes/profiles/`
  - 面向具体 agent 运行时的 profile、SOUL 与工具集配置。
- `.hermes/agents/`
  - 面向角色原型的知识与长期方法论。
- `.hermes/team/agents/`
  - 面向团队实例的成员资料与个体画像。

## 关键数据流
1. 用户或上层入口发出任务。
2. `TaskRouter` 分析意图并选择 agent。
3. `WorkflowEngine` 按步骤编排并在跨 agent 时生成 handoff。
4. `ControlPlaneExecutor` 按任务卡与执行后端完成真实执行。
5. 结果回流为上下文、报告、经验与后续知识沉淀。

## 知识在链路中的位置
- 团队知识为所有步骤提供统一背景和流程约束。
- 角色知识提供执行套路、检查清单和模板。
- 实例知识用于强化多实例角色的差异化分工。
