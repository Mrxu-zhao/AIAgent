# SQL 慢查询优化实战技巧

## 概述

本文档汇总 2024 年最新的 SQL 慢查询优化实战经验，适用于团队技术栈 Java Spring Boot + MyBatis-Plus + MySQL 8.0。

## 慢查询定位

### 开启慢查询日志

```sql
-- 查看慢查询配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 开启慢查询（临时生效）
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;  -- 超过 1 秒记录
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';

-- 永久配置（my.cnf）
[mysqld]
slow_query_log = 1
long_query_time = 1
slow_query_log_file = /var/log/mysql/slow.log
min_examined_row_limit = 1000  -- 扫描行数少于 1000 不记录
```

### 分析慢查询日志

```bash
# 使用 mysqldumpslow 工具分析
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log          # 按时间排序前 10
mysqldumpslow -s c -t 10 /var/log/mysql/slow.log          # 按次数排序前 10
mysqldumpslow -s r -t 10 /var/log/mysql/slow.log          # 按扫描行数排序前 10

# 使用 pt-query-digest（推荐，更强大）
pt-query-digest /var/log/mysql/slow.log
```

### 实时监控

```sql
-- 查看当前正在执行的慢查询
SHOW FULL PROCESSLIST;

-- 使用 performance_schema
SELECT 
    DIGEST_TEXT AS query,
    COUNT_STAR AS exec_count,
    SUM_TIMER_WAIT/1000000000000 AS total_time,
    AVG_TIMER_WAIT/1000000000000 AS avg_time,
    SUM_ROWS_EXAMINED AS rows_scanned
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 10;
```

## 常见慢查询优化

### 1. SELECT * 过度查询

```sql
-- ❌ 错误：查询所有字段，包括 TEXT/BLOB
SELECT * FROM orders o 
JOIN order_items oi ON o.id = oi.order_id
WHERE o.user_id = 1001;

-- ✅ 正确：只查询需要的字段
SELECT o.id, o.order_no, o.amount, oi.product_name, oi.quantity
FROM orders o 
JOIN order_items oi ON o.id = oi.order_id
WHERE o.user_id = 1001;
```

### 2. 分页深度偏移

```sql
-- ❌ 错误：深度分页，OFFSET 越大越慢
SELECT * FROM orders ORDER BY id LIMIT 1000000, 20;

-- ✅ 优化方案一：使用游标分页
SELECT * FROM orders 
WHERE id > 1000000 
ORDER BY id 
LIMIT 20;

-- ✅ 优化方案二：子查询优化
SELECT * FROM orders 
WHERE id >= (SELECT id FROM orders ORDER BY id LIMIT 1000000, 1)
LIMIT 20;

-- ✅ 优化方案三：延迟关联
SELECT o.* FROM orders o
INNER JOIN (SELECT id FROM orders ORDER BY id LIMIT 1000000, 20) t
ON o.id = t.id;
```

### 3. 关联查询优化

```sql
-- ❌ 错误：大表 JOIN 大表
SELECT * FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE o.created_at > '2024-01-01';

-- ✅ 正确：先过滤后关联
SELECT o.id, o.order_no, oi.product_name, p.price
FROM orders o
INNER JOIN (
    SELECT order_id, product_id, product_name 
    FROM order_items 
    WHERE created_at > '2024-01-01'
) oi ON o.id = oi.order_id
INNER JOIN products p ON oi.product_id = p.id
WHERE o.created_at > '2024-01-01';
```

### 4. COUNT(*) 优化

```sql
-- ❌ 错误：全表 COUNT
SELECT COUNT(*) FROM orders WHERE status = 1;

-- ✅ 优化：使用条件统计
SELECT COUNT(*) FROM orders WHERE status = 1 AND id >= 0;

-- ✅ 更好：维护汇总表
-- 定时任务更新统计
INSERT INTO order_stats (date, total_orders, total_amount)
SELECT DATE(created_at), COUNT(*), SUM(amount)
FROM orders
WHERE DATE(created_at) = CURDATE() - INTERVAL 1 DAY
ON DUPLICATE KEY UPDATE 
    total_orders = VALUES(total_orders),
    total_amount = VALUES(total_amount);

-- ✅ 最优：使用 MySQL 8.0 窗口函数
SELECT COUNT(*) OVER(PARTITION BY status) as status_count
FROM orders;
```

### 5. GROUP BY 优化

```sql
-- ❌ 错误：大量数据分组
SELECT user_id, COUNT(*) as order_count 
FROM orders 
GROUP BY user_id 
HAVING COUNT(*) > 10;

-- ✅ 优化：先聚合后筛选
SELECT user_id, order_count FROM (
    SELECT user_id, COUNT(*) as order_count 
    FROM orders 
    GROUP BY user_id
) t WHERE order_count > 10;

-- ✅ 更好：利用索引
SELECT user_id, COUNT(*) as order_count 
FROM orders 
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY user_id, created_at;  -- 添加 created_at 到索引
```

## MyBatis-Plus 优化技巧

### XML Mapper 优化

