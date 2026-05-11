# DBA 踩坑经验汇总

## 概述

本文档汇总数据库相关的踩坑经验，都是实战中遇到的实际问题及解决方案，供团队成员参考。

## MySQL 踩坑

### 1. 索引相关踩坑

#### 踩坑 1.1：联合索引顺序错误

```sql
-- ❌ 错误：查询频率高的列放在后面
CREATE INDEX idx_status_user ON orders(status, user_id);

-- 场景：查询 WHERE user_id = 1 AND status = 1
-- 这个查询无法有效使用索引，因为跳过了第一列

-- ✅ 正确：按区分度排序，查询频率高的放前面
CREATE INDEX idx_user_status ON orders(user_id, status);

-- ✅ 最佳：按区分度排序
-- 先判断哪个列区分度高
SELECT COUNT(DISTINCT status) / COUNT(*) FROM orders;  -- 0.0001
SELECT COUNT(DISTINCT user_id) / COUNT(*) FROM orders;  -- 0.5
-- user_id 区分度高，放在前面
```

#### 踩坑 1.2：前缀索引长度选择不当

```sql
-- ❌ 错误：固定长度，不验证
ALTER TABLE users ADD INDEX idx_email (email(10));

-- 问题：email@163.com 和 email@126.com 前 10 个字符相同
-- 导致索引选择性很低

-- ✅ 正确：先验证最优长度
SELECT 
    COUNT(DISTINCT LEFT(email, 5)) / COUNT(*) as sel5,
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) as sel10,
    COUNT(DISTINCT LEFT(email, 15)) / COUNT(*) as sel15,
    COUNT(DISTINCT LEFT(email, 20)) / COUNT(*) as sel20
FROM users;
-- 选择性与完整列接近的最小长度

-- ✅ 最佳：使用完整列而非前缀索引
ALTER TABLE users ADD INDEX idx_email (email);
```

#### 踩坑 1.3：忽略隐式类型转换

```sql
-- ❌ 错误：字段类型与查询类型不匹配
CREATE TABLE user_sessions (
    user_id VARCHAR(20) NOT NULL,  -- 用字符串存数字
    ...
    INDEX idx_user_id (user_id)
);

-- 查询时传入整数
SELECT * FROM user_sessions WHERE user_id = 12345;
-- MySQL 会将 user_id 转为数字，导致索引失效

-- ✅ 正确：类型保持一致
CREATE TABLE user_sessions (
    user_id BIGINT NOT NULL,  -- 使用整数类型
    ...
    INDEX idx_user_id (user_id)
);

-- ✅ 修复：如果必须用字符串
SELECT * FROM user_sessions WHERE user_id = '12345';  -- 加引号
```

### 2. SQL 编写踩坑

#### 踩坑 2.1：深度分页

```sql
-- ❌ 错误：OFFSET 过大
SELECT * FROM orders ORDER BY id LIMIT 100000, 20;
-- 问题：MySQL 先扫描 100020 行，丢弃前 100000 行

-- ✅ 优化 1：游标分页（推荐）
SELECT * FROM orders 
WHERE id > 100000 
ORDER BY id 
LIMIT 20;

-- ✅ 优化 2：延迟关联
SELECT o.* FROM orders o
INNER JOIN (SELECT id FROM orders ORDER BY id LIMIT 100000, 20) t
ON o.id = t.id;

-- ✅ 优化 3：记录上次查询最后一条的 ID
-- 前端传入 lastId，查询下一页
```

#### 踩坑 2.2：SELECT * 滥用

```sql
-- ❌ 错误：关联查询返回大量数据
SELECT * FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
JOIN users u ON o.user_id = u.id
WHERE o.user_id = 1001;
-- 返回：订单信息 + 明细 + 商品 + 用户信息

-- ✅ 正确：只查需要的字段
SELECT o.id, o.order_no, oi.product_name, oi.quantity, u.username
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
JOIN users u ON o.user_id = u.id
WHERE o.user_id = 1001;

-- ✅ 更好：使用 JOIN 实现需要的字段
SELECT o.id, o.order_no,
    (SELECT GROUP_CONCAT(product_name) 
     FROM order_items WHERE order_id = o.id) as products
FROM orders o
WHERE o.user_id = 1001;
```

