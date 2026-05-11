# MyBatis-Plus 高级用法

## 1. 分页插件配置

### 1.1 配置类

```java
@Configuration
@MapperScan("com.example.mapper")
public class MyBatisPlusConfig {
    
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        
        // 分页插件
        interceptor.addInnerInterceptor(
            new PaginationInnerInterceptor(DbType.MYSQL));
        
        // 乐观锁插件
        interceptor.addInnerInterceptor(new OptimisticLockerInnerInterceptor());
        
        // 防止全表更新插件
        interceptor.addInnerInterceptor(
            new BlockAttackInnerInterceptor());
        
        return interceptor;
    }
}
```

### 1.2 分页查询

```java
// 普通分页
IPage<User> page = userMapper.selectPage(
    new Page<>(current, size),  // current: 页码, size: 每页条数
    new QueryWrapper<User>().eq("status", 1)
);

// 返回结果
public class PageResult<T> {
    private long total;
    private long pages;
    private long current;
    private long size;
    private List<T> records;
}
```

```java
// 自定义 SQL 分页
IPage<User> selectUserPage(Page<User> page, @Param("status") Integer status);

<!-- XML -->
<select id="selectUserPage" resultType="User">
    SELECT * FROM sys_user 
    WHERE status = #{status}
    ORDER BY create_time DESC
</select>
```

## 2. 逻辑删除

### 2.1 实体配置

```java
@Data
@TableName(value = "sys_user", keepGlobalPrefix = true)
public class User {
    
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private String username;
    
    // 逻辑删除字段
    @TableLogic
    private Integer deleted;
    
    // 公共字段
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
    
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
```

### 2.2 配置

```yaml
mybatis-plus:
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0
```

### 2.3 注意事项

- 逻辑删除字段需要有默认值
- 子查询时需注意逻辑删除的影响
- 建议使用 `@TableField(select = false)` 避免查询出 deleted 字段

## 3. 自动填充

### 3.1 实现 MetaObjectHandler

```java
@Component
public class CommonFieldHandler implements MetaObjectHandler {
    
    @Override
    public void insertFill(MetaObject metaObject) {
        // 创建时间
        this.strictInsertFill(metaObject, "createTime", 
            LocalDateTime.class, LocalDateTime.now());
        // 创建人
        this.strictInsertFill(metaObject, "createBy", 
            String.class, getCurrentUser());
        // 更新时间
        this.strictUpdateFill(metaObject, "updateTime", 
            LocalDateTime.class, LocalDateTime.now());
    }
    
    @Override
    public void updateFill(MetaObject metaObject) {
        // 更新人
        this.strictUpdateFill(metaObject, "updateBy", 
            String.class, getCurrentUser());
        // 更新时间
        this.strictUpdateFill(metaObject, "updateTime", 
            LocalDateTime.class, LocalDateTime.now());
    }
    
    private String getCurrentUser() {
        // 从 SecurityContext 获取当前用户
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        return auth != null ? auth.getName() : "system";
    }
}
```

### 3.2 注解配置

```java
@TableField(fill = FieldFill.INSERT)
private String createBy;

@TableField(fill = FieldFill.INSERT_UPDATE)
private LocalDateTime updateTime;
```

## 4. 常用 CRUD

### 4.1 BaseMapper

```java
// 条件构造器
QueryWrapper<User> wrapper = new QueryWrapper<>();
wrapper.like("name", "张")
      .eq("status", 1)
      .in("age", Arrays.asList(18, 20, 25))
      .orderByDesc("create_time")
      .last("LIMIT 10");

userMapper.selectList(wrapper);

// Lambda 方式
LambdaQueryWrapper<User> lambdaWrapper = new LambdaQueryWrapper<>();
lambdaWrapper
    .like(User::getName, "张")
    .eq(User::getStatus, 1);
```

### 4.2 IService

```java
public interface UserService extends IService<User> {
    // 自定义方法
}

// 实现类
@Service
public class UserServiceImpl extends ServiceImpl<UserMapper, User> 
    implements UserService {
    
    @Override
    public User getByUsername(String username) {
        return getOne(new LambdaQueryWrapper<User>()
            .eq(User::getUsername, username));
    }
}
```

## 5. 常见问题

### 5.1 分页不生效

检查：
1. 是否正确配置了分页插件
2. 是否使用了 Spring 管理事务（代理问题）
3. MySQL 需要 LIMIT，使用物理分页

### 5.2 逻辑删除导致查询异常

```java
// 解决方案：使用 Wrapper 时明确指定条件
// 或者在配置中禁用逻辑删除
@TableLogic(delval = "")
private Integer deleted;
```

---

*作者: 陈启明*
*更新: 2026-04-29*