```xml
<!-- ❌ 错误：在 Mapper 中使用 SELECT * -->
<select id="selectByUserId" resultType="Order">
    SELECT * FROM orders WHERE user_id = #{userId}
</select>

<!-- ✅ 正确：只查询需要的字段 -->
<select id="selectByUserId" resultType="OrderVO">
    SELECT id, order_no, amount, status, created_at 
    FROM orders 
    WHERE user_id = #{userId}
</select>

<!-- ✅ 优化关联查询 -->
<select id="selectOrderWithItems" resultType="OrderDetailVO">
    SELECT 
        o.id, o.order_no, o.amount,
        GROUP_CONCAT(oi.product_name) as product_names
    FROM orders o
    LEFT JOIN order_items oi ON o.id = oi.order_id
    WHERE o.id = #{orderId}
    GROUP BY o.id
</select>
```

### 批量操作优化

```java
// ❌ 错误：循环单条插入
for (Order order : orders) {
    orderMapper.insert(order);
}

// ✅ 正确：批量插入
orderMapper.insertBatchSomeColumn(orders);

// ✅ 批量插入优化：分批处理
int batchSize = 1000;
for (int i = 0; i < orders.size(); i += batchSize) {
    List<Order> batch = orders.subList(i, Math.min(i + batchSize, orders.size()));
    orderMapper.insertBatchSomeColumn(batch);
}
```

### 分页查询优化

```java
// ❌ 错误：使用 Page 参数但没有索引
IPage<Order> page = new Page<>(10000, 20);
orderMapper.selectPage(page, Wrappers.lambdaQuery<Order>()
    .eq(Order::getStatus, 1));

// ✅ 正确：确保有合适索引
IPage<Order> page = new Page<>(1, 20);
orderMapper.selectPage(page, Wrappers.lambdaQuery<Order>()
    .eq(Order::getStatus, 1)
    .orderByDesc(Order::getId));

// ✅ 游标分页（适合超深分页）
List<Order> selectByCursor(Order lastOrder, int limit) {
    return orderMapper.selectList(Wrappers.lambdaQuery<Order>()
        .lt(lastOrder != null, Order::getId, lastOrder.getId())
        .orderByDesc(Order::getId)
        .last("LIMIT " + limit));
}
```

## 2024 新特性应用

### CTE 优化复杂查询

```sql
-- ❌ 旧方式：多层嵌套子查询
SELECT * FROM (
    SELECT * FROM orders WHERE status = 1
) t1 JOIN (
    SELECT * FROM order_items WHERE quantity > 10
) t2 ON t1.id = t2.order_id;

-- ✅ 新方式：使用 CTE（Common Table Expression）
WITH active_orders AS (
    SELECT * FROM orders WHERE status = 1
),
large_items AS (
    SELECT * FROM order_items WHERE quantity > 10
)
SELECT o.*, li.* 
FROM active_orders o
JOIN large_items li ON o.id = li.order_id;
```

### 窗口函数替代子查询

```sql
-- ❌ 旧方式：计算排名需要自关联
SELECT o1.*,
    (SELECT COUNT(*) + 1 FROM orders o2 
     WHERE o2.amount > o1.amount) as rank
FROM orders o1;

-- ✅ 新方式：使用窗口函数
SELECT *,
    RANK() OVER (ORDER BY amount DESC) as rank,
    SUM(amount) OVER (PARTITION BY user_id) as user_total
FROM orders;
```

### JSON 函数优化

```sql
-- ❌ 错误：存储 JSON 后按属性查询
SELECT * FROM config WHERE ext_info->>'$.feature' = 'enabled';

-- ✅ 正确：创建虚拟列索引
ALTER TABLE config ADD COLUMN feature VARCHAR(50) 
    GENERATED ALWAYS AS (ext_info->>'$.feature') STORED;
CREATE INDEX idx_feature ON config(feature);

-- ✅ 查询优化
SELECT * FROM config WHERE feature = 'enabled';
```

## 踩坑经验汇总

| 场景 | 踩坑点 | 解决方案 |
|------|--------|----------|
| 分页查询 | OFFSET 过深 | 改用游标分页或延迟关联 |
| 关联查询 | 大表 JOIN 大表 | 先过滤后关联，拆分为小查询 |
| 聚合查询 | COUNT(*) 全表扫描 | 使用条件索引或汇总表 |
| 模糊查询 | LIKE '%keyword%' | 使用全文索引或 Elasticsearch |
| 批量插入 | 循环单条插入 | 使用 INSERT ... VALUES (),() |
| 日期查询 | 隐式类型转换 | 使用 DATE 函数或 BETWEEN |
| NULL 查询 | 使用 = NULL | 使用 IS NULL / IS NOT NULL |
| OR 查询 | OR 导致索引失效 | 拆分为 UNION ALL |

## 性能测试 Checklist

```sql
-- 优化前后对比测试
EXPLAIN ANALYZE SELECT ...;  -- MySQL 8.0 支持

-- 测试 SQL 执行时间
SET profiling = 1;
SELECT ...;
SHOW PROFILES;

-- 压测工具
-- mysqlslap
mysqlslap --query="SELECT * FROM orders WHERE user_id=1" --iterations=1000

-- sysbench
sysbench oltp_read_only.lua --tables=10 --table-size=100000 prepare
```

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
