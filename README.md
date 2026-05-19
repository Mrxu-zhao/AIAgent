# AIAgent

> 面向 Hermes 风格多 Agent 协作的团队工程仓库，当前主线是把 `.hermes/team/调度框架` 与 `.hermes/team/control_plane` 收敛为一个更稳定、可验证、可扩展的仓库级控制平面。

## 项目概览

这个仓库不是单一应用，而是一套围绕多 Agent 协作研发构建的工程资产，主要包含 5 类内容：

- Agent 角色与知识库：位于 `.hermes/agents/`，沉淀不同岗位的能力边界、知识文档与行为约束
- Profile 与 Skill：位于 `.hermes/profiles/`、`.hermes/skills/`，用于定义角色配置与可复用工作流
- 团队公共知识层：位于 `.hermes/team/knowledge/`，统一维护项目背景、术语、风险、交接模板与共享知识入口
- 团队调度框架：位于 `.hermes/team/调度框架/`，保留历史命令行、消息总线、工作流与监控骨架
- 仓库级控制平面：位于 `.hermes/team/control_plane/`，是当前推荐的主入口和主要演进方向

## 当前主线

当前仓库的核心工作集中在控制平面平台化：

- 已建立统一主入口：`python .hermes/team/control_plane/cli.py <command>`
- 已打通共享批次入口：`run_batch.py` 与 `team-cli.py control-plane-run` 共用同一 runner 链路
- 已补齐配置中心、持久化消息总线、工作流运行态、handoff/continuation、Provider 注册、治理骨架、观测骨架与基础 CI
- 已落地知识闭环能力：`TaskRouter`、`WorkflowEngine`、handoff runtime 与 query 入口之间可传递并消费 `knowledge_recommendation` / `knowledge_bundle`
- 已将增强能力并入主线：补齐代码智能、上下文压缩、session security、Kanban 协作与 OAuth 预留模块
- 已落地 tool runtime 主链：支持 builtin tools、knowledge 预加载、tool transcript、session 恢复、tool 级 RBAC、审批拦截、session security 与 transcript 压缩
- 已把部分增强能力注册为 agent tools：`code_review`、`code_diagnostics`、`kanban_summary`、`kanban_create_task`、`list_oauth_services`
- 已形成团队知识治理入口：`.hermes/team/knowledge/` 可承接决策、风险、术语和协作模板的稳定沉淀
- 已对调度框架中的高风险 P0 问题完成回归验证，包括监控死锁、`workflow step.agent` 忽略和 CLI 监控生命周期

同时也需要明确当前边界：

- `control_plane` 是当前推荐主入口，但旧 CLI 仍保留兼容逻辑，尚未完全收敛为纯薄适配层
- `OpenClaw` 目前仍是 dry-run MVP，尚未完成真实 live 执行闭环
- workflow runtime 当前已覆盖快照、step 事件、knowledge feedback 与 handoff 记录，但 checkpoint/resume/audit 的完整闭环仍是后续工作
- observability、governance 与 tool runtime 已具备可验证最小实现，但仍偏 MVP，不应按生产级闭环理解

## 关键目录

```text
.
├── .github/workflows/                  # 基础 CI
├── .hermes/
│   ├── agents/                         # 各角色 Agent 知识库
│   ├── memories/                       # 记忆配置
│   ├── plugins/                        # 插件扩展
│   ├── profiles/                       # Agent Profile
│   ├── skills/                         # 可复用 Skill
│   └── team/
│       ├── control_plane/              # 当前主控制平面与统一 CLI
│       ├── knowledge/                  # 团队公共知识层与治理入口
│       └── 调度框架/                   # 历史调度框架与兼容入口
├── docs/
│   ├── architecture/                   # 控制平面总览
│   ├── contracts/                      # handoff / provider 契约
│   ├── runtime/                        # runtime 与治理文档
│   └── superpowers/                    # 计划与设计文档
├── tests/control_plane/                # 控制平面与调度框架关键回归测试
└── pyproject.toml                      # Ruff / Coverage 配置
```

## 快速开始

### 1. 查看控制平面帮助

```bash
python .hermes/team/control_plane/cli.py --help
```

### 2. 运行控制平面批次

```bash
python .hermes/team/control_plane/cli.py control-plane-run --max-workers 2
```

### 3. 运行标准 workflow

```bash
python .hermes/team/control_plane/cli.py workflow --name "项目开发"
```

