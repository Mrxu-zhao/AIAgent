# 研发团队 - Agent 配置

## 团队架构

| 序号 | 名字 | 角色 | 状态 | 知识库路径 |
|------|------|------|------|------------|
| 1 | 秦燕 | 项目经理 | ✅ 我担任 | - |
| 2 | 张欣怡 | 系统架构师 | 已训练 | agents/architect/ |
| 3 | 周嘉诚 | 数据库设计师 | 已训练 | agents/dba/ |
| 4 | 陈启明 | 后端开发 | 已训练 | agents/backend-1/ |
| 5 | 王浩然 | 后端开发 | 已训练 | agents/backend-2/ |
| 6 | 赵文杰 | 后端开发 | 已训练 | agents/backend-3/ |
| 7 | 李思雨 | 前端开发 | 已训练 | agents/frontend-1/ |
| 8 | 周晓明 | 前端开发 | 已训练 | agents/frontend-2/ |
| 9 | 林雅婷 | 前端开发 | 已训练 | agents/frontend-3/ |
| 10 | 吴俊杰 | UCD设计师 | 已训练 | agents/ucd/ |
| 11 | 郑晓彤 | 功能测试 | 已训练 | agents/qa-functional/ |
| 12 | 孙美玲 | 性能测试 | 已训练 | agents/qa-performance/ |
| 13 | 黄志远 | 运维 | 已训练 | agents/devops/ |

## Agent 调用方式

当需要调用某个 Agent 时，直接告诉我，例如：
- "让架构师分析一下这个需求"
- "叫后端组开始开发"
- "陈启明，这个接口你来写"

我会通过 subagent 方式启动相应的团队成员协助工作。

## 协作流程

```
业务需求
↓
项目经理（秦燕）→ 拆分任务
↓
┌───────────────┬───────────────┐
│ 需求分析师    │ 架构师        │  ← 规划阶段
│ (吴雪梅)      │ (张欣怡)      │
├───────────────┴───────────────┤
│ 数据库设计师(周嘉诚)           │  ← 设计阶段
├───────────────┬───────────────┤
│ 后端组        │ 前端组        │  ← 开发阶段
│ (3人)         │ (3人)         │
├───────────────┴───────────────┤
│ 测试组(2人)  │ 运维(黄志远)   │  ← 交付阶段
└───────────────┴───────────────┘
```

## 知识共享

所有 Agent 共享团队知识库：
- `knowledge/status.md` — 共享知识入口与状态
- `knowledge/project-overview.md` — 项目背景与范围
- `knowledge/domain-glossary.md` — 统一术语
- `knowledge/workflow-playbook.md` — 协作流程说明
- `knowledge/handoff-templates.md` — 跨 Agent 交接模板
- `knowledge/risk-register.md` — 已知风险与规避策略
- `knowledge/decision-log.md` — 关键决策记录
- `knowledge/templates/` — 团队通用模板
- `knowledge/patterns/` — 最佳实践沉淀
- `knowledge/lessons/` — 经验教训
- `knowledge/glossaries/` — 术语补充与命名约定

## 个体知识

每个团队成员在 `agents/<agent>/knowledge/` 下维护最小实例画像：
- `expertise.md`
- `owned-modules.md`
- `collaboration-preferences.md`
- `delivery-style.md`
- `recent-lessons.md`

---

*创建时间: 2026-04-29*
*最近更新: 2026-05-13*
*负责人: 秦燕*
