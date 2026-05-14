# Agent 知识库丰富方案设计文档

## 1. 背景

当前项目内的 agent 知识并不是单一知识库，而是由多层入口共同组成：

- 全局基础提示词位于 `.hermes/SOUL.md`
- 运行时 profile 位于 `.hermes/profiles/*/SOUL.md` 与 `config.yaml`
- 角色原型知识位于 `.hermes/agents/*/knowledge/`
- 团队实例资料位于 `.hermes/team/agents/*/profile.md`
- 共享记忆位于 `.hermes/memories/*`

现状存在四个核心问题：

- 知识入口分散，但没有统一装载顺序，更多依赖文档约定而非稳定规则。
- `backend-1/2/3` 与 `frontend-1/2/3` 共享角色原型知识，但缺少个体画像层，难以形成稳定分工。
- 多个 skill 文档引用 `~/.hermes/team/knowledge/`，仓库内却没有真实落盘的共享团队知识目录。
- 调度框架已经具备 agent 路由、workflow 与 handoff 基础能力，但尚未把“任务适配哪些知识包”制度化串入执行链路。`<mccoremem id="01KRG0XH9KSY572B133JZ1JVZM|03g400roujgec9otxvlzd7jq0" />`

因此，本设计的目标不是简单补几篇文档，而是建立一套能与现有 Hermes/team/control_plane 结构自然耦合的知识库分层与治理方案。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />`

## 2. 目标与非目标

### 2.1 目标

- 建立适配当前项目结构的三层知识体系：团队公共知识、角色知识、实例知识。
- 为 13 个团队 agent 给出清晰的知识补全优先级与首批文档建议。
- 为后续 `TaskRouter`、`WorkflowEngine` 与 handoff 链路接入知识推荐提供稳定目录基础。
- 定义统一的知识文件模板、装载顺序与治理规则，降低后续维护成本。
- 保持 Python 原生工程口径，不引入外部知识库服务或向量数据库依赖。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />`

### 2.2 非目标

- 本轮不实现真实语义检索、embedding、向量召回或外部 RAG 服务。
- 本轮不修改现有 Hermes profile 运行机制，只补齐知识资产与装载约定。
- 本轮不把所有历史任务结果自动回灌入知识库，只定义后续治理规则。
- 本轮不重写 `TaskRouter` 或 `WorkflowEngine` 的执行逻辑，只为它们预留接入点。

## 3. 方案比较

### 方案 A：继续按 Agent 分散补文档

只在各 `profile`、`knowledge/`、`profile.md` 中继续增量补内容，不新增统一团队知识层。

优点：

- 见效快，改动最小。
- 几乎不影响现有目录结构。

缺点：

- 重复内容会持续堆积。
- 跨角色共享知识仍无统一入口。
- 无法支撑后续知识推荐与治理。

### 方案 B：建立单一中央知识库

把所有知识集中到一个总目录，agent 只通过标签或索引读取。

优点：

- 形式统一，治理简单。
- 便于后续做检索或索引。

缺点：

- 容易削弱角色边界。
- 迁移成本高。
- 不贴合当前 Hermes 的 profile 与 role 原型结构。

### 方案 C：建立三层知识体系

保留现有 `team`、`agents`、`profiles` 的结构语义，在此基础上把知识分成团队公共知识、角色知识、实例知识三层。

优点：

- 与现有目录天然兼容。
- 能同时支撑共享知识、角色复用与个体差异化。
- 适合后续逐步接入路由推荐、handoff 模板与知识演化。

缺点：

- 前期需要做一次目录标准化。
- 治理规则需要明确 owner 与边界。

### 方案选择

本设计选择 **方案 C：建立三层知识体系**。

理由：

- 当前项目已经天然存在“团队层 + 角色层 + 实例层”的雏形，只是尚未标准化。
- 该方案最适合渐进落地，不需要破坏已有 Hermes/OpenClaw 适配方向。`<mccoremem id="01KRFC71P2XQXK764Q5KSAKH6K" />`
- 它能同时满足短期补齐与中长期演进两类目标。

## 4. 设计概览

本方案把 agent 知识资产拆成三层：

