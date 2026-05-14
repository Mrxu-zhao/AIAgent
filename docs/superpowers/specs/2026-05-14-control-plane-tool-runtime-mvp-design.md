# Control Plane Tool Runtime MVP 设计文档

## 1. 背景

当前仓库的主线已经明确为仓库级 `control_plane`，现有能力覆盖统一 CLI、任务状态仓、CAS 保护、共享 batch runner、Provider 注册与 workflow runtime，但执行抽象仍停留在“按 backend 组装 dispatch command”的粒度。`TaskRouter` 已经能输出任务画像、backend recommendation 与 knowledge recommendation，可这些结构化信息还没有接到一个细粒度、可复用的工具运行时里。<mccoremem id="03g415w5w3367klgad5cg68tb|01KRDKFS2XFQ1K5105VDNMG5FX|01KRG0XH9KSY572B133JZ1JVZM" />

Claude Code 源码中最值得借鉴的部分，不是其 TUI 或 Node 实现细节，而是统一 `Tool` 抽象、串并行工具调度、结果顺序回放与会话 transcript 的运行时设计。本轮目标是在当前 Python 控制平面中落一个最小可用闭环，为后续继续接入更丰富的 tool、resume 和多 agent 生命周期打基础。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K|01KRHWYAYWGCHRC3HFKW9WSY95" />

## 2. 目标与非目标

### 2.1 目标

- 在 `.hermes/team/control_plane` 下新增最小 `tools/` 与 `runtime/` 模块，建立 Python 版统一工具协议。
- 新增 `ToolExecutor`，支持只读并发安全工具并行执行、写工具串行执行，以及结果按请求顺序回放。
- 新增最小 transcript 落盘能力，记录工具调用输入、输出、agent、backend 与知识包摘要。
- 将现有 `Hermes/OpenClaw` adapter 包装为 tool handler，而不是重写 backend 层。
- 新增一个可直接运行的 CLI 子命令，验证 `task_router -> runtime context -> tool registry -> tool executor -> transcript` 闭环。
- 通过 focused `unittest` 覆盖关键行为，并保持现有测试风格。

### 2.2 非目标

- 本轮不实现完整 resume、fork、background session。
- 本轮不实现 Claude Code 风格的完整权限系统与 hook 体系。
- 本轮不引入 TUI、stream-json 或插件市场能力。
- 本轮不替换现有 `dispatch/query/workflow/control-plane-run` 主路径，只新增最小 runtime 入口。

## 3. 方案比较

### 方案 A：最小 Tool Runtime MVP

新增独立的 `tools/` 与 `runtime/` 模块，保留现有 `executor.py`、`adapters.py` 与 CLI 行为，在控制平面之上补一层细粒度 tool runtime。

优点：

- 改动集中，边界清晰。
- 可直接复用现有 backend、store 与 router。
- 后续继续扩工具、权限和 transcript 不需要推翻本轮实现。

缺点：

- 会在短期内并存“任务执行器”和“工具执行器”两套执行概念。
- 新 CLI 入口需要额外维护测试。

### 方案 B：把 Tool 概念塞进现有 `executor.py`

直接扩展 `ControlPlaneExecutor`，让其同时负责 task 与 tool 的执行。

优点：

- 改文件少。
- 对外概念数量更少。

缺点：

- `executor.py` 职责继续膨胀。
- tool runtime 会被 task batch 语义绑死，不利于后续演进。

### 方案 C：完整会话运行时先行

一次性引入 transcript、resume、permission mode、tool runtime 与 session state。

优点：

- 目标形态最接近 Claude Code。

缺点：

- 范围明显超出一次对话可稳定交付的上限。
- 会同时触碰过多现有入口与状态模型。

### 方案选择

本设计选择 **方案 A：最小 Tool Runtime MVP**。

理由：

- 用户明确要求本轮在一次对话中直接落地可运行闭环。
- 当前仓库最缺的是“细粒度工具运行时”而不是“再造一层更大的会话框架”。
- 方案 A 能在不破坏现有控制平面主线的前提下，最大化引入 Claude Code 可迁移的运行时设计。

## 4. 设计概览

本轮新增两层小模块：

1. **`tools/`**
   - 统一工具协议。
   - registry。
   - 串并行执行器。
   - 最小工具集。
   - transcript 落盘。

2. **`runtime/`**
   - 执行上下文装配。
   - knowledge bundle 规则装配。

完整链路如下：

1. CLI `tool-run` 接收任务与工具请求。
2. `TaskRouter` 分析任务意图并产出 backend/knowledge recommendation。
3. `runtime/context.py` 构造 `ToolExecutionContext`。
4. `tools/registry.py` 解析请求的工具。
5. `tools/executor.py` 执行工具并按顺序返回结果。
6. `tools/transcript.py` 将调用记录写入 JSONL。

## 5. 详细设计

### 5.1 工具协议

新增 `ToolSpec`、`ToolResult` 与 `ToolExecutionContext`。

- `ToolSpec`
  - `name`
  - `description`
  - `input_schema`
  - `is_read_only`
  - `is_concurrency_safe`
  - `handler`
- `ToolResult`
  - `ok`
  - `content`
  - `structured_data`
  - `error`
  - `artifacts`
- `ToolExecutionContext`
  - `task_id`
  - `agent_id`
  - `backend`
  - `cwd`
  - `intent`
  - `knowledge_bundle`

该协议只覆盖运行时最核心的执行与结果表达，本轮不引入复杂 UI 渲染、auto-classifier 或 permission hooks。

### 5.2 ToolExecutor

`ToolExecutor` 提供 `execute_many()`：