#### 踩坑 2.3：OR 条件导致索引失效

```sql
-- ❌ 错误：OR 导致全表扫描
SELECT * FROM orders WHERE user_id = 1 OR status = 1;
-- 原因：status 列无索引

-- ✅ 优化：拆分为 UNION
SELECT * FROM orders WHERE user_id = 1
UNION ALL
SELECT * FROM orders WHERE user_id != 1 AND status = 1;

-- ✅ 优化：为 status 添加索引
ALTER TABLE orders ADD INDEX idx_status (status);

-- ✅ 优化：使用 IN
SELECT * FROM orders WHERE user_id IN (1, 2, 3) AND status = 1;
```

#### 踩坑 2.4：GROUP BY 不规范

```sql
-- ❌ 错误：SELECT 包含未分组的列
SELECT id, user_id, COUNT(*) as cnt
FROM orders
GROUP BY user_id;
-- MySQL 5.7+ 默认开启 ONLY_FULL_GROUP_BY
-- 会报错：Expression #1 of SELECT list is not in GROUP BY

-- ✅ 正确：只 SELECT 分组列和聚合函数
SELECT user_id, COUNT(*) as order_count
FROM orders
GROUP BY user_id;

-- ✅ 正确：使用 ANY_VALUE 显式声明
SELECT ANY_VALUE(id), user_id, COUNT(*) as cnt
FROM orders
GROUP BY user_id;

-- ✅ 正确：关闭 ONLY_FULL_GROUP_BY（需评估）
SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));
```

### 3. 表设计踩坑

#### 踩坑 3.1：主键类型选择错误

```sql
-- ❌ 错误：使用 INT 作为主键
CREATE TABLE orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ...
);
-- 问题：INT 最大值 21 亿，不够用

-- ✅ 正确：使用 BIGINT UNSIGNED
CREATE TABLE orders (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ...
);

-- ✅ 迁移方案（历史表）
ALTER TABLE orders MODIFY id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT;
```

#### 踩坑 3.2：金额字段用 DOUBLE

```sql
-- ❌ 错误：使用 DOUBLE/FLOAT 存金额
CREATE TABLE products (
    price DOUBLE(10,2),  -- 精度丢失
    ...
);

-- ❌ 问题演示
INSERT INTO products (price) VALUES (0.07);
SELECT * FROM products;
-- 可能得到 0.06999999999999999

-- ✅ 正确：使用 DECIMAL
CREATE TABLE products (
    price DECIMAL(10,2) NOT NULL,
    ...
);

-- ✅ Java 代码注意
// 使用 BigDecimal 而非 double
private BigDecimal price;  // 正确
private Double price;      // 错误
```

#### 踩坑 3.3：时间字段用 TIMESTAMP

```sql
-- ❌ 错误：使用 TIMESTAMP 存时间
CREATE TABLE orders (
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ...
);
-- 问题：2038 年问题，只到 2038-01-19 03:14:07

-- ✅ 正确：使用 DATETIME
CREATE TABLE orders (
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ...
);

-- ✅ 注意时区
SET time_zone = '+08:00';  -- 统一使用东八区
```

#### 踩坑 3.4：字段过长不拆分

```sql
-- ❌ 错误：TEXT 字段建普通索引
CREATE TABLE articles (
    id BIGINT PRIMARY KEY,
    title VARCHAR(500),
    content TEXT,  -- 很大
    INDEX idx_content (content)  -- 报错：TEXT 不能直接建索引
);

-- ✅ 正确：使用前缀索引或全文索引
CREATE TABLE articles (
    id BIGINT PRIMARY KEY,
    title VARCHAR(500),
    content TEXT,
    FULLTEXT INDEX ft_content (title, content)  -- 全文索引
);

-- 模糊查询改用 MATCH...AGAINST
SELECT * FROM articles 
WHERE MATCH(title, content) AGAINST('关键词');
```

