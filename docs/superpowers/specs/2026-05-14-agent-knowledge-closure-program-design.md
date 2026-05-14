# Agent Knowledge Closure Program 设计文档

## 1. 背景

当前仓库已经具备一条可工作的知识链路：

- `TaskRouter` 可以基于 `task_type / deliverables / risk_flags / collaboration_mode` 输出 `knowledge_recommendation`。
- `WorkflowEngine` 会把知识推荐透传到 `step_contexts`、`handoffs`、`knowledge_bundles` 与 `knowledge_feedback`。
- `ToolExecutor` 与 tool runtime 会在执行前调用 `build_knowledge_bundle()` 和 `preload_knowledge_bundle()`。
- `decision-log.md` 与 `risk-register.md` 已支持 workflow 自动回写。
- CLI `dispatch / workflow / query / monitor` 已能展示部分知识推荐和反馈摘要。

但当前能力仍停留在“整文件推荐 + 整文件预加载 + 轻量查询/仪表盘”的阶段，无法覆盖你列出的 8 类增强目标：

1. 知识消费升级
2. 知识推荐优化
3. 知识治理闭环
4. Query 与检索能力
5. Dashboard 深化
6. 执行层联动
7. Handoff 深化
8. 质量与安全

当前系统最核心的结构问题不是某个点缺逻辑，而是缺少一套统一的知识域模型，导致 `router / workflow / handoff / tool runtime / control_plane / monitor / query` 只能各自附带轻量字段，难以形成闭环。`<mccoremem id="01KRG0XH9KSY572B133JZ1JVZM|03g400roujgec9otxvlzd7jq0|03g49kiy4yk240dci3220p7eu" />`

## 2. 目标与非目标

### 2.1 目标

- 在 `.hermes/team/control_plane` 下建立统一知识域层，串起推荐、消费、治理、查询、分析、执行联动和 handoff。
- 把知识消费从“整文件读取”升级为“任务画像驱动的摘要优先、片段级裁剪、按需展开原文”。
- 把知识推荐从“规则命中”升级为“规则 + 路径归属 + 历史效果反馈 + 跨角色组合包”。
- 建立 `decision-log / risk-register / recent-lessons` 的治理元数据、人工确认流、审计与归档能力。
- 提供统一 query 入口与 dashboard 统计，支持过滤、全文检索、来源反查、热度排行和覆盖率分析。
- 让 `TaskCard / batch runner / executor / Hermes / OpenClaw` 共享同一套知识注入协议。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K|01KRDKFS2XFQ1K5105VDNMG5FX|03g49kiy4yk240dci3220p7eu" />`
- 增加容错、安全和性能测试，确保大规模知识库下仍可运行。

### 2.2 非目标

- 本轮不引入外部向量数据库、外部检索服务或非 Python 原生存储。
- 本轮不把知识推荐替换为黑盒机器学习系统，只做可解释的反馈加权与统计学习。
- 本轮不重写整个调度框架或控制平面，只在现有结构上做兼容式增强。
- 本轮不把 monitor 改造成完整前端应用，仍以 CLI payload、runtime snapshot 与 Grafana 数据源为主。

## 3. 方案比较

### 方案 A：按 8 类分别补丁式实现

直接在现有 `task_router.py`、`workflow_engine.py`、`monitor.py`、`cli.py`、`runtime/rules.py` 等文件中逐点补逻辑。

优点：

- 起步快。
- 不需要新增太多文件。

缺点：

- 知识字段继续散落在多个模块里。
- query 与 dashboard 只能复用轻量快照，难以精细统计。
- 执行层和 handoff 层会继续长出各自的“半套协议”。

### 方案 B：单独抽象一个完全独立的知识服务

新建完整知识子系统，让现有 router/workflow/control_plane 全部调用该系统。

优点：

- 模型最整洁。
- 中长期扩展性最好。

缺点：

