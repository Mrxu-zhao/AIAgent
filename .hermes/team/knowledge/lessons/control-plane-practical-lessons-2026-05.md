# Control Plane 实战经验（2026-05）

---
owner: control-plane
last_reviewed: 2026-05-18
source: children-literacy-game
scope: team
---

## 适用范围
- 使用 `workflow --workflow-file ... --context-file ...` 启动文档驱动型项目。
- 使用 `dispatch --execute --wait` 做脚本化执行与复验。

## 经验 1：`context-file` 不能默认假设为 JSON
- 场景：项目上下文常以 `project-context.md` 或 `README.md` 形式存在。
- 结论：CLI 应区分结构化上下文和文本上下文；文本文件应包装到 `project_context`，而不是直接 `json.loads()`。
- 适用前提：工作流入口允许从现有项目文档直接启动。

## 经验 2：自定义 workflow 文件优先尊重仓库相对路径
- 场景：workflow 定义放在 `.hermes/team/调度框架/workflows/` 等非默认目录。
- 结论：若调用方传入的相对路径在当前仓库内已经存在，加载器应直接使用该路径，不要再重定基到默认 workflow 目录。
- 适用前提：仓库同时存在默认 workflow 目录和项目级自定义 workflow。

## 经验 3：终态版本冲突需要做完成态复核
- 场景：并发写入下，任务完成事件可能已由其他写入方成功落盘。
- 结论：若终态写入时报 `VERSION_CONFLICT`，应先读取最新 snapshot；当状态已是 `done` 时，应按成功返回，而不是直接报失败。
- 适用前提：状态存储采用乐观锁版本控制，且 CLI 需要稳定支持自动化复验。

## 推荐动作
- 新增项目模板时，默认提供 markdown 上下文文件示例。
- 自定义 workflow 的调用说明中明确区分“纯文件名”与“仓库相对路径”。
- 对并发敏感的终态写入统一采用“先写入，冲突后复核”的收敛策略。
