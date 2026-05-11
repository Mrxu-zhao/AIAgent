# 团队 Agent 调度框架

## 概述

徐钊研发团队的多 Agent 调度框架，支持：
- 13 个专业 Agent 并行协作
- 多种调度方式（命令行、交互式、tmux）
- 标准化工作流

## Agent 列表

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

### 方式二: 调度脚本

```bash
~/.hermes/team/调度框架/scripts/team-dispatch.sh <agent> [任务]
```

示例：
```bash
# 调度架构师
./team-dispatch.sh architect "设计商品模块架构"

# 使用别名
./team-dispatch.sh 后端1 "开发用户管理API"

# 续聊session
./team-dispatch.sh --session architect
```

### 方式三: tmux 团队视图

```bash
~/.hermes/team/调度框架/tmux/team-tmux.sh <命令>
```

命令：
```bash
# 启动团队工作区
./team-tmux.sh start

# 查看状态
./team-tmux.sh status

# 向指定Agent发消息
./team-tmux.sh send backend-1 "检查订单接口"

# 停止团队
./team-tmux.sh stop
```

### 方式四: 交互式菜单

```bash
~/.hermes/team/调度框架/team.sh
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

### 标准项目流程

```
需求分析 → 技术设计 → 开发 → 测试 → 交付
   ↓
 需求分析师  架构师+DBA   后端+前端  测试组  运维
```

### 并行模式

```
         ┌──────────┐
         ↓          ↓
    需求分析      架构设计    ← 并行
    (吴雪梅)     (张欣怡)
              ↓
         ┌──────────┐
         ↓          ↓
       后端       前端        ← 并行
    (3人组)      (3人组)
              ↓
         ┌──────────┐
         ↓          ↓
      功能测试    性能测试    ← 并行
     (郑晓彤)    (孙美玲)
```

## 目录结构

```
~/.hermes/team/调度框架/
├── team.sh                    # 主入口(交互式菜单)
├── scripts/
│   └── team-dispatch.sh       # 命令行调度脚本
├── tmux/
│   └── team-tmux.sh           # tmux团队视图
└── workflows/
    └── project-workflow.md    # 项目工作流定义
```

## 注意事项

1. **Profile 配置**: 每个 Agent 的 SOUL.md 已配置好角色定义
2. **Session 复用**: 使用 `--continue <agent>` 复用之前的对话
3. **tmux 可选**: 如果不需要多窗口视图，可以不用 tmux
4. **并行调度**: 可以同时启动多个 Agent 并行工作

---

*负责人: 秦燕 | 版本: v1.0 | 创建: 2026-04-30*
