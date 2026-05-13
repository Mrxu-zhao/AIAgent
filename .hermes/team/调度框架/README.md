# 团队 Agent 调度框架

## 概述

徐钊研发团队的多 Agent 调度框架，当前是仓库级控制平面治理下的单进程内存型 workstream，提供：
- 13 个专业 Agent 的路由与协作定义
- 命令行、交互式、tmux 等多种使用方式
- 标准化工作流与基础监控能力

当前边界：
- 不是跨进程持久化调度系统
- 没有真实消息消费确认
- 没有独立队列服务或已完成的故障转移编排

## Agent 列表

> 详细职责、分工、测试覆盖率要求见 [团队流程规范.md](../../团队流程规范.md)

| ID | 名字 | 角色 | Profile |
|---|------|------|---------|
| 1 | 张欣怡 | 系统架构师 | architect |
| 2 | 周嘉诚 | 数据库设计师 | dba |
| 3 | 陈启明 | 后端开发 | backend-1 |
| 4 | 王浩然 | 后端开发 | backend-2 |
| 5 | 赵文杰 | 后端开发 | backend-3 |
| 6 | 李思雨 | 前端开发 | frontend-1 |
| 7 | 周晓明 | 前端开发 | frontend-2 |
| 8 | 林雅婷 | 前端开发 | frontend-3 |
| 9 | 吴俊杰 | UCD设计师 | ucd |
| 10 | 郑晓彤 | 功能测试 | qa-functional |
| 11 | 孙美玲 | 性能测试 | qa-performance |
| 12 | 黄志远 | 运维 | devops |
| 13 | 吴雪梅 | 需求分析师 | requirements-analyst |

## 快速开始

### 方式一: 直接调用

```bash
# 调用架构师
hermes --profile architect chat -p "设计用户模块架构"

# 调用后端开发
hermes --profile backend-1 chat -p "开发登录接口"

# 调用测试
hermes --profile qa-functional chat -p "测试订单模块"
```

### 方式二: 调度脚本适配层

```bash
~/.hermes/team/调度框架/scripts/team-dispatch.sh <agent> [任务]
```

示例：
```bash
# 调度架构师，内部会转发到 cli/team-cli.py dispatch -a
./team-dispatch.sh architect "设计商品模块架构"

# 使用别名
./team-dispatch.sh 后端1 "开发用户管理API"

# 续聊session
./team-dispatch.sh --session architect
```

### 方式三: tmux 团队视图适配层

```bash
~/.hermes/team/调度框架/tmux/team-tmux.sh <命令>
```

命令：
```bash
# 启动控制平面观察会话
./team-tmux.sh start

# 查看窗口状态
./team-tmux.sh status

# 向指定窗口发消息
./team-tmux.sh send 1 "status"

# 停止会话
./team-tmux.sh stop
```

### 方式四: 交互式菜单适配层

```bash
~/.hermes/team/调度框架/team.sh
```

### 方式五: 仓库级控制平面入口

```bash
python .hermes/team/调度框架/cli/team-cli.py control-plane-run --max-workers 2
python .hermes/team/control_plane/run_batch.py --max-workers 2
```

## 调度别名

支持中文和角色别名：

| 别名 | Agent |
|------|-------|
| 架构师, 张欣怡 | architect |
| dba, 周嘉诚 | dba |
| 后端, 后端1, 陈启明 | backend-1 |
| 后端2, 王浩然 | backend-2 |
| 后端3, 赵文杰 | backend-3 |
| 前端, 前端1, 李思雨 | frontend-1 |
| 前端2, 周晓明 | frontend-2 |
| 前端3, 林雅婷 | frontend-3 |
| ucd, 吴俊杰 | ucd |
| 测试, 郑晓彤 | qa-functional |
| 性能, 孙美玲 | qa-performance |
| 运维, 黄志远 | devops |
| 需求, 吴雪梅 | requirements-analyst |

## session 管理

