# 项目概览

## 目标
- 在当前仓库中持续演进面向团队协作的 AI Agent 执行框架。
- 保持 Python 原生工程口径，同时兼容 Hermes 与 OpenClaw 两个执行后端。 
- 让调度、控制平面、协作上下文和知识沉淀逐步形成可复用闭环。

## 当前范围
- `.hermes/team/调度框架/`：工作流、任务路由、消息总线、监控与 CLI。
- `.hermes/team/control_plane/`：控制平面模型、状态仓、执行器、适配器、provider registry。
- `.hermes/profiles/`：具体 agent 运行时 profile。
- `.hermes/agents/`：角色原型与角色知识。
- `.hermes/team/agents/`：团队实例成员资料与实例知识。

## 成功标准
- 团队成员能根据统一知识入口快速理解项目状态与协作方式。
- 角色知识与实例知识可复用，不依赖单次对话记忆。
- 新任务可以沿标准 workflow、handoff 模板和风险清单推进。

## 非目标
- 不把所有一次性任务结果都沉淀为长期知识。
- 不引入外部向量数据库或复杂 RAG 基础设施。
