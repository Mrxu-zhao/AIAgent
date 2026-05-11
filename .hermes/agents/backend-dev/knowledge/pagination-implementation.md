# 分页实现方案

## 1. 前端分页 vs 后端分页

| 特性 | 前端分页 | 后端分页 |
|------|----------|----------|
| 适用场景 | 数据量小（<1000） | 数据量大 |
| 请求次数 | 一次获取全部数据 | 每次只请求一页 |
| 网络传输 | 数据量大时慢 | 数据量小，传输快 |
| 排序 | 前端排序 | 支持后端排序 |
| 服务端压力 | 低 | 中等 |
| 实现复杂度 | 简单 | 中等 |

**推荐原则**：
- 数据量 < 1000：前端分页
- 数据量 > 1000：后端分页

## 2. MyBatis-Plus 分页

### 2.1 配置

```java
@Configuration
public class MyBatisPlusConfig {
    
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = 
            new MybatisPlusInterceptor();
        
        // 分页插件
        interceptor.addInnerInterceptor(
            new PaginationInnerInterceptor(DbType.MYSQL));
        
        return interceptor;
    }
}
```

### 2.2 分页查询

```java
@Service
@RequiredArgsConstructor
public class UserService {
    
    private final UserMapper userMapper;
    
    public PageResult<UserVO> page(UserQueryDTO query) {
        Page<User> page = new Page<>(query.getPage(), query.getSize());
        
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(query.getKeyword())) {
            wrapper.like(User::getUsername, query.getKeyword());
        }
        if (query.getStatus() != null) {
            wrapper.eq(User::getStatus, query.getStatus());
        }
        wrapper.orderByDesc(User::getCreateTime);
        
        Page<User> result = userMapper.selectPage(page, wrapper);
        
        return new PageResult<>(
            result.getRecords().stream()
                .map(this::toVO)
                .collect(Collectors.toList()),
            result.getTotal(),
            result.getSize(),
            result.getCurrent(),
            result.getPages()
        );
    }
}
```

### 2.3 PageResult 定义

```java
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PageResult<T> {
    private List<T> records;    // 数据列表
    private long total;          // 总记录数
    private long size;          // 每页条数
    private long current;      // 当前页码
    private long pages;         // 总页数
    
    public static <T> PageResult<T> of(
            List<T> records, long total, long size, long current) {
        return new PageResult<>(
            records, total, size, current, 
            (total + size - 1) / size  // 计算总页数
        );
    }
}
```

## 3. PageHelper 插件

### 3.1 依赖配置

```xml
<dependency>
    <groupId>com.github.pagehelper</groupId>
    <artifactId>pagehelper-spring-boot-starter</artifactId>
    <version>2.1.0</version>
</dependency>
```

### 3.2 配置

```yaml
pagehelper:
  helper-dialect: mysql
  reasonable: true          # 启用合理化
  support-methods-arguments: true
  params: count=countSql
```

### 3.3 使用方式

```java
@Service
@RequiredArgsConstructor
public class UserService {
    
    private final UserMapper userMapper;
    
    public PageInfo<UserVO> page(int pageNum, int pageSize) {
        // 设置分页参数
        PageHelper.startPage(pageNum, pageSize);
        
        // 执行查询
        List<User> users = userMapper.selectAll();
        
        // 包装成 PageInfo
        PageInfo<User> pageInfo = new PageInfo<>(users);
        
        // 转换
        List<UserVO> voList = pageInfo.getList().stream()
            .map(this::toVO)
            .collect(Collectors.toList());
        
        PageInfo<UserVO> result = new PageInfo<>(voList);
        result.setTotal(pageInfo.getTotal());
        result.setPageNum(pageInfo.getPageNum());
        result.setPageSize(pageInfo.getPageSize());
        result.setPages(pageInfo.getPages());
        
        return result;
    }
}
```

### 3.4 PageHelper 注意事项

```java
// 1. 分页参数写在查询方法之前
PageHelper.startPage(page, size);
List<User> list = userMapper.selectList(); // 这条SQL会被分页

// 2. 多表查询分页
// 需要在 SQL 中使用 ROW_NUMBER() 或子查询

// 3. Count 查询优化
// large-pagehelper: 支持大偏移量优化
```

## 4. API 设计

### 4.1 请求格式

```
GET /v1/users?page=1&size=20&sort=createTime,desc
```

### 4.2 响应格式

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "records": [
            {"id": 1, "username": "user1"},
            {"id": 2, "username": "user2"}
        ],
        "total": 100,
        "size": 20,
        "current": 1,
        "pages": 5
    }
}
```

### 4.3 响应类定义

```java
@Data
@NoArgsConstructor
public class ApiResponse<T> {
    private int code;
    private String message;
    private T data;
    private long timestamp;
    
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(200, "success", data, 
            System.currentTimeMillis());
    }
}

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PageResult<T> {
    private List<T> records;
    private long total;
    private long size;
    private long current;
    private long pages;
}
```

## 5. 常见问题

### 5.1 分页不生效

检查清单：
1. 是否正确配置了分页插件
2. 是否使用了 Spring 管理的 Mapper
3. SQL 是否正确（MySQL 需要 LIMIT）

### 5.2 COUNT 查询慢

```sql
-- 优化方案：使用覆盖索引
EXPLAIN SELECT COUNT(*) FROM orders WHERE status = 1;

-- 添加索引
CREATE INDEX idx_orders_status ON orders(status);
```

### 5.3 大偏移量分页

```sql
-- 问题：OFFSET 1000000 时会很慢
SELECT * FROM orders LIMIT 20 OFFSET 1000000;

-- 优化：使用游标分页
SELECT * FROM orders 
WHERE id > #{lastId}
ORDER BY id
LIMIT 20;

-- 或使用延迟关联
SELECT a.* FROM orders a 
INNER JOIN (SELECT id FROM orders LIMIT 20 OFFSET 1000000) b
ON a.id = b.id;
```

### 5.4 游标分页实现

```java
// 游标分页适合大数据量
public class CursorPage {
    private Long lastId;
    private Integer pageSize;
    private LocalDateTime createTime;
}

public PageResult<UserVO> cursorPage(CursorPage cursor) {
    LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
    if (cursor.getLastId() != null) {
        wrapper.lt(User::getId, cursor.getLastId());
    } else {
        wrapper.orderByDesc(User::getId);
    }
    wrapper.last("LIMIT " + cursor.getPageSize());
    
    List<User> users = userMapper.selectList(wrapper);
    // ...
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