- 对 `is_read_only=True` 且 `is_concurrency_safe=True` 的工具并发执行。
- 对其他工具串行执行。
- 无论执行方式如何，结果都按原请求顺序回放。
- 每个工具执行后都写入 transcript。

并发策略采用最小安全原则：

- 只要工具不是只读，必定串行。
- 只要工具未显式声明并发安全，也必定串行。

### 5.3 最小工具集

首批只落 4 个工具：

- `dispatch_task`
  - 包装 `HermesExecutorAdapter` / `OpenClawExecutorAdapter`
  - 返回 command 与 backend 信息
- `query_workflow`
  - 读取 `WorkflowRunStore` snapshot 与 events
- `query_handoff`
  - 读取 `HandoffRunStore` records
- `read_knowledge`
  - 根据 `knowledge_bundle` 读取存在的知识文件并返回内容

本轮不实现通用 shell/file edit/search 工具，以免范围失控。

### 5.4 Runtime Context 与规则装配

`runtime/context.py` 负责：

- 调用 `TaskRouter.analyze_task_intent()`
- 调用 `TaskRouter.select_best_agent()`
- 获取 backend recommendation 与 knowledge recommendation
- 生成 `ToolExecutionContext`

`runtime/rules.py` 负责：

- 按 `team -> role -> instance` 顺序收集 knowledge 路径
- 仅返回存在的文件
- 形成稳定的 `knowledge_bundle`

此处直接复用 `TaskRouter` 现有 recommendation 结构，避免重复定义规则。

### 5.5 Transcript

新增 JSONL transcript 文件：

- 默认存放到 `state_dir/tool-runtime/tool-transcript.jsonl`
- 每条记录至少包含：
  - `task_id`
  - `tool_name`
  - `agent_id`
  - `backend`
  - `input`
  - `ok`
  - `error`
  - `content_preview`
  - `artifacts`
  - `knowledge_paths`
  - `timestamp`

采用 preview 而不是全量大输出，可避免日志无界膨胀。

### 5.6 CLI 入口

在现有统一 CLI 中新增 `tool-run`：

- 参数：
  - `tool`
  - `task`
  - `--agent`
  - `--backend`
  - `--actor`
- 行为：
  - 构造 runtime context
  - 注册默认工具
  - 执行单个工具请求
  - 以 JSON 输出结果
  - 写审计日志

该入口只验证最小闭环，不替代已有子命令。

## 6. 文件落点

- 新增 `\.hermes/team/control_plane/tools/spec.py`
- 新增 `\.hermes/team/control_plane/tools/registry.py`
- 新增 `\.hermes/team/control_plane/tools/executor.py`
- 新增 `\.hermes/team/control_plane/tools/builtin.py`
- 新增 `\.hermes/team/control_plane/tools/transcript.py`
- 新增 `\.hermes/team/control_plane/tools/__init__.py`
- 新增 `\.hermes/team/control_plane/runtime/context.py`
- 新增 `\.hermes/team/control_plane/runtime/rules.py`
- 新增 `\.hermes/team/control_plane/runtime/__init__.py`
- 修改 `\.hermes/team/control_plane/cli.py`
- 新增 `tests/control_plane/test_tool_executor.py`
- 新增 `tests/control_plane/test_tool_transcript.py`
- 新增 `tests/control_plane/test_tool_cli.py`

## 7. 测试策略

本轮坚持最小 TDD：

- 先写 `ToolExecutor` 失败测试：
  - 只读并发安全工具允许并发执行。
  - 写工具保持串行。
  - 返回顺序与请求顺序一致。
- 再写 transcript 失败测试：
  - 工具执行后会落盘 JSONL 记录。
- 再写 CLI 失败测试：
  - `tool-run` 能构造上下文并执行单个工具。

测试不追求覆盖所有工具边界，只锁住本轮新增运行时的关键不变量。

## 8. 风险与缓解

- **风险：与现有 `executor.py` 职责混淆**
  - 缓解：新模块命名统一为 `Tool*`，避免改动现有 batch executor 行为。
- **风险：知识路径不存在导致工具失败**
  - 缓解：`runtime/rules.py` 只返回存在路径，缺失时返回空列表而非报错。
- **风险：CLI 入口改动影响现有命令**
  - 缓解：仅新增子命令，并补 parser 与集成测试。
- **风险：OpenClaw 仍是 dry-run**
  - 缓解：`dispatch_task` 只包装现有 provider 行为，不对 backend 语义做额外承诺。<mccoremem id="03g49kiy4yk240dci3220p7eu" />

## 9. 验收标准

- 新增 `tool-run` CLI 子命令并可直接运行。
- 最少 1 个写工具与 1 个读工具可通过统一 `ToolExecutor` 执行。
- transcript JSONL 成功落盘且包含关键字段。
- 新增 focused tests 全部通过。
- 现有关键 `control_plane` 测试不被破坏。

## 10. 实施后更新（2026-05-14）

实际落地相较原始 MVP 设计有以下扩展：

- `runtime/rules.py` 新增 `preload_knowledge_bundle()`，tool runtime 从“只解析路径”升级为“执行前预加载知识内容”。
- `ToolExecutor` 已在权限与审批检查通过后自动预加载知识包，tool handler 可以直接消费预加载内容。
- `read_knowledge` 已支持使用预加载缓存，说明 tool runtime 不再只是 command 装配层，而是开始承担轻量上下文准备职责。
- 统一 CLI 已把知识包和知识反馈摘要延伸到 `query workflow` / `query handoff`，说明 MVP 已与 runtime store、handoff store 和 workflow 主线打通。
- 当前代码状态表明，本设计中的最小 runtime 已经成为控制平面知识链路的基础设施，而不是独立实验模块。
