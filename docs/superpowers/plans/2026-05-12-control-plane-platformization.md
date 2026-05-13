# Control Plane Platformization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将仓库级控制平面扩展为统一主控制平面，落地配置中心、持久化消息总线、工作流审计、统一入口、Hermes/OpenClaw 插件执行后端、观测体系、CI 与治理能力。

**Architecture:** 以 `.hermes/team/control_plane` 为唯一主控制平面，把配置、执行后端、持久化消息、工作流运行态、观测、RBAC、handoff 协议统一收敛到该目录；`调度框架` 的 `team-cli.py`、Shell 与 tmux 脚本全部改造为适配层并复用主入口。监控与治理采用 Python 原生实现：`pyproject.toml + ruff + coverage + unittest + GitHub Actions`，同时为 `Hermes/OpenClaw` 预留可继续扩展的 provider 接口。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />

**Tech Stack:** Python 3、dataclasses、pathlib、json、threading、queue、subprocess、unittest、coverage、ruff、GitHub Actions、Prometheus text exposition、Grafana dashboard JSON

---

## 文件结构

- Create: `.hermes/team/control_plane/config.py`
- Create: `.hermes/team/control_plane/persistent_bus.py`
- Create: `.hermes/team/control_plane/workflow_runtime.py`
- Create: `.hermes/team/control_plane/providers/base.py`
- Create: `.hermes/team/control_plane/providers/hermes.py`
- Create: `.hermes/team/control_plane/providers/openclaw.py`
- Create: `.hermes/team/control_plane/providers/registry.py`
- Create: `.hermes/team/control_plane/governance/rbac.py`
- Create: `.hermes/team/control_plane/governance/audit.py`
- Create: `.hermes/team/control_plane/governance/approval.py`
- Create: `.hermes/team/control_plane/protocols/handoff.py`
- Create: `.hermes/team/control_plane/protocols/handoff.schema.json`
- Create: `.hermes/team/control_plane/observability/metrics.py`
- Create: `.hermes/team/control_plane/observability/prometheus_exporter.py`
- Create: `.hermes/team/control_plane/observability/prometheus/prometheus.yml`
- Create: `.hermes/team/control_plane/observability/prometheus/rules/improvement-alerts.yml`
- Create: `.hermes/team/control_plane/observability/grafana/dashboards/improvement-overview.json`
- Create: `.hermes/team/control_plane/cli.py`
- Create: `pyproject.toml`
- Create: `.github/workflows/control-plane-ci.yml`
- Modify: `.hermes/team/control_plane/__init__.py`
- Modify: `.hermes/team/control_plane/adapters.py`
- Modify: `.hermes/team/control_plane/runner.py`
- Modify: `.hermes/team/调度框架/core/task_router.py`
- Modify: `.hermes/team/调度框架/core/message_bus.py`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Modify: `.hermes/team/调度框架/cli/team-cli.py`
- Modify: `.hermes/team/调度框架/team.sh`
- Modify: `.hermes/team/调度框架/scripts/team-dispatch.sh`
- Modify: `.hermes/team/调度框架/tmux/team-tmux.sh`
- Modify: `.hermes/team/调度框架/README.md`
- Modify: `.hermes/team/调度框架/README_v2.md`
- Create: `tests/control_plane/test_config.py`
- Create: `tests/control_plane/test_persistent_bus.py`
- Create: `tests/control_plane/test_workflow_runtime.py`
- Create: `tests/control_plane/test_provider_registry.py`
- Create: `tests/control_plane/test_governance.py`
- Create: `tests/control_plane/test_handoff.py`
- Create: `tests/control_plane/test_metrics.py`
- Create: `tests/control_plane/test_unified_cli.py`
- Create: `tests/control_plane/test_ci_smoke.py`
- Create: `.hermes/team/control_plane/artifacts/milestone-progress-report.md`

## 执行顺序

- 先做配置中心和统一入口骨架。
- 再做持久化消息总线与 workflow runtime。
- 随后做 provider registry、RBAC、handoff。
- 最后做 metrics、Prometheus/Grafana、CI、README 对照表和进展报告。

### Task 1: 统一配置中心

