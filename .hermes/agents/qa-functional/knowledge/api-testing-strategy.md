# 接口测试实战策略

> 作者：郑晓彤 | 创建时间：2026-04-29 | 适用：Java Spring Boot 管理后台 API

## 1. 接口测试分层模型

```
┌─────────────────────────────────────┐
│         UI 自动化测试层             │  ← Playwright/E2E
├─────────────────────────────────────┤
│         业务接口测试层              │  ← Postman/RestAssured
├─────────────────────────────────────┤
│         微服务接口测试层            │  ← 内部接口调用
├─────────────────────────────────────┤
│         单元测试层                  │  ← JUnit/Mockito
└─────────────────────────────────────┘
     本文重点：业务接口测试层
```

---

## 2. 标准响应格式

### 统一响应结构

```java
// 后端标准响应格式
public class ApiResponse<T> {
    private Integer code;      // 状态码：200成功，400参数错误，401未授权，403禁止，404未找到，500服务器错误
    private String message;   // 提示信息
    private T data;           // 响应数据
    private Long timestamp;   // 时间戳
    
    // 成功响应
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(200, "success", data);
    }
    
    // 失败响应
    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null);
    }
}

// 分页响应
public class PageResponse<T> {
    private List<T> list;       // 数据列表
    private Long total;        // 总记录数
    private Integer pageNum;   // 当前页码
    private Integer pageSize;  // 每页条数
    private Integer pages;     // 总页数
}
```

### 接口测试关注点

```markdown
1. 响应状态码是否符合规范
2. 响应结构是否与前端约定一致
3. 错误码是否清晰明确
4. 异常情况是否有友好提示
```

---

## 3. 登录接口测试策略

### 接口信息

```
POST /api/auth/login
Content-Type: application/json

请求参数：
{
    "username": "admin",
    "password": "Admin123!",
    "captcha": "1234",        // 可选，验证码
    "uuid": "xxx"             // 可选，验证码UUID
}

成功响应 (code=200)：
{
    "code": 200,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiJ9...",
        "refreshToken": "xxx",
        "userId": 1,
        "username": "admin",
        "roles": ["ADMIN"],
        "permissions": ["/api/users/*", "/api/depts/*"],
        "expiresIn": 7200
    }
}
```

### 测试用例设计

#### 3.1 正常登录

```markdown
用例编号：API_AUTH_001
用例名称：正常登录-账号密码正确
测试步骤：
  1. POST /api/auth/login
  2. body: {"username": "admin", "password": "Admin123!"}
预期结果：
  - HTTP Status: 200
  - code: 200
  - data.token 不为空
  - data.expiresIn > 0
  - headers 中包含 Set-Cookie（如果使用Cookie）
```

#### 3.2 异常登录场景

```markdown
用例编号：API_AUTH_002
用例名称：登录失败-密码错误
测试步骤：
  1. POST /api/auth/login
  2. body: {"username": "admin", "password": "WrongPassword"}
预期结果：
  - HTTP Status: 200
  - code: 401 或 400
  - message: "用户名或密码错误"
  - data.token 为空

用例编号：API_AUTH_003
用例名称：登录失败-账号不存在
测试步骤：
  1. POST /api/auth/login
  2. body: {"username": "notexist", "password": "AnyPassword"}
预期结果：
  - code: 401 或 400
  - message: "用户名或密码错误"（不要明确提示账号不存在，防爆破）

用例编号：API_AUTH_004
用例名称：登录失败-参数缺失
测试步骤：
  1. POST /api/auth/login
  2. body: {"username": "admin"}
预期结果：
  - code: 400
  - message: "密码不能为空"

用例编号：API_AUTH_005
用例名称：登录失败-账号格式错误
测试步骤：
  1. POST /api/auth/login
  2. body: {"username": "ab", "password": "Admin123!"}
预期结果：
  - code: 400
  - message 包含 "格式" 或 "长度"

用例编号：API_AUTH_006
用例名称：登录失败-密码格式错误
测试步骤：
  1. POST /api/auth/login
  2. body: {"username": "admin", "password": "123"}
预期结果：
  - code: 400
  - message: "密码长度6-20位"

用例编号：API_AUTH_007
用例名称：登录失败-并发登录（同一账号多设备）
测试步骤：
  1. 账号A登录设备1，获取token1
  2. 账号A登录设备2，获取token2
  3. 使用token1访问接口
预期结果：
  - 方案1：token1失效（被顶下线）
  - 方案2：token1仍然有效（多设备登录）
  - 建议：明确业务策略后测试
```

#### 3.3 安全性测试