### 4. 事务踩坑

#### 踩坑 4.1：长事务风险

```java
// ❌ 错误：在事务内进行远程调用
@Transactional
public void createOrder(Order order) {
    // 1. 插入订单
    orderMapper.insert(order);
    
    // 2. 发送消息（耗时 3 秒）
    mqClient.send(order);
    
    // 3. 发送短信（耗时 2 秒）
    smsClient.send(order.getMobile());
    
    // 事务时间过长，锁表过久
}

-- ✅ 正确：拆分事务
@Transactional
public void createOrder(Order order) {
    orderMapper.insert(order);
}

@Async
public void sendNotification(Order order) {
    mqClient.send(order);
    smsClient.send(order.getMobile());
}
```

#### 踩坑 4.2：Spring 事务失效

```java
// ❌ 错误：private 方法加 @Transactional
@Transactional
private void doSomething() {
    orderMapper.insert(order);  // 不生效
}
-- 原因：Spring AOP 不能代理 private 方法

// ✅ 正确：public 方法
@Transactional
public void createOrder(Order order) {
    orderMapper.insert(order);
}

// ❌ 错误：同类内部调用
public class OrderService {
    public void methodA() {
        this.methodB();  // 不会走代理
    }
    
    @Transactional
    public void methodB() {
        orderMapper.insert(order);  // 不生效
    }
}

// ✅ 正确：注入自身或使用 AopContext
@Service
public class OrderService {
    @Autowired
    private OrderService self;  // 自身代理
    
    public void methodA() {
        self.methodB();  // 走代理
    }
    
    @Transactional
    public void methodB() {
        orderMapper.insert(order);  // 生效
    }
}
```

### 5. 索引维护踩坑

#### 踩坑 5.1：删除数据后表空间不释放

```sql
-- 场景：DELETE 大量数据后，表文件大小没变
DELETE FROM logs WHERE created_at < '2024-01-01';
-- 60 万条数据已删除，但 .ibd 文件还是 10GB

-- ✅ 方案 1：OPTIMIZE TABLE（会锁表）
OPTIMIZE TABLE logs;

-- ✅ 方案 2：空表迁移
ALTER TABLE logs ENGINE=InnoDB;

-- ✅ 方案 3：pt-online-schema-change（不锁表）
pt-online-schema-change --alter "ENGINE=InnoDB" D=ticket,t=logs

-- ✅ 方案 4：分区表（最佳）
CREATE TABLE logs (
    id BIGINT,
    ...
    created_at DATETIME
) PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);

-- 删除历史分区
ALTER TABLE logs DROP PARTITION p2023;
```

#### 踩坑 5.2：在线加索引阻塞

```sql
-- ❌ 错误：在业务高峰期在线加索引
ALTER TABLE orders ADD INDEX idx_user_status(user_id, status);
-- 问题：会锁表！对于大表可能锁几小时

-- ✅ 正确：使用 pt-online-schema-change
pt-online-schema-change \
    --alter "ADD INDEX idx_user_status(user_id, status)" \
    --user=root \
    --password=xxx \
    --database=shop \
    --tables=orders

-- ✅ MySQL 8.0 可使用 Instant ADD COLUMN
-- 但 ADD INDEX 仍需重建
```

### 6. 配置踩坑

#### 踩坑 6.1：max_connections 设置过大

```sql
-- ❌ 错误：设置为 100000
SET GLOBAL max_connections = 100000;
-- 问题：每个连接占用内存，100000 连接可能占用 10GB+

-- ✅ 正确：根据服务器内存设置
-- 计算公式：max_connections = 可用内存 / 单连接内存
-- 单连接内存约 100-200KB
-- 16GB 服务器：16000 / 200 = 80 个连接

-- ✅ 正确：使用连接池
-- HikariCP 推荐
spring:
  datasource:
    hikari:
      maximum-pool-size: 50  # 比 max_connections 小
      minimum-idle: 10
```

#### 踩坑 6.2：binlog 保留时间过长

