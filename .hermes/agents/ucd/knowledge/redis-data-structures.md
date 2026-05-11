# Redis 数据结构与业务场景选型

## 概述

Redis 是团队技术栈的重要组成，用于缓存、Session、分布式锁等场景。本文详细讲解 Redis 8 种数据结构及其适用场景。

## 数据结构总览

| 数据结构 | 命令前缀 | 适用场景 |
|----------|----------|----------|
| STRING | SET/GET | 缓存、计数器、分布式锁 |
| HASH | HSET/HGET | 对象存储、购物车 |
| LIST | LPUSH/RPOP | 消息队列、最新列表 |
| SET | SADD/SMEMBERS | 标签、好友关系、去重 |
| ZSET | ZADD/ZRANGE | 排行榜、延迟队列 |
| BITMAP | SETBIT/GETBIT | 用户签到、活跃用户统计 |
| HyperLogLog | PFADD/PFCOUNT | UV 统计 |
| GEO | GEOADD/GEORADIUS | 附近的人、门店查询 |

## STRING 字符串

### 基本操作

```bash
# 设置和获取
SET user:1001:name "张三"
GET user:1001:name

# 设置过期时间
SET user:1001:token "abc123" EX 3600  # 1 小时后过期
SETEX user:1001:token 3600 "abc123"  # 效果相同

# 批量操作
MSET user:1001:name "张三" user:1001:age "25"
MGET user:1001:name user:1001:age

# 计数操作
INCR article:1001:views        # +1
INCRBY article:1001:views 100  # +100
DECR article:1001:views         # -1

# CAS 操作（乐观锁）
WATCH user:1001:balance
GET user:1001:balance
# ... 业务逻辑
MULTI
SET user:1001:balance 900
EXEC
# 如果 key 被其他客户端修改，EXEC 返回空
```

### Java 操作

```java
@Autowired
private StringRedisTemplate redisTemplate;

// 基本操作
public void setUserName(Long userId, String name) {
    String key = "user:" + userId + ":name";
    redisTemplate.opsForValue().set(key, name, Duration.ofHours(1));
}

public String getUserName(Long userId) {
    String key = "user:" + userId + ":name";
    return redisTemplate.opsForValue().get(key);
}

// 计数器
public long incrViewCount(Long articleId) {
    String key = "article:" + articleId + ":views";
    return redisTemplate.opsForValue().increment(key);
}
```

### 业务场景

```java
// 场景一：缓存
public User getUserById(Long userId) {
    String key = "user:" + userId;
    String cached = redisTemplate.opsForValue().get(key);
    if (cached != null) {
        return JSON.parseObject(cached, User.class);
    }
    
    User user = userMapper.selectById(userId);
    if (user != null) {
        redisTemplate.opsForValue().set(key, JSON.toJSONString(user), 
            Duration.ofHours(1));
    }
    return user;
}

// 场景二：分布式锁
public boolean lock(String key, String value, Duration expire) {
    return Boolean.TRUE.equals(
        redisTemplate.opsForValue().setIfAbsent(key, value, expire));
}

public void unlock(String key, String value) {
    String current = redisTemplate.opsForValue().get(key);
    if (value.equals(current)) {
        redisTemplate.delete(key);
    }
}

// 场景三：验证码 / Token
public String generateToken(Long userId) {
    String token = UUID.randomUUID().toString();
    String key = "token:" + token;
    redisTemplate.opsForValue().set(key, userId.toString(), Duration.ofDays(7));
    return token;
}
```

## HASH 哈希

### 基本操作

```bash
# 设置和获取
HSET user:1001 name "张三" age "25" city "北京"
HGET user:1001 name
HGETALL user:1001

# 批量操作
HMSET user:1001 name "张三" age "25"  # 已废弃，用 HSET 替代
HMGET user:1001 name age
HKEYS user:1001
HVALS user:1001

# 计数
HINCRBY user:1001 order_count 1

# 判断字段是否存在
HEXISTS user:1001 name
```

### Java 操作

```java
// 对象存储（购物车）
public void addToCart(Long userId, Long productId, Integer quantity) {
    String key = "cart:" + userId;
    redisTemplate.opsForHash().put(key, productId.toString(), quantity.toString());
}

public Map<Object, Object> getCart(Long userId) {
    String key = "cart:" + userId;
    return redisTemplate.opsForHash().entries(key);
}

public void removeFromCart(Long userId, Long productId) {
    String key = "cart:" + userId;
    redisTemplate.opsForHash().delete(key, productId.toString());
}
```

### 业务场景