- 初次改动过大。
- 迁移风险高。
- 容易与当前 `Hermes / OpenClaw` 适配链路产生割裂。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />`

### 方案 C：兼容式统一知识域层

保留现有主链路与入口，在 `.hermes/team/control_plane/knowledge/` 下增加统一知识域对象与服务，再由 router/workflow/handoff/runtime/query/dashboard 渐进接入。

优点：

- 对当前代码结构最友好。
- 可以一次性覆盖 8 类能力，又不需要重写框架。
- 有利于让 `TaskCard`、handoff 和 backend 注入协议最终收敛到同一套对象。`<mccoremem id="01KRDKFS2XFQ1K5105VDNMG5FX|03g49kiy4yk240dci3220p7eu" />`

缺点：

- 需要设计一套清晰的兼容边界。
- 现有代码会短期存在“旧字段 + 新对象”的过渡期。

### 方案选择

本设计选择 **方案 C：兼容式统一知识域层**。

## 4. 设计原则

- **兼容优先**：保留当前 `knowledge_recommendation` 字段，但内部升级为更完整的结构。
- **摘要优先**：默认消费摘要和高优先级片段，不把整文件内容无差别塞入执行上下文。
- **显式可解释**：每个推荐、裁剪、降级、回写和过滤都必须可解释。
- **治理可追踪**：所有自动写回都要能追溯来源 workflow/step，并支持人工确认。
- **后端中立**：Hermes/OpenClaw 的知识注入协议保持同构，由 provider adapter 落地。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K|03g49kiy4yk240dci3220p7eu" />`
- **Python 原生实现**：索引、缓存、快照、审计和统计都以文件制品和 dataclass 为主。

## 5. 总体架构

新增目录：

```text
.hermes/team/control_plane/knowledge/
  __init__.py
  models.py
  catalog.py
  consumer.py
  recommendation.py
  governance.py
  query.py
  analytics.py
```

各模块职责：

- `models.py`
  - 定义统一知识域对象。
- `catalog.py`
  - 负责知识文件元数据、索引、路径校验、快照和缓存。
- `consumer.py`
  - 负责摘要、片段抽取、优先级裁剪、按需展开原文与容错。
- `recommendation.py`
  - 负责推荐、历史反馈加权、跨角色组合包与降级解释。
- `governance.py`
  - 负责 `decision-log / risk-register / recent-lessons` 回写、review 状态、owner、审计和归档。
- `query.py`
  - 负责 workflow/handoff/knowledge 的统一过滤、统计与全文检索接口。
- `analytics.py`
  - 负责 dashboard 所需热度、消费分布、未使用推荐、高风险覆盖率与待确认数量统计。

## 6. 统一数据模型

### 6.1 KnowledgeProfile

用于描述一次任务需要什么知识，核心字段：

- `task_type`
- `deliverables`
- `risk_flags`
- `workflow_id`
- `step_id`
- `owner_agent`
- `role_key`
- `collaboration_mode`
- `upstream_agent`
- `upstream_role`
- `scope_paths`
- `module_hints`

来源：

- `TaskRouter.analyze_task_intent()`
- `WorkflowEngine` step 元信息
- handoff payload
- `TaskCard`

### 6.2 KnowledgeExcerpt

用于描述裁剪后的知识片段，核心字段：

- `path`
- `resolved_path`
- `summary`
- `excerpt`
- `priority`
- `matched_by`
- `tokens_estimate`
- `expandable`
- `degraded_reason`

### 6.3 KnowledgeBundle

用于描述执行前真正可消费的知识包，核心字段：

- `profile`
- `load_order`
- `team`
- `role`
- `instance`
- `cross_role`
- `excerpts`
- `raw_paths`
- `missing_paths`
- `cache_key`
- `usage`

### 6.4 KnowledgeUsage

用于记录推荐和真实消费的偏差，核心字段：

- `recommended_paths`
- `consumed_paths`
- `expanded_paths`
- `unused_paths`
- `decision_helpful_count`
- `risk_helpful_count`
- `feedback_score`

### 6.5 GovernanceEntry

用于知识治理，核心字段：

- `entry_type`
- `content`
- `owner`
- `review_status`
- `accepted`
- `rejected`
- `source_workflow_id`
- `source_step_id`
- `source_agent`
- `created_at`
- `reviewed_at`
- `audit_trail`

## 7. 详细设计

### 7.1 知识消费升级

从 `runtime/rules.py` 的整文件预读升级为：

1. `catalog.py` 解析推荐路径并构建带元信息的候选集合。
2. `consumer.py` 按 `task_type / deliverables / risk_flags / collaboration_mode / module_hints` 生成片段和摘要。
3. 默认只把 `summary + top excerpts` 注入执行上下文。
4. `read_knowledge` 与 query 能力支持按需展开原文。
5. 对过大文件、损坏文件、编码异常和路径失效输出降级摘要，而不是抛出未处理异常。

