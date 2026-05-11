# 参数校验方案

## 1. 依赖配置

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
</dependency>
```

Spring Boot 3.x 使用 `jakarta.validation` 替代 `javax.validation`。

## 2. 常用校验注解

### 2.1 空值校验

| 注解 | 说明 | 示例 |
|------|------|------|
| @NotNull | 不能为 null | @NotNull |
| @NotBlank | 不能为空字符串 | @NotBlank |
| @NotEmpty | 不能为 null 或空 | @NotEmpty |

### 2.2 字符串校验

| 注解 | 说明 | 示例 |
|------|------|------|
| @Size | 长度范围 | @Size(min=6, max=20) |
| @Length | 长度范围 | @Length(min=6, max=20) |
| @Pattern | 正则匹配 | @Pattern(regexp="^[a-zA-Z]+$") |

### 2.3 数值校验

| 注解 | 说明 | 示例 |
|------|------|------|
| @Min | 最小值 | @Min(0) |
| @Max | 最大值 | @Max(150) |
| @DecimalMin | 最小值（BigDecimal） | @DecimalMin("0.01") |
| @DecimalMax | 最大值（BigDecimal） | @DecimalMax("9999.99") |
| @Digits | 整数和小数位数 | @Digits(integer=3, fraction=2) |
| @Positive | 正数 | @Positive |
| @Negative | 负数 | @Negative |

### 2.4 其他校验

| 注解 | 说明 | 示例 |
|------|------|------|
| @Email | 邮箱格式 | @Email |
| @URL | URL 格式 | @URL |
| @Phone | 电话格式 | @Phone |
| @IdentityCard | 身份证 | @IdentityCard |
| @Range | 范围 | @Range(min=1, max=100) |

## 3. DTO 定义

### 3.1 创建 DTO

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserCreateDTO {
    
    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 20, message = "用户名长度3-20位")
    @Pattern(regexp = "^[a-zA-Z][a-zA-Z0-9_]*$", 
             message = "用户名以字母开头，可包含字母数字下划线")
    private String username;
    
    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 20, message = "密码长度6-20位")
    private String password;
    
    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;
    
    @NotNull(message = "年龄不能为空")
    @Min(value = 0, message = "年龄不能小于0")
    @Max(value = 150, message = "年龄不能超过150")
    private Integer age;
    
    private List<@NotBlank String> roles;
    
    private Map<@NotBlank String, @NotBlank String> extInfo;
}
```

### 3.2 更新 DTO

```java
@Data
public class UserUpdateDTO {
    
    @NotNull(message = "ID不能为空")
    private Long id;
    
    @Size(min = 3, max = 20, message = "用户名长度3-20位")
    private String username;
    
    @Email(message = "邮箱格式不正确")
    private String email;
    
    @Min(value = 0, message = "年龄不能小于0")
    @Max(value = 150, message = "年龄不能超过150")
    private Integer age;
}
```

### 3.3 查询参数

```java
@Data
public class UserQueryDTO {
    
    private String keyword;
    
    @Min(value = 1, message = "页码最小为1")
    private Integer page = 1;
    
    @Min(value = 1, message = "每页数量最小为1")
    @Max(value = 100, message = "每页数量最大为100")
    private Integer size = 20;
}
```

## 4. Controller 使用

### 4.1 基本使用

```java
@RestController
@RequestMapping("/v1/users")
@RequiredArgsConstructor
public class UserController {
    
    @PostMapping
    public ApiResponse<Long> create(
            @RequestBody @Valid UserCreateDTO dto) {
        // @Valid 触发生效校验
        return ApiResponse.success(userService.create(dto));
    }
    
    @PutMapping
    public ApiResponse<Void> update(
            @RequestBody @Valid UserUpdateDTO dto) {
        userService.update(dto);
        return ApiResponse.success();
    }
    
    @GetMapping
    public ApiResponse<PageResult<UserVO>> list(
            @Validated UserQueryDTO query) {
        // @Validated 触发生效校验
        return ApiResponse.success(userService.page(query));
    }
}
```