```java
// 场景一：用户信息缓存
public void cacheUserInfo(User user) {
    String key = "user:info:" + user.getId();
    Map<String, String> map = new HashMap<>();
    map.put("name", user.getName());
    map.put("email", user.getEmail());
    map.put("mobile", user.getMobile());
    redisTemplate.opsForHash().putAll(key, map);
}

public User getCachedUser(Long userId) {
    String key = "user:info:" + userId;
    Map<Object, Object> map = redisTemplate.opsForHash().entries(key);
    if (map.isEmpty()) {
        return null;
    }
    // 转换为 User 对象
    return convertToUser(map);
}

// 场景二：购物车
public void updateCartQuantity(Long userId, Long skuId, Integer quantity) {
    String key = "cart:" + userId;
    if (quantity <= 0) {
        redisTemplate.opsForHash().delete(key, skuId.toString());
    } else {
        redisTemplate.opsForHash().put(key, skuId.toString(), quantity.toString());
    }
}
```

## LIST 列表

### 基本操作

```bash
# 插入
LPUSH queue:tasks "task1"      # 左边插入
RPUSH queue:tasks "task2"      # 右边插入

# 弹出
LPOP queue:tasks               # 左边弹出
RPOP queue:tasks               # 右边弹出
BRPOP queue:tasks 0           # 阻塞等待右边弹出

# 范围查询
LRANGE queue:tasks 0 -1       # 获取所有
LINDEX queue:tasks 0          # 按索引获取

# 长度
LLEN queue:tasks

# 修剪
LTRIM queue:tasks 0 99        # 只保留前 100 条
```

### Java 操作

```java
// 消息队列
public void sendMessage(String queue, String message) {
    redisTemplate.opsForList().rightPush(queue, message);
}

public String receiveMessage(String queue) {
    return (String) redisTemplate.opsForList().leftPop(queue);
}

public String blockingReceive(String queue, Duration timeout) {
    return (String) redisTemplate.opsForList().leftPop(queue, 
        timeout.toSeconds(), TimeUnit.SECONDS);
}
```

### 业务场景

```java
// 场景一：消息队列
@Service
public class MessageQueueService {
    
    private static final String ORDER_QUEUE = "queue:orders";
    
    public void sendOrder(Order order) {
        redisTemplate.opsForList().rightPush(ORDER_QUEUE, JSON.toJSONString(order));
    }
    
    public Order receiveOrder() {
        String json = (String) redisTemplate.opsForList().leftPop(ORDER_QUEUE);
        return json != null ? JSON.parseObject(json, Order.class) : null;
    }
}

// 场景二：最新消息列表
public void addLatestMessage(Long userId, String message) {
    String key = "user:" + userId + ":messages";
    redisTemplate.opsForList().leftPush(key, message);
    redisTemplate.opsForList().trim(key, 0, 99);  // 只保留 100 条
}

public List<String> getLatestMessages(Long userId, int limit) {
    String key = "user:" + userId + ":messages";
    return redisTemplate.opsForList().range(key, 0, limit - 1);
}
```

## SET 集合

### 基本操作

```bash
# 添加删除
SADD tags:article:1001 "Java" "Redis" "MySQL"
SREM tags:article:1001 "MySQL"

# 查询
SMEMBERS tags:article:1001
SISMEMBER tags:article:1001 "Java"  # 是否存在

# 集合运算
SINTER tags:user:1001 tags:user:1002  # 交集
SUNION tags:user:1001 tags:user:1002  # 并集
SDIFF tags:user:1001 tags:user:1002   # 差集

# 随机
SRANDMEMBER tags:article:1001 5     # 随机获取 5 个
SPOP tags:article:1001 2            # 随机弹出 2 个
```

### Java 操作

```java
// 标签系统
public void addTags(Long articleId, Set<String> tags) {
    String key = "tags:article:" + articleId;
    redisTemplate.opsForSet().add(key, tags.toArray());
}

public Set<String> getTags(Long articleId) {
    String key = "tags:article:" + articleId;
    return redisTemplate.opsForSet().members(key);
}

public boolean hasTag(Long articleId, String tag) {
    String key = "tags:article:" + articleId;
    return Boolean.TRUE.equals(redisTemplate.opsForSet().isMember(key, tag));
}
```

### 业务场景

```java
// 场景一：文章标签
public void addArticleTags(Long articleId, List<String> tags) {
    String key = "article:tags:" + articleId;
    redisTemplate.opsForSet().add(key, tags.toArray());
}

public List<String> getRecommendArticles(Long articleId) {
    // 获取当前文章标签
    String key = "article:tags:" + articleId;
    Set<String> tags = redisTemplate.opsForSet().members(key);
    
    // 找出拥有相同标签的文章
    Set<Object> articleIds = new HashSet<>();
    for (String tag : tags) {
        Set<Object> ids = redisTemplate.opsForSet().members("tag:" + tag);
        articleIds.addAll(ids);
    }
    articleIds.remove(articleId);  // 排除自己
    return articleIds.stream().map(Object::toString).collect(Collectors.toList());
}

// 场景二：用户画像 / 兴趣标签
public void addUserInterest(Long userId, String interest) {
    String key = "user:interest:" + userId;
    redisTemplate.opsForSet().add(key, interest);
}

public Set<String> getUserInterests(Long userId) {
    String key = "user:interest:" + userId;
    return redisTemplate.opsForSet().members(key);
}
```