消费策略：

- 团队层默认摘要优先。
- 角色层优先保留 checklist、playbook、template、recent-lessons 的高分片段。
- 实例层优先保留 `owned-modules / delivery-style / recent-lessons` 的高相关内容。
- 原文只有在 tool/query 显式请求展开时才读取完整内容。

### 7.2 知识推荐优化

推荐从“静态规则 + 文件存在性”升级为“静态规则 + 归属 + 反馈”三段式：

- **静态规则**：保留当前按 `task_type / risk_flags / collaboration_mode` 的推荐逻辑。
- **归属匹配**：基于模块、目录、接口关键词和 `owned-modules` 增加更细粒度打分。
- **反馈加权**：结合历史 `KnowledgeUsage.feedback_score` 提升有效路径，降低高推荐低消费路径。

新增能力：

- 支持 `cross_role` 组合包，如 `architect + backend-dev + qa-functional`。
- 对“推荐但文件不存在”输出可解释降级，如 `missing-path -> fallback-role-overview`。
- 输出 `recommendation_reason` 与 `degradation_reason` 供 query/dashboard 展示。

### 7.3 知识治理闭环

治理扩展到三类文件：

- `.hermes/team/knowledge/decision-log.md`
- `.hermes/team/knowledge/risk-register.md`
- `.hermes/team/agents/*/knowledge/recent-lessons.md`

新增规则：

- 自动写回记录默认状态为 `pending_review`。
- 每条记录必须补齐 `owner / review_status / source_workflow_id / source_step_id / source_agent`。
- 提供 `accepted / rejected / archived` 状态迁移。
- 提供重复合并与过期归档。
- 每次治理变更写入审计快照，支持“是谁确认/拒绝/归档了什么”。

### 7.4 Query 与检索能力

扩展 `cli.py query` 和 tool runtime 查询能力，支持：

- 按 `agent / role / workflow / task_type / risk tag / review_status` 过滤。
- 统一全文搜索 `decision-log / risk-register / recent-lessons`。
- 统计最常被推荐、最常被消费、最常被回写的知识包。
- 反查某条 decision/risk 来源于哪个 workflow/step。

统一查询输出包含：

- `filters`
- `records`
- `summary`
- `aggregations`

### 7.5 Dashboard 深化

在 `monitor.py` 上新增 analytics 汇总：

- `knowledge_heat_ranking`
- `knowledge_consumption_by_agent`
- `unused_recommendations`
- `high_risk_workflow_coverage`
- `pending_governance_counts`

这些数据来自统一知识域，而不是各模块临时拼装。

### 7.6 执行层联动

扩展 `TaskCard` 与控制平面执行链：

- `TaskCard` 新增 `knowledge_recommendation`、`knowledge_bundle` 与 `knowledge_summary`。
- `WorkflowEngine._build_task_card_for_step()` 与 `HandoffCoordinator._build_task_card()` 把同一知识包带入任务卡。
- `runner.py` / `executor.py` 在真实命令装配前注入知识摘要。
- Hermes/OpenClaw adapter 接收统一的 `knowledge injection payload`：
  - `summary`
  - `next_read`
  - `risks`
  - `open_questions`
  - `raw_paths`

### 7.7 Handoff 深化

扩展 `HandoffPayload` 与 `HandoffRecord`：

- handoff 必带：
  - `knowledge_summary`
  - `open_questions`
  - `risks`
  - `next_read`
- handoff record 追踪：
  - `knowledge_consumed`
  - `knowledge_consumed_at`
  - `knowledge_failure_reason`
  - `inherited_knowledge_chain`

校验规则：

- 缺少 handoff 强约束字段时，payload 校验失败。
- 目标 agent 消费知识后记录确认状态。
- 多跳 handoff 继承上游知识链，但允许目标步骤追加补充知识。

### 7.8 质量与安全

新增保证：

- 知识文件过大时自动裁剪并记录降级原因。
- 编码异常或损坏文件时输出安全占位摘要。
- 所有知识路径必须限制在仓库根目录下。
- 对可疑知识内容提供隔离标记，不直接注入执行上下文。
- 增加 benchmark，分别评估：
  - 预加载裁剪成本
  - query 全文检索成本
  - dashboard 聚合成本
  - 大规模知识库推荐成本

## 8. 文件级变更

### 8.1 新增

