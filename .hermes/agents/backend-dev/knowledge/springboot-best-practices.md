# Spring Boot 3.x + MyBatis-Plus 最佳实践

## 项目结构规范

```
src/main/java/com/team/project/
├── config/              # 配置类
│   ├── MybatisPlusConfig.java
│   └── WebConfig.java
├── controller/          # REST控制器
├── service/            # 服务接口
│   └── impl/           # 服务实现
├── mapper/              # MyBatis-Plus Mapper接口
├── entity/              # 数据库实体
├── dto/                 # 数据传输对象
├── vo/                  # 视图对象
└── common/              # 通用类
    ├── Result.java
    └── BaseEntity.java
```

## MyBatis-Plus 核心配置

### pom.xml 依赖

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>com.baomidou</groupId>
        <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
        <version>3.5.5</version>
    </dependency>
    <dependency>
        <groupId>com.mysql</groupId>
        <artifactId>mysql-connector-j</artifactId>
    </dependency>
</dependencies>
```

### application.yml 配置

```yaml
spring:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://localhost:3306/dbname?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: root
    password: password

mybatis-plus:
  mapper-locations: classpath*:/mapper/**/*.xml
  global-config:
    db-config:
      id-type: auto
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl
```

## CRUD 最佳实践

### 1. 基础Mapper

```java
@Mapper
public interface UserMapper extends BaseMapper<User> {
    // 继承自动CRUD，无需额外编写
    
    // 自定义查询
    LambdaQueryWrapper<User> queryByCondition(UserQuery query);
}
```

### 2. 分页查询

```java
@Configuration
public class MybatisPlusConfig {
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor());
        return interceptor;
    }
}

// Service中使用
public IPage<User> getUserPage(int current, int size, UserQuery query) {
    return userMapper.selectPage(
        new Page<>(current, size),
        Wrappers.lambdaQuery(User.class)
            .like(StringUtils.isNotBlank(query.getName()), User::getName, query.getName())
            .eq(User::getStatus, query.getStatus())
            .orderByDesc(User::getCreateTime)
    );
}
```

### 3. 逻辑删除

```java
@Data
@TableName(value = "sys_user", autoResultMap = true)
public class User extends BaseEntity {
    @TableId(type = IdType.AUTO)
    private Long id;
    
    private String name;
    
    @TableLogic  // 自动逻辑删除
    private Integer deleted;
}
```

## 常用注解

| 注解 | 用途 |
|------|------|
| @TableName | 指定表名 |
| @TableId | 主键策略 |
| @TableField | 字段映射 |
| @TableLogic | 逻辑删除 |
| @Version | 乐观锁 |
| @EnumValue | 枚举属性映射 |

## 事务管理

```java
@Service
@Transactional(rollbackFor = Exception.class)
public class OrderService {
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void independentOperation() {
        // 独立事务，用于日志记录等
    }
}
```

## 性能优化

1. **字段映射**：设置 `autoResultMap = true` 处理JSON字段
2. **批量操作**：使用 `saveBatch()` / `updateBatchById()`
3. **索引优化**：合理使用 `Wrapper` 条件构造器

---

*文档类型：后端技术规范*
*适用范围：后端开发*
*最后更新：2026-04-29*
