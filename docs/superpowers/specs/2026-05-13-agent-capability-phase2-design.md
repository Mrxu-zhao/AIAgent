# Agent 能力增强二期设计文档

## 1. 背景

一期已经补上了上层 agent 能力的最小骨架：`TaskRouter` 具备任务画像与基础可解释路由，`WorkflowEngine` 能返回 `step_contexts` 与 `handoffs`，`HandoffPayload` 也已支持结构化交接字段。<mccoremem id="01KRG0XH9KSY572B133JZ1JVZM" />

但用户明确要求继续补完三件事并进入二期：

- reviewer 路由从“识别 review 信号”升级为“真正优先 reviewer 候选池，但保留可回退能力”；
- workflow 的 `artifacts/open_questions/risks` 从单步字段升级为跨步骤累积的协作上下文；
- handoff 需要解释为什么继续走当前 backend，或者为什么建议切到另一个 backend。

用户同时已指定 reviewer 路由采用 **软约束**：优先 reviewer/QA 候选池，但如果候选不满足负载或可用性，允许回退到其他合适 agent。

## 2. 目标与非目标

### 2.1 目标

- 为 review 类任务建立 reviewer 优先候选池与回退逻辑。
- 为 `WorkflowEngine` 建立全局 `collaboration_context`，聚合多步骤产出的 artifacts、问题、风险与决策。
- 为 `HandoffPayload` 增加 backend 选择解释字段，让 Hermes/OpenClaw 交接原因可追踪。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />
- 保持当前 Python 原生、控制平面优先的增量演进方式，不把二期扩成底座重构。<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K|03g415w5w3367klgad5cg68tb" />

### 2.2 非目标

- 本轮不改 `providers/*` 的真实执行链，不新增 live 切换逻辑。
- 本轮不引入新的调度存储或审批流。
- 本轮不做学习型路由或历史反馈训练。
- 本轮不把 workflow 变量系统重写成新的 DSL。

## 3. 方案比较

### 方案 A：规则增强闭环

在现有一期实现上继续增强规则：

- `TaskRouter` 增加 reviewer 候选池与回退理由。
- `WorkflowEngine` 增加全局协作上下文聚合。
- `handoff` 增加 backend 解释字段。

优点：

- 改动面小，延续一期实现。
- 能直接补完用户点名的三件事。
- 风险最低，最符合“上层先行、底座随后补齐”。

缺点：

- 仍然是规则驱动，非学习型路由。

### 方案 B：新增统一协作计划对象

引入新的 `CollaborationPlan` 统一承载 reviewer 策略、上下文聚合和 handoff 解释。

优点：

- 长期结构更整齐。

缺点：

- 这一轮会演变成中等规模重构。
- 与“尽快补完三件事”的目标不匹配。

### 方案 C：只扩字段，不改策略

只增加返回字段，不增强 reviewer 路由和协作累积。

优点：

- 风险最低。

缺点：

- 用户体感提升最弱。
- 三件事只有表面覆盖，没有形成闭环。

### 方案选择

本设计选择 **方案 A：规则增强闭环**。

## 4. 设计概览

二期拆成三块：

1. **Reviewer 软约束路由**
   - review 任务优先走 reviewer 候选池。
   - 若 reviewer 不可用，再回退到普通候选。
   - 路由结果保留清晰解释。

2. **协作上下文累积**
   - workflow 不再只保留每一步自己的 `step_context`。
   - 新增全局 `collaboration_context`，聚合 artifacts、open questions、risks、decisions。

3. **Backend 选择解释**
   - handoff 记录 `selected_backend`、候选 backend、选择理由。
   - 二期只解释，不改真实 provider 执行行为。

## 5. 详细设计

### 5.1 Reviewer 软约束路由

#### 核心规则

- 当 `TaskIntent.collaboration_mode == "review"` 时，优先 reviewer 候选池：
  - `qa-functional`
  - `qa-performance`
- 若 review 任务同时带 `performance` 风险标记，优先 `qa-performance`。
- 若 reviewer 候选全部满载或不可选，回退到普通评分逻辑。
- 若提供了 `upstream_agent` 或 `upstream_role`，review 时尽量避免派回上游角色。

#### 数据与接口变化

- `TaskIntent` 新增：
  - `upstream_agent`
  - `upstream_role`
  - `review_policy`
