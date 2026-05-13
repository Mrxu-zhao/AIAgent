# Team 团队配置

## 目录结构
```
team/
├── agents/           # Agent profile 汇总与实例知识
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
# 调度单个 Agent
hermes team dispatch -a <agent> -t "<task>"

# 调度多个 Agent
hermes team dispatch -a <agent1,agent2> -t "<task>"
```

## 知识使用建议
- 团队公共背景与流程：`knowledge/`
- 角色原型知识：`../agents/<role>/knowledge/`
- 实例成员画像：`agents/<agent>/knowledge/`

## 详见各 Agent 知识库
`../agents/` 目录下有各角色的完整知识库，`agents/` 目录下有团队实例成员的个体知识。