```markdown
用例编号：API_AUTH_010
用例名称：登录安全-密码加密传输
测试步骤：
  1. 使用抓包工具捕获登录请求
预期结果：
  - 密码字段（password）在请求体中加密或使用HTTPS传输
  - 密码不以明文形式出现在URL参数中

用例编号：API_AUTH_011
用例名称：登录安全-暴力破解防护
测试步骤：
  1. 连续使用错误密码登录同一账号 10 次
  2. 第11次使用正确密码登录
预期结果：
  - 被锁定或需要验证码
  - 正确密码也被拒绝

用例编号：API_AUTH_012
用例名称：登录安全-Token有效性
测试步骤：
  1. 登录获取token
  2. 使用token访问 /api/user/info
  3. 删除token最后一位，再次访问
预期结果：
  - 步骤2：成功
  - 步骤3：401 Unauthorized
```

---

## 4. 列表查询接口测试策略

### 接口信息

```
GET /api/users
Authorization: Bearer {{token}}

Query参数：
  - pageNum: 1              // 页码（默认1）
  - pageSize: 10           // 每页条数（默认10）
  - username: ""           // 用户名（模糊搜索）
  - status: 1              // 状态：1启用，0禁用
  - deptId: 10              // 部门ID
  - startDate: "2024-01-01" // 创建开始日期
  - endDate: "2024-12-31"   // 创建结束日期
  - orderBy: "createTime"   // 排序字段
  - sort: "desc"            // 排序方向：asc/desc

成功响应：
{
    "code": 200,
    "data": {
        "list": [
            {
                "id": 1,
                "username": "admin",
                "email": "admin@company.com",
                "mobile": "13800138000",
                "status": 1,
                "deptName": "技术部",
                "roleNames": ["管理员"],
                "createTime": "2024-01-01 10:00:00"
            }
        ],
        "total": 100,
        "pageNum": 1,
        "pageSize": 10,
        "pages": 10
    }
}
```

### 测试用例设计

#### 4.1 分页功能测试

```markdown
用例编号：API_USER_001
用例名称：分页查询-首页数据
测试步骤：
  1. GET /api/users?pageNum=1&pageSize=10
预期结果：
  - 返回第1-10条数据
  - total 正确
  - pageNum=1, pageSize=10, pages=总页数

用例编号：API_USER_002
用例名称：分页查询-中间页
测试步骤：
  1. GET /api/users?pageNum=5&pageSize=10
预期结果：
  - 返回第41-50条数据
  - pageNum=5

用例编号：API_USER_003
用例名称：分页查询-末页数据
测试步骤：
  1. GET /api/users?pageNum=10&pageSize=10
预期结果：
  - 返回最后10条数据
  - pages=10

用例编号：API_USER_004
用例名称：分页查询-超出总页数
测试步骤：
  1. GET /api/users?pageNum=100&pageSize=10
预期结果：
  - 返回空列表 list=[]
  - total 不变
  - pages 正确

用例编号：API_USER_005
用例名称：分页查询-第0页
测试步骤：
  1. GET /api/users?pageNum=0
预期结果：
  - code: 400（参数校验失败）
  - 或自动修正为 pageNum=1

用例编号：API_USER_006
用例名称：分页查询-负数页码
测试步骤：
  1. GET /api/users?pageNum=-1
预期结果：
  - code: 400
  - message: "页码必须大于0"

用例编号：API_USER_007
用例名称：分页查询-超大分页大小
测试步骤：
  1. GET /api/users?pageNum=1&pageSize=1000
预期结果：
  - 方案1：拒绝请求，返回错误
  - 方案2：使用最大分页限制（如最多100条）

用例编号：API_USER_008
用例名称：分页查询-分页大小为0
测试步骤：
  1. GET /api/users?pageNum=1&pageSize=0
预期结果：
  - code: 400
  - 或使用默认值 pageSize=10
```

#### 4.2 搜索筛选测试

```markdown
用例编号：API_USER_010
用例名称：搜索-用户名模糊匹配
测试步骤：
  1. GET /api/users?username=admin
预期结果：
  - 返回所有 username 包含 "admin" 的用户
  - 支持大小写不敏感

用例编号：API_USER_011
用例名称：搜索-多条件组合
测试步骤：
  1. GET /api/users?username=admin&status=1&deptId=10
预期结果：
  - 同时满足所有条件
  - 结果数量 ≤ 单条件结果

用例编号：API_USER_012
用例名称：搜索-状态筛选
测试步骤：
  1. GET /api/users?status=1
  2. GET /api/users?status=0
预期结果：
  - 步骤1只返回启用用户
  - 步骤2只返回禁用用户

用例编号：API_USER_013
用例名称：搜索-日期范围
测试步骤：
  1. GET /api/users?startDate=2024-01-01&endDate=2024-01-31
预期结果：
  - 返回2024年1月创建的用户
  - 开始日期 <= createTime <= 结束日期

用例编号：API_USER_014
用例名称：搜索-无效日期范围（结束<开始）
测试步骤：
  1. GET /api/users?startDate=2024-12-31&endDate=2024-01-01
预期结果：
  - code: 400
  - message: "结束日期不能早于开始日期"
  - 或忽略参数返回全量数据

用例编号：API_USER_015
用例名称：搜索-无数据匹配
测试步骤：
  1. GET /api/users?username=notexist999
预期结果：
  - 返回空列表 list=[]
  - total=0
```

