# Agent 能力增强一期设计文档

## 1. 背景

当前仓库的仓库级控制平面已经具备最小可运行闭环：任务状态仓、CAS 保护、共享 runner、统一 CLI、基础 metrics、provider registry 与 workflow runtime 都已落地。<mccoremem id="03g415w5w3367klgad5cg68tb|01KRDCERG2AM5X3EVDFZMDDV2G|01KRDKFS2XFQ1K5105VDNMG5FX" />

但如果把目标从“框架可跑”提升到“agent 能力可用”，当前上层仍有三个明显短板：

- `TaskRouter` 主要依赖关键词命中与静态负载分数，无法识别任务中的显式角色、协作意图与上下文约束。
- `WorkflowEngine` 会执行步骤，但不会把步骤输出规范化为后续步骤可消费的结构化上下文。
- `handoff` 协议只校验最小字段，无法稳定表达前一步产物、待确认事项、推荐接手角色与执行后端切换理由。

用户已明确下一阶段采用“上层能力先行、底座闭环随后补齐”的推进顺序，因此本轮只做最小上层闭环：让路由更懂任务，让工作流真正传递协作上下文，并让 handoff 成为可复用的跨 agent 交接载荷。

## 2. 目标与非目标

### 2.1 目标

- 为 `TaskRouter` 增加“任务意图画像”，让路由决策不仅看关键词，还看显式角色、协作信号、风险等级与交付物类型。
- 为 `WorkflowEngine` 增加“结构化步骤上下文”，让每个步骤都能沉淀可供后续步骤消费的摘要、产物、风险与待确认项。
- 扩展 `HandoffPayload`，让 Hermes/OpenClaw 或不同 agent 之间的交接信息可序列化、可校验、可追踪。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />
- 保持 Python 原生工程口径，只在现有 `.hermes/team/调度框架` 与 `.hermes/team/control_plane` 模块上增量演进，不引入新的外部服务依赖。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />
- 用单元测试锁住新增能力，并维持现有控制平面测试口径。

### 2.2 非目标

- 本轮不实现真实 LLM 语义分类器，也不接外部 embedding 或向量检索。
- 本轮不实现 workflow checkpoint/resume/audit 全闭环，只增强步骤间上下文传递。
- 本轮不重构 provider 执行链路，不新增新的执行后端。
- 本轮不引入复杂的策略学习或基于历史数据的自动调参。

## 3. 方案比较

### 方案 A：只增强路由

只改 `TaskRouter`，加入更细粒度的分类和 agent 选择逻辑，`WorkflowEngine` 与 `handoff` 保持现状。

优点：

- 改动面最小。
- 见效快，派单精度可直接提升。

缺点：

- 多 agent 协作质量仍受限于“上下文靠字符串拼接”。
- `workflow` 和 `handoff` 仍会把高质量路由结果浪费掉。

### 方案 B：只增强工作流上下文

只改 `WorkflowEngine` 与 `handoff`，让步骤产出结构化，但路由仍然依赖旧的关键词打分。

优点：

- 多步骤工作流的结果质量改善明显。
- handoff 语义更稳定。

缺点：

- 第一步派给谁仍可能不准。
- 无法体现“更聪明的 agent 选择”这一用户预期。

### 方案 C：路由 + 协作上下文最小闭环

同时增强 `TaskRouter`、`WorkflowEngine` 与 `handoff`，但只做最小能力集：任务画像、路由理由、结构化步骤上下文、结构化 handoff。

优点：

- 能形成一条完整的上层能力链路。
- 不依赖底座重写，适合当前“先上层后底座”的推进顺序。
- 能直接服务 `workflow`、`dispatch`、Hermes/OpenClaw handoff 三个入口。

缺点：

- 改动面比单点优化更大。
- 需要同时补多组测试。

### 方案选择

本设计选择 **方案 C：路由 + 协作上下文最小闭环**。

理由：

