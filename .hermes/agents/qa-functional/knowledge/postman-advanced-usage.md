# Postman 高级用法指南

> 作者：郑晓彤 | 创建时间：2026-04-29 | 版本：Postman 10.x | 适用：Spring Boot API 测试

## 1. 环境变量配置

### 环境分层策略

```
开发环境（Development）
  - Base URL: http://localhost:8080
  - 数据库：本地 MySQL
  - 调试模式：开启

测试环境（Testing）
  - Base URL: http://test-api.company.com
  - 数据库：测试 MySQL
  - 测试数据：隔离

预发布环境（Staging）
  - Base URL: https://staging-api.company.com
  - 数据库：预发布 MySQL

生产环境（Production）
  - Base URL: https://api.company.com
  - 数据库：生产 MySQL
```

### 环境变量配置示例

```javascript
// Development 环境变量
{
  "baseUrl": "http://localhost:8080",
  "adminToken": "eyJhbGciOiJIUzI1NiJ9.xxx",
  "adminUsername": "admin",
  "adminPassword": "Admin123!",
  "testUserId": "1001",
  "testDeptId": "10"
}

// Testing 环境变量
{
  "baseUrl": "https://test-api.company.com",
  "adminToken": "eyJhbGciOiJIUzI1NiJ9.yyy",
  "adminUsername": "test_admin",
  "adminPassword": "Test@2024",
  "testUserId": "2001",
  "testDeptId": "20"
}
```

### 全局变量 vs 环境变量

| 类型 | 作用域 | 使用场景 |
|------|--------|----------|
| 全局变量 | 所有环境 | Token、公共配置 |
| 环境变量 | 单个环境 | 环境特定 URL、账号 |

```javascript
// 在 Pre-request Script 中设置全局变量
pm.globals.set("global_token", "xxx");

// 引用变量
// {{baseUrl}}/api/users 或 {{adminToken}}
```

---

## 2. 集合（Collection）组织结构

### 推荐的集合结构

```
公司管理后台 API
├── 00_认证模块
│   ├── 登录
│   ├── 登出
│   ├── 获取用户信息
│   └── 刷新Token
├── 01_用户管理
│   ├── 查询用户列表
│   ├── 创建用户
│   ├── 更新用户
│   ├── 删除用户
│   └── 重置密码
├── 02_部门管理
│   ├── 查询部门树
│   ├── 创建部门
│   ├── 更新部门
│   └── 删除部门
├── 03_角色权限
│   ├── 查询角色列表
│   ├── 分配角色权限
│   └── 角色绑定用户
├── 04_业务模块
│   ├── 订单管理
│   ├── 审批流程
│   └── 数据报表
└── 05_系统配置
    ├── 系统参数
    └── 日志查询
```

### 集合变量配置

```javascript
// 集合初始化脚本 (Collection -> Pre-request Script)
pm.collectionVariables.set("defaultPageSize", "20");
pm.collectionVariables.set("maxUploadSize", "10485760"); // 10MB
```

---

## 3. Pre-request Script 自动化

### 自动登录获取Token

```javascript
// 在认证模块的"登录"请求的 Tests 中保存 Token
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    if (jsonData.code === 200 && jsonData.data) {
        // 保存 token 到环境变量
        pm.environment.set("accessToken", jsonData.data.token);
        pm.environment.set("refreshToken", jsonData.data.refreshToken);
        pm.environment.set("userId", jsonData.data.userId);
        
        console.log("Token saved: " + jsonData.data.token);
    }
}
```

### 自动刷新 Token

```javascript
// 在需要认证的请求的 Pre-request Script 中
var accessToken = pm.environment.get("accessToken");
var refreshToken = pm.environment.get("refreshToken");

// 如果没有token或即将过期，先刷新
if (!accessToken || isTokenExpired()) {
    pm.sendRequest({
        url: pm.environment.get("baseUrl") + "/api/auth/refresh",
        method: 'POST',
        header: {
            'Content-Type': 'application/json'
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                refreshToken: refreshToken
            })
        }
    }, function(err, res) {
        if (res.status === 200) {
            var data = res.json();
            pm.environment.set("accessToken", data.data.token);
        }
    });
}

function isTokenExpired() {
    // 检查 token 是否过期（假设 token 24小时有效）
    var tokenTime = pm.environment.get("tokenTime");
    if (!tokenTime) return true;
    
    var expiresIn = 24 * 60 * 60 * 1000; // 24小时
    return Date.now() - parseInt(tokenTime) > expiresIn;
}
```

### 自动添加认证头

