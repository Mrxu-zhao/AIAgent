# RESTful API 设计最佳实践

## URL 设计规范

### 基本原则

```
GET    /users          # 获取用户列表
GET    /users/{id}     # 获取单个用户
POST   /users          # 创建用户
PUT    /users/{id}     # 更新用户（完整）
PATCH  /users/{id}     # 部分更新
DELETE /users/{id}     # 删除用户
```

### 资源命名

| 场景 | 错误 | 正确 |
|------|------|------|
| 获取用户订单 | GET /getUserOrders | GET /users/{id}/orders |
| 批量操作 | POST /batchDelete | POST /users/batch-delete |
| 搜索 | GET /searchUsers | GET /users/search |

### 嵌套资源

```
GET /users/{userId}/orders/{orderId}     # 用户的订单
GET /orders/{orderId}/items              # 订单的商品明细
```

---

## HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | OK | 成功响应 |
| 201 | Created | 资源创建成功 |
| 204 | No Content | 删除成功，无返回 |
| 400 | Bad Request | 参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable Entity | 校验失败 |
| 500 | Internal Server Error | 服务器错误 |

---

## 统一响应格式

### 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "name": "张三",
    "email": "zhangsan@example.com"
  },
  "timestamp": "2026-04-29T12:00:00Z"
}
```

### 分页响应

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [...],
    "pagination": {
      "current": 1,
      "size": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

### 错误响应

```json
{
  "code": 400,
  "message": "参数校验失败",
  "errors": [
    {"field": "email", "message": "邮箱格式不正确"},
    {"field": "age", "message": "年龄必须在18-60之间"}
  ],
  "timestamp": "2026-04-29T12:00:00Z"
}
```

---

## 过滤器与排序

### 查询参数

```
GET /users?status=active&page=1&size=20&sort=createdTime,desc
```

### 搜索与过滤

```
GET /users/search?name=张三&email=@example.com&status=active
```

---

## 版本管理

### URL 版本（推荐）

```
/api/v1/users
/api/v2/users
```

### Header 版本

```
Accept: application/vnd.api.v2+json
```

---

## 安全最佳实践

1. **参数校验**：使用 @Valid 注解
2. **限流**：防止DDoS攻击
3. **敏感数据**：脱敏处理后再返回
4. **幂等性**：POST 请求需考虑幂等设计

---

## 接口文档示例

```yaml
/openapi/v1/users:
  get:
    summary: 获取用户列表
    parameters:
      - name: page
        in: query
        schema:
          type: integer
          default: 1
      - name: size
        in: query
        schema:
          type: integer
          default: 20
    responses:
      '200':
        description: 成功
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UserListResponse'
```

---

*文档类型：后端技术规范*
*适用范围：前后端开发*
*最后更新：2026-04-29*
