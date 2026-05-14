# Control Plane Session、Tools 与最小权限模型设计文档

## 1. 背景

仓库级 `control_plane` 已经有最小工具运行时 MVP：统一 `ToolSpec`、`ToolExecutor`、默认工具注册表、knowledge bundle 装配以及 `tool-run` CLI 入口都已落地。但这层运行时仍缺三块决定上限的核心能力：

- 没有真正的 session/resume 语义，只有工具执行后的一次性 transcript。
- 工具集合仍偏窄，缺少足够高频的原子工具来验证 runtime 的复用价值。
- 权限模型只有 CLI 层零散 RBAC 骨架，尚未进入 tool runtime，也没有最小审批拦截。

当前仓库同时已经具备几个可复用基础：`WorkflowRunStore`/`TaskStore` 的快照与事件模型、`PersistentMessageBus` 的恢复语义、`TaskRouter` 的任务画像与知识推荐，以及 `sensitive_actions + RBACPolicy + ApprovalGate` 这套治理骨架。<mccoremem id="03g415w5w3367klgad5cg68tb|01KRDCERG2AM5X3EVDFZMDDV2G|01KRG0XH9KSY572B133JZ1JVZM" />

本轮目标是在现有 Python 控制平面内，沿着刚落地的 tool runtime MVP 继续升级一轮：补 session/resume、扩高频工具、把最小权限模型真正接进工具执行链。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K|01KRHWYAYWGCHRC3HFKW9WSY95" />

## 2. 目标与非目标

### 2.1 目标

- 新增 session store 与 resume coordinator，让 `tool-run` 能基于 session id 持久化和恢复最近一次工具运行上下文。
- 将当前 transcript 从“仅工具日志”升级为“session + tool transcript”双层结构。
- 新增 3 到 5 个高频原子工具，优先覆盖路由、知识发现、状态总览与文件读取。
- 为工具协议增加最小权限语义，并把 RBAC/敏感动作/审批检查接入 `ToolExecutor`。
- 新增相应 CLI 子命令或参数，验证创建 session、resume session 与受限工具拦截都可运行。
- 使用 focused `unittest` 覆盖恢复、权限与新增工具行为。

### 2.2 非目标

- 本轮不实现 Claude Code 级别的完整多 agent sidechain transcript、fork session 或 background task。
- 本轮不引入复杂 hook、自动权限分类器或外部审批系统。
- 本轮不把兼容层脚本 `team-dispatch.sh`、`team-tmux.sh` 全量纳入统一权限控制。
- 本轮不实现通用 shell 执行工具，避免引入过大的安全面。

## 3. 方案比较

### 方案 A：只补 session/resume

只把 transcript 升级成 session snapshot，并提供 resume CLI。

优点：

- 范围最小。
- 可以尽快把“可恢复”补上。

缺点：

- 工具仍不够实用，无法验证 runtime 的长期价值。
- 权限仍在 tool runtime 之外，恢复后照样没有治理闭环。

### 方案 B：只扩工具和权限

继续增加高频工具，并为工具加权限检查，但不做 session/resume。

优点：

- 用户体感提升更直接。
- 能尽快形成更丰富的 builtin tool 池。

缺点：

- 仍然缺恢复语义，工具执行历史不能被稳定接续。
- 后续接多 agent 生命周期时会再次返工 transcript 和状态层。

### 方案 C：session/resume + 高频工具 + 最小权限模型闭环

同时补三块，但只做最小闭环：单 session snapshot、最近状态恢复、4 到 5 个高频工具、基于 tool action 的 RBAC 与敏感动作审批拦截。

优点：

- 能把本轮已经有的 tool runtime 真正推进到“可长期演进”的阶段。
- 范围仍受控，不需要一次性实现完整会话系统。
- 与当前仓库已有 store、router、governance 骨架高度贴合。

缺点：

- 改动面会同时涉及 `tools/`、`runtime/`、`governance/`、`cli.py` 与测试。

### 方案选择

本设计选择 **方案 C：session/resume + 高频工具 + 最小权限模型闭环**。

