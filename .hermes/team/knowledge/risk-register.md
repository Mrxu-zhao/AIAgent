---
owner: control-plane
last_reviewed: 2026-05-18
source: workflow-feedback
---

# 风险登记册

| 风险 | 影响范围 | 预警信号 | 缓解策略 |
|------|----------|----------|----------|
| workflow 与真实执行语义脱节 | 调度、执行、handoff | recommendation 与 executor 不一致 | 优先补齐结构化上下文与执行绑定 |
| 多实例角色分工不稳定 | backend/frontend 协作 | 任务反复改派、上下文流失 | 用实例画像知识补齐专长与默认分工 |
| 团队知识长期缺失 | 全链路协作 | 相同背景被反复解释 | 建立团队层真实目录并持续维护 |
| 风险信息停留在对话中 | 架构、测试、交付 | 相同问题重复出现 | 每次任务收尾同步更新风险登记册 |
| 文档型项目上下文被强制按 JSON 解析 | workflow 启动、需求型项目 | `project-context.md` 触发 `JSONDecodeError` | `context-file` 对 JSON 走结构化解析，对其他文本走 `project_context` 包装 |
| 仓库内自定义 workflow 路径被错误重定基 | 自定义 workflow 启动、项目模板 | `workflow definition not found`，且路径被拼成 `.hermes/workflows/.hermes/...` | 已存在的相对路径直接使用，仅在纯文件名场景回退默认 workflow 目录 |
| 并发完成写入导致终态误报失败 | dispatch、CI、自动复验 | `stderr` 出现 `snapshot version mismatch`，但 `final_status=done` | 终态写入冲突时先读取最新 snapshot，若已 `done` 则按成功处理 |

## 使用规则
- 只登记值得跨任务复用的风险。
- 风险需要有明确触发条件和缓解动作。
- 问题解决后可补充“关闭条件”，但保留历史经验。
| design-risk | workflow: wf-collab | 见工作流结果与 step_contexts | 在交付前复核对应步骤的风险缓解动作 |
| review-risk | workflow: wf-collab | 见工作流结果与 step_contexts | 在交付前复核对应步骤的风险缓解动作 |
