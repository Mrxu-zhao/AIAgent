# Mock数据管理模板

## 1. Mock数据基本信息
- **所属模块**：
- **接口名称**：
- **接口路径**：
- **数据类型**：静态数据/动态数据/代理数据

## 2. 数据定义

### 2.1 数据模型
```typescript
interface User {
  id: number;
  name: string;
  email: string;
  avatar: string;
  status: 'active' | 'inactive';
  createdAt: string;
}
```

### 2.2 示例数据
```json
{
  "id": 1,
  "name": "张三",
  "email": "zhangsan@example.com",
  "avatar": "https://example.com/avatar.jpg",
  "status": "active",
  "createdAt": "2024-01-01T00:00:00Z"
}
```

## 3. Mock规则

### 3.1 静态Mock
- **规则**：固定返回示例数据
- **适用场景**：开发初期、接口未就绪
- **配置方式**：
```javascript
// mock/user.js
export default {
  'GET /api/users/:id': {
    id: 1,
    name: '张三',
    email: 'zhangsan@example.com'
  }
}
```

### 3.2 动态Mock
- **规则**：根据参数动态生成数据
- **适用场景**：需要模拟多种场景
- **配置方式**：
```javascript
// mock/user.js
export default {
  'GET /api/users/:id': (req, res) => {
    const { id } = req.params;
    res.json({
      id: Number(id),
      name: `用户${id}`,
      email: `user${id}@example.com`
    });
  }
}
```

### 3.3 代理Mock
- **规则**：代理到真实服务或第三方Mock平台
- **适用场景**：需要真实数据验证
- **配置方式**：
```javascript
// vite.config.js
server: {
  proxy: {
    '/api': 'http://localhost:8080'
  }
}
```

## 4. 场景覆盖
| 场景 | 参数 | 响应 | 说明 |
|------|------|------|------|
| 正常场景 | id=1 | 200 + 用户数据 | |
| 用户不存在 | id=999 | 404 + 错误信息 | |
| 参数错误 | id=abc | 400 + 错误信息 | |
| 服务器错误 | id=500 | 500 + 错误信息 | |

## 5. 数据维护
- **更新频率**：
- **维护责任人**：
- **变更记录**：

## 6. 附录
- **Mock工具**：Mock.js / MSW / Vite Plugin
- **文档链接**：