1. **团队公共知识**

   - 服务所有 agent 的共享事实、流程和模板。
   - 解决术语不统一、项目背景重复解释、handoff 缺少统一模板的问题。
2. **角色知识**

   - 服务同一角色的共性能力，如架构师、后端、前端、测试、DBA、DevOps。
   - 解决高频任务执行模式、检查清单、反模式与模板沉淀问题。
3. **实例知识**

   - 服务具体 agent 的个体差异，如 `backend-1`、`frontend-2` 的专长、常接模块、协作偏好。
   - 解决多实例角色无法形成稳定分工的问题。

统一装载顺序建议为：

`全局 SOUL -> 团队公共知识 -> 角色知识 -> 实例知识 -> memories -> 当前任务 handoff/context`

这样可以先确保共享规则，再叠加角色差异和个体特征，最后用当前任务上下文做收敛。`<mccoremem id="01KRG0XH9KSY572B133JZ1JVZM" />`

## 5. 详细设计

### 5.1 团队公共知识层

新增真实目录：

```text
.hermes/team/knowledge/
  README.md
  project-overview.md
  domain-glossary.md
  architecture-map.md
  repo-map.md
  workflow-playbook.md
  handoff-templates.md
  risk-register.md
  decision-log.md
```

各文件职责如下：

- `project-overview.md`
  - 记录项目目标、边界、核心模块、成功标准。
- `domain-glossary.md`
  - 统一业务术语、实体定义、缩写与别名。
- `architecture-map.md`
  - 记录核心模块关系、关键数据流、主要依赖边界。
- `repo-map.md`
  - 记录仓库结构、关键入口、高风险目录与改动注意事项。
- `workflow-playbook.md`
  - 记录标准协作路径、阶段责任、交付节奏。
- `handoff-templates.md`
  - 定义跨 agent 交接模板，直接服务 handoff 与 workflow 协作。`<mccoremem id="01KRG0XH9KSY572B133JZ1JVZM" />`
- `risk-register.md`
  - 记录已知风险、影响、预警信号、规避策略。
- `decision-log.md`
  - 记录关键设计决策、理由、替代方案与影响范围。

### 5.2 角色知识层

角色知识继续落在 `.hermes/agents/<role>/knowledge/`，但统一为标准目录：

```text
.hermes/agents/<role>/knowledge/
  README.md
  overview.md
  playbooks/
    common-tasks.md
    troubleshooting.md
  patterns/
    preferred-patterns.md
    anti-patterns.md
  checklists/
    design-checklist.md
    delivery-checklist.md
  pitfalls/
    common-mistakes.md
  templates/
    output-templates.md
  examples/
    good-examples.md
```

各目录职责如下：

- `overview.md`
  - 定义角色职责边界、输入输出、上下游接口。
- `playbooks/`
  - 沉淀高频任务执行套路。
- `patterns/`
  - 沉淀推荐模式与反模式。
- `checklists/`
  - 沉淀提交前、评审前、交付前的固定检查项。
- `pitfalls/`
  - 沉淀重复出现的踩坑。
- `templates/`
  - 沉淀标准输出模板。
- `examples/`
  - 存放高质量范例，以“为什么好”为主，不追求大量堆积。

### 5.3 实例知识层

为每个团队实例 agent 新增最小实例知识目录：

```text
.hermes/team/agents/<agent>/knowledge/
  README.md
  expertise.md
  owned-modules.md
  collaboration-preferences.md
  delivery-style.md
  recent-lessons.md
```

各文件职责如下：

- `expertise.md`
  - 记录擅长任务类型、技术栈、适配场景与不适配场景。
- `owned-modules.md`
  - 记录最熟悉的代码区域、长期负责模块、历史上下文较深的部分。
- `collaboration-preferences.md`
  - 记录最有效的输入形式、交接方式与协作边界。
- `delivery-style.md`
  - 记录默认输出结构、关注重点、常用验收格式。
- `recent-lessons.md`
  - 记录最近稳定有效的经验结论，只保留可复用内容。

### 5.4 13 个 Agent 的知识补全清单

