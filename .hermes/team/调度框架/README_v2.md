# AI Agent 团队调度框架 v2.0

## 概述

基于原有框架全面升级，新增智能路由、消息总线、工作流引擎、监控告警等核心能力。

## 新增核心能力

### 1. 智能任务路由 (`core/task_router.py`)
- **自动任务分类**: 根据关键词自动识别任务类型（需求/架构/开发/测试等）
- **智能Agent匹配**: 综合技能匹配度(40%) + 负载均衡(30%) + 历史成功率(20%) + 响应时间(10%)
- **动态负载均衡**: 实时监控Agent任务负载，自动分配到最空闲的Agent
- **自适应评分**: 根据Agent历史表现动态调整路由评分

### 2. Agent消息总线 (`core/message_bus.py`)
- **点对点通信**: Agent之间直接发送消息
- **广播**: 向所有Agent广播消息
- **组播**: 向特定组发送消息（如backend/frontend/qa组）
- **内存态消息历史**: 当前仅保留进程内历史，便于查询与兼容统计
- **订阅发布模式**: 支持按消息类型订阅

### 3. 工作流引擎 (`core/workflow_engine.py`)
- **顺序执行**: 按依赖关系依次执行
- **并行执行**: 无依赖的步骤并行执行
- **条件执行**: 根据条件判断是否执行
- **循环执行**: 支持循环直到条件满足
- **人工审核**: 支持人工介入节点
- **自动依赖解析**: 自动构建依赖图，处理复杂依赖关系

### 4. 监控与故障恢复 (`core/monitor.py`)
- **实时监控**: Agent负载、任务队列、错误率
- **自动告警**: 负载过高、错误率异常自动告警
- **基础恢复能力**: 
  - 自动重试（指数退避）
  - 降低失败 Agent 评分，供后续重新路由参考
  - 严重故障升级告警
- **日志聚合**: 统一日志收集和查询
- **仪表盘**: 可视化展示系统状态

## 与仓库级控制平面的关系

当前调度框架作为仓库级控制平面下的一个被治理 workstream 使用。

- P0 正确性修复由 `tests/control_plane/` 回归测试统一覆盖
- `Hermes` 调度命令装配由 `.hermes/team/control_plane/adapters.py` 与 `executor.py` 统一管理
- `OpenClaw` 仅保留适配接口，不在第一阶段参与运行时执行
- 后续性能基线、执行日志与聚合报告由 `.hermes/team/control_plane/` 输出

## 目录结构

```
调度框架/
├── core/                       # 核心模块 (NEW)
│   ├── __init__.py
│   ├── task_router.py         # 智能任务路由
│   ├── message_bus.py         # Agent消息总线
│   ├── workflow_engine.py     # 工作流引擎
│   └── monitor.py             # 监控与故障恢复
├── cli/                        # 命令行工具 (NEW)
│   └── team-cli.py            # 增强版CLI
├── scripts/
│   └── team-dispatch.sh       # 原有调度脚本
├── tmux/
│   └── team-tmux.sh           # 原有tmux视图
├── workflows/
│   └── project-workflow.md    # 原有工作流文档
├── team.sh                     # 原有交互菜单
└── README.md                   # 本文档
```

## 快速开始

### 方式一: 新版CLI工具（推荐）

```bash
# 查看团队状态
python cli/team-cli.py status

# 智能调度任务（自动选择最优Agent）
python cli/team-cli.py dispatch "开发用户登录接口"

# 指定Agent调度
python cli/team-cli.py dispatch -a backend-1 "开发订单接口"

# 设置优先级调度
python cli/team-cli.py dispatch -p critical "修复生产环境Bug"

# 广播消息给所有Agent
python cli/team-cli.py broadcast "项目启动会议"

# 执行标准项目工作流
python cli/team-cli.py workflow -n "电商平台"

# 查看监控仪表盘
python cli/team-cli.py monitor --dashboard

# 运行仓库级控制平面批次
python cli/team-cli.py control-plane-run --max-workers 2

# 交互式模式
python cli/team-cli.py interactive
```

### 方式二: Python API

```python
from core import get_router, get_bus, get_monitor

# 初始化组件
router = get_router()
bus = get_bus()
monitor = get_monitor()

# 1. 智能路由任务
agent_id, task = router.route_task("设计数据库表结构")
print(f"任务分配给: {agent_id}")

# 2. Agent间通信
from core.message_bus import Message, MessageType

msg = Message.create(
    MessageType.COLLAB_REQUEST,
    "backend-1",
    "frontend-1",
    {"api": "/api/users", "method": "GET"}
)
bus.send(msg)

# 3. 广播消息
broadcast_msg = Message.create(
    MessageType.BROADCAST,
    "pm",
    None,
    {"message": "今日站会取消"}
)
bus.send(broadcast_msg)

# 4. 监控指标
monitor.record_agent_metric("backend-1", "response_time", 0.5)

# 5. 查看状态
status = router.get_agent_status()
dashboard = monitor.get_dashboard_data()
```

### 方式三: 工作流编程

