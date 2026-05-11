# MySQL 事务隔离级别与锁机制

## 概述

理解 MySQL 的事务隔离级别和锁机制是解决并发问题、保证数据一致性的基础。本文详细讲解四种隔离级别、MVCC 原理及常见锁场景。

## 四种隔离级别

### 隔离级别对比

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 并发性能 |
|----------|------|------------|------|----------|
| READ UNCOMMITTED | ✅ 可能 | ✅ 可能 | ✅ 可能 | 最高 |
| READ COMMITTED | ❌ 不可能 | ✅ 可能 | ✅ 可能 | 较高 |
| REPEATABLE READ (默认) | ❌ 不可能 | ❌ 不可能 | ✅ 可能 | 中等 |
| SERIALIZABLE | ❌ 不可能 | ❌ 不可能 | ❌ 不可能 | 最低 |

### 设置隔离级别

```sql
-- 查看当前会话隔离级别
SELECT @@transaction_isolation;

-- 设置当前会话隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 设置全局隔离级别
SET GLOBAL transaction_isolation = 'READ-COMMITTED';

-- 永久配置（my.cnf）
[mysqld]
transaction-isolation = READ-COMMITTED
```

## 事务隔离级别详解

### READ UNCOMMITTED（读未提交）

```sql
-- Session 1: 开启事务，修改数据（未提交）
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;

-- Session 2: 开启事务，读取数据（读到了未提交的数据）
BEGIN;
SELECT balance FROM account WHERE id = 1;
-- 结果: 900（脏读）
-- 如果 Session 1 回滚，数据实际没变，但 Session 2 已经使用了这个数据

-- Session 1: 回滚
ROLLBACK;

-- Session 2: 再次查询
SELECT balance FROM account WHERE id = 1;
-- 结果: 1000（和之前读的不一样）
```

### READ COMMITTED（读已提交）

```sql
-- Session 1: 开启事务，修改数据
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- Session 2: 开启事务，读取数据
BEGIN;
SELECT balance FROM account WHERE id = 1;
-- 结果: 1000（读不到未提交的，只能读到已提交的）

-- Session 1: 提交后
-- Session 2: 再次读取
SELECT balance FROM account WHERE id = 1;
-- 结果: 900（和之前读的不一样，叫不可重复读）
```

### REPEATABLE READ（可重复读）- MySQL 默认

```sql
-- Session 1: 开启事务，修改数据
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- Session 2: 开启事务，读取数据
BEGIN;
SELECT balance FROM account WHERE id = 1;
-- 结果: 1000（在事务内，多次读取结果一致）

-- Session 1: 提交后
-- Session 2: 再次读取
SELECT balance FROM account WHERE id = 1;
-- 结果: 1000（和之前读的一样，叫可重复读）
-- MySQL 使用 MVCC 实现

-- 但是：INSERT 可能产生幻读
SELECT * FROM orders WHERE status = 'pending';
-- 0 rows
-- Session 1: INSERT 一条 pending 订单
INSERT INTO orders (...) VALUES (...);
COMMIT;
-- Session 2: 再查询
SELECT * FROM orders WHERE status = 'pending';
-- 1 row（幻读：多了一条）
```

### SERIALIZABLE（串行化）

```sql
-- Session 1: 开启事务，读取数据
BEGIN;
SELECT balance FROM account WHERE id = 1;
-- Session 2: 也读取，会被阻塞
SELECT balance FROM account WHERE id = 1;
-- Session 1: 提交
COMMIT;
-- Session 2: 此时才能读取到结果
```

## MVCC 原理

### 原理图

```
┌─────────────────────────────────────────────────┐
│ InnoDB 行结构                                    │
├─────────────────────────────────────────────────┤
│ db_trx_id: 事务 ID                               │
│ db_roll_ptr: 回滚指针                            │
│ DELETE_BIT: 删除标记                            │
├─────────────────────────────────────────────────┤
│                                                 │
│  每行数据可能有多个版本（undo log 链）           │
│                                                 │
│  [行数据] ← [undo log 2] ← [undo log 1]         │
│  trx:3      trx:2        trx:1                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### ReadView 机制

```sql
-- READ COMMITTED: 每次读取都生成新的 ReadView
-- 事务 A: 读取时生成 ReadView-A
-- 事务 B: 提交后，事务 A 再次读取，生成新的 ReadView-A'
-- 可以看到事务 B 的修改