| Agent                    | 角色原型                 | 最该补的知识                                   | 首批建议文件                                                                                                  |
| ------------------------ | ------------------------ | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `requirements-analyst` | `requirements-analyst` | 业务术语、需求澄清、PRD/SRS 模板、变更影响分析 | `domain-glossary.md` `elicitation-checklist.md` `prd-template.md` `change-impact-template.md`         |
| `architect`            | `architect`            | 系统边界、技术选型、非功能需求、架构评审       | `system-context.md` `tech-decision-matrix.md` `nfr-checklist.md` `architecture-review-checklist.md`   |
| `dba`                  | `dba`                  | 建模规范、索引策略、事务一致性、慢 SQL 排查    | `naming-conventions.md` `index-strategy.md` `consistency-patterns.md` `slow-sql-playbook.md`          |
| `backend-1`            | `backend-dev`          | 个人擅长模块、常用接口范式、默认交付习惯       | `expertise.md` `owned-modules.md` `api-checklist.md` `delivery-style.md`                              |
| `backend-2`            | `backend-dev`          | 同上，但强调差异化分工                         | `expertise.md` `owned-modules.md` `integration-patterns.md` `delivery-style.md`                       |
| `backend-3`            | `backend-dev`          | 同上，但强调差异化分工                         | `expertise.md` `owned-modules.md` `troubleshooting-focus.md` `delivery-style.md`                      |
| `frontend-1`           | `frontend-dev`         | 擅长页面类型、组件模式、接口联调习惯           | `expertise.md` `owned-pages.md` `component-patterns.md` `delivery-style.md`                           |
| `frontend-2`           | `frontend-dev`         | 同上，但强调差异化分工                         | `expertise.md` `owned-pages.md` `state-patterns.md` `delivery-style.md`                               |
| `frontend-3`           | `frontend-dev`         | 同上，但强调差异化分工                         | `expertise.md` `owned-pages.md` `a11y-focus.md` `delivery-style.md`                                   |
| `ucd`                  | `ucd`                  | 信息架构、交互规范、原型交付、可用性检查       | `ia-template.md` `interaction-guidelines.md` `wireframe-delivery-spec.md` `usability-checklist.md`    |
| `qa-functional`        | `qa-functional`        | 用例设计、回归矩阵、缺陷分级、数据库校验       | `case-design-patterns.md` `regression-matrix.md` `bug-severity-rules.md` `db-validation-checklist.md` |
| `qa-performance`       | `qa-performance`       | 压测模型、指标基线、瓶颈定位、报告模板         | `load-model-template.md` `performance-baseline.md` `bottleneck-playbook.md` `report-template.md`      |
| `devops`               | `devops`               | 环境差异、发布回滚、CI/CD 约束、监控指标       | `env-matrix.md` `release-rollback-playbook.md` `pipeline-rules.md` `observability-metrics.md`         |

### 5.5 首批优先文件

建议先落地以下 10 个文件：

- `.hermes/team/knowledge/project-overview.md`
- `.hermes/team/knowledge/repo-map.md`
- `.hermes/team/knowledge/workflow-playbook.md`
- `.hermes/team/knowledge/handoff-templates.md`
- `.hermes/team/knowledge/risk-register.md`
- `.hermes/agents/backend-dev/knowledge/overview.md`
- `.hermes/agents/backend-dev/knowledge/checklists/delivery-checklist.md`
- `.hermes/agents/frontend-dev/knowledge/overview.md`
- `.hermes/agents/architect/knowledge/checklists/architecture-review-checklist.md`
- `.hermes/agents/requirements-analyst/knowledge/templates/output-templates.md`

这些文件能最先解决共享上下文缺失、后端/前端角色沉淀不足，以及需求到交付链路不一致的问题。

## 6. 装载与演进策略

### 6.1 装载顺序

统一装载顺序为：

1. 全局 `SOUL`
2. 团队公共知识
3. 角色知识
4. 实例知识
5. memories
6. 当前任务 handoff 与上下文

接入原则：

- 团队公共知识负责提供“所有人都应知道”的事实和流程。
- 角色知识负责提供“这类角色通常怎么做”的规则和模板。
- 实例知识负责提供“这个具体 agent 更擅长什么、应该怎么协作”的差异信息。
- 当前任务 handoff 负责覆盖当次任务的临时上下文，不直接反写长期知识。

