# 仓库地图

## 关键目录
- `.hermes/team/调度框架/`：当前团队调度框架核心。
- `.hermes/team/control_plane/`：仓库级控制平面实现。
- `.hermes/profiles/`：运行时 agent profile。
- `.hermes/agents/`：角色原型及领域知识。
- `.hermes/team/agents/`：团队实例成员资料。
- `docs/superpowers/specs/`：设计文档。
- `docs/superpowers/plans/`：实施计划文档。
- `tests/control_plane/`：控制平面与调度能力回归测试。

## 改动建议
- 先判断需求属于团队层、角色层还是实例层，再决定知识落点。
- 修改 `.hermes/team/调度框架/` 时优先关注 workflow、router、handoff 与 executor 的边界。
- 需要补新知识时，优先新增标准入口文件，不直接打散旧知识文件。

## 高风险区域
- workflow 与 control plane 的接口边界。
- backend recommendation 与真实执行绑定。
- 多 agent 协作时的 handoff 结构一致性。