- `select_best_agent()` 新增 reviewer 候选池分支。
- `routing_reason` 新增：
  - `review_policy`
  - `fallback_used`
  - `excluded_agents`
  - `candidate_pool`

#### 兼容性

- 非 review 任务走现有逻辑。
- review 任务如果没有上游信息，也仍可运行。

### 5.2 协作上下文累积

#### 新增结构

- `workflow.variables["collaboration_context"]`
  - `artifacts`: 去重后的列表
  - `open_questions`: 累积问题列表
  - `risks`: 累积风险列表
  - `decisions`: 结构化决策列表

#### 核心行为

- `_build_step_context()` 新增支持从结果中读取：
  - `decisions`
  - `backend_recommendation`
- `_merge_step_context_into_variables()` 除了更新单步变量，也同步更新全局 `collaboration_context`。
- workflow 结果新增：
  - `collaboration_context`

#### 数据累积原则

- `artifacts`：按字符串去重。
- `open_questions`：保留顺序，避免重复。
- `risks`：保留顺序，避免重复。
- `decisions`：每条记录至少包含 `step_id` 与 `summary`。

### 5.3 Handoff backend 解释字段

#### `HandoffPayload` 新增字段

- `selected_backend`
- `backend_candidates`
- `backend_reason`
- `review_policy`

#### 生成规则

- 默认 `selected_backend` 先沿用 `source_backend`。
- 若 step context 中包含 `backend_recommendation`，则：
  - `selected_backend` 取推荐值；
  - `backend_reason` 取推荐理由；
  - `backend_candidates` 记录候选后端集合。
- 若没有推荐值，则生成保守解释：
  - 继续沿用当前 backend，因为本轮未触发 provider 切换条件。

#### 兼容性

- 旧载荷继续有效。
- 新字段全部可选。

## 6. 代码落点

- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\task_router.py`
  - reviewer 软约束路由、上游规避、解释字段扩展。
- `d:\KIMIK2.5\AIAgent\.hermes\team\调度框架\core\workflow_engine.py`
  - `collaboration_context` 聚合、step context 字段扩展、handoff backend 解释。
- `d:\KIMIK2.5\AIAgent\.hermes\team\control_plane\protocols\handoff.py`
  - backend 解释字段与校验逻辑扩展。
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_task_router.py`
  - reviewer 候选池优先与回退测试。
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_workflow_runtime.py`
  - `collaboration_context` 累积与 backend 解释测试。
- `d:\KIMIK2.5\AIAgent\tests\control_plane\test_handoff.py`
  - backend 字段兼容与校验测试。

## 7. 测试策略

- `TaskRouter`
  - review 任务优先落到 QA/reviewer 候选池。
  - QA 满载时会回退，且 `routing_reason["fallback_used"] == True`。
  - 高风险性能 review 优先 `qa-performance`。

- `WorkflowEngine`
  - 多步 workflow 结束后返回 `collaboration_context`。
  - `artifacts/open_questions/risks/decisions` 被正确累积。
  - handoff 中包含 backend 选择解释字段。

- `HandoffPayload`
  - backend 字段可创建、可序列化、可校验。
  - 不带 backend 扩展字段的旧载荷依旧合法。

## 8. 风险与回滚

- 风险 1：review 优先 QA 后，某些普通 review 会偏离原来的专业角色
  - 缓解：采用软约束，允许回退。

- 风险 2：协作上下文累积过多，导致结果体积膨胀
  - 缓解：只保留有限结构，不复制原始大对象。

- 风险 3：backend 解释字段让用户误以为 provider 真切换已落地
  - 缓解：文档与字段命名明确这是 recommendation/explanation，不是执行链切换。

回滚策略：

- review 路由异常时，只回退 reviewer 候选池分支；
- `collaboration_context` 如有兼容问题，可保留单步 `step_contexts`，关闭全局聚合写入；
- backend 解释字段如有歧义，可保留基础 handoff，不写扩展 backend 字段。

## 9. 完成判定

满足以下条件视为二期完成：

- review 类任务具备 reviewer 优先、可回退、可解释的路由行为。
- workflow 结果包含 `collaboration_context`，且能跨步骤累积核心协作信息。
- handoff 能表达 backend 候选、最终选择与解释原因。
- 相关测试通过，新增改动无 diagnostics。
