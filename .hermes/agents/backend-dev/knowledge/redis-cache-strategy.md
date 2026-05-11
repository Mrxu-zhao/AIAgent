# Redis 缓存策略

## 缓存模式

### 1. Cache-Aside（旁路缓存）

```
读：Cache → Miss → DB → 更新Cache
写：DB → Delete Cache（不是更新）
```

```java
public User getUser(Long id) {
    // 1. 读缓存
    String key = "user:" + id;
    User user = JSON.parseObject(redisTemplate.opsForValue().get(key), User.class);
    if (user != null) {
        return user;
    }
    
    // 2. 读数据库
    user = userMapper.selectById(id);
    
    // 3. 写缓存（设置过期时间）
    redisTemplate.opsForValue().set(key, JSON.toJSONString(user), 30, TimeUnit.MINUTES);
    return user;
}

public void updateUser(User user) {
    userMapper.updateById(user);
    // 删除缓存，而不是更新
    redisTemplate.delete("user:" + user.getId());
}
```

### 2. Read-Through / Write-Through

应用不直接操作缓存，由缓存层负责加载/写入。

### 3. Write-Behind

异步写入数据库，性能最高但存在数据丢失风险。

---

## 三大缓存问题及解决方案

### 问题一：缓存穿透

**原因**：查询不存在的数据，每次都打到数据库。

**解决方案**：

```java
// 方案1：缓存空值
public User getUser(Long id) {
    String key = "user:" + id;
    String json = redisTemplate.opsForValue().get(key);
    
    if (json != null) {
        if ("NULL".equals(json)) return null;  // 空值缓存
        return JSON.parseObject(json, User.class);
    }
    
    User user = userMapper.selectById(id);
    if (user == null) {
        redisTemplate.opsForValue().set(key, "NULL", 5, TimeUnit.MINUTES);
    } else {
        redisTemplate.opsForValue().set(key, JSON.toJSONString(user), 30, TimeUnit.MINUTES);
    }
    return user;
}

// 方案2：布隆过滤器
@Service
public class BloomFilterService {
    private BloomFilter<Long> filter = BloomFilter.create(
        Funnels.longFunnel(), 1000000, 0.01);
    
    public boolean mightExist(Long id) {
        return filter.mightContain(id);
    }
}
```

### 问题二：缓存击穿

**原因**：热点Key过期瞬间，大量请求涌入数据库。

**解决方案**：

```java
// 方案1：互斥锁（推荐简单场景）
public User getUserWithLock(Long id) {
    String key = "user:" + id;
    String json = redisTemplate.opsForValue().get(key);
    if (json != null) {
        return JSON.parseObject(json, User.class);
    }
    
    // 获取锁
    String lockKey = "lock:user:" + id;
    String lockValue = UUID.randomUUID().toString();
    
    if (redisTemplate.opsForValue().setIfAbsent(lockKey, lockValue, 10, TimeUnit.SECONDS)) {
        try {
            // 双重检查
            json = redisTemplate.opsForValue().get(key);
            if (json != null) return JSON.parseObject(json, User.class);
            
            User user = userMapper.selectById(id);
            redisTemplate.opsForValue().set(key, JSON.toJSONString(user), 30, TimeUnit.MINUTES);
            return user;
        } finally {
            redisTemplate.delete(lockKey);
        }
    } else {
        // 等待其他线程加载
        Thread.sleep(50);
        return getUserWithLock(id);
    }
}

// 方案2：逻辑过期（推荐高并发场景）
public User getUserWithLogicalExpire(Long id) {
    String key = "user:" + id;
    String json = redisTemplate.opsForValue().get(key);
    
    if (json == null) {
        return loadAndCache(id);
    }
    
    RedisData data = JSON.parseObject(json, RedisData.class);
    User user = JSON.parseObject(data.getData(), User.class);
    
    if (data.getExpireTime() < System.currentTimeMillis()) {
        // 逻辑过期，异步更新缓存
        threadPool.submit(() -> loadAndCache(id));
        return user;  // 返回旧数据
    }
    return user;
}
```

### 问题三：缓存雪崩

**原因**：大量缓存同时过期或Redis宕机。

**解决方案**：

```java
// 方案1：过期时间随机化
int expireTime = 30 + random.nextInt(10);  // 30-40分钟随机
redisTemplate.opsForValue().set(key, value, expireTime, TimeUnit.MINUTES);

// 方案2：多级缓存
@Cacheable(value = "user", cacheManager = "caffeineCacheManager")
public User getUser(Long id) {
    return userMapper.selectById(id);
}

// 方案3：Redis高可用集群
// 使用Sentinel或Cluster模式
```

---

## 缓存Key设计规范

```
{业务}:{实体}:{主键}:{属性}
```

示例：
- `user:1001:profile` - 用户1001的基本信息
- `order:list:user:1001:page1` - 用户1001的订单列表
- `product:hot:top10` - 热门商品TOP10

## 缓存过期策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| TTL | 固定过期时间 | 大多数场景 |
| LRU | 最近最少使用 | 内存敏感 |
| 惰性删除 | 访问时删除过期 | 节省资源 |

---

*文档类型：后端技术规范*
*适用范围：后端开发*
*最后更新：2026-04-29*
