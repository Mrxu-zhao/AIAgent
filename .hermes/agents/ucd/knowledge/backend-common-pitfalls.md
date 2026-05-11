# 后端开发踩坑记录

## 1. Spring Boot 3.x 兼容性问题

### 1.1 Jakarta EE 迁移

**问题描述**：Spring Boot 3.x 将 `javax.*` 包迁移到 `jakarta.*`，导致原有的 Servlet、Validation 等代码编译失败。

**错误信息**：
```
The import javax.servlet cannot be accessed
```

**解决方案**：
```bash
# Maven 依赖更新
# 旧: javax.servlet:servlet-api
# 新: jakarta.servlet:jakarta.servlet-api

# 批量替换
find . -name "*.java" -exec sed -i 's/javax\.\(servlet|validation|annotation\)/jakarta.\1/g' {} \;
```

**预防措施**：
1. 升级前先检查所有依赖
2. 使用 IDE 的批量重命名功能
3. 制定升级计划，分阶段迁移

---

## 2. MyBatis-Plus 逻辑删除坑

### 2.1 条件查询忽略逻辑删除

**问题描述**：使用 QueryWrapper 查询时，逻辑删除字段被自动添加条件，导致某些查询结果为空。

**错误示例**：
```java
// 查询所有管理员（包括已删除的）
List<User> admins = userMapper.selectList(
    new LambdaQueryWrapper<User>()
        .eq(User::getRole, "admin")
        // 自动追加 deleted = 0
);

// 期望: 返回包括已删除的管理员
// 实际: 只返回未删除的管理员
```

**解决方案**：
```java
// 方案1: 使用 Wrapper 禁用逻辑删除
List<User> admins = userMapper.selectList(
    new LambdaQueryWrapper<User>()
        .eq(User::getRole, "admin")
        .last("WHERE deleted IS NOT NULL OR deleted = 1")  // 不推荐
);

// 方案2: 使用自定义 SQL
List<User> admins = userMapper.selectAllAdmins();

// XML
<select id="selectAllAdmins" resultType="User">
    SELECT * FROM sys_user WHERE role = 'admin'
</select>
```

**预防措施**：
1. 明确查询语义（逻辑删除 vs 物理删除）
2. 在方法命名上体现（如 `selectAllIncludingDeleted`）
3. 统一团队的查询规范

---

## 3. 分页插件不生效

### 3.1 Spring 代理问题

**问题描述**：在 Service 方法上使用 `@Transactional` 后，分页查询结果为空或报错。

**错误信息**：
```
Cause: java.sql.SQLSyntaxErrorException: 
For update is not allowed in 'default' statement
```

**原因分析**：
```java
@Service
public class UserServiceImpl {
    
    @Transactional
    public PageResult<User> page(int page, int size) {
        // 事务开启后，Mapper 通过代理调用
        // 如果 Mapper 注入方式不对，分页拦截器不生效
    }
}
```

**解决方案**：
```java
@Configuration
public class MyBatisPlusConfig {
    
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = 
            new MybatisPlusInterceptor();
        interceptor.addInnerInterceptor(
            new PaginationInnerInterceptor(DbType.MYSQL));
        return interceptor;
    }
    
    @Bean
    public SqlSessionFactory sqlSessionFactory(...) {
        // 确保 MapperScanner 配置正确
    }
}
```

**正确的注入方式**：
```java
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {
    
    private final UserMapper userMapper;  // 使用构造器注入
}
```

**预防措施**：
1. 使用构造器注入而非字段注入
2. 确保 MapperScanner 扫描路径正确
3. 测试时验证分页 SQL

---

## 4. @Valid 校验不生效

### 4.1 缺少 @Valid 注解

**问题描述**：Controller 方法有 `@RequestBody` 但没有 `@Valid`，导致参数校验不生效。

**错误代码**：
```java
@PostMapping
public ApiResponse<Void> create(@RequestBody UserDTO dto) {
    // dto 没有被校验
    userService.create(dto);  // 可能收到无效数据
}
```

**解决方案**：
```java
@PostMapping
public ApiResponse<Void> create(@RequestBody @Valid UserDTO dto) {
    // 添加 @Valid 触发生效校验
}
```