## ZSET 有序集合

### 基本操作

```bash
# 添加
ZADD leaderboard:2024 100 "张三" 90 "李四" 80 "王五"

# 查询
ZRANGE leaderboard:2024 0 9 WITHSCORES  # 按分数升序
ZREVRANGE leaderboard:2024 0 9 WITHSCORES # 按分数降序

# 获取排名
ZRANK leaderboard:2024 "张三"   # 返回排名（0 开始）
ZREVRANK leaderboard:2024 "张三"  # 返回倒序排名

# 获取分数
ZSCORE leaderboard:2024 "张三"

# 范围查询
ZRANGEBYSCORE leaderboard:2024 90 100  # 90-100 分之间

# 删除
ZREM leaderboard:2024 "李四"
ZREMRANGEBYRANK leaderboard:2024 0 9  # 删除前 10 名
```

### Java 操作

```java
// 排行榜
public void addScore(Long userId, double score) {
    String key = "leaderboard:" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
    redisTemplate.opsForZSet().add(key, userId.toString(), score);
}

public Long getRank(Long userId) {
    String key = "leaderboard:" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
    Long rank = redisTemplate.opsForZSet().reverseRank(key, userId.toString());
    return rank != null ? rank + 1 : null;  // 转为 1 开始
}

public Double getScore(Long userId) {
    String key = "leaderboard:" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
    return redisTemplate.opsForZSet().score(key, userId.toString());
}
```

### 业务场景

```java
// 场景一：商品排行榜
public void incrementProductSales(Long productId, int amount) {
    String key = "product:sales:daily:" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
    redisTemplate.opsForZSet().incrementScore(key, productId.toString(), amount);
}

public List<Long> getTopProducts(int limit) {
    String key = "product:sales:daily:" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
    Set<ZSetOperations.TypedTuple<Object>> set = 
        redisTemplate.opsForZSet().reverseRangeWithScores(key, 0, limit - 1);
    return set.stream()
        .map(t -> Long.parseLong(t.getValue().toString()))
        .collect(Collectors.toList());
}

// 场景二：延迟队列
public void addDelayTask(String taskId, long delaySeconds) {
    String key = "delay:queue";
    long score = System.currentTimeMillis() + delaySeconds * 1000;
    redisTemplate.opsForZSet().add(key, taskId, score);
}

public String pollDelayTask() {
    String key = "delay:queue";
    Set<Object> tasks = redisTemplate.opsForZSet()
        .rangeByScore(key, 0, System.currentTimeMillis(), 0, 1);
    if (tasks.isEmpty()) {
        return null;
    }
    String taskId = tasks.iterator().next().toString();
    redisTemplate.opsForZSet().remove(key, taskId);
    return taskId;
}

// 场景三：用户签到
public boolean signIn(Long userId, LocalDate date) {
    String key = "sign:" + userId + ":" + date.format(DateTimeFormatter.ofPattern("yyyy-MM"));
    return Boolean.TRUE.equals(redisTemplate.opsForValue().setBit(key, date.getDayOfMonth(), true));
}
```

## BITMAP 位图

### 基本操作

```bash
# 设置和获取
SETBIT user:1001:sign:2024-04 1 1  # 4 月 2 日签到（第 1 天，偏移量 0）
GETBIT user:1001:sign:2024-04 1

# 统计
BITCOUNT user:1001:sign:2024-04  # 签到天数

# 位置运算
BITOP AND result:2024-04 user:1001:sign:2024-04 user:1002:sign:2024-04
```

### 业务场景

```java
// 用户每日签到
public boolean signIn(Long userId, LocalDate date) {
    String key = String.format("sign:%d:%s", userId, 
        date.format(DateTimeFormatter.ofPattern("yyyy-MM")));
    int offset = date.getDayOfMonth() - 1;
    return Boolean.TRUE.equals(
        redisTemplate.opsForValue().setBit(key, offset, true));
}

public int getSignCount(Long userId, YearMonth month) {
    String key = String.format("sign:%d:%s", userId, month.format(DateTimeFormatter.ofPattern("yyyy-MM")));
    Long count = redisTemplate.opsForValue().getBit(key, 0);  // 获取所有位
    return count != null && count ? 1 : 0;
}

// 活跃用户统计
public void recordActivity(Long userId) {
    String key = "active:users:" + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
    redisTemplate.opsForValue().setBit(key, userId, true);
}

public long getActiveUsers(LocalDate date) {
    String key = "active:users:" + date.format(DateTimeFormatter.BASIC_ISO_DATE);
    return redisTemplate.opsForValue().bitCount(key);
}
```

