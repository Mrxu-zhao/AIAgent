# 郑晓彤 - 最近经验

## 2026-05

<!-- lesson-key: qa-functional|regression_test|任务已分配给 qa-functional: 回归验证修复结果 -->
### 经验：任务已分配给 qa-functional: 回归验证修复结果
- 场景：workflow: primary_learning_delivery; step: regression_test; agent: qa-functional
- 做法：任务已分配给 qa-functional: 回归验证修复结果
- 结果：任务已分配给 qa-functional: 回归验证修复结果
- 适用前提：适用于 regression_test 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: qa-functional|functional_test|任务已分配给 qa-functional: 执行功能测试，验证识字/口算/字母模块 -->
### 经验：任务已分配给 qa-functional: 执行功能测试，验证识字/口算/字母模块
- 场景：workflow: primary_learning_delivery; step: functional_test; agent: qa-functional
- 做法：任务已分配给 qa-functional: 执行功能测试，验证识字/口算/字母模块
- 结果：任务已分配给 qa-functional: 执行功能测试，验证识字/口算/字母模块
- 适用前提：适用于 functional_test 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: qa-functional|review|review-decision -->
### 经验：review-decision
- 场景：workflow: wf-collab; step: review; agent: qa-functional
- 做法：review:评审 design:设计方案
- 结果：review:评审 design:设计方案
- 适用前提：review-risk
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: qa-functional|functional_test|执行功能测试 -->
### 经验：执行功能测试
- 场景：workflow: wf-quality-gate; step: functional_test; agent: qa-functional
- 做法：执行功能测试
- 结果：执行功能测试
- 适用前提：适用于 functional_test 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: qa-functional|closure_confirmation|确认闭环 -->
### 经验：确认闭环
- 场景：workflow: wf-missing-deliverable; step: closure_confirmation; agent: qa-functional
- 做法：确认闭环
- 结果：确认闭环
- 适用前提：适用于 closure_confirmation 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


### 经验：接口测试的"契约测试"实践
- **场景**：前后端联调时发现接口字段不一致，导致测试阻塞
- **做法**：引入契约测试，前后端先对齐接口契约（JSON Schema），再各自开发
- **结果**：联调阻塞减少80%，接口兼容性提升
- **适用前提**：前后端并行开发、接口频繁变更
- **沉淀方向**：已补充到角色层《接口测试最佳实践》

### 经验：回归测试的"优先级分级"策略
- **场景**：回归测试用例过多（500+），执行时间长，资源不足
- **做法**：将用例分为P0（核心流程）、P1（重要功能）、P2（一般功能），按优先级执行
- **结果**：回归测试时间从2天降到4小时，核心流程覆盖率100%
- **适用前提**：用例多、时间紧、资源有限
- **沉淀方向**：已补充到角色层《回归测试策略》

## 2026-04

### 经验：缺陷根因的"5Why分析法"
- **场景**：缺陷反复出现，修复后过一段时间又出现
- **做法**：采用5Why分析法，追溯缺陷根因（如：为什么有bug→因为没测试→为什么没测试→因为没写用例→为什么没写用例→因为需求变更频繁）
- **结果**：缺陷复发率从30%降到5%
- **适用前提**：缺陷反复出现、需要系统性改进
- **沉淀方向**：已补充到角色层《缺陷分析方法》

## 记录模板
- 日期：
- 场景：
- 做法：
- 结果：
- 适用前提：
- 是否可沉淀到角色层或团队层：
