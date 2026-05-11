# MySQL 慢查询分析和优化思路

> 作者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29

## 1. 慢查询日志配置

### 1.1 开启慢查询日志

```sql
-- 查看慢查询配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';
SET GLOBAL long_query_time = 1;  -- 超过1秒记录
SET GLOBAL log_queries_not_using_indexes = 'ON';  -- 记录未使用索引的查询
```

### 1.2 永久配置 (my.cnf)

```ini
[mysqld]
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 1
log_queries_not_using_indexes = 1
min_examined_row_limit = 1000  -- 只记录扫描超过1000行的查询
```

## 2. 慢查询分析工具

### 2.1 mysqldumpslow

```bash
# 查看最慢的10条SQL
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

# 参数说明:
# -s: 排序方式 (c=次数, t=时间, l=锁定时间)
# -t: 显示前N条
# -g: 正则匹配

# 示例
mysqldumpslow -s c -t 20 /var/log/mysql/slow.log    # 按次数排序
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log    # 按时间排序
mysqldumpslow -s l -t 10 /var/log/mysql/slow.log    # 按锁定时间排序
```

### 2.2 pt-query-digest

```bash
# 安装
# yum install percona-toolkit

# 分析慢查询
pt-query-digest /var/log/mysql/slow.log

# 输出到文件
pt-query-digest slow.log > report.txt

# 分析最近24小时的查询
pt-query-digest --since=24h /var/log/mysql/slow.log

# 只分析特定数据库
pt-query-digest --filter '$event->{db} eq "mydb"' slow.log
```

## 3. EXPLAIN 执行计划分析

### 3.1 EXPLAIN 用法

```sql
EXPLAIN SELECT * FROM users WHERE username = 'john';

+------+-------------+-------+------------+------+---------------+------+---------+-------+
| id   | select_type| table | type       | key  | rows          | Extra| Ref    | Cost  |
+------+-------------+-------+------------+------+---------------+------+---------+-------+
|    1 | SIMPLE     | users | const      | name |             1 |      | const  | 1.00  |
+------+-------------+-------+------------+------+---------------+------+---------+-------+
```

### 3.2 关键字段解读

```yaml
EXPLAIN 字段分析:

type (连接类型):
├── system:     系统表，只有1行
├── const:      常量连接，使用主键或唯一索引
├── eq_ref:     多表连接，使用主键或唯一索引
├── ref:        使用非唯一索引
├── range:      索引范围扫描
├── index:      全索引扫描
└── ALL:        全表扫描 ⚠️ 需要优化

key (使用的索引):
- 显示实际使用的索引
- NULL表示未使用索引 ⚠️

rows (扫描行数):
- 估算需要扫描的行数
- 数值越大，性能越差

Extra (额外信息):
├── Using index:          使用覆盖索引 ✓
├── Using where:          使用WHERE过滤
├── Using temporary:     使用临时表 ⚠️
├── Using filesort:       文件排序 ⚠️
├── Using index condition: 使用索引下推
└── Using MRR:            使用MRR优化
```

### 3.3 优化示例

```sql
-- 优化前: 全表扫描
EXPLAIN SELECT * FROM orders WHERE YEAR(create_time) = 2026;
+------+-------------+--------+------+---------------+------+
| type | key         | rows   | Extra               |
+------+-------------+--------+----+------------------+
| ALL  | NULL        | 100000 | Using where        |
+------+-------------+--------+------+---------------+------+
问题: YEAR()函数导致索引失效

-- 优化后: 使用范围查询
EXPLAIN SELECT * FROM orders 
WHERE create_time >= '2026-01-01' 
  AND create_time < '2027-01-01';
+------+-------------+--------+------+---------------+------+
| type | key         | rows   | Extra               |
+------+-------------+--------+----+------------------+
| range| idx_create  | 10000  | Using index condition|
+------+-------------+--------+------+---------------+------+
```

## 4. 常见慢查询场景

### 4.1 场景1: 全表扫描

```sql
-- 问题SQL
SELECT * FROM users WHERE name LIKE '%john%';

-- 优化方案
-- 1. 使用搜索引擎
ALTER TABLE users ADD FULLTEXT INDEX idx_name(name);
SELECT * FROM users WHERE MATCH(name) AGAINST('john');

-- 2. 业务优化
--    - 限制返回数量
--    - 添加搜索条件
--    - 使用ES等搜索引擎
```

### 4.2 场景2: 缺失索引

```sql
-- 问题: 频繁查询的字段无索引
SELECT * FROM orders WHERE customer_id = 12345;
SELECT * FROM orders WHERE status = 'pending';

-- 解决: 添加索引
ALTER TABLE orders ADD INDEX idx_customer_id(customer_id);
ALTER TABLE orders ADD INDEX idx_status(status);
ALTER TABLE orders ADD INDEX idx_customer_status(customer_id, status);
```

### 4.3 场景3: 隐式类型转换

```sql
-- 表结构: user_id VARCHAR(20)
-- 查询:   user_id = 12345 (传入整数)

-- 问题SQL (索引失效)
SELECT * FROM users WHERE user_id = 12345;

-- 优化方案
SELECT * FROM users WHERE user_id = '12345';
```

### 4.4 场景4: 深度分页

```sql
-- 问题: LIMIT 100000, 10
SELECT * FROM orders ORDER BY id LIMIT 100000, 10;
-- 需要扫描100010行

-- 优化方案1: 使用ID游标
SELECT * FROM orders WHERE id > 100000 ORDER BY id LIMIT 10;
-- 只需扫描10行

-- 优化方案2: 使用延迟关联
SELECT t.* FROM (
  SELECT id FROM orders ORDER BY id LIMIT 100000, 10
) AS t JOIN orders USING(id);

-- 优化方案3: 记录总数优化
SELECT SQL_CALC_FOUND_ROWS * FROM orders LIMIT 100000, 10;
SELECT FOUND_ROWS();
```

