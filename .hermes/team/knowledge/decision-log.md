---
owner: control-plane
last_reviewed: 2026-05-15
source: workflow-feedback
---

# 关键决策记录

| 日期 | 决策 | 理由 | 影响范围 |
|------|------|------|----------|
| 2026-05-13 | 采用团队层 + 角色层 + 实例层三层知识体系 | 与现有 Hermes/team/agents 结构天然兼容，利于渐进演进 | team knowledge、role knowledge、instance knowledge |
| 2026-05-13 | 团队知识增加真实 `status.md` 与兼容目录 | 兼容现有 skill 文档读取约定 | `.hermes/team/knowledge/` |
| 2026-05-13 | 角色知识采用“标准入口 + 保留旧文件”的兼容策略 | 避免一次性迁移打断已有知识沉淀 | `.hermes/agents/*/knowledge/` |

## 记录规则
- 只记录影响跨角色协作或后续维护的重要决策。
- 每条记录至少包含理由和影响范围。
- 若发生逆转，需要在本文件追加新的决策，而不是覆盖旧记录。
| 2026-05-14 | [wf-collab] [design] design-decision | rationale: n/a | impact: n/a | next: n/a | workflow result | workflow: wf-collab; step: design |
| 2026-05-14 | [wf-collab] [review] review-decision | rationale: n/a | impact: n/a | next: n/a | workflow result | workflow: wf-collab; step: review |
| 2026-05-14 | [wf-decision-summary] [design] design-decision | rationale: 因为需要统一执行口径 | impact: 影响后续实现与验收 | next: 同步到 handoff | workflow result | workflow: wf-decision-summary; step: design |
| 2026-05-14 | [wf-decision-summary] [review] review-decision | rationale: 因为需要统一执行口径 | impact: 影响后续实现与验收 | next: 同步到 handoff | workflow result | workflow: wf-decision-summary; step: review |