**Files:**
- Create: `.hermes/team/control_plane/config.py`
- Modify: `.hermes/team/调度框架/core/task_router.py`
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Test: `tests/control_plane/test_config.py`

- [ ] 写失败测试：验证配置中心能统一提供 agents、groups、thresholds、executors、directories
- [ ] 运行 `python -m unittest tests.control_plane.test_config -v` 并确认失败
- [ ] 实现 `ControlPlaneConfig` 与 `load_control_plane_config()`
- [ ] 让 `TaskRouter` 从配置中心加载 agent 元数据与别名，而不是硬编码
- [ ] 让 `Monitor` 从配置中心加载阈值，而不是硬编码
- [ ] 再跑 `python -m unittest tests.control_plane.test_config -v` 确认通过

### Task 2: 持久化消息总线与 ACK

**Files:**
- Create: `.hermes/team/control_plane/persistent_bus.py`
- Modify: `.hermes/team/调度框架/core/message_bus.py`
- Test: `tests/control_plane/test_persistent_bus.py`

- [ ] 写失败测试：验证 `send/receive/ack/nack/requeue/stats`、落盘恢复、消费确认
- [ ] 运行 `python -m unittest tests.control_plane.test_persistent_bus -v` 并确认失败
- [ ] 实现 `PersistentMessageBus`
- [ ] 让 `MessageBus` 可在配置开关下代理到持久化总线，同时保留当前 API 兼容
- [ ] 再跑 `python -m unittest tests.control_plane.test_persistent_bus -v` 确认通过

### Task 3: 工作流运行态持久化与执行日志

**Files:**
- Create: `.hermes/team/control_plane/workflow_runtime.py`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Test: `tests/control_plane/test_workflow_runtime.py`

- [ ] 写失败测试：验证 workflow run 状态文件、step 事件、恢复点与审计日志路径
- [ ] 运行 `python -m unittest tests.control_plane.test_workflow_runtime -v` 并确认失败
- [ ] 实现 `WorkflowRunStore`
- [ ] 在 `WorkflowEngine.execute_workflow()` 与 `_execute_step()` 中接入 workflow runtime
- [ ] 再跑 `python -m unittest tests.control_plane.test_workflow_runtime -v` 确认通过

### Task 4: 插件式执行后端

**Files:**
- Create: `.hermes/team/control_plane/providers/base.py`
- Create: `.hermes/team/control_plane/providers/hermes.py`
- Create: `.hermes/team/control_plane/providers/openclaw.py`
- Create: `.hermes/team/control_plane/providers/registry.py`
- Modify: `.hermes/team/control_plane/adapters.py`
- Test: `tests/control_plane/test_provider_registry.py`

- [ ] 写失败测试：验证 registry 注册、Hermes/OpenClaw provider 命令构造、dry-run 与异常日志
- [ ] 运行 `python -m unittest tests.control_plane.test_provider_registry -v` 并确认失败
- [ ] 实现 provider registry 与两个 provider
- [ ] 让 `adapters.py` 转向 provider registry，而不是只暴露两个孤立类
- [ ] 再跑 `python -m unittest tests.control_plane.test_provider_registry -v` 确认通过

### Task 5: 统一主入口与旧入口适配

**Files:**
- Create: `.hermes/team/control_plane/cli.py`
- Modify: `.hermes/team/control_plane/runner.py`
- Modify: `.hermes/team/调度框架/cli/team-cli.py`
- Modify: `.hermes/team/调度框架/team.sh`
- Modify: `.hermes/team/调度框架/scripts/team-dispatch.sh`
- Modify: `.hermes/team/调度框架/tmux/team-tmux.sh`
- Test: `tests/control_plane/test_unified_cli.py`

- [ ] 写失败测试：验证统一入口支持 `dispatch/workflow/monitor/control-plane-run/validate`
- [ ] 运行 `python -m unittest tests.control_plane.test_unified_cli -v` 并确认失败
- [ ] 实现主 CLI
- [ ] 把 `team-cli.py` 与三个旧脚本退化为参数转发适配层
- [ ] 再跑 `python -m unittest tests.control_plane.test_unified_cli -v` 确认通过

### Task 6: RBAC、审计、审批点

