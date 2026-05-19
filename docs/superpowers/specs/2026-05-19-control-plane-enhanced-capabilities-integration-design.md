# Control Plane 增强能力融合设计文档

> **日期**: 2026-05-19
> **目标**: 将 `aiagent_enhanced/` 中经过验证的代码智能、上下文压缩、安全会话、协作能力与 OAuth 预留能力并入 `.hermes/team/control_plane/` 主线，使增强能力既能服务 CLI，也能服务 agent 的 tool runtime 主链
> **范围**: `control_plane` 主线收敛、目录迁移、runtime/governance/handoff 增强、agent tools 暴露、CLI 补充命令；不做前端，不实现完整真实 OAuth 外部授权闭环

---

## 1. 背景与问题

仓库当前推荐主线是 `.hermes/team/control_plane/`，它已经承载统一 CLI、workflow runtime、handoff、knowledge bundle、tool runtime、session 恢复、RBAC 与审批等核心能力。与此同时，仓库根目录下存在一组独立的 `aiagent_enhanced/` 模块，内容来自 4 个开源智能体的能力整合：

- `Claude Code` 风格的代码智能
- `OpenHuman` 风格的上下文压缩和 OAuth 集成
- `OpenClaw` 风格的安全模型
- `Hermes Agent` 风格的 Kanban 与技能生命周期能力

这些增强模块本身已经形成一定的能力闭环，但当前存在三个明显问题：

1. **目录分叉**: 增强能力位于仓库根目录 `aiagent_enhanced/`，不在主线 `control_plane` 内，导致其不是当前控制平面的一部分。
2. **能力双轨**: `handoff / approval / audit / rbac / session` 等方向在 `control_plane` 已有主线实现，如果简单把增强包整块复制进去，会形成两套语义重叠的实现。
3. **接入不完整**: 即使增强能力迁入主线，如果只给 CLI 增加命令，而不把能力注册为 agent 可调用工具，那么项目里的 agent 仍然无法通过 tool runtime 直接消费这些增强能力。

当前用户目标不是单纯保留一份示例代码，而是要让这些优化后的能力真正进入项目主线，并且在使用时能实际发挥作用，同时保证整个项目改完后仍然可运行、可验证。

---

## 2. 设计目标

### 2.1 目标

本次融合设计要完成以下六件事：

1. 把 `aiagent_enhanced/` 中的能力按主线职责拆分，迁入 `.hermes/team/control_plane/` 合适目录。
2. 对与主线已重叠的能力做“增量增强”，而不是整块替换主线逻辑。
3. 让上下文压缩、安全会话、handoff 增强字段进入公共执行链路，使走 tool runtime 的 agent 自动继承这些能力。
4. 让代码审查、代码诊断、Kanban 等能力不仅可通过 CLI 使用，也能注册为 agent 可直接调用的工具。
5. 为 OAuth 保留主线内稳定模块和查看入口，但当前不接入真实第三方授权闭环。
6. 删除根目录 `aiagent_enhanced/` 独立入口，避免仓库继续维护双轨实现。

### 2.2 成功标准

- 新能力最终位于 `.hermes/team/control_plane/` 主线目录，而不是停留在根目录独立包。
- `ToolExecutor` 执行链能消费压缩和会话安全能力。
- `handoff_runtime` 能落盘 `knowledge_summary / decisions / risks / next_steps` 等增强字段。
- `build_default_tool_registry()` 中新增增强工具，agent 可像调用现有 `generate_service` 一样直接调用这些能力。
- `ROLE_TOOL_PERMISSIONS` 为相应角色放通新增工具。
- CLI 具备增强命令，但这些命令不是唯一入口。
- `OAuth` 模块处于 `deferred` 预留状态，不影响当前可运行性。
- 迁移完成后通过主线 `unittest`、`ruff` 与诊断检查，无新增结构性报错。

### 2.3 非目标

- 不实现独立可视化页面、Dashboard 前端或新的 UI 层。<mccoremem id="03g5ajs7v7yxmiy32i7wrolb5" />
- 不把 `MemoryTree` 深接入 `session_store` 持久化结构。
- 不实现完整 OAuth 回调、token 交换、第三方 API 真连接。
- 不重写整个 `control_plane` 架构，也不替换现有 workflow/provider 总调度语义。
- 不把 `Skill Curator` 一次性深接到整个角色/技能生态，只先提供主线模块与必要入口。

---

## 3. 设计约束

本次设计必须遵守以下仓库约束：

- **主线优先**: 真实落点必须在 `.hermes/team/control_plane/`。
- **兼容已存在实现**: `handoff / approval / audit / rbac / session` 已有主线骨架，只做增强，不做替换。
- **可运行优先**: 所有外部依赖增强能力都必须支持降级，例如 LSP/tree-sitter 不存在时可回落到基础审查逻辑。
- **最小破坏**: 不改现有 `dispatch/workflow/query/tool-run` 命令语义，只增加能力。
- **agent 可消费**: 设计必须把“agent 如何用上这些能力”作为一级约束，不能只停留在 CLI 层。

