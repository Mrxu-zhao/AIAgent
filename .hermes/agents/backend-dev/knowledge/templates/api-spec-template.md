# API接口规范模板

## 1. 接口基本信息
- **接口名称**：
- **接口路径**：
- **请求方法**：GET/POST/PUT/DELETE/PATCH
- **接口版本**：v1/v2
- **接口状态**：开发中/已发布/已废弃
- **负责人**：

## 2. 请求参数
### 2.1 Path参数
| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|

### 2.2 Query参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|--------|------|------|--------|------|------|

### 2.3 Body参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|--------|------|------|--------|------|------|

## 3. 响应数据
### 3.1 成功响应
```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 3.2 错误响应
```json
{
  "code": 400,
  "message": "参数错误",
  "data": null
}
```

## 4. 错误码
| 错误码 | 错误信息 | 说明 |
|--------|----------|------|
| 200 | success | 成功 |
| 400 | Bad Request | 参数错误 |
| 401 | Unauthorized | 未授权 |
| 403 | Forbidden | 禁止访问 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器内部错误 |

## 5. 接口示例
### 5.1 请求示例
```bash
curl -X POST "https://api.example.com/v1/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "张三",
    "email": "zhangsan@example.com"
  }'
```

### 5.2 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "name": "张三",
    "email": "zhangsan@example.com",
    "createdAt": "2024-01-01T00:00:00Z"
  }
}
```

## 6. 变更日志
| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|----------|--------|