```javascript
// Collection 级别的 Pre-request Script
var token = pm.environment.get("accessToken");
if (token) {
    pm.request.headers.add({
        key: "Authorization",
        value: "Bearer " + token
    });
}
```

### 时间戳和随机数生成

```javascript
// 生成时间戳
pm.variables.set("timestamp", Date.now());

// 生成随机字符串
pm.variables.set("randomString", 
    Math.random().toString(36).substring(2, 15) + 
    Math.random().toString(36).substring(2, 15)
);

// 生成唯一ID（用于测试数据隔离）
pm.variables.set("uniqueEmail", 
    "test_" + Date.now() + "@company.com"
);
```

---

## 4. Tests 脚本断言实战

### 标准响应断言

```javascript
// 基础状态码断言
pm.test("状态码为200", function() {
    pm.response.to.have.status(200);
});

// JSON 响应断言
pm.test("返回码正确", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.code).to.eql(200);
});

pm.test("返回数据不为空", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.data).to.not.be.null;
    pm.expect(jsonData.data).to.be.an('object');
});

// 数组长度断言
pm.test("用户列表至少有一条数据", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.data.list).to.have.length.above(0);
});

// 字段值断言
pm.test("用户名正确", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.data.username).to.eql("admin");
    pm.expect(jsonData.data.status).to.be.oneOf([0, 1]);
});
```

### 数据验证断言

```javascript
// 验证数据结构
pm.test("返回字段完整", function() {
    var jsonData = pm.response.json();
    var requiredFields = ['id', 'username', 'email', 'status', 'createTime'];
    
    requiredFields.forEach(function(field) {
        pm.expect(jsonData.data).to.have.property(field);
    });
});

// 验证数据类型
pm.test("数据类型正确", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.data.id).to.be.a('number');
    pm.expect(jsonData.data.username).to.be.a('string');
    pm.expect(jsonData.data.status).to.be.a('number');
    pm.expect(jsonData.data.tags).to.be.an('array');
});

// 验证分页结构
pm.test("分页数据结构正确", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.data).to.have.property('total');
    pm.expect(jsonData.data).to.have.property('pageNum');
    pm.expect(jsonData.data).to.have.property('pageSize');
    pm.expect(jsonData.data).to.have.property('list');
    
    // 验证分页计算正确
    var total = jsonData.data.total;
    var pageSize = jsonData.data.pageSize;
    var totalPages = Math.ceil(total / pageSize);
    pm.expect(jsonData.data.pages).to.eql(totalPages);
});
```

### 响应时间断言

```javascript
pm.test("响应时间小于500ms", function() {
    pm.expect(pm.response.responseTime).to.be.below(500);
});

pm.test("响应时间小于2000ms", function() {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});
```

### Header 断言

```javascript
pm.test("Content-Type正确", function() {
    pm.response.headers.has("Content-Type");
    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
});
```

---

## 5. 业务场景自动化

### 完整 CRUD 测试流程

```javascript
// ====== 创建用户 ======
// POST /api/users
var createResponse = pm.response.json();
pm.test("创建用户成功", function() {
    pm.expect(createResponse.code).to.eql(200);
});

// 保存创建的用户ID供后续使用
if (createResponse.code === 200) {
    pm.collectionVariables.set("createdUserId", createResponse.data.id);
}

// ====== 查询用户 ======
// GET /api/users/{{createdUserId}}
pm.test("查询用户成功", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.code).to.eql(200);
    pm.expect(jsonData.data.id).to.eql(parseInt(pm.collectionVariables.get("createdUserId")));
});

// ====== 更新用户 ======
// PUT /api/users/{{createdUserId}}
pm.test("更新用户成功", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.code).to.eql(200);
});

// ====== 删除用户 ======
// DELETE /api/users/{{createdUserId}}
pm.test("删除用户成功", function() {
    var jsonData = pm.response.json();
    pm.expect(jsonData.code).to.eql(200);
});

// ====== 验证删除 ======
// GET /api/users/{{createdUserId}} (应该在Tests中使用 pm.sendRequest)
// pm.test("用户已删除", function() {
//     pm.expect(response.code).to.eql(404);
// });
```

### 数据驱动测试

```javascript
// 在 Tests 中定义测试数据
var testData = [
    { username: "test001", email: "test001@company.com", expected: 200 },
    { username: "test002", email: "test002@company.com", expected: 200 },
    { username: "", email: "test@company.com", expected: 400 },
    { username: "ab", email: "invalid-email", expected: 400 }
];

// 从环境变量或数据文件读取
// var testData = pm.variables.get("userTestData");

testData.forEach(function(data) {
    pm.test("测试用户: " + data.username, function() {
        var jsonData = pm.response.json();
        pm.expect(jsonData.code).to.eql(data.expected);
    });
});
```