说明：

- `workflow` 默认加载 `.hermes/workflows/project_delivery.json`
- 该定义就是当前仓库的团队全流程标准工作流，覆盖需求、设计、开发、测试、闭环和部署上线

### 4. 查看 workflow / handoff 摘要

```bash
python .hermes/team/control_plane/cli.py query workflow --id project_delivery --summary --knowledge-only
python .hermes/team/control_plane/cli.py query handoff --summary --knowledge-only
```

### 5. 运行 tool runtime

```bash
python .hermes/team/control_plane/cli.py tool-run --tool read_knowledge --actor admin
python .hermes/team/control_plane/cli.py tool-session list
```

### 6. 从兼容入口触发共享 runner

```bash
python .hermes/team/调度框架/cli/team-cli.py control-plane-run --max-workers 2
```

### 7. 运行增强能力命令

```bash
python .hermes/team/control_plane/cli.py code-review --inline-code "eval(user_input)"
python .hermes/team/control_plane/cli.py kanban summary
python .hermes/team/control_plane/cli.py oauth list
```

### 8. 重建基线与性能报告

```bash
python .hermes/team/control_plane/run_benchmarks.py
```

### 9. 执行测试

```bash
python -m unittest discover -s tests/control_plane -p "test_*.py" -v
```

## 当前验证状态

- 单元回归：`348 tests, OK`
- 已验证主线：统一 CLI、workflow runtime、handoff/continuation、knowledge feedback、tool runtime、代码智能、上下文压缩、session security、协作模块、兼容入口
- Ruff：`python -m ruff check .hermes/team/control_plane .hermes/team/调度框架/core .hermes/team/调度框架/cli/team-cli.py tests/control_plane`
- Coverage 门槛配置：`pyproject.toml` 中对 `config.py`、`persistent_bus.py`、`workflow_runtime.py`、`cli.py` 设置 `fail_under = 90`

说明：

- `348 tests, OK` 来自当前仓库执行 `python -m unittest discover -s tests/control_plane -p "test_*.py" -v` 的结果
- Coverage 阈值是仓库配置，不代表整个仓库的整体覆盖率，也不代表所有文件都达到同一水平
- Prometheus/Grafana 交付物、治理、多后端与 tool runtime 当前均应按 MVP/骨架能力理解

## 推荐阅读

- `.hermes/team/control_plane/README.md`：控制平面能力、入口和验证基线
- `.hermes/team/knowledge/README.md`：团队公共知识层入口与治理规则
- `.hermes/team/调度框架/README.md`：历史调度框架与控制平面对齐情况
- `docs/superpowers/specs/2026-05-19-control-plane-enhanced-capabilities-integration-design.md`：增强能力融合设计
- `docs/superpowers/plans/2026-05-19-control-plane-enhanced-capabilities-integration.md`：增强能力实施计划
- `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`：本轮实施执行摘要
- `.hermes/team/control_plane/artifacts/milestone-progress-report.md`：里程碑交付与指标口径
- `docs/architecture/control-plane-overview.md`：控制平面总览与当前边界
- `docs/runtime/handoff-and-continuation.md`：handoff 与 continuation 运行时语义
- `docs/superpowers/specs/2026-05-14-control-plane-session-tools-permissions-design.md`：session / tools / 权限设计
- `docs/superpowers/specs/2026-05-14-control-plane-tool-runtime-mvp-design.md`：tool runtime MVP 设计
- `docs/superpowers/specs/2026-05-14-agent-knowledge-closure-program-design.md`：知识闭环设计文档

## 适用场景

这个仓库目前适合以下场景：

- 搭建一套本地可演进的多 Agent 团队工程骨架
- 研究 Hermes 风格任务分发、工作流执行、handoff、知识闭环与控制平面治理
- 在已有调度框架上逐步演进为更统一的仓库级控制平面
- 验证 tool runtime、session 恢复、最小权限、上下文压缩和团队知识治理的最小实现
- 让 agent 直接调用代码审查、代码诊断、Kanban 摘要等主线增强能力
- 为后续接入真实执行后端、外部集成和更强观测能力预留结构

如果你希望直接把它当成“生产级多 Agent 平台”使用，建议先补齐统一入口收敛、审批/审计闭环、workflow 恢复语义、持久化总线 cursor/订阅语义、真实 provider 执行链路，以及观测抓取闭环。

## License

MIT
