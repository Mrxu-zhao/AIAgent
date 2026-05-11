# MySQL 8.0 最佳实践

## 索引设计

### 索引原则

1. **最左前缀匹配**：复合索引 (a,b,c) 支持 a、ab、abc 查询
2. **区分度优先**：选择区分度高的列建立索引
3. **避免冗余索引**：如 (a,b) 和 (a) 冗余

### 索引类型选择

| 类型 | 使用场景 |
|------|---------|
| B-Tree | 默认，适用于范围查询 |
| Hash | 等值查询，不支持范围 |
| 全文索引 | 文本搜索 |
| 复合索引 | 多条件查询 |

### 最佳实践

```sql
-- 避免全表扫描
EXPLAIN SELECT * FROM user WHERE name = '张三';

-- 创建复合索引（区分度高的放前面）
CREATE INDEX idx_user_status_name ON user(status, name);

-- 覆盖索引，减少回表
CREATE INDEX idx_user_cover ON user(status, name) INCLUDE(email);
```

### 禁止事项

- ❌ 避免在索引列上使用函数
- ❌ 避免 % 开头的 LIKE 查询
- ❌ 避免 OR 连接不同条件

## 事务隔离级别

| 级别 | 脏读 | 不可重复读 | 幻读 |
|------|------|----------|------|
| Read Uncommitted | √ | √ | √ |
| Read Committed | × | √ | √ |
| Repeatable Read | × | × | √ |
| Serializable | × | × | × |

**团队建议**：MySQL默认Repeatable Read，大多数场景足够。

### 事务使用规范

```java
// 短事务原则：事务内操作越少越好
@Transactional
public void createOrder(OrderDTO dto) {
    // 校验
    validateOrder(dto);
    
    // 核心操作（保持轻量）
    Order order = new Order();
    orderService.save(order);
    
    // 异步通知（事务外）
    eventPublisher.publish(new OrderCreatedEvent(order));
}
```

## 分库分表策略

### 分片策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 哈希分片 | hash(key) % 数量 | 数据均匀分布 |
| 范围分片 | 按ID/时间范围 | 时序数据 |
| 地理分片 | 按地域 | LBS应用 |

### ShardingSphere 配置示例

```yaml
spring:
  shardingsphere:
    rules:
      sharding:
        tables:
          t_order:
            actual-data-nodes: ds_${0..1}.t_order_${0..15}
            table-strategy:
              standard:
                sharding-column: order_id
                sharding-algorithm-name: order_inline
            key-generate-strategy:
              key-generator: snowflake
```

### 分库分表注意事项

1. **跨分片查询**：使用广播表或ES辅助
2. **分布式事务**：使用Seata AT模式
3. **唯一ID**：使用雪花算法生成器

## SQL编写规范

```sql
-- ✅ 推荐：使用参数化查询
SELECT * FROM user WHERE id = ?

-- ✅ 推荐：分页查询
SELECT * FROM orders 
WHERE status = 1 
ORDER BY create_time DESC 
LIMIT 20 OFFSET 40;

-- ❌ 禁止：SELECT *
SELECT id, name, email FROM user WHERE id = ?

-- ❌ 禁止：隐式类型转换
SELECT * FROM user WHERE phone = 13800138000  -- phone是varchar
```

## 常用运维SQL

```sql
-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query_log';
SHOW FULL PROCESSLIST;

-- 分析执行计划
EXPLAIN ANALYZE SELECT ...

-- 查看索引使用
SHOW INDEX FROM table_name;

-- 批量更新（分批执行）
UPDATE orders SET status = 2 
WHERE status = 1 AND id BETWEEN 1 AND 1000;
```

---

*文档类型：后端技术规范*
*适用范围：后端开发、DBA*
*最后更新：2026-04-29*