## HyperLogLog

### 基本操作

```bash
# 添加
PFADD uv:daily:2024-04-29 user1 user2 user3

# 统计基数（UV）
PFCOUNT uv:daily:2024-04-29

# 合并
PFMERGE uv:weekly uv:daily:2024-04-29 uv:daily:2024-04-30
```

### 业务场景

```java
// UV 统计
public void addUV(String date) {
    String key = "uv:" + date;
    // 添加当前访问用户
    String userId = getCurrentUserId();
    redisTemplate.opsForHyperLogLog().add(key, userId);
}

public long getUV(String date) {
    String key = "uv:" + date;
    return redisTemplate.opsForHyperLogLog().size(key);
}

public long getWeeklyUV(String startDate) {
    LocalDate start = LocalDate.parse(startDate);
    String[] keys = new String[7];
    for (int i = 0; i < 7; i++) {
        keys[i] = "uv:" + start.plusDays(i).format(DateTimeFormatter.BASIC_ISO_DATE);
    }
    return redisTemplate.opsForHyperLogLog().size(keys);
}
```

## GEO 地理位置

### 基本操作

```bash
# 添加位置
GEOADD stores 116.404 39.915 "store:1001"  # 经度 纬度 成员
GEOADD stores 116.408 39.918 "store:1002"

# 查询距离
GEODIST stores store:1001 store:1002 km  # 距离（公里）

# 查询附近
GEORADIUS stores 116.404 39.915 5 km WITHDIST WITHCOORD ASC COUNT 10
GEOSEARCH stores FROMLONLAT 116.404 39.915 BYRADIUS 5 km ASC COUNT 10  # Redis 6.2+
```

### 业务场景

```java
// 附近门店查询
public void addStore(Long storeId, double longitude, double latitude) {
    String key = "stores";
    redisTemplate.opsForGeo().add(key, new Point(longitude, latitude), storeId.toString());
}

public List<StoreVO> searchNearbyStores(double longitude, double latitude, double radiusKm) {
    String key = "stores";
    Circle circle = new Circle(new Point(longitude, latitude), 
        new Distance(radiusKm, Metrics.KILOMETERS));
    RedisGeo.GeoRadiusCommandArgs args = RedisGeo.GeoRadiusCommandArgs
        .newGeoRadiusArgs()
        .includeDistance()
        .includeCoordinates()
        .sortAscending()
        .limit(20);
    
    GeoResults<RedisGeo.GeoLocation<Object>> results = 
        redisTemplate.opsForGeo().radius(key, circle, args);
    
    return results.getContent().stream()
        .map(r -> new StoreVO(
            Long.parseLong(r.getContent().getName().toString()),
            r.getDistance().getValue()))
        .collect(Collectors.toList());
}
```

## 数据结构选型决策表

| 需求 | 推荐数据结构 | 备选方案 |
|------|--------------|----------|
| 缓存对象 | STRING (JSON) | HASH |
| 会话存储 | STRING | - |
| 分布式锁 | STRING (SETNX) | Redisson |
| 计数器 | STRING (INCR) | - |
| 实时排行榜 | ZSET | - |
| 用户标签 | SET | - |
| 消息队列 | LIST | Streams / Kafka |
| 购物车 | HASH | STRING |
| 签到 | BITMAP | SET |
| UV 统计 | HyperLogLog | SET (精确) |
| 附近搜索 | GEO | - |
| 延迟任务 | ZSET | Sorted List |

## 踩坑经验汇总

| 坑点 | 问题 | 解决方案 |
|------|------|----------|
| 内存溢出 | 大 Key 导致 OOM | 拆分 Key、设置 TTL |
| 热 Key | 单 Key QPS 过高 | Hash Tag + 多副本 |
| 持久化阻塞 | RDB/AOF 阻塞主线程 | 使用集群版 |
| 容量规划 | 内存预估不准 | 定期监控 INFO memory |
| 缓存穿透 | 空值穿透 | 布隆过滤器 |
| 缓存击穿 | 热 Key 失效瞬间 | 互斥锁 / 永不过期 |
| 缓存雪崩 | 大量 Key 同时过期 | 过期时间加随机值 |
| 数据一致性 | 缓存与 DB 不一致 | Canal + 双写 |

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
