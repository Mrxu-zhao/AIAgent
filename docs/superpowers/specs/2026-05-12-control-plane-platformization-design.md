# 控制平面平台化设计文档

## 1. 背景

当前仓库已经具备仓库级控制平面的最小闭环：`TaskStore`、`ControlPlaneExecutor`、`ControlPlaneOrchestrator`、共享 runner、`team-cli.py control-plane-run` 与一组控制平面回归测试已经落地。但评估报告中 `P1/P2` 的大量事项仍停留在“分散模块 + 最小可运行原型”阶段，主要缺口集中在统一配置、消息持久化、工作流审计、统一主入口、插件式执行后端、RBAC 与审计、Prometheus/Grafana 观测、CI 与回滚治理。

本设计的目标不是再追加一条孤立脚本链路，而是在现有控制平面之上，把 `.hermes/team/调度框架`、`.hermes/team/control_plane`、`Hermes/OpenClaw` 运行时能力收敛为一个主控制平面，旧入口全部退化为适配层。

## 2. 设计目标

### 2.1 核心目标

- 把评估报告中的全部 `P1` 事项在现有仓库内落地为真实代码、测试、文档与 CI。
- 把全部 `P2` 事项落为最小可用版本（MVP），并保留清晰的扩展点与后续迭代计划。
- 建立统一配置中心，消除 `task_router.py`、`message_bus.py`、`monitor.py`、Shell 脚本与控制平面模块中的重复配置。
- 将消息总线升级为“持久化任务/事件存储 + 消费确认”模型，并保持对现有 `MessageBus` 调用方式的兼容。
- 将工作流运行状态、步骤执行日志和恢复元数据统一落盘到控制平面事件目录。
- 统一入口为 `control_plane` CLI，`team-cli.py`、`team.sh`、`team-dispatch.sh`、`team-tmux.sh` 保留为薄适配层。
- 建立 Prometheus 指标、Grafana Dashboard、告警规则、GitHub Actions CI 和进展报告。
- 提供对 `Hermes` 与 `OpenClaw` 的插件式执行后端接口，优先保证运行时契合这两个后端。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />

### 2.2 非目标

- 本轮不实现真正的分布式队列或外部数据库依赖，持久化优先采用仓库内文件存储。
- 本轮不引入复杂 Web 服务面板，Grafana 与 Prometheus 采用配置和静态 JSON/YAML 交付。
- 本轮不删除旧入口，只将其改造成兼容适配层，确保可回滚。

## 3. 方案选择

### 方案 A：Control Plane First

以 `.hermes/team/control_plane` 为唯一主控制平面，调度框架与旧脚本入口改为适配层，统一配置、事件流、执行后端、观测与治理都围绕控制平面扩展。

优点：

- 与当前仓库已落地的控制平面方向一致。
- 最适合承接 `Hermes/OpenClaw` 执行后端插件化。
- 最符合评估报告 `P1-5`“只保留一个主控制平面”的要求。

缺点：

- 需要把原本分散在 `调度框架/core` 的部分逻辑上推或包裹到控制平面。

### 方案 B：Framework First

继续把 `.hermes/team/调度框架/core` 作为主内核，控制平面退化为围绕它的包装层。

优点：

- 对旧脚本路径变动较少。

缺点：

- 会和当前已经落地的控制平面主链方向冲突。
- 长期仍要再做一次统一入口收敛。

### 方案 C：Dual Track

保留双内核并新增 façade。

优点：

- 兼容性最好。

缺点：

- 复杂度最高，且和 `P1-5` 目标相悖。

### 方案选择

本设计选择 **方案 A：Control Plane First**。<mccoremem id="03g415w5w3367klgad5cg68tb|01KRDKFS2XFQ1K5105VDNMG5FX" />

## 4. 架构设计

### 4.1 目标分层

系统按五层组织：

1. **统一入口层**
   - 新增 `control_plane` CLI 作为唯一主入口。
   - 旧入口只做参数翻译与调用转发。
2. **配置与协议层**
   - 提供统一配置中心、handoff schema、执行后端注册表、RBAC 规则。
3. **执行与状态层**
   - 提供持久化消息总线、工作流状态存储、任务与事件仓。
4. **治理与观测层**
   - 提供审计日志、审批点、Prometheus 指标、Grafana 仪表盘、告警规则。
5. **适配与回滚层**
   - 为 `Hermes/OpenClaw` 提供 provider/executor 接口，旧入口走适配层，所有新特性可用配置开关关闭。

### 4.2 目录规划

- `.hermes/team/control_plane/config/`
  - 统一配置中心与默认值。
- `.hermes/team/control_plane/providers/`
  - Hermes/OpenClaw provider 注册与执行器实现。
- `.hermes/team/control_plane/governance/`
  - RBAC、审批、审计。
- `.hermes/team/control_plane/protocols/`
  - handoff schema 与跨会话协作协议。
- `.hermes/team/control_plane/observability/`
  - Prometheus exporter、Grafana dashboard JSON、告警规则 YAML。
- `.hermes/team/control_plane/cli.py`
  - 唯一主入口。

### 4.3 关键接口

- `ControlPlaneConfig`
  - 加载 Agent 元数据、组配置、阈值、执行后端、目录、特性开关。
- `PersistentMessageBus`
  - 兼容 `send/receive/subscribe`，新增 `ack/nack/requeue/get_cursor`。