```sql
-- ❌ 错误：binlog 保留 30 天
expire_logs_days = 30
-- 问题：每天 100GB binlog，30 天就是 3TB！

-- ✅ 正确：根据磁盘空间计算
-- 假设每天写入 100GB binlog，磁盘 1TB
-- 保留 7 天：700GB，安全
expire_logs_days = 7

-- ✅ 更好：使用 binlog_expire_logs_seconds
binlog_expire_logs_seconds = 604800  # 7 天

-- ✅ 使用 PURGE 手动清理
PURGE BINARY LOGS TO 'mysql-bin.000100';  -- 清理到某个文件
PURGE BINARY LOGS BEFORE '2024-04-01 00:00:00';  -- 清理到某个时间
```

## Redis 踩坑

### 1. 缓存踩坑

#### 踩坑 1.1：缓存穿透

```sql
-- ❌ 场景：查询不存在的用户
SELECT * FROM users WHERE id = -1;
-- 每次都查数据库，但返回空

-- ✅ 方案 1：缓存空值
public User getUser(Long userId) {
    String key = "user:" + userId;
    String cached = redisTemplate.opsForValue().get(key);
    if ("NULL".equals(cached)) {
        return null;
    }
    if (cached != null) {
        return JSON.parseObject(cached, User.class);
    }
    
    User user = userMapper.selectById(userId);
    if (user == null) {
        redisTemplate.opsForValue().set(key, "NULL", Duration.ofMinutes(5));
    } else {
        redisTemplate.opsForValue().set(key, JSON.toJSONString(user), Duration.ofHours(1));
    }
    return user;
}

-- ✅ 方案 2：布隆过滤器（更优）
public class BloomFilterUtil {
    private static BloomFilter<Long> bloomFilter = BloomFilter.create(
        Funnels.longFunnel(), 1000000, 0.01);
    
    public void addUserId(Long userId) {
        bloomFilter.put(userId);
    }
    
    public boolean mightContain(Long userId) {
        return bloomFilter.mightContain(userId);
    }
}
```

#### 踩坑 1.2：缓存击穿

```java
// ❌ 场景：热点 key 过期瞬间，大量请求打到数据库
// 某个商品信息，缓存过期时间是 1 小时
// 到期瞬间，1000 个请求同时穿透

// ✅ 方案 1：互斥锁
public String getProductInfo(Long productId) {
    String key = "product:" + productId;
    String cached = redisTemplate.opsForValue().get(key);
    if (cached != null) {
        return cached;
    }
    
    // 获取锁
    String lockKey = "lock:product:" + productId;
    String lockValue = UUID.randomUUID().toString();
    Boolean locked = redisTemplate.opsForValue().setIfAbsent(lockKey, lockValue, Duration.ofSeconds(10));
    
    if (locked) {
        try {
            // 查数据库
            String data = queryFromDB(productId);
            redisTemplate.opsForValue().set(key, data, Duration.ofHours(1));
            return data;
        } finally {
            // 释放锁
            redisTemplate.delete(lockKey);
        }
    } else {
        // 等待其他线程加载完成
        Thread.sleep(100);
        return redisTemplate.opsForValue().get(key);
    }
}

// ✅ 方案 2：永不过期 + 异步更新
public String getProductInfo(Long productId) {
    String key = "product:" + productId;
    String cached = redisTemplate.opsForValue().get(key);
    if (cached != null) {
        ProductVO vo = JSON.parseObject(cached, ProductVO.class);
        // 如果数据过期，异步更新
        if (vo.getCacheTime() < System.currentTimeMillis() - 3600000) {
            CompletableFuture.runAsync(() -> refreshCache(productId));
        }
        return cached;
    }
    // 缓存不存在，直接查库并设置
    return refreshCache(productId);
}
```

#### 踩坑 1.3：缓存雪崩

