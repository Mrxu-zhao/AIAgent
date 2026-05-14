# 仓库级控制平面

## 文档入口
- 总览：`../../../docs/architecture/control-plane-overview.md`
- handoff 契约：`../../../docs/contracts/handoff-contract.md`
- provider 契约：`../../../docs/contracts/provider-contracts.md`
- 运行时治理：`../../../docs/runtime/runtime-governance.md`
- handoff 与 continuation：`../../../docs/runtime/handoff-and-continuation.md`
- 知识库 enrichment 计划：`../../../docs/superpowers/plans/2026-05-13-agent-knowledge-base-enrichment.md`
- tool runtime MVP 计划：`../../../docs/superpowers/plans/2026-05-14-control-plane-tool-runtime-mvp.md`
- session/tools/permissions 计划：`../../../docs/superpowers/plans/2026-05-14-control-plane-session-tools-permissions.md`

## 目录
- `models.py`：任务卡、事件、状态与锁域模型
- `tasks.py`：第一批标准任务注册表
- `store.py`：任务快照与事件日志落盘
- `conflicts.py`：文件级、模块级、契约级冲突检测
- `adapters.py`：`Hermes` 直连执行适配器与 `OpenClaw` 预留接口
- `executor.py`：失败隔离、重试判断与命令装配
- `orchestrator.py`：高层 ready 任务调度与依赖阻塞传播
- `workflow_runtime.py`：workflow snapshot、step 事件与知识反馈落盘
- `handoff_runtime.py`：handoff 记录与 continuation 状态落盘
- `protocols/handoff.py`：handoff payload 与 schema 对齐
- `knowledge_feedback.py`：把 workflow 决策与风险回写到团队知识层
- `runtime/`：knowledge bundle 规则、预加载与 tool execution context
- `tools/`：tool spec、registry、executor、builtin tools、transcript、session store
- `runner.py`：共享批次入口，负责任务注册与调度装配
- `cli.py`：统一控制平面 CLI，覆盖 dispatch、workflow、query、monitor、tool-run、tool-session

## 当前边界
- 第一阶段直接支持 `Hermes` 调度命令装配。
- `OpenClaw` 已提供 dry-run MVP 适配接口，真实 live 执行仍留待后续阶段。
- 调度框架的 P0 修复由控制平面的测试集统一验证。
- `TaskStore` 已支持基于 `expected_version` 的乐观并发拒绝，以及基于 `version` / `last_event_id` 的快照校验。
- `ControlPlaneExecutor` 已在关键状态迁移中消费 `expected_version`，对完成态写入提供最小 compare-and-swap 保护。
- `ControlPlaneOrchestrator` 已负责高层多任务并行调度，并把 CAS 语义上推到 ready 任务选择、冲突解释和直接依赖阻塞传播。
- `runner.py` 已把 `TASKS`、`TaskStore`、`ControlPlaneExecutor` 和 `ControlPlaneOrchestrator` 装配为统一批次执行入口。
- 统一 CLI 已支持 `dispatch`、`workflow`、`query workflow`、`query handoff`、`monitor`、`tool-run`、`tool-session`。
- workflow runtime 现已记录 `knowledge_recommendations`、`knowledge_bundles`、`knowledge_feedback`，不再只落快照与 step 事件。
- handoff 协议与 runtime 已支持 `knowledge_recommendation`，跨 agent 交接会附带目标知识包建议。
- tool runtime 已支持 knowledge bundle 预加载、tool transcript、session 恢复、tool 级 RBAC 与审批拦截。
- query 入口已支持 `--knowledge-only` 与 `--summary`，可以直接查看 workflow/handoff 的知识摘要视图。
- dashboard 已新增 `recommended_knowledge` 与 `recent_knowledge_feedback` 面板。

## 知识链路现状
- `TaskRouter` 会输出 `knowledge_recommendation`，并给出 `path_scores`、文件存在性和 `recent-lessons.md` 命中优先级。
- `WorkflowEngine` 会把知识推荐透传到 `step_contexts`、handoffs、顶层结果与 runtime snapshot，并生成 `knowledge_bundles`。
- `decision-log.md` 与 `risk-register.md` 已接通 workflow 自动回写，具备 metadata 补齐和重复条目去重。
- `ToolExecutor` 会在 handler 执行前预加载知识文件内容，`read_knowledge` 优先复用预加载结果。
- query 和 dashboard 已经能直接消费这些知识结构，而不是只展示原始运行时记录。

## 推荐执行顺序
1. 使用 `runner.py` 或 `run_batch.py` 注册任务并建立状态仓。
2. 通过共享 runner 装配执行器、适配器与 `ControlPlaneOrchestrator`。
3. 在 tool 级能力场景使用 `tool-run` / `tool-session` 验证 knowledge bundle、session 与权限语义。
4. 使用 `query workflow --knowledge-only --summary` 与 `query handoff --knowledge-only --summary` 查看知识摘要视图。
5. 使用 `monitor --dashboard` 观察推荐知识包与最近知识回写结果。
6. 运行调度框架与控制平面相关回归测试。
7. 聚合执行结果并生成最终报告。

## 验证基线
- `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`：控制平面主线测试可运行。
- `python -m unittest tests.control_plane.test_tool_executor tests.control_plane.test_tool_cli tests.control_plane.test_tool_transcript tests.control_plane.test_unified_cli tests.control_plane.test_handoff tests.control_plane.test_handoff_coordinator tests.control_plane.test_task_router tests.control_plane.test_workflow_runtime tests.control_plane.test_framework_monitor tests.control_plane.test_framework_compat tests.control_plane.test_metrics tests.control_plane.test_orchestrator`：`89 tests, OK`
- 使用编辑器诊断检查 `.hermes/team/control_plane` 与 `.hermes/team/调度框架/core` 关键文件：无新增诊断错误。
