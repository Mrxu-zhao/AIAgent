# 吴雪梅 - 最近经验

## 2026-05

<!-- lesson-key: requirements-analyst|requirements_analysis|任务已分配给 requirements-analyst: 分析小学1-3年级学习助手需求，输出 PRD 文档 -->
### 经验：任务已分配给 requirements-analyst: 分析小学1-3年级学习助手需求，输出 PRD 文档
- 场景：workflow: primary_learning_delivery; step: requirements_analysis; agent: requirements-analyst
- 做法：任务已分配给 requirements-analyst: 分析小学1-3年级学习助手需求，输出 PRD 文档
- 结果：任务已分配给 requirements-analyst: 分析小学1-3年级学习助手需求，输出 PRD 文档
- 适用前提：适用于 requirements_analysis 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: requirements-analyst|requirements|任务已分配给 requirements-analyst: Analyze requirements -->
### 经验：任务已分配给 requirements-analyst: Analyze requirements
- 场景：workflow: baseline_workflow; step: requirements; agent: requirements-analyst
- 做法：任务已分配给 requirements-analyst: Analyze requirements
- 结果：任务已分配给 requirements-analyst: Analyze requirements
- 适用前提：适用于 requirements 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: requirements-analyst|requirements|任务已分配给 requirements-analyst: 分析需求 -->
### 经验：任务已分配给 requirements-analyst: 分析需求
- 场景：workflow: wf-runtime; step: requirements; agent: requirements-analyst
- 做法：任务已分配给 requirements-analyst: 分析需求
- 结果：任务已分配给 requirements-analyst: 分析需求
- 适用前提：适用于 requirements 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


### 经验：B端表单类需求的标准化表达
- **场景**：物资管理平台的采购申请模块，表单字段多达30+，开发反馈需求描述混乱
- **做法**：将表单需求拆分为"字段清单（含校验规则）+ 状态流转（含触发条件）+ 异常处理"三部分
- **结果**：开发理解度提升，返工率降低
- **适用前提**：字段数量>10的复杂表单
- **沉淀方向**：已补充到角色层《B端表单类需求设计模式》

### 经验：需求评审中的技术可行性预判断
- **场景**：用户提出"实时库存同步"需求，未考虑数据一致性
- **做法**：评审前与架构师预沟通，识别出分布式事务风险，在PRD中明确"最终一致性"策略
- **结果**：避免了开发阶段才发现技术不可行的问题
- **适用前提**：涉及分布式系统、实时同步、大数据量的需求
- **沉淀方向**：建议补充到团队层《需求评审checklist》

## 2026-04

### 经验：权限体系需求的数据隔离表达
- **场景**：RBAC权限模型中，数据隔离规则（行级/列级）描述不清，导致DBA和后端理解不一致
- **做法**：采用"角色-数据范围-操作权限"三维矩阵表达，配合示例数据
- **结果**：DBA、后端、测试三方理解一致
- **适用前提**：涉及数据权限、多租户、数据隔离的需求
- **沉淀方向**：已补充到角色层《权限体系需求分析checklist》

## 记录模板
- 日期：
- 场景：
- 做法：
- 结果：
- 适用前提：
- 是否可沉淀到角色层或团队层：