- 用户已经明确选择“两者一起”作为本轮第一优先。
- 当前仓库最缺的不是某个点状特性，而是一条真正连起来的 agent 协作链。
- 这条链路能在不触碰重底座问题的前提下，最大化提升体感能力。

## 4. 设计概览

本轮把上层能力拆成三块：

1. **任务画像与可解释路由**
   - 新增任务画像提取逻辑。
   - 路由时同时考虑显式角色、任务类型、协作信号、负载与成功率。
   - 为每次路由产出结构化 `routing_reason`。

2. **结构化工作流上下文**
   - 每个步骤执行后，把结果归一化为统一的上下文条目。
   - 后续步骤不再只依赖字符串模板，也能引用前置步骤的摘要、产物和风险。
   - workflow 返回值中增加 `handoffs` 与 `step_contexts`。

3. **结构化 handoff 协议**
   - 扩展 `HandoffPayload` 字段，使其能够表达来源步骤、目标角色、待确认项与交接理由。
   - workflow 在跨角色步骤之间自动生成 handoff。

## 5. 详细设计

### 5.1 TaskRouter：任务画像与可解释路由

#### 新增数据结构

- `TaskIntent`
  - `task_type`: 现有 `TaskType`
  - `requested_agent`: 用户显式指定的 agent 或 alias
  - `requested_role`: 用户显式指定的角色
  - `collaboration_mode`: `single` / `review` / `handoff` / `parallel`
  - `deliverables`: 识别出的交付物类型列表，如 `spec`、`test`、`review`、`code`
  - `risk_flags`: 风险标签，如 `critical`、`production`、`performance`
  - `keywords`: 命中的关键词

#### 核心行为

- 新增 `analyze_task_intent(content: str) -> TaskIntent`
  - 先识别显式角色或 alias，如“交给 architect”“让 backend 看一下”“请 qa review”。
  - 再识别协作信号，如“review”“验收”“交接”“并行”。
  - 最后回退到现有关键词分类。

- 新增 `select_best_agent(intent: TaskIntent, priority: TaskPriority) -> tuple[str, dict]`
  - 若命中显式 agent 或 alias，优先选择该 agent。
  - 若命中显式角色，则优先在对应角色池中按负载与成功率排序。
  - 若任务带 `review` 信号，尽量避开与上游相同角色，优先找 QA 或 reviewer 型角色。
  - 若无显式信号，再回退到现有打分模型。

- `route_task()` 返回的 `Task` 上新增：
  - `routing_reason`
  - `intent`

#### 兼容性

- 现有 `route_task()` 的返回签名不变，仍为 `(agent_id, task)`。
- 原有基于 `TaskType` 的调用不需要改。

### 5.2 WorkflowEngine：结构化步骤上下文

#### 新增数据结构

- `StepContext`
  - `step_id`
  - `agent`
  - `summary`
  - `artifacts`
  - `open_questions`
  - `risks`
  - `handoff_hint`

#### 核心行为

- 新增 `_build_step_context(step, result, task_content) -> Dict[str, Any]`
  - 把步骤结果统一转成结构化上下文。
  - 若结果只是字符串，则自动降级成 `summary`。
  - 若结果是字典，则从 `output/summary/artifacts/open_questions/risks` 中归一化字段。

- 新增 `_merge_step_context_into_variables(workflow, step_context)`
  - 把步骤上下文写入：
    - `workflow.variables[f"{step.id}_summary"]`
    - `workflow.variables[f"{step.id}_artifacts"]`
    - `workflow.variables[f"{step.id}_open_questions"]`
    - `workflow.variables[f"{step.id}_risks"]`
  - 同时维护 `workflow.variables["step_contexts"]`

- `_render_template()` 保持字符串替换能力，但 workflow 返回值新增：
  - `step_contexts`
  - `handoffs`

#### 协作行为

- 当某一步骤的 `agent` 与其直接后继步骤的 `agent` 不同，自动生成 handoff。
- 当某一步骤是自动路由，且最终落到与前一步不同角色，也生成 handoff。