### 4.2 嵌套对象校验

**问题描述**：DTO 中包含嵌套对象，嵌套对象的校验注解不生效。

**错误代码**：
```java
@Data
public class OrderDTO {
    @NotBlank
    private String orderNo;
    
    private List<ItemDTO> items;  // 嵌套对象
}

@Data
public class ItemDTO {
    @NotNull
    private Long productId;  // 不生效
}
```

**解决方案**：
```java
@Data
public class OrderDTO {
    @NotBlank
    private String orderNo;
    
    @NotEmpty
    @Valid  // 添加 @Valid 触发生效嵌套校验
    private List<ItemDTO> items;
}
```

**预防措施**：
1. 统一使用 `@Valid` 命名规范（对比 `@Validated`）
2. 嵌套对象必须添加 `@Valid`
3. 编写测试用例验证校验生效

---

## 5. 事务不回滚

### 5.1 异常被 catch 吞掉

**问题描述**：Service 方法中 catch 了异常但未重新抛出，导致事务不生效。

**错误代码**：
```java
@Service
public class UserServiceImpl {
    
    @Transactional
    public void createUser(UserDTO dto) {
        try {
            User user = new User();
            user.setUsername(dto.getUsername());
            userMapper.insert(user);
            
            // 发送消息失败
            messageService.send(user);
        } catch (Exception e) {
            log.error("发送消息失败", e);
            // 异常被吞掉，事务不回滚！
        }
    }
}
```

**解决方案**：
```java
// 方案1: 重新抛出异常
catch (Exception e) {
    log.error("发送消息失败", e);
    throw new RuntimeException("发送消息失败", e);
}

// 方案2: 使用 CompleteableFuture
CompletableFuture.runAsync(() -> messageService.send(user));

// 方案3: 使用消息队列
messageQueue.send(user);
```

### 5.2 异常类型不匹配

**问题描述**：`@Transactional(rollbackFor = Exception.class)` 没有指定，导致特定异常不回滚。

**解决方案**：
```java
@Transactional(rollbackFor = Exception.class)
public void createUser(UserDTO dto) {
    // 所有 Exception 都会回滚
}
```

---

## 6. 缓存与数据库不一致

### 6.1 Cache Aside 模式问题

**问题描述**：更新数据库后未及时删除/更新缓存，导致读取到脏数据。

**场景**：
```
线程A: 更新数据库 user.id=1, name='new'
线程A: 删除缓存
线程B: 读取缓存为空
线程B: 读数据库得到旧值
线程B: 写入缓存（脏数据）
```

**解决方案**：
```java
@Service
@RequiredArgsConstructor
public class UserService {
    
    private final UserMapper userMapper;
    private final UserCacheService userCacheService;
    
    public void update(Long id, String name) {
        // 1. 更新数据库
        User user = userMapper.selectById(id);
        user.setName(name);
        userMapper.updateById(user);
        
        // 2. 删除缓存（而非更新缓存）
        userCacheService.delete(id);
        
        // 3. 可选：延迟双删
        CompletableFuture.runAsync(() -> {
            try {
                Thread.sleep(100);
                userCacheService.delete(id);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
    }
}
```

**预防措施**：
1. 使用 Redis 分布式锁
2. 设置合理的缓存过期时间
3. 关键数据使用 Cache Aside 模式

---

## 7. 常见性能问题

### 7.1 N+1 查询问题

**问题描述**：循环中查询数据库，导致性能问题。

**错误代码**：
```java
List<User> users = userMapper.selectList();
for (User user : users) {
    List<Order> orders = orderMapper.selectByUserId(user.getId());
    user.setOrders(orders);
}
```

**解决方案**：
```java
// 批量查询
List<Long> userIds = users.stream()
    .map(User::getId)
    .collect(Collectors.toList());

Map<Long, List<Order>> orderMap = orderMapper.selectByUserIds(userIds)
    .stream()
    .collect(Collectors.groupingBy(Order::getUserId));

for (User user : users) {
    user.setOrders(orderMap.get(user.getId()));
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