---

## 4. 方案对比

### 4.1 方案 A: 仅做目录归位

- 把 `aiagent_enhanced/` 文件移动到 `control_plane` 下
- 不改 runtime、registry、权限和 CLI

优点：

- 改动最小

缺点：

- 只是“放对位置”，没有真正接入主线
- agent 仍然无法直接使用大部分增强能力
- 用户目标无法满足

### 4.2 方案 B: 主链适度融合

- 拆分增强模块到 `control_plane` 合适子目录
- 将公共增强接入 `runtime/context.py`、`tools/executor.py`、`handoff_runtime.py`
- 将显式能力注册为 agent tools，同时补 CLI 命令
- 保留 OAuth 预留态

优点：

- 与现有主线边界一致
- 能同时满足“项目主线可运行”和“agent/CLI 实际用上能力”
- 回归范围可控

缺点：

- 需要修改若干主线关键入口
- 需要补一批聚焦测试

### 4.3 方案 C: 增强包替换主线同类模块

- 用 `security_model.py` 替换 governance
- 用增强 handoff 替换现有 handoff runtime
- 用增强 session 概念替换现有 session/runtime

优点：

- 表面上整合最彻底

缺点：

- 风险最高
- 很容易打破现有主线验证基线
- 不适合当前仓库阶段

### 4.4 推荐方案

选择 **方案 B: 主链适度融合**。

原因：

- 它符合仓库“主线优先、兼容层薄适配、可运行优先”的现状。
- 它能让增强能力真正进入 `tool runtime` 和 `agent tools`，而不是留在旁路脚本。
- 它避免了对已有稳定主线语义的大规模替换。

---

## 5. 总体架构

### 5.1 模块划分

增强能力迁移后的主线模块如下：

- `control_plane/intelligence/`
  - `code_intelligence.py`
  - 提供 `CodeReviewer`、LSP 诊断、定义跳转、基础结构化编辑
- `control_plane/runtime/token_compressor.py`
  - 提供 `TokenCompressor` 与 `MemoryTreeManager`
  - 作为运行时上下文压缩组件，不作为持久层模型
- `control_plane/governance/session_security.py`
  - 提供会话类型、配对、敏感工具二次门禁、路径与工具级限制
- `control_plane/collaboration/`
  - `kanban.py`
  - `skill_curator.py`
- `control_plane/integrations/oauth.py`
  - 提供 OAuth 服务注册表、本地 token 表达与 `deferred` 预留态管理
- `control_plane/tools/builtin.py`
  - 注册增强能力对应的 agent tools
- `control_plane/cli.py`
  - 增加增强能力命令入口

### 5.2 接入层次

增强能力分为三类接入：

#### 一类：公共主链增强

这些能力一旦接入，所有走 tool runtime 的 agent 都会自动继承：

- 上下文压缩
- transcript preview 压缩
- 会话安全检查
- handoff 增强字段

接入点：

- `runtime/context.py`
- `tools/executor.py`
- `handoff_runtime.py`
- `governance/tool_permissions.py`

#### 二类：agent 可直接调用工具

这些能力必须注册为 `ToolSpec`，否则 agent 无法直接用：

- `code_review`
- `code_diagnostics`
- `kanban_summary`
- `kanban_create_task`
- `list_oauth_services`

接入点：

- `tools/builtin.py`
- `governance/tool_permissions.py`

#### 三类：CLI 运维/显式命令

这些命令方便开发者或运维直接调用，但不是唯一入口：

- `code-review`
- `code-diagnostics`
- `kanban summary`
- `oauth list`

接入点：

- `cli.py`

---

## 6. 详细设计

### 6.1 代码智能

目标：

- 为主线增加基于代码文本的审查能力
- 在存在本地 LSP 时提供增强诊断
- 在无 LSP/tree-sitter 环境下仍能运行

设计要点：

- 保留 `CodeReviewer` 作为当前最稳妥的主用能力
- `LSPClient` 采用可选依赖和可选二进制策略：
  - 命令存在才启动
  - 启动失败时返回空结果，不中断主链
- `ASTCodeEditor` 保留轻量结构化编辑接口，但主线初期不把它强接到写文件主链

直接消费方式：

- CLI `code-review` / `code-diagnostics`
- agent tool `code_review` / `code_diagnostics`

### 6.2 上下文压缩与 MemoryTree

目标：

- 降低大工具输出、大知识包和长对话对工具运行时的污染
- 保留 `MemoryTree` 作为运行时分层上下文机制，但不改变现有 session 文件结构

