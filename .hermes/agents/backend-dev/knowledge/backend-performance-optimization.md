# 后端性能优化

## 1. 数据库优化

### 1.1 索引优化

```sql
-- 创建复合索引
CREATE INDEX idx_user_status_create ON sys_user(status, create_time);

-- 分析慢查询
EXPLAIN SELECT * FROM sys_user WHERE status = 1;
```

### 1.2 SQL 优化原则

1. 避免 SELECT *
2. 使用 LIMIT 限制结果集
3. 避免子查询，改用 JOIN
4. 使用批量操作

## 2. 缓存优化

### 2.1 本地缓存

```java
@Component
public class UserCache {
    
    private final Map<Long, User> cache = new ConcurrentHashMap<>();
    private final LoadingCache<Long, User> loadingCache = 
        Caffeine.newBuilder()
            .maximumSize(1000)
            .expireAfterWrite(5, TimeUnit.MINUTES)
            .build(id -> userMapper.selectById(id));
}
```

### 2.2 分布式缓存

```java
@Service
@RequiredArgsConstructor
public class UserService {
    
    private final RedisTemplate<String, User> redisTemplate;
    private static final String USER_KEY = "user:";
    
    public User getById(Long id) {
        String key = USER_KEY + id;
        User user = redisTemplate.opsForValue().get(key);
        
        if (user == null) {
            user = userMapper.selectById(id);
            redisTemplate.opsForValue().set(key, user, 
                30, TimeUnit.MINUTES);
        }
        
        return user;
    }
}
```

## 3. 并发优化

### 3.1 异步处理

```java
@Service
@RequiredArgsConstructor
public class OrderService {
    
    private final AsyncService asyncService;
    
    public void createOrder(OrderDTO dto) {
        Order order = createOrderSync(dto);
        
        // 异步发送消息
        asyncService.sendOrderMessage(order.getId());
        
        // 异步更新统计
        asyncService.updateStatistics(order);
    }
}

@Service
public class AsyncService {
    
    @Async
    public void sendOrderMessage(Long orderId) {
        messageQueue.send(orderId);
    }
}
```

### 3.2 批量处理

```java
@Service
@RequiredArgsConstructor
public class UserService {
    
    private final UserMapper userMapper;
    
    public void batchImport(List<UserDTO> dtos) {
        // 分批处理，每批 1000 条
        List<List<UserDTO>> batches = Lists.partition(dtos, 1000);
        
        for (List<UserDTO> batch : batches) {
            List<User> users = batch.stream()
                .map(this::toEntity)
                .collect(Collectors.toList());
            userMapper.insertBatchSomeColumns(users);
        }
    }
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