理由：

- 用户已经明确要求直接按这条路线完整落地。
- 当前 runtime 真正的短板恰好就是这三块，分开做会降低本轮升级收益。
- 现有仓库已经有足够多可复用骨架，可以把范围压在一个稳定的 MVP 闭环内。

## 4. 设计概览

本轮在上一轮 `tool runtime MVP` 之上新增三层能力：

1. **Session Layer**
   - `session snapshot`
   - `resume coordinator`
   - `session transcript index`

2. **Expanded Builtin Tools**
   - `route_task`
   - `find_knowledge_files`
   - `read_file`
   - `query_bus_status`
   - 保留并整合已有 4 个工具

3. **Permission Layer**
   - 工具级 action 定义
   - RBAC 检查
   - 敏感动作审批检查
   - 权限结果审计

完整链路变为：

1. CLI 创建或恢复 session。
2. `SessionStore` 读写当前 session snapshot。
3. `runtime/context.py` 从 task/router/session 组装执行上下文。
4. `ToolRegistry` 解析工具并提供 action 元信息。
5. `ToolExecutor` 在执行前做权限与审批检查。
6. 工具执行结果同时写入 `tool transcript` 与 `session snapshot`。
7. 下次 `resume` 时从 session snapshot 恢复最近上下文与工具历史摘要。

## 5. 详细设计

### 5.1 Session / Resume

新增 `SessionSnapshot` 与 `SessionStore`。

- `SessionSnapshot`
  - `session_id`
  - `task`
  - `agent_id`
  - `backend`
  - `status`
  - `created_at`
  - `updated_at`
  - `last_tool_name`
  - `last_tool_result`
  - `knowledge_bundle`
  - `intent`
  - `history`

- `SessionStore`
  - 按 `state_dir/tool-runtime/sessions/<session_id>.json` 存储 snapshot
  - 提供 `create_session()`、`read_session()`、`update_session()`、`list_sessions()`

恢复策略：

- 本轮只支持“恢复最近状态”，不恢复线程内执行中的中间 future。
- `resume` 读取 snapshot 后，重新构造 `ToolExecutionContext`。
- `history` 只保留精简条目：
  - `tool_name`
  - `ok`
  - `content_preview`
  - `timestamp`

CLI 行为：

- `tool-run` 新增 `--session-id`
- `tool-run` 新增 `--resume`
- 未传 `--session-id` 时自动创建 session id
- `--resume` 要求对应 session 存在，否则报错

### 5.2 高频工具扩展

在现有 `dispatch_task`、`query_workflow`、`query_handoff`、`read_knowledge` 基础上补 4 个高频工具：

- `route_task`
  - 使用 `TaskRouter.route_task()`
  - 返回 `agent_id`、`task_id`、`intent`、`routing_reason`
- `find_knowledge_files`
  - 直接返回 knowledge bundle 中的相对路径与绝对路径
  - 作用是把“知识发现”与“知识读取”拆开
- `read_file`
  - 仅允许读取仓库工作区内文件
  - 返回文件内容与路径
- `query_bus_status`
  - 复用 `PersistentMessageBus.stats()`
  - 返回 `history/pending/unacked` 计数

工具总数会变成 8 个，仍然保持都在 `builtin.py` 中集中定义，避免本轮过早拆散。

### 5.3 最小权限模型

扩展 `ToolSpec`，新增权限相关字段：

- `action`
- `requires_approval`
- `is_sensitive`

规则：

- 只读查询工具：
  - `query.*`、`tool.read.*`
  - 允许 `viewer/operator/admin`
- 路由和知识发现工具：
  - `tool.route`
  - 允许 `operator/admin`
- dispatch 构造工具：
  - `tool.dispatch`
  - 允许 `operator/admin`
- 若 backend 为 `openclaw` 且非 dry-run，则映射为敏感动作 `provider.openclaw.live`
- 若工具 `requires_approval=True`，则额外通过 `ApprovalGate.requires_approval(action)` 判断并返回拒绝结果

实现位置：