设计要点：

- 新建 `runtime/token_compressor.py`
- `runtime/context.py` 只负责构建压缩相关元数据，不落盘完整 `MemoryTree`
- `tools/executor.py` 在 transcript 写入前压缩 `result.content`
- `knowledge_bundle` 预加载后如内容过大，可在构造预览时压缩

明确限制：

- 不修改 `SessionStore` 持久化 schema
- 不把中期/长期记忆单独写入 `tool-runtime/sessions/*.json`

### 6.3 会话安全

目标：

- 在现有 `RBAC + approval` 之外，增加更细粒度的会话级安全门禁

设计要点：

- 新建 `SessionSecurityManager`
- 支持三类 session：
  - `main`
  - `secondary`
  - `untrusted`
- `ToolExecutor` 在执行前增加一次 session security 检查
- 检查结果分为：
  - `allowed`
  - `needs_confirmation`
  - `denied`

与现有治理模块关系：

- `RBAC` 仍负责“actor 是否有此动作权限”
- `ApprovalGate` 仍负责“该动作是否需要审批”
- `SessionSecurityManager` 负责“当前 session 类型下是否允许实际执行”

这样三者职责清晰，不互相替代。

### 6.4 Handoff 增强

目标：

- 吸收增强包里的交接摘要语义，让跨 agent 交接信息更完整

新增字段：

- `knowledge_summary`
- `deliverables`
- `decisions`
- `risks`
- `next_steps`

接入方式：

- 在 `protocols/handoff.py` 扩展可选字段契约
- 在 `handoff_runtime.py` 写入和读取时补默认值

不做事项：

- 不重新设计 handoff ID、归档路径或 continuation 机制

### 6.5 协作能力

目标：

- 将 Kanban 看板与 Skill Curator 纳入主线，作为协作增强模块

设计要点：

- `KanbanBoard` 使用 SQLite 文件持久化，默认落在主线 `.hermes` 状态目录
- `SkillCurator` 支持文件存储和内存存储两种模式，测试使用 memory 模式
- 主线初期优先接：
  - `kanban_summary`
  - `kanban_create_task`
- `SkillCurator` 先作为模块和测试面落入主线，不要求首轮深接所有 agent 生命周期

### 6.6 OAuth 预留态

目标：

- 把 OAuth 集成能力保留在主线目录中，作为后续可扩展能力

设计要点：

- 模块提供服务列表、token 结构、本地状态与 `exchange_mode = "deferred"`
- CLI 和 agent tool 只能查看可用服务与当前模式
- 不实现真实 `code -> token` 外部交换

这样既能满足“保留项目内后续可接入”，又不破坏当前可运行性。

### 6.7 Agent Tools 暴露

这是本次设计的关键点。

必须把增强能力注册进 `build_default_tool_registry()`，否则它们只会存在于模块或 CLI 中，agent 无法直接使用。

新增工具建议：

- `code_review`
- `code_diagnostics`
- `kanban_summary`
- `kanban_create_task`
- `list_oauth_services`

对应角色权限放通建议：

- `architect`
  - `code_review`
  - `code_diagnostics`
  - `kanban_summary`
  - `kanban_create_task`
- `backend-dev`
  - `code_review`
  - `code_diagnostics`
  - `kanban_summary`
- `qa-functional`
  - `code_review`
  - `kanban_summary`
- `requirements-analyst`
  - `kanban_summary`

### 6.8 CLI 暴露

CLI 仍然需要保留显式入口，方便本地使用和验证。

新增命令：

- `code-review`
- `code-diagnostics`
- `kanban summary`
- `oauth list`

命令职责：

- 提供人可直接执行的能力入口
- 方便开发期验证 agent tool 底层模块
- 不与 agent tool 形成双轨语义，底层应复用同一能力模块

---

## 7. 数据流变化

### 7.1 当前 tool runtime

```text
tool-run
-> build_tool_execution_context()
-> build_default_tool_registry()
-> ToolExecutor.execute_many()
-> RBAC / approval / preload knowledge
-> tool handler
-> transcript
```

### 7.2 目标 tool runtime

```text
tool-run / agent tool call
-> build_tool_execution_context()
-> 初始化压缩元数据与 session security policy
-> build_default_tool_registry()
-> ToolExecutor.execute_many()
-> RBAC
-> approval
-> session security
-> preload knowledge
-> tool handler
-> 压缩 transcript preview
-> audit / transcript / session snapshot
```

### 7.3 目标 handoff

```text
workflow/handoff emit
-> protocols.handoff normalize optional fields
-> handoff_runtime.record_handoff()
-> 记录 summary / decisions / risks / next_steps
-> query / read_knowledge / consumer 继续复用原逻辑
```

---

## 8. 文件级改动

### 8.1 新增文件

