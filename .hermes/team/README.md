# Team 团队配置

> 当前推荐主入口：`.hermes/team/control_plane/cli.py`

## 目录结构
```
team/
├── agents/           # Agent profile 汇总与实例知识
├── control_plane/    # 当前主线控制平面与统一 CLI
├── knowledge/        # 团队公共知识库
├── 调度框架/         # 团队调度脚本与 workflow 能力
├── README.md
├── AGENTS.md         # 团队成员详情
├── STATUS.md         # 团队状态
├── EVOLUTION.md      # 团队演进
└── LEARNING_PLAN.md  # 学习计划
```

## 调度方式
```bash
# 当前推荐：统一控制平面入口
python .hermes/team/control_plane/cli.py --help
python .hermes/team/control_plane/cli.py workflow --name "项目开发"
python .hermes/team/control_plane/cli.py tool-run --tool read_knowledge --actor admin
python .hermes/team/control_plane/cli.py code-review --inline-code "eval(user_input)"

# 调度单个 Agent
hermes team dispatch -a <agent> -t "<task>"

# 调度多个 Agent
hermes team dispatch -a <agent1,agent2> -t "<task>"
```

## 当前主线能力
- `control_plane/` 已并入代码智能、上下文压缩、session security、Kanban 协作与 OAuth 预留模块。
- 走 `tool runtime` 的 agent 会自动继承 knowledge bundle 预加载、transcript 压缩和 session security。
- agent 现在可直接调用 `code_review`、`code_diagnostics`、`kanban_summary`、`kanban_create_task`、`list_oauth_services` 等增强工具。
- `调度框架/` 保留为兼容入口和历史工作流骨架，不再作为新增能力首选落点。

## 知识使用建议
- 团队公共背景与流程：`knowledge/`
- 角色原型知识：`../agents/<role>/knowledge/`
- 实例成员画像：`agents/<agent>/knowledge/`
- 这些知识目录同时会被控制平面的 knowledge bundle、handoff 推荐和 `read_knowledge` 工具消费。

## 详见各 Agent 知识库
`../agents/` 目录下有各角色的完整知识库，`agents/` 目录下有团队实例成员的个体知识。