```python
from core.workflow_engine import WorkflowEngine, create_standard_project_workflow

# 创建工作流引擎
engine = WorkflowEngine()

# 定义自定义工作流
steps = [
    {
        "id": "requirements",
        "name": "需求分析",
        "type": "sequential",
        "agent": "requirements-analyst",
        "task": "分析{project_name}需求"
    },
    {
        "id": "architecture",
        "name": "架构设计",
        "type": "sequential", 
        "agent": "architect",
        "task": "设计系统架构",
        "dependencies": ["requirements"]
    },
    {
        "id": "dev",
        "name": "并行开发",
        "type": "parallel",
        "agent": "dev",
        "task": "后端开发 | 前端开发",
        "dependencies": ["architecture"]
    }
]

# 注册并执行
workflow = engine.create_workflow("my_project", "我的项目", "", steps, 
                                 {"project_name": "电商平台"})
result = engine.execute_workflow(workflow.id)
```

## 核心特性详解

### 智能路由算法

```
匹配分数 = 技能匹配(40%) + 负载均衡(30%) + 成功率(20%) + 响应时间(10%)

- 技能匹配: 任务类型与Agent技能是否匹配
- 负载均衡: Agent当前任务数 / 最大任务数
- 成功率: Agent历史任务成功率
- 响应时间: Agent平均响应时间
```

### 消息总线通信模式

| 模式 | 用法 | 示例 |
|-----|------|------|
| 点对点 | `bus.send(Message(to="agent_id"))` | 架构师 → 后端开发 |
| 广播 | `bus.send(Message(to=None))` | PM → 所有Agent |
| 组播 | `bus.send(Message(to="backend"))` | 架构师 → 后端组 |

### 工作流步骤类型

| 类型 | 说明 | 使用场景 |
|-----|------|---------|
| sequential | 顺序执行 | 有依赖关系的步骤 |
| parallel | 并行执行 | 无依赖的多任务 |
| conditional | 条件执行 | 根据条件判断是否执行 |
| loop | 循环执行 | 需要重复执行的步骤 |
| human | 人工审核 | 需要人工确认的节点 |

### 监控告警规则

| 规则 | 阈值 | 级别 |
|-----|------|------|
| Agent负载过高 | > 80% | warning |
| 错误率过高 | > 10% | critical |
| 任务超时 | > 300秒 | warning |
| 队列过长 | > 10 | warning |

### 故障恢复策略

| 场景 | 策略 | 说明 |
|-----|------|------|
| 任务失败 | 自动重试 | 指数退避，最多3次 |
| Agent连续失败 | 降级路由评分 | 为后续调度提供更低成功率权重，不保证立即切换执行端 |
| 所有Agent满载 | 无独立排队服务 | 当前仍为进程内路由，不提供持久化等待队列 |
| 严重故障 | 升级告警 | 通知人工介入 |

## 与原有框架的兼容

原有脚本仍然可用，但仓库级控制平面已成为新的主执行平面：

```bash
# 原有方式（仍然支持）
./team.sh
./scripts/team-dispatch.sh architect "任务"
./tmux/team-tmux.sh start

# 新增方式（推荐）
python cli/team-cli.py dispatch "任务"
python cli/team-cli.py workflow -n "项目"
python cli/team-cli.py control-plane-run --max-workers 2
```

## 配置说明

### Agent配置

在 `core/task_router.py` 中修改 `AGENT_SKILLS` 和 `_init_agents()`：

```python
AGENT_SKILLS = {
    "backend-1": [TaskType.BACKEND, TaskType.DATABASE],  # 扩展技能
    # ...
}
```

### 告警阈值

在 `core/monitor.py` 中修改 `thresholds`：

```python
self.thresholds = {
    "agent_load_high": 0.8,    # 调整负载阈值
    "task_timeout": 300,        # 调整超时时间
    "error_rate_high": 0.1,    # 调整错误率阈值
}
```

### 重试策略

```python
recovery = get_recovery_manager()
recovery.set_retry_policy("backend-1", max_retries=5, backoff_factor=2.0)
```

## 进阶使用

### 自定义工作流模板

创建 `workflows/custom-workflow.json`：

```json
{
  "name": "快速修复流程",
  "steps": [
    {
      "id": "analysis",
      "name": "问题分析",
      "type": "sequential",
      "agent": "architect",
      "task": "分析Bug原因"
    },
    {
      "id": "fix",
      "name": "修复",
      "type": "sequential",
      "agent": "backend-1",
      "task": "修复Bug",
      "dependencies": ["analysis"]
    },
    {
      "id": "test",
      "name": "验证",
      "type": "sequential",
      "agent": "qa-functional",
      "task": "验证修复",
      "dependencies": ["fix"]
    }
  ]
}
```

### 集成到CI/CD

```yaml
# .github/workflows/agent-team.yml
- name: 调度Agent团队
  run: |
    python cli/team-cli.py workflow -n "${{ github.event.head_commit.message }}"
```

## 故障排查

### 查看日志

```bash
python cli/team-cli.py monitor --logs --limit 50
```

### 导出诊断数据

```bash
python cli/team-cli.py monitor --export diagnostics.json
```

### 重置Agent状态

```python
from core import get_router
router = get_router()
router.agents["backend-1"].current_tasks = 0
router.agents["backend-1"].success_rate = 1.0
```

## 版本历史

| 版本 | 日期 | 说明 |
|-----|------|------|
| v1.0 | 2026-04-30 | 初始版本，基础调度功能 |
| v2.0 | 2026-05-12 | 新增智能路由、消息总线、工作流引擎、监控告警 |

---

*负责人: 秦燕 | 版本: v2.0*