### 5.3 HandoffPayload：跨 agent 交接协议增强

#### 扩展字段

- 保留现有字段：
  - `source_backend`
  - `target_backend`
  - `task_id`
  - `summary`
  - `context`
  - `created_at`

- 新增字段：
  - `source_agent`
  - `target_agent`
  - `source_step`
  - `target_step`
  - `reason`
  - `artifacts`
  - `open_questions`
  - `risks`

#### 核心行为

- `HandoffPayload.create()` 支持上述字段的可选入参。
- `validate_handoff_payload()` 改为：
  - 检查新增字段类型是否合法。
  - 允许没有 `target_agent`，但若存在必须为字符串。
  - `artifacts/open_questions/risks` 必须是列表。

#### 兼容性

- 旧测试里只依赖最小字段时仍然成立。
- 新字段全部为向后兼容的可选字段。

## 6. 代码落点

- `\.hermes/team/调度框架/core/task_router.py`
  - 新增任务画像提取、显式角色解析、可解释路由字段。
- `\.hermes/team/调度框架/core/workflow_engine.py`
  - 新增结构化步骤上下文、跨步骤 handoff 自动生成、workflow 返回值增强。
- `\.hermes/team/control_plane/protocols/handoff.py`
  - 扩展 `HandoffPayload` 字段与校验逻辑。
- `tests/control_plane/test_task_router.py`
  - 新增路由画像与显式角色/alias/协作信号测试。
- `tests/control_plane/test_workflow_runtime.py`
  - 新增步骤上下文与自动 handoff 测试。
- `tests/control_plane/test_handoff.py`
  - 新增增强字段与兼容性测试。
- `tests/control_plane/test_unified_cli.py`
  - 如需经由 `workflow` CLI 返回增强结果，补相应断言。

## 7. 测试策略

- `TaskRouter`
  - 显式 alias 应优先命中目标 agent。
  - review/handoff 信号应影响选择逻辑与 `routing_reason`。
  - 未命中显式信号时仍保持原有回退行为。

- `WorkflowEngine`
  - 步骤结果会被归一化为 `step_contexts`。
  - 跨 agent 步骤会自动产出 handoff。
  - 原有 runtime snapshot 与 step event 行为不回退。

- `HandoffPayload`
  - 新字段可被创建、序列化、校验。
  - 旧最小字段载荷依然通过验证。

## 8. 风险与回滚

- 风险 1：路由规则过度偏向显式角色，导致负载均衡变差
  - 缓解：显式角色仅在候选池内生效，不取消负载检查。

- 风险 2：步骤上下文字段膨胀，导致 workflow 变量变得难读
  - 缓解：只沉淀固定字段，不把原始 result 全量复制到顶层变量。

- 风险 3：handoff 字段扩展影响旧调用方
  - 缓解：全部字段向后兼容，保留原有 `to_dict()` 基础键集合。

回滚策略：

- 若新增路由逻辑有问题，可只回退 `TaskRouter` 的任务画像选择分支，保留旧评分路径。
- 若 handoff 增强逻辑影响现有 workflow，可先停用自动 handoff 生成，保留步骤上下文能力。

## 9. 里程碑

- `M1`：补红灯测试，覆盖任务画像、结构化上下文、增强 handoff。
- `M2`：实现 `TaskRouter` 任务画像与可解释路由。
- `M3`：实现 `WorkflowEngine` 结构化步骤上下文与自动 handoff。
- `M4`：回归 `tests/control_plane` 相关测试，并检查 lint/diagnostics。

## 10. 完成判定

满足以下条件视为本轮一期完成：

- `TaskRouter` 能识别显式 agent/role/alias 与 review/handoff 协作信号。
- `WorkflowEngine.execute_workflow()` 返回结构化 `step_contexts` 与 `handoffs`。
- `HandoffPayload` 能稳定表达跨 agent 交接元数据。
- 相关控制平面测试通过，且无新增诊断错误。