**Files:**
- Create: `.hermes/team/control_plane/governance/rbac.py`
- Create: `.hermes/team/control_plane/governance/audit.py`
- Create: `.hermes/team/control_plane/governance/approval.py`
- Test: `tests/control_plane/test_governance.py`

- [ ] 写失败测试：验证角色权限、敏感动作审批、审计事件落盘
- [ ] 运行 `python -m unittest tests.control_plane.test_governance -v` 并确认失败
- [ ] 实现治理模块
- [ ] 在统一 CLI 与 provider 执行前加治理钩子
- [ ] 再跑 `python -m unittest tests.control_plane.test_governance -v` 确认通过

### Task 7: Handoff Schema

**Files:**
- Create: `.hermes/team/control_plane/protocols/handoff.py`
- Create: `.hermes/team/control_plane/protocols/handoff.schema.json`
- Test: `tests/control_plane/test_handoff.py`

- [ ] 写失败测试：验证 handoff payload 构造、Hermes/OpenClaw 兼容字段、schema 校验
- [ ] 运行 `python -m unittest tests.control_plane.test_handoff -v` 并确认失败
- [ ] 实现 handoff 协议模块
- [ ] 再跑 `python -m unittest tests.control_plane.test_handoff -v` 确认通过

### Task 8: Metrics、Prometheus、Grafana

**Files:**
- Create: `.hermes/team/control_plane/observability/metrics.py`
- Create: `.hermes/team/control_plane/observability/prometheus_exporter.py`
- Create: `.hermes/team/control_plane/observability/prometheus/prometheus.yml`
- Create: `.hermes/team/control_plane/observability/prometheus/rules/improvement-alerts.yml`
- Create: `.hermes/team/control_plane/observability/grafana/dashboards/improvement-overview.json`
- Modify: `.hermes/team/调度框架/core/monitor.py`
- Modify: `.hermes/team/调度框架/core/workflow_engine.py`
- Modify: `.hermes/team/调度框架/core/message_bus.py`
- Test: `tests/control_plane/test_metrics.py`

- [ ] 写失败测试：验证 `improvement_*` 指标注册、文本导出、阈值告警配置生成
- [ ] 运行 `python -m unittest tests.control_plane.test_metrics -v` 并确认失败
- [ ] 实现 metrics registry 与 exporter
- [ ] 把 dashboard availability、workflow role hit、config source count、audit/high risk 等埋点接入关键路径
- [ ] 生成 Prometheus、Grafana、告警规则交付物
- [ ] 再跑 `python -m unittest tests.control_plane.test_metrics -v` 确认通过

### Task 9: CI、Coverage 与 README 对照表

**Files:**
- Create: `pyproject.toml`
- Create: `.github/workflows/control-plane-ci.yml`
- Modify: `.hermes/team/调度框架/README.md`
- Modify: `.hermes/team/调度框架/README_v2.md`
- Create: `.hermes/team/control_plane/artifacts/milestone-progress-report.md`
- Test: `tests/control_plane/test_ci_smoke.py`

- [ ] 写失败测试：验证 CI 命令链、README 对照表、进展报告关键字段
- [ ] 运行 `python -m unittest tests.control_plane.test_ci_smoke -v` 并确认失败
- [ ] 实现 `pyproject.toml`、ruff、coverage、GitHub Actions
- [ ] 在 README 增加“评估报告实现对照表”并逐条勾选
- [ ] 生成里程碑进展报告，PR 标题按 `里程碑-{序号}-{简述}` 写入表格
- [ ] 再跑 `python -m unittest tests.control_plane.test_ci_smoke -v` 确认通过

### Task 10: 全量验证与交付

**Files:**
- Modify: `.hermes/team/control_plane/artifacts/execution-summary-2026-05-12.md`

- [ ] 运行 `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
- [ ] 运行 `python -m coverage run -m unittest discover -s tests/control_plane -p "test_*.py"`
- [ ] 运行 `python -m coverage report`
- [ ] 记录覆盖率结果与量化目标实际值到执行摘要和里程碑进展报告
- [ ] 自查旧入口回滚路径和特性开关，确认关闭新功能不影响既有控制平面最小闭环