```java
// ❌ 场景：大量 key 同时过期
// 比如：大量商品缓存都设置 1 小时过期
// 到点全部失效，数据库被打爆

// ✅ 方案 1：过期时间加随机值
public void setProductCache(Long productId, String data) {
    String key = "product:" + productId;
    // 1 小时基础过期时间 + 最多 10 分钟随机
    int expireSeconds = 3600 + new Random().nextInt(600);
    redisTemplate.opsForValue().set(key, data, Duration.ofSeconds(expireSeconds));
}

// ✅ 方案 2：多级缓存
// L1: Caffeine（本地缓存，1 分钟）
// L2: Redis（分布式缓存，10 分钟）
// L3: MySQL（数据库）

// ✅ 方案 3：Redis 集群高可用
// 使用 Redis Sentinel 或 Redis Cluster
// 防止 Redis 单点故障导致缓存失效
```

### 2. 内存踩坑

#### 踩坑 2.1：大 Key 问题

```bash
# ❌ 问题：某个 Key 占用内存过大
# 比如：用户购物车，一个用户可能有几万条商品

# 诊断
redis-cli --bigkeys  # 找出大 Key

# 场景：社交系统，朋友圈内容
# @user:1001:timeline 可能有 10000 条记录
# 每次 LPUSH 都遍历整个列表

# ✅ 优化 1：分段存储
# 改用 ZSET，按时间分桶
ZADD timeline:user:1001:2024-04 1234567890 "post_id"
# 每天一个 key，避免单个 key 过大

# ✅ 优化 2：限制列表长度
LTRIM timeline:user:1001 0 999  # 只保留最新的 1000 条
```

#### 踩坑 2.2：热 Key 问题

```bash
# ❌ 问题：某个 Key QPS 过高
# 比如：秒杀商品，库存 key 被大量请求

# 诊断
redis-cli --hotkeys  # 找出热 Key

# ✅ 优化 1：Key 分片
# 库存从 1 个 key 改为 10 个
SET stock:1 100
SET stock:2 100
...
# 查询时随机选一个
int shard = new Random().nextInt(10);

# ✅ 优化 2：本地缓存
// 使用 Redis 做集中存储，热点数据本地缓存
private Map<Long, Integer> localCache = new ConcurrentHashMap<>();

public int getStock(Long productId) {
    // 先查本地缓存
    if (localCache.containsKey(productId)) {
        return localCache.get(productId);
    }
    // 查 Redis
    Integer stock = Integer.parseInt(redisTemplate.opsForValue().get("stock:" + productId));
    localCache.put(productId, stock);
    return stock;
}
```

### 3. 持久化踩坑

#### 踩坑 3.1：AOF 刷盘策略不当

```bash
# ❌ 错误：everysec 模式在高并发下丢数据
appendfsync everysec
# 最多可能丢失 1 秒数据

# ✅ 推荐：always 模式（数据安全优先）
appendfsync always
# 每次操作都刷盘，性能略低但数据不丢

# ✅ 折中：no + 外部监控
appendfsync no
# 操作系统决定刷盘，性能最高但可能丢更多数据
# 需要配合监控和备份

# ✅ MySQL 团队方案：使用 RDB + AOF
appendonly yes
appendfsync everysec
save 900 1      # 15 分钟内有 1 个 key 变化则保存 RDB
save 300 10     # 5 分钟内有 10 个 key 变化则保存 RDB
```

## 总结 Checklist

### 上线前检查

```markdown
## MySQL 检查清单
- [ ] 主键使用 BIGINT UNSIGNED
- [ ] 金额使用 DECIMAL
- [ ] 时间使用 DATETIME
- [ ] 字段有适当索引
- [ ] 避免 SELECT *
- [ ] 分页使用游标或限制 OFFSET
- [ ] 事务不要过长
- [ ] 避免大事务

## Redis 检查清单
- [ ] 热点数据有缓存
- [ ] 设置合理 TTL
- [ ] 避免缓存穿透（空值 / 布隆过滤器）
- [ ] 避免缓存击穿（互斥锁 / 永不过期）
- [ ] 避免缓存雪崩（随机 TTL / 多级缓存）
- [ ] 大 Key 已拆分
- [ ] 热 Key 已识别
- [ ] 内存使用率 < 70%
```

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