### 批量数据清理

```javascript
// 测试结束后清理测试数据
// 在 Collection 或 Folder 的 Trash 图标中使用

var createdIds = pm.collectionVariables.get("createdUserIds") || [];

// 使用 Postman API 或直接调用清理接口
createdIds.forEach(function(id) {
    pm.sendRequest({
        url: pm.environment.get("baseUrl") + "/api/users/" + id,
        method: 'DELETE',
        header: {
            'Authorization': 'Bearer ' + pm.environment.get("accessToken")
        }
    });
});

// 清空记录
pm.collectionVariables.set("createdUserIds", []);
```

---

## 6. 集合运行器（Collection Runner）

### 配置运行计划

```
运行设置：
├── 迭代次数：10（使用不同数据文件）
├── 延迟：500ms（避免请求过快）
├── 日志：详细
├── 数据文件：users_test_data.csv
└── 保存响应：✓

环境变量：
└── Testing 环境

输出报告：
├── HTML 报告
├── JSON 报告
└── JUnit XML 报告（对接CI/CD）
```

### CSV 数据文件格式

```csv
username,email,password,mobile,expectedCode
test_user_001,user001@company.com,Test123456,13800001001,200
test_user_002,user002@company.com,Test123456,13800001002,200
test_user_003,,Test123456,,400
test_user_004,user004@company.com,,,400
test_user_005,invalid_email,Test123456,13800001005,400
```

---

## 7. Mock Server（接口模拟）

### 创建 Mock Server

```javascript
// 模拟登录接口
pm.mock.add(
    {
        name: "Mock Login",
        method: "POST",
        url: pm.environment.get("baseUrl") + "/api/auth/login",
        mode: "draft",
        responses: [
            {
                status: 200,
                body: {
                    code: 200,
                    message: "success",
                    data: {
                        token: "mock_token_123",
                        userId: 1001,
                        username: "mock_user"
                    }
                }
            }
        ]
    },
    function(err, mock) {
        console.log("Mock created:", mock.name);
    }
);
```

### 条件响应

```javascript
// 根据请求参数返回不同响应
if (pm.request.body.raw.includes("admin")) {
    response = {
        status: 200,
        body: {
            code: 200,
            data: { role: "admin" }
        }
    };
} else {
    response = {
        status: 200,
        body: {
            code: 200,
            data: { role: "user" }
        }
    };
}
```

---

## 8. 常见问题排查

### Token 失效问题

```javascript
// 问题：请求返回 401 Unauthorized
// 排查步骤：

// 1. 检查环境变量是否设置了 token
console.log("Current Token:", pm.environment.get("accessToken"));

// 2. 检查请求头是否正确添加
console.log("Request Headers:", pm.request.headers);

// 3. 检查 token 是否过期
// 重新执行登录接口获取新 token
```

### 中文乱码问题

```javascript
// 问题：响应中文显示乱码
// 解决方案：在请求头添加 Accept-Charset

pm.request.headers.add({
    key: "Accept-Charset",
    value: "UTF-8"
});

// 或在 Tests 中解码
var responseBody = pm.response.text();
var jsonData = JSON.parse(responseBody);
```

### 请求超时问题

```javascript
// 问题：请求超时
// 解决方案：增加超时时间或优化接口

// 在 Collection Settings 中设置
{
    "timeout": 30000  // 30秒
}

// 或使用 pm.sendRequest 时指定
pm.sendRequest({
    url: "...",
    timeout: 60000  // 60秒
}, callback);
```

---

## 附录：常用代码片段

### JSON Schema 验证

```javascript
var schema = {
    "type": "object",
    "properties": {
        "code": { "type": "integer" },
        "message": { "type": "string" },
        "data": {
            "type": "object",
            "properties": {
                "id": { "type": "integer" },
                "username": { "type": "string" }
            },
            "required": ["id", "username"]
        }
    },
    "required": ["code", "data"]
};

pm.test("JSON Schema 验证", function() {
    var jsonData = pm.response.json();
    tv4.validateResult(jsonData, schema, true, true);
    if (!tv4.validateResult.valid) {
        console.log("Schema errors:", tv4.error);
    }
});
```

### 设置 Cookie

```javascript
// 自动保存和发送 Cookie
pm.request.headers.add({
    key: "Cookie",
    value: pm.environment.get("cookies")
});
```

---

*文档版本：v1.0*
*后续更新：补充 Newman CI/CD 集成示例*
