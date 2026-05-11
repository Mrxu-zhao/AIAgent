# MySQL 8.0 InnoDB 索引原理

## 概述

MySQL 8.0 中 InnoDB 是默认存储引擎，其索引采用 B+ 树（Balanced Tree）结构。本文详细讲解索引的底层原理和最左前缀原则。

## B+ 树结构

### 什么是 B+ 树

B+ 树是一种自平衡的多路搜索树，相比二叉树更矮更宽，适合磁盘存储。

```
                    [15]
               /          \
         [5,10]            [20,25]
        /    \    \        /    |    \
    [1,3] [6,8] [11,13] [16,18] [21,23] [26,28]
```

### InnoDB B+ 树特点

1. **所有数据都存储在叶子节点**：非叶子节点只存储索引键和子节点指针
2. **叶子节点互联**：通过双向链表连接，便于范围查询
3. **高度可控**：千万级数据树高通常为 3-4 层
4. **聚簇索引**：主键索引的叶子节点存储完整行数据

### 索引类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| 主键索引 (PK) | 聚簇索引，叶子节点存整行数据 | 主键查询 |
| 唯一索引 | 唯一约束，叶子节点存主键 | 唯一性校验 |
| 普通索引 | 单列索引，叶子节点存主键 | 加速单列查询 |
| 前缀索引 | 字符串前缀索引 | 字符串列 |
| 联合索引 | 多列组合索引 | 多条件查询 |

## 最左前缀原则

### 原理

联合索引 (a, b, c) 的结构是按 a 排序，a 相同时按 b 排序，b 相同时按 c 排序。

```sql
-- 创建联合索引
CREATE INDEX idx_name_age_dept ON employees(name, age, department_id);

-- 索引结构示意
(a='张', b=25) → [主键列表]
(a='张', b=30) → [主键列表]
(a='李', b=28) → [主键列表]
(a='王', b=35) → [主键列表]
```

### 查询匹配规则

```sql
-- ✅ 有效使用索引（全匹配）
SELECT * FROM employees WHERE name='张' AND age=25 AND department_id=1;

-- ✅ 有效使用索引（前缀匹配）
SELECT * FROM employees WHERE name='张';

-- ✅ 有效使用索引（两口匹配）
SELECT * FROM employees WHERE name='张' AND age=25;

-- ❌ 无法使用索引（跳过第一列）
SELECT * FROM employees WHERE age=25;

-- ⚠️ 范围查询后的列无法使用索引
SELECT * FROM employees WHERE name='张' AND age>25;
-- age、department_id 列无法使用索引
```

### 常见踩坑

```sql
-- ❌ 错误：使用函数导致索引失效
SELECT * FROM employees WHERE YEAR(birth_date)=1990;

-- ✅ 正确：改写为范围查询
SELECT * FROM employees WHERE birth_date >= '1990-01-01' AND birth_date < '1991-01-01';

-- ❌ 错误：隐式类型转换
SELECT * FROM employees WHERE employee_id = '1001';  -- employee_id 是 INT

-- ✅ 正确：保持类型一致
SELECT * FROM employees WHERE employee_id = 1001;
```

## 索引设计规范

### 选择性原则

```sql
-- 计算列的选择性（越接近 1 越好）
SELECT COUNT(DISTINCT column_name) / COUNT(*) FROM table_name;

-- 示例：性别列选择性很低，不适合建索引
SELECT COUNT(DISTINCT gender) / COUNT(*) FROM employees;
-- 结果：约 0.5
```

### 前缀索引长度选择

```sql
-- 通过实验确定最优长度
SELECT 
    COUNT(DISTINCT LEFT(email, 5)) / COUNT(*) AS sel5,
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) AS sel10,
    COUNT(DISTINCT LEFT(email, 15)) / COUNT(*) AS sel15,
    COUNT(DISTINCT LEFT(email, 20)) / COUNT(*) AS sel20
FROM users;

-- 创建前缀索引
ALTER TABLE users ADD INDEX idx_email (email(10));
```

### 联合索引设计

```sql
-- 原则：区分度高的列放前面
-- 用户表常见索引设计
CREATE INDEX idx_status_created ON orders (status, created_at);      -- 状态+时间
CREATE INDEX idx_user_status ON order_items (user_id, status);       -- 用户+状态
CREATE INDEX idx_dept_manager ON departments (dept_id, manager_id);  -- 部门+经理
```

## EXPLAIN 分析

```sql
-- 查看执行计划
EXPLAIN SELECT * FROM employees WHERE name='张' AND age=25;

-- 关键字段说明
-- type: const(最优) > eq_ref > ref > range > index > ALL(最差)
-- key: 实际使用的索引名
-- key_len: 索引使用长度
-- rows: 预计扫描行数
-- Extra: Using index(覆盖索引) / Using where / Using index condition
```

## 最佳实践

### 索引创建

```sql
-- 1. 为主键设置自增 ID
CREATE TABLE orders (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,  -- 使用无符号 BIGINT
    order_no VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    INDEX idx_user_status (user_id, status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 避免索引失效

```sql
-- ❌ 避免
SELECT * FROM orders WHERE status IN (1, 2, 3);  -- IN 过多可改为范围

-- ✅ 优化
SELECT * FROM orders WHERE status = 1 
UNION ALL SELECT * FROM orders WHERE status = 2
UNION ALL SELECT * FROM orders WHERE status = 3;

-- ❌ 避免：LIKE 前缀通配符
SELECT * FROM users WHERE name LIKE '%三%';

-- ✅ 使用全文索引
ALTER TABLE users ADD FULLTEXT INDEX ft_name (name);
SELECT * FROM users WHERE MATCH(name) AGAINST('三' IN BOOLEAN MODE);
```

### 索引维护

```sql
-- 查看索引使用情况
SELECT 
    object_schema,
    object_name,
    index_name,
    cardinality
FROM mysql.innodb_index_stats 
WHERE table_name = 'orders';

-- 分析表重建索引
OPTIMIZE TABLE orders;

-- 检查重复/冗余索引
SELECT 
    a.table_schema,
    a.table_name,
    a.index_name,
    a.column_name,
    b.index_name AS redundant_index,
    b.column_name AS redundant_column
FROM information_schema.statistics a
JOIN information_schema.statistics b 
    ON a.table_schema = b.table_schema 
    AND a.table_name = b.table_name
    AND a.index_name != b.index_name
WHERE a.seq_in_index = 1 
    AND b.seq_in_index = 1
    AND a.column_name = b.column_name;
```

## 踩坑经验汇总

| 坑点 | 错误做法 | 正确做法 |
|------|----------|----------|
| 联合索引顺序 | 按列名字母排序 | 按区分度和查询频率排序 |
| 前缀索引 | 固定长度 10 | 通过 SELECTIVITY 实验确定 |
| 外键索引 | 不建外键索引 | 建外键必须建索引 |
| 索引列类型 | 字符串存 ID | 使用整数类型 BIGINT |
| 模糊查询 | LIKE '%keyword' | 使用全文索引或 ES |

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
