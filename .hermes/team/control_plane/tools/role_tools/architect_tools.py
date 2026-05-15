from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_architecture_doc_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    system_name = str(payload.get("system_name", "Example System"))
    requirements = str(payload.get("requirements", ""))
    doc = f'''# {system_name} 架构设计文档

## 1. 概述

{requirements}

## 2. 架构决策

- **架构风格**: 分层架构 + 微服务
- **技术栈**: Spring Boot + Vue3 + MySQL + Redis
- **部署方式**: Kubernetes + Docker

## 3. 系统边界

```
[用户] → [网关] → [服务层] → [数据层]
```

## 4. 模块划分

| 模块 | 职责 | 技术 |
|---|---|---|
| 网关层 | 路由、鉴权 | Spring Cloud Gateway |
| 服务层 | 业务逻辑 | Spring Boot |
| 数据层 | 持久化 | MyBatis + MySQL |

## 5. 非功能需求

- 可用性: 99.9%
- 响应时间: P99 < 500ms
- 并发: 1000 QPS

## 6. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 单点故障 | 多实例 + 负载均衡 |
| 数据一致性 | 分布式事务 |
'''
    return ToolResult.ok_result(
        content=doc,
        structured_data={"system_name": system_name},
        artifacts=[],
    )


def review_api_design_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    api_spec = str(payload.get("api_spec", ""))
    review = f'''# API 设计评审意见

## 原始设计

```
{api_spec}
```

## 评审意见

### 1. RESTful 规范
- [ ] URL 是否使用名词复数？
- [ ] HTTP 方法是否语义正确？
- [ ] 状态码是否规范？

### 2. 安全性
- [ ] 是否包含鉴权机制？
- [ ] 敏感参数是否加密？
- [ ] 是否有防重放攻击？

### 3. 可维护性
- [ ] 是否有版本控制？
- [ ] 错误信息是否统一？
- [ ] 是否有分页设计？

### 4. 建议

- 建议统一返回格式: {{"code": 0, "data": ..., "message": ""}}
- 建议添加请求 ID 便于追踪
- 建议添加限流和熔断机制
'''
    return ToolResult.ok_result(
        content=review,
        structured_data={"review_points": 4},
        artifacts=[],
    )