-- REPEATABLE READ: 事务开始时生成 ReadView，之后复用
-- 事务 A: 事务开始时生成 ReadView-A
-- 事务 B: 提交后，事务 A 再次读取，仍使用 ReadView-A
-- 看不到事务 B 的修改（因为 ReadView 不变）
```

### MVCC 示例

```sql
-- 时间线:
-- T1: 事务 A (ID=100) 开始
-- T2: 事务 B (ID=101) 开始
-- T3: 事务 B 修改 id=1 的行，balance=900
-- T4: 事务 A 读取 id=1 的行
-- T5: 事务 B 提交
-- T6: 事务 A 再次读取 id=1 的行

-- READ COMMITTED 结果:
-- T4: balance=1000（看不到 B 的修改）
-- T6: balance=900（能看到 B 的提交）

-- REPEATABLE READ 结果:
-- T4: balance=1000（看不到 B 的修改）
-- T6: balance=1000（仍看不到，因为 ReadView 不变）
```

## 锁机制

### 锁类型

| 类型 | 粒度 | 说明 |
|------|------|------|
| 行锁 (Record Lock) | 行 | 锁定单行记录 |
| 间隙锁 (Gap Lock) | 范围 | 锁定行之间的间隙 |
| Next-Key Lock | 行+间隙 | 锁定行及其前后间隙 |
| 意向锁 | 表 | 表级锁，表明正在锁定某些行 |

### 锁模式

| 模式 | 说明 | 兼容 |
|------|------|------|
| 共享锁 (S) | 允许读取，阻止写 | 与 S 兼容，与 X 互斥 |
| 排他锁 (X) | 允许读写，阻止其他锁 | 与 S、X 都互斥 |

### 行锁示例

```sql
-- 共享锁：读取数据时加锁
BEGIN;
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE;
-- 其他事务可以读取，但不能修改

-- 排他锁：修改数据时加锁
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 其他事务不能读取也不能修改

-- 普通 SELECT（不加锁）
BEGIN;
SELECT * FROM orders WHERE id = 1;
-- 使用 MVCC 读取快照，不加锁
```

### 间隙锁示例

```sql
-- REPEATABLE READ 隔离级别下
BEGIN;
SELECT * FROM orders WHERE id BETWEEN 10 AND 20 FOR UPDATE;
-- 锁定的范围: (-∞, 10), [10, 20], (20, +∞)
-- 即使 id=10, 20 不存在，也会锁定

-- 场景：防止幻读
-- Session 1: 锁定 id > 10 AND id < 20 的范围
-- Session 2: 无法插入 id=15 的记录
```

### Next-Key Lock 示例

```sql
-- 等值查询的 Next-Key Lock
BEGIN;
SELECT * FROM orders WHERE id = 10 FOR UPDATE;
-- 锁定: (上一个值, 10] 区间

-- 索引上的 Next-Key Lock
-- orders 表有索引 idx_status(status)
-- 执行: SELECT * FROM orders WHERE status = 'pending' FOR UPDATE;
-- 锁定: 所有 status='pending' 的行及其间隙

-- 唯一索引等值查询
-- 只锁定行本身，不锁定间隙
SELECT * FROM orders WHERE id = 10 FOR UPDATE;
-- 只锁定 id=10 的行
```

## 锁问题诊断

### 查看锁等待

```sql
-- 查看当前锁等待
SELECT 
    r.trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    r.trx_query AS waiting_query,
    b.trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    b.trx_query AS blocking_query
FROM information_schema.INNODB_LOCK_WAITS w
JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id
JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id;

-- 查看当前锁
SELECT 
    trx_id,
    trx_state,
    trx_started,
    trx_rows_locked,
    trx_mysql_thread_id,
    trx_query
FROM information_schema.INNODB_TRX;

-- 查看锁详情
SELECT 
    lock_id,
    lock_trx_id,
    lock_mode,
    lock_type,
    lock_table,
    lock_index,
    lock_space,
    lock_page,
    lock_rec,
    lock_data
FROM information_schema.INNODB_LOCKS;
```

### 死锁处理

```sql
-- 查看死锁日志
SHOW ENGINE INNODB STATUS;

-- 示例输出:
-- LATEST DETECTED DEADLOCK
-- *** (1) TRANSACTION:
-- TRANSACTION 12345, ACTIVE 5 sec inserting
-- mysql tables in use 1, locked 1
-- LOCK WAIT 2 lock struct(s), heap size 376
-- ... (锁等待链详情)

