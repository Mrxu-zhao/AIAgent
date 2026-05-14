# Agent Knowledge Closure Remaining Roadmap

## 1. 目的

本文档用于汇总 `Agent Knowledge Closure Program` 在当前已完成主链基础上的剩余工作，给出统一的阶段划分、优先级顺序、目标产出、建议落点和完成判定，方便后续持续推进。

当前已经完成的基础能力包括：

- 统一知识域层：`models / catalog / consumer / recommendation / governance / query / analytics`
- 摘要优先的知识消费链路
- `TaskCard / workflow / handoff / executor / runner` 的基础知识联动
- `query knowledge` 独立资源与基础过滤
- dashboard 的基础知识 analytics
- handoff 知识消费确认 API
- bundle 缓存的最小版本

剩余工作不再是“是否有知识链路”，而是把现有链路升级为“效果驱动、治理完整、观测充分、协议稳定、性能可控”的长期形态。

## 2. 总体判断

剩余路线分为 3 个阶段，共 12 项工作：

- `P1`：高优先级闭环增强，重点解决“能不能真正用起来”
- `P2`：治理与协议深化，重点解决“能不能长期稳定演进”
- `P3`：性能、收尾与可运维性，重点解决“能不能规模化持续使用”

## 3. 阶段划分

### P1：高优先级闭环增强

#### 1. Query 聚合增强

目标：

- 让 `query knowledge` 直接返回可消费聚合，而不仅是过滤后的记录列表。

要补的能力：

- `top_recommended`
- `top_consumed`
- `top_writeback`
- `top_unused`
- `by_role`
- `by_agent`
- `by_review_status`

建议落点：

- `.hermes/team/control_plane/knowledge/query.py`
- `.hermes/team/control_plane/knowledge/analytics.py`
- `.hermes/team/control_plane/cli.py`
- `tests/control_plane/test_knowledge_query.py`
- `tests/control_plane/test_unified_cli.py`

完成判定：

- `query knowledge --summary` 能输出聚合统计
- CLI 和 tool runtime 都能拿到统一聚合结构

#### 2. Handoff 失败归因标准化

目标：

- 把 `knowledge_failure_reason` 从自由文本升级为标准原因枚举与稳定写入规则。

建议标准原因：

- `missing-bundle`
- `outdated-summary`
- `wrong-recommendation`
- `no-read-action`
- `path-invalid`
- `decode-error`

建议落点：

- `.hermes/team/control_plane/handoff_runtime.py`
- `.hermes/team/control_plane/protocols/handoff.py`
- `.hermes/team/control_plane/tools/builtin.py`
- `.hermes/team/调度框架/core/handoff_coordinator.py`
- `tests/control_plane/test_handoff.py`
- `tests/control_plane/test_handoff_runtime.py`

完成判定：

- handoff 记录可明确区分“未消费”和“消费失败”
- dashboard/query 能按失败原因聚合

#### 3. 推荐反馈闭环落地

目标：

- 让 `KnowledgeUsage.feedback_score` 真正影响下一轮推荐排序，而不是只保留字段。

要补的能力：

- 推荐结果与真实消费结果对齐
- 读过但未展开、展开但未帮助、推荐但未读的差异权重
- 根据最近周期与累计周期混合打分

建议落点：

- `.hermes/team/control_plane/knowledge/recommendation.py`
- `.hermes/team/control_plane/knowledge/models.py`
- `.hermes/team/control_plane/knowledge/analytics.py`
- `.hermes/team/调度框架/core/task_router.py`
- `tests/control_plane/test_task_router.py`

完成判定：

- 连续两次相近任务的推荐顺序会因反馈发生合理变化
- 推荐结果中能解释“为什么这次排序变了”

#### 4. Analytics 深化

目标：

- 把当前 dashboard 从“看到了什么”升级为“哪些知识有效、哪些低效”。

要补的能力：

- 推荐了但没读
- 读了但没有帮助
- 高风险任务知识覆盖不足
- 失败 handoff 的知识原因分布

建议落点：

- `.hermes/team/control_plane/knowledge/analytics.py`
- `.hermes/team/调度框架/core/monitor.py`
- `tests/control_plane/test_knowledge_analytics.py`
- `tests/control_plane/test_framework_monitor.py`

完成判定：

- dashboard 能识别低效知识包与高风险覆盖缺口

#### 5. Backend 知识注入协议补完

目标：

- 把当前 `knowledge_summary / next_read` 的最小形态升级为稳定注入协议，统一 Hermes 与 OpenClaw。

建议协议字段：

- `summary`
- `next_read`
- `raw_paths`
- `risks`
- `open_questions`
- `bundle_id`
- `cache_hit`

建议落点：

- `.hermes/team/control_plane/executor.py`
- `.hermes/team/control_plane/runner.py`
- `.hermes/team/control_plane/runtime/context.py`
- `.hermes/team/control_plane/adapters/*.py`
- `tests/control_plane/test_executor.py`

完成判定：

- 两个 backend 都能收到同构知识注入 payload
- payload 能在执行结果和 transcript 中回放

### P2：治理与协议深化

#### 6. 治理文件双写统一

