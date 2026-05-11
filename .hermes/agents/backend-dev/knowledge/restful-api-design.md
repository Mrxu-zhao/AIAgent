# RESTful API 设计规范

## 1. URL 规范

### 1.1 基本格式

```
协议://域名/版本/模块/资源/{id}/子资源
```

示例：
```
https://api.example.com/v1/users/123/orders
```

### 1.2 命名规范

| 规范 | 正确 | 错误 |
|------|------|------|
| 使用名词复数 | `/users` | `/user`, `/getUser` |
| 小写字母 | `/user-roles` | `/userRoles` |
| 层级不过深 | `/users/123/orders` | `/users/123/orders/456/items/789` |
| 不用动词 | `/users` | `/getUsers`, `/createUser` |

### 1.3 HTTP 方法对应

| 方法 | 用途 | 示例 |
|------|------|------|
| GET | 查询 | `GET /users/123` |
| POST | 创建 | `POST /users` |
| PUT | 全量更新 | `PUT /users/123` |
| PATCH | 部分更新 | `PATCH /users/123` |
| DELETE | 删除 | `DELETE /users/123` |

## 2. 请求参数规范

### 2.1 Query 参数

```
GET /users?status=1&page=1&size=20&sort=createTime,desc
```

### 2.2 Path 参数

```
GET /users/{id}
GET /users/{userId}/orders/{orderId}
```

### 2.3 Header 参数

```
Content-Type: application/json
Authorization: Bearer {token}
X-Request-Id: uuid
```

### 2.4 请求体

```json
{
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "age": 25,
    "roles": ["admin", "user"]
}
```

## 3. 响应格式规范

### 3.1 统一响应结构

```json
{
    "code": 200,
    "message": "success",
    "data": { },
    "timestamp": 1714378800000,
    "requestId": "uuid-string"
}
```

### 3.2 成功响应

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ApiResponse<T> {
    private int code;
    private String message;
    private T data;
    private long timestamp;
    private String requestId;
    
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(200, "success", data, 
            System.currentTimeMillis(), getRequestId());
    }
    
    public static <T> ApiResponse<T> success() {
        return success(null);
    }
}
```

### 3.3 分页响应

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "records": [...],
        "total": 100,
        "size": 20,
        "current": 1,
        "pages": 5
    },
    "timestamp": 1714378800000
}
```

### 3.4 错误响应

```json
{
    "code": 400,
    "message": "参数校验失败",
    "errors": [
        {
            "field": "username",
            "message": "用户名不能为空"
        },
        {
            "field": "email",
            "message": "邮箱格式不正确"
        }
    ],
    "timestamp": 1714378800000
}
```

## 4. HTTP 状态码

| 状态码 | 说明 | 使用场景 |
|--------|------|----------|
| 200 | OK | 成功 |
| 201 | Created | 创建成功 |
| 204 | No Content | 删除成功（无返回体） |
| 400 | Bad Request | 参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 冲突（如重复创建） |
| 422 | Unprocessable | 业务校验失败 |
| 500 | Server Error | 服务器错误 |

## 5. 版本控制

### 5.1 URL 路径版本

```
/v1/users
/v2/users
```

### 5.2 Header 版本

```
Accept: application/vnd.api+json;version=2
```

推荐使用 URL 路径版本，更直观。

## 6. Controller 示例

```java
@RestController
@RequestMapping("/v1/users")
@RequiredArgsConstructor
@Slf4j
public class UserController {
    
    private final UserService userService;
    
    @GetMapping("/{id}")
    public ApiResponse<UserVO> getUser(@PathVariable Long id) {
        return ApiResponse.success(userService.getById(id));
    }
    
    @GetMapping
    public ApiResponse<PageResult<UserVO>> listUsers(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) Integer status) {
        return ApiResponse.success(userService.page(page, size, status));
    }
    
    @PostMapping
    public ApiResponse<Long> createUser(@RequestBody @Valid UserCreateDTO dto) {
        return ApiResponse.success(userService.create(dto));
    }
    
    @PutMapping("/{id}")
    public ApiResponse<Void> updateUser(
            @PathVariable Long id,
            @RequestBody @Valid UserUpdateDTO dto) {
        dto.setId(id);
        userService.update(dto);
        return ApiResponse.success();
    }
    
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteUser(@PathVariable Long id) {
        userService.delete(id);
    }
}
```

## 7. 安全规范

1. **敏感数据加密传输** - HTTPS
2. **认证授权** - JWT Token / OAuth2
3. **参数校验** - 使用 @Valid 注解
4. **限流** - 防止接口滥用
5. **日志脱敏** - 手机号、身份证等打码

---

*作者: 陈启明*
*更新: 2026-04-29*
