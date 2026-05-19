---
owner: control-plane
last_reviewed: 2026-05-19
source: workflow-feedback
---

# 关键决策记录

| 日期 | 决策 | 理由 | 影响范围 |
|------|------|------|----------|
| 2026-05-13 | 采用团队层 + 角色层 + 实例层三层知识体系 | 与现有 Hermes/team/agents 结构天然兼容，利于渐进演进 | team knowledge、role knowledge、instance knowledge |
| 2026-05-13 | 团队知识增加真实 `status.md` 与兼容目录 | 兼容现有 skill 文档读取约定 | `.hermes/team/knowledge/` |
| 2026-05-13 | 角色知识采用“标准入口 + 保留旧文件”的兼容策略 | 避免一次性迁移打断已有知识沉淀 | `.hermes/agents/*/knowledge/` |
| 2026-05-18 | `workflow --context-file` 对非 JSON 文件按文本装载到 `project_context` | 实战项目使用 `project-context.md` 时，严格 `json.loads()` 会阻断 workflow 启动 | `control_plane/cli.py`、文档驱动型项目启动链路 |
| 2026-05-18 | 自定义 workflow 定义优先使用已存在的仓库相对路径 | `.hermes\team\调度框架\workflows\*.json` 会被错误 rebasing 到默认 workflow 目录，导致真实文件找不到 | `workflow_engine.load_workflow_definition()`、自定义 workflow 入口 |
| 2026-05-18 | 终态事件写入遇到 `VERSION_CONFLICT` 时先复核最新 snapshot | 并发完成写入可能让任务已 `done` 却返回 `success=false`，误导 CLI 与复验脚本 | `executor.execute_task()`、dispatch/自动化复验链路 |

## 记录规则
- 只记录影响跨角色协作或后续维护的重要决策。
- 每条记录至少包含理由和影响范围。
- 若发生逆转，需要在本文件追加新的决策，而不是覆盖旧记录。
| 2026-05-14 | [wf-collab] [design] design-decision | rationale: n/a | impact: n/a | next: n/a | workflow result | workflow: wf-collab; step: design |
| 2026-05-14 | [wf-collab] [review] review-decision | rationale: n/a | impact: n/a | next: n/a | workflow result | workflow: wf-collab; step: review |
| 2026-05-14 | [wf-decision-summary] [design] design-decision | rationale: 因为需要统一执行口径 | impact: 影响后续实现与验收 | next: 同步到 handoff | workflow result | workflow: wf-decision-summary; step: design |
| 2026-05-14 | [wf-decision-summary] [review] review-decision | rationale: 因为需要统一执行口径 | impact: 影响后续实现与验收 | next: 同步到 handoff | workflow result | workflow: wf-decision-summary; step: review |
