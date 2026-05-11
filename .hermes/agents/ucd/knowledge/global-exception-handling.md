# 全局异常处理方案

## 1. 核心组件

### 1.1 自定义异常

```java
// 业务异常
@Getter
public class BusinessException extends RuntimeException {
    private final int code;
    private final String message;
    
    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
        this.message = message;
    }
    
    public BusinessException(BusinessExceptionCode code) {
        this(code.getCode(), code.getMessage());
    }
}

// 异常码定义
public enum BusinessExceptionCode {
    USER_NOT_FOUND(1001, "用户不存在"),
    USER_ALREADY_EXISTS(1002, "用户已存在"),
    INVALID_PASSWORD(1003, "密码错误"),
    PERMISSION_DENIED(2001, "无权限访问"),
    RESOURCE_NOT_FOUND(3001, "资源不存在");
    
    private final int code;
    private final String message;
    
    BusinessExceptionCode(int code, String message) {
        this.code = code;
        this.message = message;
    }
    
    public int getCode() { return code; }
    public String getMessage() { return message; }
}
```

### 1.2 全局异常处理器

```java
@Slf4j
@RestControllerAdvice
@RequiredArgsConstructor
public class GlobalExceptionHandler {
    
    // 业务异常
    @ExceptionHandler(BusinessException.class)
    public ApiResponse<Void> handleBusinessException(BusinessException e) {
        log.warn("业务异常: code={}, message={}", e.getCode(), e.getMessage());
        return ApiResponse.error(e.getCode(), e.getMessage());
    }
    
    // 参数校验异常
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ApiResponse<Void> handleValidationException(
            MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
            .map(error -> error.getField() + ": " + error.getDefaultMessage())
            .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", message);
        return ApiResponse.error(400, message);
    }
    
    // 绑定异常
    @ExceptionHandler(BindException.class)
    public ApiResponse<Void> handleBindException(BindException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
            .map(error -> error.getField() + ": " + error.getDefaultMessage())
            .collect(Collectors.joining("; "));
        return ApiResponse.error(400, message);
    }
    
    // 实体类校验异常
    @ExceptionHandler(ConstraintViolationException.class)
    public ApiResponse<Void> handleConstraintViolation(
            ConstraintViolationException e) {
        String message = e.getConstraintViolations().stream()
            .map(v -> v.getPropertyPath() + ": " + v.getMessage())
            .collect(Collectors.joining("; "));
        return ApiResponse.error(400, message);
    }
    
    // 404 异常
    @ExceptionHandler(NoHandlerFoundException.class)
    public ApiResponse<Void> handleNotFoundException(
            NoHandlerFoundException e) {
        return ApiResponse.error(404, "接口不存在: " + e.getRequestURL());
    }
    
    // 类型转换异常
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ApiResponse<Void> handleHttpMessageNotReadable(
            HttpMessageNotReadableException e) {
        log.warn("请求体解析失败: {}", e.getMessage());
        return ApiResponse.error(400, "请求体格式错误");
    }
    
    // 文件上传异常
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ApiResponse<Void> handleMaxUploadSizeExceeded(
            MaxUploadSizeExceededException e) {
        return ApiResponse.error(400, "文件大小超过限制");
    }
    
    // 权限异常
    @ExceptionHandler(AccessDeniedException.class)
    public ApiResponse<Void> handleAccessDenied(AccessDeniedException e) {
        return ApiResponse.error(403, "无权限访问");
    }
    
    // 认证异常
    @ExceptionHandler({AuthenticationException.class, 
            UnauthorizedException.class})
    public ApiResponse<Void> handleAuthenticationException(Exception e) {
        return ApiResponse.error(401, "未认证");
    }
    
    // 其他异常
    @ExceptionHandler(Exception.class)
    public ApiResponse<Void> handleException(Exception e) {
        log.error("系统异常", e);
        return ApiResponse.error(500, "系统错误");
    }
}
```

### 1.3 ApiResponse 定义

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
    
    public static <T> ApiResponse<T> error(int code, String message) {
        return new ApiResponse<>(code, message, null, 
            System.currentTimeMillis(), getRequestId());
    }
    
    private static String getRequestId() {
        // 从 RequestContextHolder 获取或生成
        HttpServletRequest request = getRequest();
        if (request != null) {
            String requestId = request.getHeader("X-Request-Id");
            if (requestId != null) return requestId;
        }
        return UUID.randomUUID().toString();
    }
}
```

## 2. 异常使用示例

### 2.1 Service 层抛出异常

```java
@Service
@RequiredArgsConstructor
public class UserService {
    
    private final UserMapper userMapper;
    
    public User getById(Long id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(
                BusinessExceptionCode.USER_NOT_FOUND);
        }
        return user;
    }
    
    public void create(User user) {
        // 检查用户名是否存在
        User existUser = userMapper.selectByUsername(user.getUsername());
        if (existUser != null) {
            throw new BusinessException(
                BusinessExceptionCode.USER_ALREADY_EXISTS);
        }
        userMapper.insert(user);
    }
}
```

### 2.2 Controller 层异常处理

```java
@RestController
@RequestMapping("/v1/users")
@RequiredArgsConstructor
public class UserController {
    
    private final UserService userService;
    
    @GetMapping("/{id}")
    public ApiResponse<UserVO> getUser(@PathVariable Long id) {
        // 异常由 GlobalExceptionHandler 统一处理
        UserVO userVO = userService.getById(id);
        return ApiResponse.success(userVO);
    }
}
```

## 3. 常见异常处理

### 3.1 MyBatis 异常

```java
@ExceptionHandler(PersistenceException.class)
public ApiResponse<Void> handlePersistenceException(
        PersistenceException e) {
    // MyBatis 异常包装
    Throwable cause = e.getCause();
    if (cause instanceof org.springframework.dao.DuplicateKeyException) {
        return ApiResponse.error(409, "数据已存在");
    }
    if (cause instanceof org.springframework.dao.DataIntegrityViolationException) {
        return ApiResponse.error(400, "数据完整性违规");
    }
    log.error("数据库异常", e);
    return ApiResponse.error(500, "数据库错误");
}
```

### 3.2 异步异常

```java
// 异步方法的异常需要特殊处理
@Async
public void asyncProcess(Long id) {
    try {
        doProcess(id);
    } catch (Exception e) {
        // 异步异常不能被 @ControllerAdvice 捕获
        // 需要记录日志或发送消息通知
        log.error("异步处理失败: id={}", id, e);
    }
}

// 推荐：使用 Future 返回结果
@Async
public Future<Boolean> asyncProcess(Long id) {
    try {
        doProcess(id);
        return AsyncResult.forSuccess(true);
    } catch (Exception e) {
        return AsyncResult.forFailure(e);
    }
}
```

## 4. 日志记录

```java
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(BusinessException.class)
    public ApiResponse<Void> handleBusinessException(BusinessException e) {
        // WARN: 业务异常需要记录
        log.warn("业务异常: code={}, message={}", e.getCode(), e.getMessage());
        return ApiResponse.error(e.getCode(), e.getMessage());
    }
    
    @ExceptionHandler(Exception.class)
    public ApiResponse<Void> handleException(Exception e) {
        // ERROR: 系统异常需要详细记录
        log.error("系统异常: message={}", e.getMessage(), e);
        return ApiResponse.error(500, "系统错误");
    }
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