### 4.5 场景5: 慢JOIN

```sql
-- 问题: 大表JOIN
SELECT o.*, u.name 
FROM orders o 
JOIN users u ON o.user_id = u.id 
WHERE o.create_time > '2026-01-01';

-- 优化方案
-- 1. 确保JOIN字段有索引
ALTER TABLE orders ADD INDEX idx_user_id(user_id);

-- 2. 控制驱动表顺序 (小表驱动大表)
EXPLAIN SELECT * FROM small_table s JOIN large_table l ON s.id = l.sid;

-- 3. 添加查询条件
SELECT o.*, u.name 
FROM orders o 
JOIN users u ON o.user_id = u.id 
WHERE o.create_time > '2026-01-01'
  AND o.status = 'completed';

-- 4. 拆分为多次查询
--    - 先查小表获取ID列表
--    - 再用IN查询大表
```

## 5. 索引优化

### 5.1 索引设计原则

```yaml
索引设计原则:

1. 选择性高的字段优先
   -- 性别字段选择性低，不适合建索引
   -- 用户ID/订单ID选择性强，适合建索引

2. 联合索引设计
   -- 最左前缀原则
   -- 区分度高的放左边
   -- 例: (status, create_time) 比 (create_time, status) 更好

3. 覆盖索引
   -- SELECT * 不利于覆盖索引
   -- 尽量只查索引字段

4. 避免冗余索引
   -- 已有的索引不要重复创建
   -- (a) 和 (a,b) 存在冗余
```

### 5.2 联合索引设计

```sql
-- 查询条件
WHERE status = 'active' AND create_time > '2026-01-01'

-- 最佳索引
ALTER TABLE orders ADD INDEX idx_status_time(status, create_time);

-- 索引创建顺序:
-- 1. 等值查询字段 (status)
-- 2. 范围查询字段 (create_time)

-- 验证索引使用
EXPLAIN SELECT * FROM orders 
WHERE status = 'active' AND create_time > '2026-01-01';
```

### 5.3 索引失效场景

```sql
-- 1. 使用函数
SELECT * FROM orders WHERE YEAR(create_time) = 2026;  -- 失效
SELECT * FROM orders WHERE create_time >= '2026-01-01'; -- 生效

-- 2. 使用OR (部分失效)
SELECT * FROM users WHERE name = 'john' OR email = 'john@test.com';
-- 解决: 创建联合索引

-- 3. 类型转换
SELECT * FROM users WHERE phone = 13800138000;  -- phone是VARCHAR
SELECT * FROM users WHERE phone = '13800138000'; -- 正确

-- 4. LIKE前置通配符
SELECT * FROM users WHERE name LIKE '%john%';  -- 失效
SELECT * FROM users WHERE name LIKE 'john%';   -- 生效

-- 5. NOT NULL判断
SELECT * FROM users WHERE age IS NOT NULL;  -- 可能失效
SELECT * FROM users WHERE age > 0;          -- 生效
```

## 6. SQL 性能分析实战

### 6.1 慢查询分析流程

```
慢查询分析流程:

1. 收集慢查询日志
   pt-query-digest slow.log > report.txt

2. 识别TOP SQL
   - 执行次数最多的
   - 执行时间最长的
   - 扫描行数最多的

3. 分析执行计划
   EXPLAIN [FORMAT=JSON] <SQL>

4. 优化SQL
   - 添加索引
   - 重写SQL
   - 拆分复杂查询

5. 验证效果
   - 对比优化前后
   - 观察监控指标
```

### 6.2 性能问题诊断

```sql
-- 1. 查看当前连接
SHOW PROCESSLIST;

-- 2. 查看锁等待
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
SELECT * FROM information_schema.INNODB_LOCKS;

-- 3. 查看事务
SELECT * FROM information_schema.INNODB_TRX;

-- 4. 查看表状态
SHOW TABLE STATUS FROM db_name LIKE 'orders';

-- 5. 查看索引
SHOW INDEX FROM orders;

-- 6. 查看表大小
SELECT 
  table_name,
  ROUND(data_length/1024/1024, 2) AS 'MB',
  ROUND(index_length/1024/1024, 2) AS 'idx MB'
FROM information_schema.tables 
WHERE table_schema = 'mydb';
```

### 6.3 优化案例

```sql
-- 原始慢SQL (执行时间: 5秒)
SELECT o.*, u.username, u.email, p.product_name
FROM orders o
JOIN users u ON o.user_id = u.id
JOIN products p ON o.product_id = p.id
WHERE o.status = 'pending'
  AND o.create_time BETWEEN '2026-01-01' AND '2026-03-31'
ORDER BY o.create_time DESC;

-- 问题分析:
-- 1. 无status索引
-- 2. 无create_time索引
-- 3. 无覆盖索引
-- 4. 排序字段无索引

-- 优化后SQL (执行时间: 50ms)
-- 1. 添加索引
ALTER TABLE orders ADD INDEX idx_status_time(status, create_time);
ALTER TABLE orders ADD INDEX idx_status_time_user(status, create_time, user_id);

-- 2. 使用覆盖索引
SELECT o.id, o.create_time, o.amount,
       u.username, u.email,
       p.product_name
FROM orders o
JOIN users u ON o.user_id = u.id
JOIN products p ON o.product_id = p.id
WHERE o.status = 'pending'
  AND o.create_time BETWEEN '2026-01-01' AND '2026-03-31'
ORDER BY o.create_time DESC;
```

---

*相关文档：[Redis 性能问题排查](./redis-performance-troubleshooting.md)*  
*返回：[QA 性能测试知识库索引](../index.md)*
