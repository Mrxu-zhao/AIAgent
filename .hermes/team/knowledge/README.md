# 团队公共知识库

## 作用
- 为所有 agent 提供共享的项目背景、术语、仓库地图、协作流程和交接模板。
- 作为 `~/.hermes/team/knowledge/` 的真实落盘目录，兼容现有 skill 文档中的读取约定。
- 为后续 `TaskRouter`、`WorkflowEngine` 和 handoff 推荐知识包提供稳定入口。

## 装载顺序
1. 全局 `SOUL.md`
2. 团队公共知识
3. 角色知识
4. 实例知识
5. memories
6. 当前任务 handoff/context

## 目录说明
- `status.md`：团队知识库状态与入口索引。
- `project-overview.md`：项目目标、范围与成功标准。
- `domain-glossary.md`：统一术语与别名。
- `architecture-map.md`：关键模块与数据流。
- `repo-map.md`：仓库入口、高风险区域、改动注意事项。
- `workflow-playbook.md`：从需求到交付的协作方式。
- `handoff-templates.md`：跨 agent 交接模板。
- `risk-register.md`：已知风险与规避策略。
- `decision-log.md`：关键决策记录。
- `templates/`、`patterns/`、`lessons/`、`glossaries/`：兼容旧约定的共享目录。

## 治理规则
- 负责人：团队 owner
- 更新日期：2026-05-13
- 仅沉淀稳定事实、重复问题和已验证最佳实践。
- 一次性任务过程不直接写入团队层。