```bash
# 新建session
hermes --profile <agent> chat -p "任务"

# 续聊最近session
hermes --continue <agent> chat

# 列出所有session
hermes sessions list

# 指定session续聊
hermes --resume <session_id> chat
```

## 工作流

详见 `workflows/project-workflow.md`

详细流程规范见 [团队流程规范.md](../../团队流程规范.md)

## 目录结构

```
~/.hermes/team/调度框架/
├── team.sh                    # 旧交互式菜单入口
├── cli/
│   └── team-cli.py            # 当前命令行入口，含 control-plane-run 桥接
├── scripts/
│   └── team-dispatch.sh       # 命令行调度脚本
├── tmux/
│   └── team-tmux.sh           # tmux团队视图
└── workflows/
    └── project-workflow.md    # 项目工作流定义
```

## 与控制平面对齐

- 当前推荐主入口是 `.hermes/team/control_plane/cli.py`。
- `cli/team-cli.py` 保留为兼容 CLI，其中 `control-plane-run` 直接桥接仓库级控制平面 runner。
- `team.sh`、`scripts/team-dispatch.sh`、`tmux/team-tmux.sh` 都已退化为参数翻译和调用转发层。
- `.hermes/team/control_plane/runner.py` 负责真实任务批次装配，旧入口不再复制调度逻辑。
- 调度框架中的 Monitor、Workflow、CLI 关键回归由 `tests/control_plane/` 统一覆盖。

## 评估报告实现对照表

| 事项 | 状态 | 落地位置 | 里程碑 |
|------|------|----------|--------|
| P1-1 统一配置中心 | [x] 已完成 | `.hermes/team/control_plane/config.py`、`core/task_router.py`、`core/monitor.py` | 里程碑-1-配置与统一入口 |
| P1-2 持久化任务/事件存储 + 消费确认 | [x] 已完成 | `.hermes/team/control_plane/persistent_bus.py`、`core/message_bus.py` | 里程碑-2-持久化总线与工作流审计 |
| P1-3 工作流显式状态持久化与执行日志 | [x] 已完成 | `.hermes/team/control_plane/workflow_runtime.py`、`core/workflow_engine.py` | 里程碑-2-持久化总线与工作流审计 |
| P1-4 安全表达式解释器 | [x] 已完成 | `core/workflow_engine.py`、`tests/control_plane/test_framework_workflow.py` | 里程碑-2-持久化总线与工作流审计 |
| P1-5 统一新旧入口 | [x] 已完成 | `.hermes/team/control_plane/cli.py`、`cli/team-cli.py`、`team.sh`、`scripts/team-dispatch.sh`、`tmux/team-tmux.sh` | 里程碑-1-配置与统一入口 |
| P2-1 插件式 Agent Provider / Executor | [x] MVP 已完成 | `.hermes/team/control_plane/providers/`、`adapters.py` | 里程碑-3-治理与多后端插件 |
| P2-2 RBAC、审计日志、审批点 | [x] MVP 已完成 | `.hermes/team/control_plane/governance/` | 里程碑-3-治理与多后端插件 |
| P2-3 指标、日志、追踪 | [x] MVP 已完成 | `.hermes/team/control_plane/observability/`、Prometheus/Grafana 交付物 | 里程碑-4-观测与CI |
| P2-4 跨会话协作协议与 Handoff Schema | [x] MVP 已完成 | `.hermes/team/control_plane/protocols/` | 里程碑-3-治理与多后端插件 |
| P2-5 CI | [x] MVP 已完成 | `pyproject.toml`、`.github/workflows/control-plane-ci.yml` | 里程碑-4-观测与CI |

## 注意事项

1. **Profile 配置**: 每个 Agent 的 SOUL.md 已配置好角色定义
2. **Session 复用**: 使用 `--continue <agent>` 复用之前的对话
3. **tmux 可选**: 如果不需要多窗口视图，可以不用 tmux
4. **并行调度**: 可以同时启动多个 Agent 并行工作

---

*负责人: 秦燕 | 版本: v2.0 | 创建: 2026-04-30*
