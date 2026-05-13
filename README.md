# AIAgent 团队智能体

> 徐钊 AIAgent 团队 - 完整的 Agent 技能库和知识库，拿下来即可复用

## 目录结构

```
.hermes/
├── agents/           # 9个Agent角色 + 知识库
│   ├── architect/    # 架构师 (3个知识库文件)
│   ├── backend-dev/  # 后端开发 (17个知识库文件)
│   ├── dba/         # 数据库设计师 (15个知识库文件)
│   ├── devops/      # 运维工程师 (9个知识库文件)
│   ├── frontend-dev/# 前端开发 (8个知识库文件)
│   ├── qa-functional/ # 功能测试 (7个知识库文件)
│   ├── qa-performance/ # 性能测试 (10个知识库文件)
│   ├── requirements-analyst/ # 需求分析 (10个知识库文件)
│   └── ucd/         # UI/UX设计 (9个知识库文件)
├── profiles/        # Agent角色配置 (14个profile)
├── skills/          # 技能库 (13个技能)
├── team/            # 团队调度框架
├── plugins/         # 插件
├── memories/        # 记忆配置
└── SOUL.md          # 核心灵魂
```

## 快速开始

```bash
# 克隆
git clone https://github.com/Mrxu-zhao/AIAgent.git

# 复制到Hermes工作目录
cp -r .hermes/* ~/.hermes/
```

## 控制平面交付

- 主入口：`python .hermes/team/control_plane/cli.py <command>`
- 兼容入口：`python .hermes/team/调度框架/cli/team-cli.py control-plane-run --max-workers 2`
- 旧脚本：`.hermes/team/调度框架/team.sh`、`scripts/team-dispatch.sh`、`tmux/team-tmux.sh` 已退化为适配层
- 交付物：Prometheus 配置、Grafana Dashboard、告警规则、里程碑进展报告均位于 `.hermes/team/control_plane/`
- 验证结果：`90 tests, OK`，P1 关键路径覆盖率 `94%`

## Agent知识库

每个 agent/ 目录包含：
- `SOUL.md` - Agent灵魂定义
- `config.yaml` - 配置文件
- `knowledge/` - 领域知识库（patterns + lessons）

## License

MIT
