# 张欣怡 - 最近经验

## 2026-05

<!-- lesson-key: architect|design|design:设计方案 -->
### 经验：design:设计方案
- 场景：workflow: wf-backend; step: design; agent: architect
- 做法：design:设计方案
- 结果：design:设计方案
- 适用前提：适用于 design 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: architect|design|任务已分配给 architect: 产出接口 spec -->
### 经验：任务已分配给 architect: 产出接口 spec
- 场景：workflow: wf-handoff; step: design; agent: architect
- 做法：任务已分配给 architect: 产出接口 spec
- 结果：任务已分配给 architect: 产出接口 spec
- 适用前提：适用于 design 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: architect|design|design-decision -->
### 经验：design-decision
- 场景：workflow: wf-collab; step: design; agent: architect
- 做法：design:设计方案
- 结果：design:设计方案
- 适用前提：design-risk
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: architect|design|ok -->
### 经验：ok
- 场景：workflow: wf-bus-handoff; step: design; agent: architect
- 做法：ok
- 结果：ok
- 适用前提：适用于 design 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: architect|requirements_review|评审需求 -->
### 经验：评审需求
- 场景：workflow: wf-blocked-approval; step: requirements_review; agent: architect
- 做法：评审需求
- 结果：评审需求
- 适用前提：适用于 requirements_review 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


### 经验：微服务拆分的"黄金粒度"
- **场景**：物资管理平台初期拆分过细（8个服务），导致调用链过长、运维复杂
- **做法**：重新评估，按"业务边界+团队规模+数据一致性"三维度合并为4个服务
- **结果**：调用链缩短50%，部署复杂度降低，性能提升
- **适用前提**：团队规模<10人，业务复杂度中等
- **沉淀方向**：已补充到角色层《微服务拆分决策树》

### 经验：分布式事务的"最终一致性"实践
- **场景**：库存扣减与订单创建需要强一致性，初期采用TCC方案过于复杂
- **做法**：改为"本地事务+异步对账+补偿机制"，接受秒级不一致
- **结果**：实现复杂度降低70%，性能提升，无数据不一致问题
- **适用前提**：业务允许秒级延迟，有对账机制
- **沉淀方向**：建议补充到团队层《分布式事务选型指南》

## 2026-04

### 经验：API网关的限流策略设计
- **场景**：初期限流采用"全局固定阈值"，导致大促时正常用户被误杀
- **做法**：改为"分层限流（用户级+接口级+系统级）+ 动态阈值调整"
- **结果**：误杀率从15%降到<1%，系统稳定性提升
- **适用前提**：流量波动大，有监控数据支撑动态调整
- **沉淀方向**：已补充到角色层《API网关设计模式》

## 记录模板
- 日期：
- 场景：
- 做法：
- 结果：
- 适用前提：
- 是否可沉淀到角色层或团队层：