#### 4.3 排序功能测试

```markdown
用例编号：API_USER_020
用例名称：排序-升序
测试步骤：
  1. GET /api/users?orderBy=createTime&sort=asc
预期结果：
  - 结果按 createTime 从早到晚排序

用例编号：API_USER_021
用例名称：排序-降序
测试步骤：
  1. GET /api/users?orderBy=createTime&sort=desc
预期结果：
  - 结果按 createTime 从晚到早排序

用例编号：API_USER_022
用例名称：排序-非法排序字段
测试步骤：
  1. GET /api/users?orderBy=xxx
预期结果：
  - code: 400
  - 或忽略排序参数使用默认排序
```

---

## 5. 增删改查（CRUD）测试策略

### 5.1 创建（Create）

```markdown
POST /api/users

请求体：
{
    "username": "newuser",
    "password": "Pass123!",
    "email": "newuser@company.com",
    "mobile": "13800138001",
    "deptId": 10,
    "roleIds": [1, 2],
    "status": 1
}
```

```markdown
用例编号：API_USER_C001
用例名称：创建用户-正常创建
测试步骤：
  1. POST /api/users
  2. body: {完整且正确的信息}
预期结果：
  - code: 200
  - 返回新用户ID
  - 数据库中新增一条记录

用例编号：API_USER_C002
用例名称：创建用户-必填字段缺失
测试步骤：
  1. POST /api/users
  2. body: {username: "newuser"}  // 缺少password等必填字段
预期结果：
  - code: 400
  - message 列出缺失的必填字段

用例编号：API_USER_C003
用例名称：创建用户-用户名重复
测试步骤：
  1. POST /api/users
  2. body: {username: "existing"}  // 使用已存在的用户名
预期结果：
  - code: 400
  - message: "用户名已存在"

用例编号：API_USER_C004
用例名称：创建用户-字段格式校验
测试步骤：
  1. POST /api/users
  2. body: {email: "invalid-email", mobile: "123"}
预期结果：
  - code: 400
  - message 包含格式错误提示

用例编号：API_USER_C005
用例名称：创建用户-无权限
测试步骤：
  1. 使用普通用户token
  2. POST /api/users
预期结果：
  - code: 403
  - message: "无权限创建用户"
```

### 5.2 查询（Read）

```markdown
GET /api/users/{id}
```

```markdown
用例编号：API_USER_R001
用例名称：查询用户-正常查询
测试步骤：
  1. GET /api/users/1
预期结果：
  - code: 200
  - 返回用户完整信息

用例编号：API_USER_R002
用例名称：查询用户-ID不存在
测试步骤：
  1. GET /api/users/999999
预期结果：
  - code: 404
  - message: "用户不存在"

用例编号：API_USER_R003
用例名称：查询用户-非法ID格式
测试步骤：
  1. GET /api/users/abc
预期结果：
  - code: 400
  - message: "ID格式错误"

用例编号：API_USER_R004
用例名称：查询用户-无权限查看
测试步骤：
  1. 用户A尝试查看用户B的数据
预期结果：
  - code: 403 或 返回空（根据业务策略）
```

### 5.3 更新（Update）

```markdown
PUT /api/users/{id}

请求体：
{
    "email": "newemail@company.com",
    "mobile": "13900139000",
    "status": 1
}
```

```markdown
用例编号：API_USER_U001
用例名称：更新用户-正常更新
测试步骤：
  1. PUT /api/users/1
  2. body: {email: "new@company.com"}
预期结果：
  - code: 200
  - 数据库中 email 已更新
  - 返回更新后的用户信息

用例编号：API_USER_U002
用例名称：更新用户-部分更新
测试步骤：
  1. PUT /api/users/1
  2. body: {email: "new@company.com"}  // 只更新email
预期结果：
  - 其他字段保持不变
  - email 已更新

用例编号：API_USER_U003
用例名称：更新用户-更新不存在的用户
测试步骤：
  1. PUT /api/users/999999
  2. body: {...}
预期结果：
  - code: 404
  - message: "用户不存在"

用例编号：API_USER_U004
用例名称：更新用户-乐观锁冲突
测试步骤：
  1. 用户A获取用户数据（version=1）
  2. 用户B更新同一用户（version变为2）
  3. 用户A提交更新（version=1，数据库已是2）
预期结果：
  - code: 409 或 400
  - message: "数据已被修改，请刷新后重试"

用例编号：API_USER_U005
用例名称：更新用户-禁止修改敏感字段
测试步骤：
  1. PUT /api/users/1
  2. body: {password: "hacked"}  // 尝试修改密码
预期结果：
  - code: 400
  - 或忽略该字段（更新接口不应允许直接改密码）
```