- `.hermes/team/control_plane/knowledge/models.py`
- `.hermes/team/control_plane/knowledge/catalog.py`
- `.hermes/team/control_plane/knowledge/consumer.py`
- `.hermes/team/control_plane/knowledge/recommendation.py`
- `.hermes/team/control_plane/knowledge/governance.py`
- `.hermes/team/control_plane/knowledge/query.py`
- `.hermes/team/control_plane/knowledge/analytics.py`
- `tests/control_plane/test_knowledge_models.py`
- `tests/control_plane/test_knowledge_consumer.py`
- `tests/control_plane/test_knowledge_query.py`
- `tests/control_plane/test_knowledge_analytics.py`

### 8.2 修改

- `.hermes/team/control_plane/models.py`
- `.hermes/team/control_plane/runtime/rules.py`
- `.hermes/team/control_plane/runtime/context.py`
- `.hermes/team/control_plane/tools/builtin.py`
- `.hermes/team/control_plane/executor.py`
- `.hermes/team/control_plane/runner.py`
- `.hermes/team/control_plane/cli.py`
- `.hermes/team/control_plane/protocols/handoff.py`
- `.hermes/team/调度框架/core/task_router.py`
- `.hermes/team/调度框架/core/workflow_engine.py`
- `.hermes/team/调度框架/core/handoff_coordinator.py`
- `.hermes/team/调度框架/core/monitor.py`
- `tests/control_plane/test_workflow_runtime.py`
- `tests/control_plane/test_handoff.py`
- `tests/control_plane/test_unified_cli.py`
- `tests/control_plane/test_framework_monitor.py`
- `tests/control_plane/test_executor.py`

## 9. 兼容策略

- 旧字段 `knowledge_recommendation` 继续存在，但内部值允许携带 richer payload。
- `build_knowledge_bundle()` 与 `preload_knowledge_bundle()` 保持原函数名，改为调用新知识域实现。
- 旧的 query 输出字段不删除，只追加 `filters / aggregations / analytics`。
- 旧 handoff payload 中只有 `knowledge_recommendation` 的场景仍可读取，但新生产路径必须输出强约束字段。

## 10. 验收标准

### 10.1 功能验收

- 一个 workflow step 能得到摘要化知识包，而不是整文件原文集合。
- `TaskCard`、handoff payload、tool runtime context 能拿到同一套知识摘要与下一步阅读建议。
- query 能按 agent/role/workflow/task_type/risk tag/review_status 过滤。
- dashboard 能给出热度排行、消费分布、未使用推荐、高风险覆盖率、待确认数量。
- 自动写回的 decision/risk/lesson 支持人工确认与来源反查。

### 10.2 质量验收

- 大文件、坏文件、路径越权、编码异常场景均有测试覆盖。
- benchmark 可输出基础性能结果。
- 现有 workflow/handoff/control_plane 回归测试继续通过。

## 11. 风险与缓解

### 风险 1：统一知识域层过重

缓解：

- 用 dataclass + 文件制品实现，不引入外部服务。
- 保持 `runtime/rules.py` 为兼容入口，降低调用面改动。

### 风险 2：旧链路与新对象并存，增加复杂度

缓解：

- 统一从新知识域生成兼容字段，避免多源拼装。
- 在测试中固定旧字段和新字段的对齐关系。

### 风险 3：查询和 dashboard 成本明显上升

缓解：

- 增加缓存与 snapshot 聚合。
- query 和 analytics 采用渐进聚合，不在每次命令里重建所有统计。

### 风险 4：治理写回噪音过大

缓解：

- 默认 `pending_review`，必须显式确认后才进入稳定知识面。
- 提供去重、归档和 rejected 语义。

## 12. 分期

- `P0`：统一知识域对象、摘要消费、TaskCard/handoff 注入、query 基础过滤、dashboard 基础统计、关键测试。
- `P1`：反馈学习、跨角色组合包、治理责任链、未使用推荐分析、高风险覆盖率、更多容错测试。
- `P2`：缓存增强、全文检索优化、归档/审计完善、大规模 benchmark。

## 13. 完成判定

当以下条件满足时，本设计视为完成：

- 8 类能力都已映射到明确模块、数据对象和接入点。
- 所有变更都能落在现有 Hermes/OpenClaw 兼容结构上。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K|03g49kiy4yk240dci3220p7eu" />`
- plan 可以直接基于本 spec 拆成逐任务执行步骤。