- `WorkflowRunStore`
  - 为 workflow run 记录状态快照、step 事件、恢复点。
- `ExecutorProviderRegistry`
  - 统一注册 `Hermes` 与 `OpenClaw` 后端。
- `MetricsRegistry`
  - 暴露 `improvement_*` 命名空间指标。

## 5. P1 落地映射

### P1-1 统一配置中心

- 模块：`.hermes/team/control_plane/config/`
- 替代位置：
  - `task_router.py` 中的 `TASK_KEYWORDS / AGENT_SKILLS / agent_configs`
  - `message_bus.py` 中的 `_groups`
  - `monitor.py` 中的 `thresholds`
  - `adapters.py` 中的默认命令与后端配置
  - `runner.py / validation.py / CLI` 中的默认目录与并发参数

### P1-2 持久化任务/事件存储 + 消费确认

- 模块：`persistent_bus.py`
- 兼容接口：
  - `register_agent`
  - `send`
  - `receive`
  - `subscribe`
  - `stats`
- 新增接口：
  - `ack`
  - `nack`
  - `requeue`
  - `list_unacked`
  - `load_from_disk`

### P1-3 工作流显式状态持久化与执行日志

- 模块：`workflow_runtime.py`
- 对接位置：
  - `workflow_engine.py`
  - 控制平面 artifacts/state/events

### P1-4 安全表达式解释器

- 模块：`workflow_engine.py`
- 现状：已完成最小 `ast` 替换
- 本轮补强：
  - 更完整表达式测试
  - README 说明
  - 指标埋点

### P1-5 统一新旧入口

- 主入口：`.hermes/team/control_plane/cli.py`
- 适配层：
  - `.hermes/team/调度框架/cli/team-cli.py`
  - `.hermes/team/调度框架/team.sh`
  - `.hermes/team/调度框架/scripts/team-dispatch.sh`
  - `.hermes/team/调度框架/tmux/team-tmux.sh`

## 6. P2 MVP 落地映射

### P2-1 插件式 Agent Provider / Executor

- `providers/base.py`
- `providers/hermes.py`
- `providers/openclaw.py`
- `providers/registry.py`

MVP：

- 后端注册
- 参数规范化
- 构造命令
- 基础失败日志

### P2-2 RBAC、审计日志、审批点

- `governance/rbac.py`
- `governance/audit.py`
- `governance/approval.py`

MVP：

- 角色到动作白名单
- 敏感命令审批钩子
- 审计事件落盘

### P2-3 指标、日志、追踪

- `observability/metrics.py`
- `observability/prometheus_exporter.py`
- `observability/prometheus/prometheus.yml`
- `observability/prometheus/rules/improvement-alerts.yml`
- `observability/grafana/dashboards/improvement-overview.json`

MVP：

- metrics 文本导出
- Prometheus 配置
- Grafana Dashboard JSON
- YAML 告警规则

### P2-4 跨会话协作协议与 Handoff Schema

- `protocols/handoff.py`
- `protocols/handoff.schema.json`

MVP：

- 统一 handoff 对象
- 基础校验
- Hermes/OpenClaw 兼容字段

### P2-5 CI

- `pyproject.toml`
- `.github/workflows/control-plane-ci.yml`

MVP：

- `ruff`
- `coverage`
- `unittest discover`
- artifacts 上传

## 7. 量化目标与指标

### 7.1 指标映射

- `improvement_dashboard_availability_ratio`
- `improvement_workflow_role_hit_ratio`
- `improvement_test_files_total`
- `improvement_core_path_coverage_ratio`
- `improvement_doc_impl_gap_total`
- `improvement_config_sources_total`
- `improvement_cross_process_trace_ratio`
- `improvement_high_risk_issues_total`
- `improvement_auto_recovery_closure_ratio`

### 7.2 指标来源

- `Monitor`
- `WorkflowEngine`
- `PersistentMessageBus`
- 配置中心扫描结果
- 测试与 coverage 脚本输出
- 文档对照表统计

## 8. 里程碑与 PR 对应

- `里程碑-1-配置与统一入口`
  - 覆盖：`P1-1`、`P1-5`
- `里程碑-2-持久化总线与工作流审计`
  - 覆盖：`P1-2`、`P1-3`
- `里程碑-3-治理与多后端插件`
  - 覆盖：`P2-1`、`P2-2`、`P2-4`
- `里程碑-4-观测与CI`
  - 覆盖：`P2-3`、`P2-5` 与量化目标交付

每个里程碑都必须附带：

- 源代码与测试
- README 对照表更新
- 监控 JSON / 告警规则 YAML / CI 变更
- 里程碑进展报告条目

## 9. 测试策略

- 单元测试：配置中心、provider registry、持久化消息总线、workflow store、RBAC、handoff schema、metrics registry
- 集成测试：统一 CLI、旧入口适配、workflow 恢复、Hermes/OpenClaw provider 调度、Prometheus 导出、CI 命令链
- 覆盖率：本轮新增/修改的 `P1` 模块覆盖率目标 `>= 90%`

## 10. 回滚策略

- 所有新功能提供配置开关。
- 旧入口不删除，只适配到主控制平面。
- `PersistentMessageBus` 保留内存回退模式。
- `OpenClaw` provider 若不可用，自动退化为只生成命令的 dry-run 模式。
- 每个里程碑均可独立回退，不影响既有控制平面最小闭环。