### 5.4 删除（Delete）

```markdown
DELETE /api/users/{id}
```

```markdown
用例编号：API_USER_D001
用例名称：删除用户-正常删除
测试步骤：
  1. DELETE /api/users/100
预期结果：
  - code: 200
  - message: "删除成功"
  - 数据库中该记录被删除或标记为已删除

用例编号：API_USER_D002
用例名称：删除用户-批量删除
测试步骤：
  1. DELETE /api/users?ids=1,2,3
预期结果：
  - 批量删除成功
  - 返回删除数量

用例编号：API_USER_D003
用例名称：删除用户-ID不存在
测试步骤：
  1. DELETE /api/users/999999
预期结果：
  - code: 404 或 200（幂等性）
  - 建议：返回成功（幂等），避免重复删除报错

用例编号：API_USER_D004
用例名称：删除用户-有关联数据
测试步骤：
  1. 用户有关联订单/审批记录
  2. 尝试删除该用户
预期结果：
  - code: 400
  - message: "该用户有关联数据，无法删除"
  - 或提示具体关联项

用例编号：API_USER_D005
用例名称：删除用户-禁止删除自己
测试步骤：
  1. 使用当前登录用户token
  2. DELETE /api/users/{当前用户ID}
预期结果：
  - code: 400
  - message: "不允许删除当前登录账号"

用例编号：API_USER_D006
用例名称：删除用户-禁止删除管理员
测试步骤：
  1. DELETE /api/users/1  // 系统管理员
预期结果：
  - code: 400
  - message: "系统管理员不允许删除"
```

---

## 6. 关联接口测试

### 6.1 审批流程测试

```markdown
流程：提交申请 → 部门经理审核 → 财务复核 → 完成

用例编号：API_FLOW_001
用例名称：审批流-完整正常流程
测试步骤：
  1. 用户A提交采购申请（POST /api/orders）
  2. 获取申请ID
  3. 部门经理B审核通过（POST /api/orders/{id}/approve）
  4. 财务C复核通过（POST /api/orders/{id}/finance-approve）
预期结果：
  - 每步都返回成功
  - 最终状态变为"已完成"

用例编号：API_FLOW_002
用例名称：审批流-驳回重提
测试步骤：
  1. 提交申请
  2. 部门经理驳回（原因：预算不足）
  3. 修改申请内容
  4. 重新提交
预期结果：
  - 驳回后状态变为"已驳回"
  - 重提后状态变为"待审核"

用例编号：API_FLOW_003
用例名称：审批流-并发审批
测试步骤：
  1. 提交申请
  2. 用户B和用户C同时审批
预期结果：
  - 只有一人成功
  - 另一人收到"该申请已被处理"的提示

用例编号：API_FLOW_004
用例名称：审批流-越权审批
测试步骤：
  1. 普通员工尝试审批（应该由经理审批）
预期结果：
  - code: 403
  - message: "无审批权限"
```

---

## 7. 接口测试检查清单

### 通用检查项

```markdown
□ 正常参数返回正确数据
□ 异常参数返回友好错误提示
□ 必填参数校验
□ 参数格式校验（邮箱、手机号、日期等）
□ 参数边界值测试（0、最大值、负数、超长）
□ 未授权访问返回401
□ 无权限访问返回403
□ 资源不存在返回404
□ 服务器错误返回500
□ 响应时间在可接受范围内（<2s）
□ 敏感数据脱敏（密码不返回）
□ 列表为空时返回空数组[]而非null
□ 分页参数边界测试
□ 排序功能正常
□ 中文/特殊字符处理
□ SQL注入防护（输入 '; DROP TABLE）
□ XSS防护（输入 <script>alert(1)</script>）
```

### 安全检查项

```markdown
□ Token过期后访问返回401
□ 刷新Token功能正常
□ 禁止Token在URL中传递（应放在Header）
□ 禁止明文密码在日志中输出
□ 敏感操作（删除/修改）有审计日志
□ 防止CSRF攻击（如果使用Cookie）
□ 接口限流（防止恶意刷接口）
```

---

*文档版本：v1.0*
*后续更新：补充实际项目的接口测试案例*
