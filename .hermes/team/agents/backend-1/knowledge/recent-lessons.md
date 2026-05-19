# 陈启明 - 最近经验

## 2026-05

<!-- lesson-key: backend-1|backend|Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2 -->
### 经验：Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2
- 场景：workflow: baseline_workflow; step: backend; agent: backend-1
- 做法：Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2
- 结果：Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2
- 适用前提：适用于 backend 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|done -->
### 经验：done
- 场景：workflow: wf-real-exec-success-shape; step: implement; agent: backend-1
- 做法：done
- 结果：done
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|模拟执行: 实现代码 -->
### 经验：模拟执行: 实现代码
- 场景：workflow: wf-simulated; step: implement; agent: backend-1
- 做法：模拟执行: 实现代码
- 结果：模拟执行: 实现代码
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|implement:实现代码 -->
### 经验：implement:实现代码
- 场景：workflow: wf-backend; step: implement; agent: backend-1
- 做法：implement:实现代码
- 结果：implement:实现代码
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|任务已分配给 backend-1: 实现接口并补测试 -->
### 经验：任务已分配给 backend-1: 实现接口并补测试
- 场景：workflow: wf-knowledge-pack; step: implement; agent: backend-1
- 做法：任务已分配给 backend-1: 实现接口并补测试
- 结果：任务已分配给 backend-1: 实现接口并补测试
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码 -->
### 经验：任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码
- 场景：workflow: wf-handoff; step: implement; agent: backend-1
- 做法：任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码
- 结果：任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|review|任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口 -->
### 经验：任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口
- 场景：workflow: wf-review-routing; step: review; agent: backend-1
- 做法：任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口
- 结果：任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口
- 适用前提：适用于 review 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|任务已分配给 backend-1: 实现接口 -->
### 经验：任务已分配给 backend-1: 实现接口
- 场景：workflow: wf-review-routing; step: implement; agent: backend-1
- 做法：任务已分配给 backend-1: 实现接口
- 结果：任务已分配给 backend-1: 实现接口
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|ok -->
### 经验：ok
- 场景：workflow: wf-bus-handoff; step: implement; agent: backend-1
- 做法：ok
- 结果：ok
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


<!-- lesson-key: backend-1|implement|实现代码 -->
### 经验：实现代码
- 场景：workflow: wf-routing-priority-failure; step: implement; agent: backend-1
- 做法：实现代码
- 结果：实现代码
- 适用前提：适用于 implement 等类似工作流步骤
- 是否可沉淀到角色层或团队层：团队层 lessons


### 经验：API版本控制的"兼容性优先"策略
- **场景**：订单接口v1需要增加字段，但已有客户端在使用
- **做法**：采用"扩展不修改"策略，新增字段有默认值，旧客户端不感知
- **结果**：零 breaking change，客户端平滑升级
- **适用前提**：接口已发布、有多个客户端、不能强制升级
- **沉淀方向**：已补充到角色层《API版本管理规范》

### 经验：微服务间调用的"熔断+降级"实践
- **场景**：库存服务故障导致订单服务雪崩
- **做法**：引入Sentinel熔断，库存不可用时降级为"允许超卖+异步对账"
- **结果**：订单服务可用性从95%提升到99.9%
- **适用前提**：服务间有依赖、允许短暂不一致、有补偿机制
- **沉淀方向**：已补充到角色层《微服务容错设计模式》

## 2026-04

### 经验：单元测试的"边界值"覆盖
- **场景**：订单金额计算bug，只在金额为0.01时触发
- **做法**：补充边界值测试（最小值、最大值、临界值、非法值）
- **结果**：发现3个类似bug，提升代码健壮性
- **适用前提**：涉及数值计算、有明确边界条件
- **沉淀方向**：已补充到角色层《单元测试最佳实践》

## 记录模板
- 日期：
- 场景：
- 做法：
- 结果：
- 适用前提：
- 是否可沉淀到角色层或团队层：