- 新增 `governance/tool_permissions.py`
  - 负责 `resolve_tool_action()`、`check_tool_permission()`、`check_tool_approval()`
- `ToolExecutor._execute_one()` 在真正调用 handler 前执行权限校验
- 权限拒绝不抛未处理异常，而返回 `ToolResult.error_result()`

### 5.4 审计与 transcript

本轮新增两类记录：

- `tool transcript`
  - 继续记录每次工具调用
  - 额外补 `session_id`、`action`、`permission_outcome`

- `session snapshot`
  - 记录最近一次执行后的 compact 状态

对权限拒绝也要写 transcript 和审计：

- transcript 记录 `ok=False`
- `permission_outcome=denied` 或 `approval_required`
- `AuditLogger` 记录 `tool-run` 事件时补充 `session_id`、`tool`、`action`

### 5.5 CLI 入口

继续使用现有 `tool-run`，但扩展参数：

- `tool-run <tool> <task>`
- `--agent`
- `--backend`
- `--actor`
- `--session-id`
- `--resume`

另外新增一个查询入口：

- `tool-session`
  - `tool-session list`
  - `tool-session get --session-id <id>`

这样可以直接验证 session snapshot 的读写，而不依赖查看底层 JSON 文件。

## 6. 文件落点

- 新增 `\.hermes/team/control_plane\tools\session_store.py`
- 修改 `\.hermes/team/control_plane\tools\spec.py`
- 修改 `\.hermes/team/control_plane\tools\executor.py`
- 修改 `\.hermes/team/control_plane\tools\transcript.py`
- 修改 `\.hermes/team/control_plane\tools\builtin.py`
- 视情况修改 `\.hermes/team/control_plane\tools\registry.py`
- 新增 `\.hermes/team/control_plane\governance\tool_permissions.py`
- 修改 `\.hermes/team/control_plane\governance\rbac.py`
- 修改 `\.hermes/team/control_plane\cli.py`
- 新增 `tests\control_plane\test_tool_session_store.py`
- 修改 `tests\control_plane\test_tool_executor.py`
- 修改 `tests\control_plane\test_tool_transcript.py`
- 修改 `tests\control_plane\test_tool_cli.py`

## 7. 测试策略

本轮坚持最小 TDD，测试按三段推进：

1. **Session / Resume**
   - 创建 session 后写 snapshot
   - `--resume` 能恢复上一次 agent/backend/task
   - 不存在的 session 恢复时报错

2. **高频工具**
   - `route_task` 返回结构化路由结果
   - `find_knowledge_files` 返回稳定路径集合
   - `read_file` 仅允许仓库内文件
   - `query_bus_status` 返回 bus 统计

3. **最小权限模型**
   - `viewer` 可运行只读工具
   - `viewer` 不可运行 `route_task/dispatch_task`
   - `operator` 可运行 `route_task`
   - 敏感动作触发审批要求时返回拒绝结果

## 8. 风险与缓解

- **风险：session snapshot 与 transcript 重复记录**
  - 缓解：snapshot 只保存 compact 状态；完整调用历史仍以 transcript 为准。
- **风险：权限模型与现有 CLI RBAC 冲突**
  - 缓解：保留 CLI 既有校验；tool runtime 新增的是 tool 级第二层校验。
- **风险：`read_file` 暴露仓库外路径**
  - 缓解：严格校验解析后路径必须位于仓库根目录下。
- **风险：`openclaw` live 动作与 dry-run 混淆**
  - 缓解：动作解析明确区分 `dry-run` 与 `live`，只有 live 命中敏感动作。<mccoremem id="03g49kiy4yk240dci3220p7eu" />

## 9. 验收标准

- `tool-run` 支持创建 session 与 `--resume` 恢复。
- `tool-session list/get` 可查询 session snapshot。
- 工具池扩展到至少 8 个，其中新增 4 个高频工具。
- 工具执行前有稳定的 RBAC/审批检查。
- 新增与修改测试全部通过。
- 现有关键 `control_plane` CLI、executor、adapters 测试不被破坏。
