# Workflow 实战经验（2026-05-19）

---
owner: control-plane
last_reviewed: 2026-05-19
source: wf-exec-bind
scope: team
---

## 2026-05-19
<!-- lesson-key: architect|architecture|任务已分配给 architect: Design architecture -->
### 经验：任务已分配给 architect: Design architecture
- 场景：workflow: baseline_workflow; step: architecture; agent: architect
- 做法：任务已分配给 architect: Design architecture
- 结果：任务已分配给 architect: Design architecture
- 适用前提：适用于 architecture 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|backend|Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2 -->
### 经验：Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2
- 场景：workflow: baseline_workflow; step: backend; agent: backend-1
- 做法：Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2
- 结果：Implement backend service chunk 0 | Implement backend service chunk 1 | Implement backend service chunk 2
- 适用前提：适用于 backend 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: dba|database|任务已分配给 dba: Design architecture review package -->
### 经验：任务已分配给 dba: Design architecture review package
- 场景：workflow: baseline_workflow; step: database; agent: dba
- 做法：任务已分配给 dba: Design architecture review package
- 结果：任务已分配给 dba: Design architecture review package
- 适用前提：适用于 database 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: requirements-analyst|requirements|任务已分配给 requirements-analyst: Analyze requirements -->
### 经验：任务已分配给 requirements-analyst: Analyze requirements
- 场景：workflow: baseline_workflow; step: requirements; agent: requirements-analyst
- 做法：任务已分配给 requirements-analyst: Analyze requirements
- 结果：任务已分配给 requirements-analyst: Analyze requirements
- 适用前提：适用于 requirements 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: qa-functional|closure_confirmation|确认闭环 -->
### 经验：确认闭环
- 场景：workflow: wf-missing-deliverable; step: closure_confirmation; agent: qa-functional
- 做法：确认闭环
- 结果：确认闭环
- 适用前提：适用于 closure_confirmation 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: qa-functional|functional_test|执行功能测试 -->
### 经验：执行功能测试
- 场景：workflow: wf-quality-gate; step: functional_test; agent: qa-functional
- 做法：执行功能测试
- 结果：执行功能测试
- 适用前提：适用于 functional_test 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: architect|requirements_review|评审需求 -->
### 经验：评审需求
- 场景：workflow: wf-blocked-approval; step: requirements_review; agent: architect
- 做法：评审需求
- 结果：评审需求
- 适用前提：适用于 requirements_review 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|实现代码 -->
### 经验：实现代码
- 场景：workflow: wf-routing-priority-failure; step: implement; agent: backend-1
- 做法：实现代码
- 结果：实现代码
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: architect|design|ok -->
### 经验：ok
- 场景：workflow: wf-bus-handoff; step: design; agent: architect
- 做法：ok
- 结果：ok
- 适用前提：适用于 design 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|ok -->
### 经验：ok
- 场景：workflow: wf-bus-handoff; step: implement; agent: backend-1
- 做法：ok
- 结果：ok
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: architect|design|design-decision -->
### 经验：design-decision
- 场景：workflow: wf-collab; step: design; agent: architect
- 做法：design:设计方案
- 结果：design:设计方案
- 适用前提：design-risk

## 2026-05-19
<!-- lesson-key: qa-functional|review|review-decision -->
### 经验：review-decision
- 场景：workflow: wf-collab; step: review; agent: qa-functional
- 做法：review:评审 design:设计方案
- 结果：review:评审 design:设计方案
- 适用前提：review-risk

## 2026-05-19
<!-- lesson-key: backend-1|implement|任务已分配给 backend-1: 实现接口 -->
### 经验：任务已分配给 backend-1: 实现接口
- 场景：workflow: wf-review-routing; step: implement; agent: backend-1
- 做法：任务已分配给 backend-1: 实现接口
- 结果：任务已分配给 backend-1: 实现接口
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|review|任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口 -->
### 经验：任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口
- 场景：workflow: wf-review-routing; step: review; agent: backend-1
- 做法：任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口
- 结果：任务已分配给 backend-1: 请 review 任务已分配给 backend-1: 实现接口
- 适用前提：适用于 review 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: architect|design|任务已分配给 architect: 产出接口 spec -->
### 经验：任务已分配给 architect: 产出接口 spec
- 场景：workflow: wf-handoff; step: design; agent: architect
- 做法：任务已分配给 architect: 产出接口 spec
- 结果：任务已分配给 architect: 产出接口 spec
- 适用前提：适用于 design 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码 -->
### 经验：任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码
- 场景：workflow: wf-handoff; step: implement; agent: backend-1
- 做法：任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码
- 结果：任务已分配给 backend-1: 根据 任务已分配给 architect: 产出接口 spec 完成代码
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|任务已分配给 backend-1: 实现接口并补测试 -->
### 经验：任务已分配给 backend-1: 实现接口并补测试
- 场景：workflow: wf-knowledge-pack; step: implement; agent: backend-1
- 做法：任务已分配给 backend-1: 实现接口并补测试
- 结果：任务已分配给 backend-1: 实现接口并补测试
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: requirements-analyst|requirements|任务已分配给 requirements-analyst: 分析需求 -->
### 经验：任务已分配给 requirements-analyst: 分析需求
- 场景：workflow: wf-runtime; step: requirements; agent: requirements-analyst
- 做法：任务已分配给 requirements-analyst: 分析需求
- 结果：任务已分配给 requirements-analyst: 分析需求
- 适用前提：适用于 requirements 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: architect|design|design:设计方案 -->
### 经验：design:设计方案
- 场景：workflow: wf-backend; step: design; agent: architect
- 做法：design:设计方案
- 结果：design:设计方案
- 适用前提：适用于 design 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|implement:实现代码 -->
### 经验：implement:实现代码
- 场景：workflow: wf-backend; step: implement; agent: backend-1
- 做法：implement:实现代码
- 结果：implement:实现代码
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|模拟执行: 实现代码 -->
### 经验：模拟执行: 实现代码
- 场景：workflow: wf-simulated; step: implement; agent: backend-1
- 做法：模拟执行: 实现代码
- 结果：模拟执行: 实现代码
- 适用前提：适用于 implement 等类似工作流步骤

## 2026-05-19
<!-- lesson-key: backend-1|implement|done -->
### 经验：done
- 场景：workflow: wf-real-exec-success-shape; step: implement; agent: backend-1
- 做法：done
- 结果：done
- 适用前提：适用于 implement 等类似工作流步骤