### 6.2 与调度框架的关系

本期不直接改代码，但后续可沿以下路径与现有调度链路对齐：

- `TaskRouter` 在任务画像输出中增加推荐知识包，例如推荐读取哪些团队知识或角色 checklist。
- `WorkflowEngine` 在跨 agent handoff 时引用 `handoff-templates.md` 的固定结构。
- `ControlPlaneExecutor` 在任务级 backend 之外，后续可以补“任务级知识包”选择，但不改变现有 backend 执行语义。`<mccoremem id="03g49kiy4yk240dci3220p7eu" />`

## 7. 治理规则

每份知识文档都应带最小元信息：

- `owner`
- `scope`
- `last_reviewed`
- `source`
- `applies_to`

治理原则如下：

- 团队知识由团队层 owner 维护。
- 角色知识由角色 owner 维护。
- 实例知识由具体 agent owner 维护。
- 只沉淀稳定事实、重复问题、已验证最佳实践。
- 不把一次性任务过程、临时讨论、未验证猜测写入长期知识库。
- 能用 checklist 表达的内容优先用 checklist，不用大段叙述。
- 能用模板固定的内容优先写模板，减少自由发挥。

## 8. 里程碑

- `M1`：创建 `.hermes/team/knowledge/` 并补 5 个团队公共知识文件。
- `M2`：标准化 `backend-dev` 与 `frontend-dev` 角色知识目录。
- `M3`：补 `architect`、`requirements-analyst`、`qa-functional` 三类关键角色模板。
- `M4`：为 13 个实例 agent 建最小实例知识目录。
- `M5`：把 `handoff-templates`、`decision-log`、`risk-register` 纳入日常任务收尾流程。

## 9. 风险与缓解

### 风险 1：知识层级重叠，导致内容重复

缓解：

- 明确团队层只写共享事实与流程。
- 角色层只写角色共性。
- 实例层只写个体差异。

### 风险 2：补文档后仍无人维护

缓解：

- 每份文档必须明确 `owner` 与 `last_reviewed`。
- 把高频知识更新动作纳入任务收尾流程。

### 风险 3：共享层写得过大，降低检索效率

缓解：

- 团队层只保留高稳定度、高复用度资产。
- 项目细节优先写入角色层或实例层，避免全部堆到共享层。

### 风险 4：知识沉淀与执行链路脱节

缓解：

- 优先补 `workflow-playbook.md` 与 `handoff-templates.md`。
- 后续在 `TaskRouter` 与 `WorkflowEngine` 中以推荐知识包形式逐步接入。

## 10. 完成判定

满足以下条件视为本轮“知识库丰富方案”设计完成：

- 团队公共知识、角色知识、实例知识三层结构被明确并可落盘。
- 13 个团队 agent 的知识补全重点与首批文件建议明确。
- 装载顺序、治理规则、风险与阶段目标明确。
- 首批优先文件与演进里程碑明确，可直接进入实施规划阶段。

## 11. 实施后更新（2026-05-14）

本设计最初聚焦“三层知识体系”的目录与治理方案，当前实现已在设计基础上继续推进到运行时链路：

- `TaskRouter` 已不止推荐团队/角色/实例知识，还会对路径做存在性检查、基础评分，并在实例层优先考虑 `recent-lessons.md` 的关键词命中。
- `WorkflowEngine` 已把知识推荐真正接入执行结果，生成 `knowledge_recommendations`、`knowledge_bundles`、`knowledge_feedback`，并在跨 agent handoff 中为目标步骤自动计算推荐知识包。
- `handoff` 协议和 schema 已扩展 `knowledge_recommendation` 字段，知识交接不再只是任务摘要。
- `decision-log.md` 与 `risk-register.md` 已从设计中的“团队资产”演进为 workflow 自动回写落点，具备 `owner`、`last_reviewed`、`source` 等 metadata，并对重复回写做去重。
- 统一 CLI、tool runtime、dashboard 和 query 能力已经消费这套知识结构，而不是只停留在文档约定层。

因此，当前代码状态已经超过本设计最初的“目录与治理”范围，进入“知识推荐 + 知识消费 + 知识回写 + 知识观测”的闭环阶段。