- `.hermes/team/control_plane/intelligence/__init__.py`
- `.hermes/team/control_plane/intelligence/code_intelligence.py`
- `.hermes/team/control_plane/runtime/token_compressor.py`
- `.hermes/team/control_plane/governance/session_security.py`
- `.hermes/team/control_plane/collaboration/__init__.py`
- `.hermes/team/control_plane/collaboration/kanban.py`
- `.hermes/team/control_plane/collaboration/skill_curator.py`
- `.hermes/team/control_plane/integrations/__init__.py`
- `.hermes/team/control_plane/integrations/oauth.py`
- `tests/control_plane/test_code_intelligence.py`
- `tests/control_plane/test_token_compressor.py`
- `tests/control_plane/test_session_security.py`
- `tests/control_plane/test_collaboration.py`
- `tests/control_plane/test_tool_registry.py`
- `tests/control_plane/test_cli_enhanced.py`

### 8.2 修改文件

- `.hermes/team/control_plane/__init__.py`
- `.hermes/team/control_plane/runtime/context.py`
- `.hermes/team/control_plane/tools/spec.py`
- `.hermes/team/control_plane/tools/executor.py`
- `.hermes/team/control_plane/tools/builtin.py`
- `.hermes/team/control_plane/tools/__init__.py`
- `.hermes/team/control_plane/governance/tool_permissions.py`
- `.hermes/team/control_plane/governance/audit.py`
- `.hermes/team/control_plane/protocols/handoff.py`
- `.hermes/team/control_plane/handoff_runtime.py`
- `.hermes/team/control_plane/cli.py`
- `.hermes/team/control_plane/README.md`

### 8.3 删除文件

- `aiagent_enhanced/__init__.py`
- `aiagent_enhanced/code_intelligence.py`
- `aiagent_enhanced/token_compressor.py`
- `aiagent_enhanced/security_model.py`
- `aiagent_enhanced/oauth_integrations.py`
- `aiagent_enhanced/collaboration.py`
- `aiagent_enhanced/tests/test_all.py`

---

## 9. 风险与缓解

### 9.1 风险：外部依赖导致主链不稳

场景：

- 本机没有 `pylsp`
- 没有 `typescript-language-server`
- 没有 `tree_sitter`

缓解：

- 所有代码智能增强走可选依赖策略
- 主线可运行性以 `CodeReviewer` 为保底

### 9.2 风险：治理链路重复判断过多

场景：

- `RBAC`、`approval`、`session security` 都在做拦截

缓解：

- 明确职责边界
- 错误码分层输出
- 测试分别覆盖三层拦截

### 9.3 风险：agent tools 与 CLI 逻辑重复

场景：

- CLI 单独实现一套逻辑，tool runtime 又有一套逻辑

缓解：

- CLI 优先复用能力模块
- agent tool 与 CLI 使用同一底层类

### 9.4 风险：删除旧目录后仍有隐式引用

场景：

- 测试或导出路径仍引用 `aiagent_enhanced`

缓解：

- 新增“旧目录已移除”断言测试
- 全量回归和 grep 检查旧路径引用

---

## 10. 测试策略

测试分四层：

1. **模块测试**
   - `CodeReviewer`
   - `TokenCompressor`
   - `SessionSecurityManager`
   - `KanbanBoard`
   - `SkillCurator`
   - `OAuthManager`

2. **接线测试**
   - `ToolExecutor` 接入压缩和安全检查
   - `handoff_runtime` 保留增强字段
   - `tool registry` 暴露增强能力

3. **CLI 测试**
   - `code-review`
   - `kanban summary`
   - `oauth list`

4. **主线回归**
   - `python -m unittest discover -s tests/control_plane -p "test_*.py" -v`
   - `python -m ruff check .hermes/team/control_plane tests/control_plane`

---

## 11. 实施顺序

建议按以下顺序落地：

1. 迁移文件与新目录
2. 接入公共主链增强
3. 增强 handoff 与协作模块
4. 注册 agent tools
5. 增加 CLI 命令
6. 删除旧目录
7. 跑测试、ruff、诊断检查

---

## 12. 结论

本次融合不是把 `aiagent_enhanced/` 原样平移到 `control_plane`，而是将其中真正有价值的能力按主线边界拆分并接入：

- **主链公共增强**: 压缩、安全会话、handoff 增强
- **agent 可直接调用**: 代码审查、代码诊断、Kanban、OAuth 服务查看
- **CLI 可直接使用**: 与 agent tool 对应的显式命令
- **后续可扩展能力**: OAuth 真连接、Skill Curator 深接生态

这样可以同时满足四个要求：

1. 增强能力进入当前推荐主线
2. agent 在项目内真实用上这些能力
3. CLI 具备直接验证入口
4. 项目优化后仍保持可运行、可验证