-- *** (2) TRANSACTION:
-- TRANSACTION 12346, ACTIVE 5 sec inserting
-- mysql tables in use 1, locked 1
-- ... (另一个事务的锁信息)

-- *** (1) TRANSACTION: ROLLBACK
-- InnoDB 会自动回滚一个事务解决死锁
```

### 锁优化建议

```sql
-- 1. 按固定顺序访问数据（避免循环依赖）
-- Session A: 锁 A → 锁 B
-- Session B: 锁 A → 锁 B（避免：锁 B → 锁 A）

-- 2. 减小事务大小
-- ❌ 错误：大事务
BEGIN;
UPDATE orders ... WHERE ...;  -- 大量数据
INSERT INTO order_logs ...;
UPDATE order_stats ...;
COMMIT;

-- ✅ 正确：拆分小事务
BEGIN;
UPDATE orders ... WHERE id IN (1,2,3);
COMMIT;

BEGIN;
INSERT INTO order_logs ...;
COMMIT;

-- 3. 使用低隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 4. 添加适当索引（减少锁范围）
CREATE INDEX idx_user_status ON orders(user_id, status);
```

## Spring 事务实践

### 编程式事务

```java
@Service
public class OrderService {
    
    @Autowired
    private TransactionTemplate transactionTemplate;
    
    public void createOrder(Order order) {
        transactionTemplate.executeWithoutResult(status -> {
            // 业务逻辑
            orderMapper.insert(order);
            // 如果抛异常，事务自动回滚
        });
    }
}
```

### 声明式事务

```java
@Service
public class OrderService {
    
    // 默认：RuntimeException + Error 回滚
    @Transactional
    public void createOrder(Order order) {
        orderMapper.insert(order);
    }
    
    // 指定回滚异常
    @Transactional(rollbackFor = Exception.class)
    public void createOrder2(Order order) throws Exception {
        orderMapper.insert(order);
    }
    
    // 指定不回滚异常
    @Transactional(noRollbackFor = BusinessException.class)
    public void createOrder3(Order order) throws BusinessException {
        orderMapper.insert(order);
    }
    
    // 设置超时
    @Transactional(timeout = 5)  // 5 秒超时
    public void createOrder4(Order order) {
        orderMapper.insert(order);
    }
    
    // 设置隔离级别
    @Transactional(isolation = Isolation.READ_COMMITTED)
    public void createOrder5(Order order) {
        orderMapper.insert(order);
    }
}
```

### 嵌套事务（Savepoint）

```java
@Service
public class OrderService {
    
    @Transactional
    public void parentTransaction() {
        orderMapper.insert(order1);  // 成功
        
        try {
            childTransaction();  // 子事务失败
        } catch (Exception e) {
            // 子事务回滚，但父事务继续
            // 使用 Savepoint 实现
        }
        
        orderMapper.insert(order2);  // 仍然成功
        // 最终：order1 和 order2 都提交
    }
    
    @Transactional(propagation = Propagation.NESTED)
    public void childTransaction() {
        orderMapper.insert(order3);  // 失败回滚
    }
}
```

### 事务传播行为

| 传播行为 | 说明 |
|----------|------|
| REQUIRED | 默认，加入当前事务，不存在则创建新事务 |
| REQUIRES_NEW | 挂起当前事务，创建新事务 |
| NESTED | 使用 Savepoint，嵌套事务 |
| SUPPORTS | 支持当前事务，不存在则以非事务执行 |
| NOT_SUPPORTED | 以非事务执行，挂起当前事务 |
| NEVER | 非事务执行，存在事务则抛异常 |
| MANDATORY | 必须存在事务，不存在则抛异常 |

## 踩坑经验汇总

| 坑点 | 问题 | 解决方案 |
|------|------|----------|
| 长事务 | 占用大量锁和 undo | 拆分为短事务 |
| 索引缺失 | 锁全表 | 添加合适索引 |
| 循环依赖 | 死锁 | 按固定顺序获取锁 |
| 脏写 | 未提交数据被覆盖 | 使用乐观锁版本号 |
| 幻读 | 同一事务两次查询结果不同 | 使用间隙锁或提高隔离级别 |
| 丢失更新 | 并发更新丢失 | 使用 SELECT FOR UPDATE |
| Spring 事务失效 | 非 public 方法、AOP 代理问题 | 确认方法在同一个类内 |
| 嵌套事务回滚 | 全部回滚 | 使用 NESTED + Savepoint |

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