### 4.2 分组校验

```java
// 定义分组
public interface CreateGroup {
}

public interface UpdateGroup {
}

// DTO 使用分组
@Data
public class UserDTO {
    
    @NotNull(groups = {UpdateGroup.class}, 
             message = "ID不能为空")
    private Long id;
    
    @NotBlank(groups = {CreateGroup.class}, 
              message = "用户名不能为空")
    private String username;
}

// Controller 使用分组
@PostMapping
public ApiResponse<Long> create(
        @RequestBody @Validated(CreateGroup.class) UserDTO dto) {
}

@PutMapping
public ApiResponse<Void> update(
        @RequestBody @Validated(UpdateGroup.class) UserDTO dto) {
}
```

### 4.3 级联校验

```java
@Data
public class OrderCreateDTO {
    
    @NotBlank(message = "订单号不能为空")
    private String orderNo;
    
    @NotNull(message = "订单项不能为空")
    @Size(min = 1, message = "至少包含一个订单项")
    private List<@Valid OrderItemDTO> items;
}

@Data
public class OrderItemDTO {
    
    @NotNull(message = "商品ID不能为空")
    private Long productId;
    
    @NotNull(message = "数量不能为空")
    @Min(value = 1, message = "数量至少为1")
    private Integer quantity;
}
```

## 5. 自定义校验

### 5.1 自定义校验注解

```java
@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = PhoneValidator.class)
@Documented
public @interface PhoneNumber {
    String message() default "手机号格式不正确";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class PhoneValidator implements 
        ConstraintValidator<PhoneNumber, String> {
    
    private static final Pattern PHONE_PATTERN = 
        Pattern.compile("^1[3-9]\\d{9}$");
    
    @Override
    public void initialize(PhoneNumber constraintAnnotation) {
    }
    
    @Override
    public boolean isValid(String value, 
            ConstraintValidatorContext context) {
        if (value == null || value.isEmpty()) {
            return true; // 使用 @NotNull 处理空值
        }
        return PHONE_PATTERN.matcher(value).matches();
    }
}
```

### 5.2 枚举值校验

```java
@Target({ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = EnumValidator.class)
@Documented
public @interface EnumValue {
    Class<? extends Enum<?>> enumClass();
    String message() default "值不在有效范围内";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class EnumValidator implements 
        ConstraintValidator<EnumValue, Integer> {
    
    private Set<Integer> values;
    
    @Override
    public void initialize(EnumValue constraintAnnotation) {
        values = Arrays.stream(constraintAnnotation.enumClass()
                .getEnumConstants())
            .map(e -> ((Enum<?>) e).ordinal())
            .collect(Collectors.toSet());
    }
    
    @Override
    public boolean isValid(Integer value, 
            ConstraintValidatorContext context) {
        if (value == null) return true;
        return values.contains(value);
    }
}

// 使用
public enum UserStatus {
    DISABLED(0),
    ENABLED(1),
    LOCKED(2);
    
    private final int value;
}

// DTO
@EnumValue(enumClass = UserStatus.class)
private Integer status;
```

## 6. 全局异常处理

```java
@RestControllerAdvice
@RequiredArgsConstructor
public class ValidationExceptionHandler {
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ApiResponse<Void> handleValidationException(
            MethodArgumentNotValidException e) {
        List<String> errors = e.getBindingResult()
            .getFieldErrors()
            .stream()
            .map(error -> error.getField() + ": " + 
                         error.getDefaultMessage())
            .collect(Collectors.toList());
        
        return ApiResponse.error(400, String.join("; ", errors));
    }
    
    @ExceptionHandler(ConstraintViolationException.class)
    public ApiResponse<Void> handleConstraintViolation(
            ConstraintViolationException e) {
        List<String> errors = e.getConstraintViolations()
            .stream()
            .map(v -> v.getPropertyPath() + ": " + v.getMessage())
            .collect(Collectors.toList());
        
        return ApiResponse.error(400, String.join("; ", errors));
    }
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