目标：

- 统一 markdown 展示层和结构化治理层之间的映射规则，避免出现“双真源”。

要补的能力：

- markdown 的稳定区块格式
- 结构化 entry 和 markdown section 的一一映射
- accept/reject/archive 后 markdown 自动同步

建议落点：

- `.hermes/team/control_plane/knowledge/governance.py`
- `.hermes/team/knowledge/decision-log.md`
- `.hermes/team/knowledge/risk-register.md`
- `tests/control_plane/test_governance.py`

完成判定：

- 用户读 markdown 和 CLI/query 看到的是同一组知识状态

#### 7. Recent Lessons 治理闭环

目标：

- 把 agent 级 `recent-lessons` 也纳入统一确认、去重、归档流程。

建议落点：

- `.hermes/team/control_plane/knowledge/governance.py`
- `.hermes/team/agents/*/knowledge/recent-lessons.md`
- `tests/control_plane/test_governance.py`

完成判定：

- lessons 不再只是 append-only，而有状态迁移与去重逻辑

#### 8. 多跳 Handoff 知识继承链补完

目标：

- 把 `inherited_knowledge_chain` 从记录字段升级成真实继承和裁剪逻辑。

要补的能力：

- 多跳 handoff 继承父知识包
- 当前 step 可以增量追加知识
- 目标 agent 可确认“沿用”还是“重选”

建议落点：

- `.hermes/team/调度框架/core/handoff_coordinator.py`
- `.hermes/team/调度框架/core/workflow_engine.py`
- `.hermes/team/control_plane/protocols/handoff.py`
- `tests/control_plane/test_handoff.py`
- `tests/control_plane/test_workflow_runtime.py`

完成判定：

- 多跳协作时能追溯知识来源链和覆盖变化

#### 9. 全文检索与来源反查增强

目标：

- 让 `decision / risk / lesson` 不只支持轻量过滤，还支持更稳定的全文检索和来源定位。

要补的能力：

- 全文索引
- `workflow -> step -> governance entry` 反查
- `entry -> workflow/step/handoff` 正查

建议落点：

- `.hermes/team/control_plane/knowledge/query.py`
- `.hermes/team/control_plane/knowledge/governance.py`
- `tests/control_plane/test_knowledge_query.py`

完成判定：

- 可以直接反查某条 decision 是从哪个 workflow/step 沉淀来的

### P3：性能、收尾与可运维性

#### 10. Cache 正式化

目标：

- 把当前进程内 `_KNOWLEDGE_BUNDLE_CACHE` 升级为可控缓存对象。

要补的能力：

- TTL 或版本失效
- 最大容量
- 命中率统计
- 按 bundle/profile 维度清理

建议落点：

- `.hermes/team/control_plane/knowledge/catalog.py`
- `.hermes/team/control_plane/runtime/rules.py`
- `tests/control_plane/test_knowledge_consumer.py`

完成判定：

- 缓存命中、失效、清理都有明确测试与输出

#### 11. Benchmark 扩展

目标：

- 把知识查询、预加载和 analytics 成本做成更稳定的基线输出。

要补的能力：

- before/after 可比
- 大知识库下的耗时趋势
- query、preload、analytics 分项指标

建议落点：

- `.hermes/team/control_plane/baseline.py`
- `tests/control_plane/test_baseline.py`

完成判定：

- baseline 报告中能稳定比较知识相关性能项

#### 12. 文档与 CLI 示例补完

目标：

- 给现有能力补齐“如何用”的说明，降低后续接手成本。

要补的文档：

- `docs/runtime/runtime-governance.md`
- `docs/runtime/handoff-and-continuation.md`
- `docs/architecture/control-plane-overview.md`
- 新增一份知识查询与治理示例文档

建议内容：

- 常见命令示例
- 典型查询样例
- 治理流转样例
- handoff 消费确认样例

完成判定：

- 新接手的人只看文档就能跑通知识查询、治理和 handoff 关键流程

## 4. 推荐执行顺序

推荐按以下顺序推进：

1. Query 聚合增强
2. Handoff 失败归因标准化
3. 推荐反馈闭环落地
4. Analytics 深化
5. Backend 知识注入协议补完
6. 治理文件双写统一
7. Recent Lessons 治理闭环
8. 多跳 Handoff 知识继承链补完
9. 全文检索与来源反查增强
10. Cache 正式化
11. Benchmark 扩展
12. 文档与 CLI 示例补完

## 5. 完成定义

当以下条件满足时，可认为知识闭环进入“长期可用”阶段：

- 推荐结果受历史反馈影响，且可解释
- handoff 能明确知道知识是否被消费、为何失败
- query 和 dashboard 能识别有效知识、低效知识和高风险覆盖缺口
- governance 的 markdown 与结构化记录无分叉
- cache、benchmark 和文档足以支撑日常维护

## 6. 建议命名

后续如果继续写分阶段文档，建议使用：

- `2026-05-14-agent-knowledge-p1-closure.md`
- `2026-05-14-agent-knowledge-p2-governance.md`
- `2026-05-14-agent-knowledge-p3-performance.md`

这样可以和当前总路线图文档配套使用。
