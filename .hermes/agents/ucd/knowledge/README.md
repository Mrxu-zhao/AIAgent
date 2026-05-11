# 数据库设计模式知识库

## 概述

本文档是数据库设计模式知识库的索引目录，为团队提供 MySQL 和 Redis 的系统性参考。

## 文档目录

### 核心原理

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [mysql-index-principles.md](./mysql-index-principles.md) | MySQL 8.0 InnoDB 索引原理 | B+树、最左前缀、索引设计 |
| [mysql-transaction-locking.md](./mysql-transaction-locking.md) | 事务隔离级别与锁机制 | MVCC、间隙锁、Next-Key Lock |
| [read-write-separation.md](./read-write-separation.md) | 读写分离与主从复制 | GTID、半同步、MHA |

### 实战技巧

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [sql-optimization-2024.md](./sql-optimization-2024.md) | SQL 慢查询优化 | EXPLAIN、分页优化、CTE |
| [table-design-standards.md](./table-design-standards.md) | 表设计规范 | 命名规范、字段类型、约束 |
| [sharding-solution.md](./sharding-solution.md) | 分库分表方案 | ShardingSphere、MyCat、分片键 |

### 数据存储

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [redis-data-structures.md](./redis-data-structures.md) | Redis 数据结构选型 | String、Hash、ZSet、Geo |
| [er-diagram-guide.md](./er-diagram-guide.md) | ER 图绘制指南 | 实体关系、符号规范、工具 |

### 踩坑经验

| 文档 | 说明 | 关键词 |
|------|------|--------|
| [../lessons/dba-pitfalls.md](../lessons/dba-pitfalls.md) | DBA 踩坑汇总 | MySQL、Redis、实战案例 |

## 学习路径建议

### 初级（1-3 年经验）

```
1. table-design-standards.md  → 表设计基础
2. mysql-index-principles.md  → 索引原理
3. er-diagram-guide.md       → ER 图绘制
4. dba-pitfalls.md            → 常见踩坑
```

### 中级（3-5 年经验）

```
1. sql-optimization-2024.md   → SQL 优化
2. mysql-transaction-locking.md → 事务与锁
3. redis-data-structures.md   → Redis 选型
4. read-write-separation.md   → 读写分离
```

### 高级（5 年以上）

```
1. sharding-solution.md       → 分库分表
2. mysql-transaction-locking.md → MVCC 深入
3. read-write-separation.md   → 延迟优化
```

## 快速查询

### 遇到慢查询？

1. 查看执行计划：`EXPLAIN your_sql`
2. 参考：[sql-optimization-2024.md](./sql-optimization-2024.md)
3. 检查索引：[mysql-index-principles.md](./mysql-index-principles.md)

### 设计新表？

1. 参考命名规范：[table-design-standards.md](./table-design-standards.md)
2. 绘制 ER 图：[er-diagram-guide.md](./er-diagram-guide.md)
3. 检查踩坑：[dba-pitfalls.md](../lessons/dba-pitfalls.md)

### 需要缓存？

1. 选择数据结构：[redis-data-structures.md](./redis-data-structures.md)
2. 避免常见问题：[dba-pitfalls.md](../lessons/dba-pitfalls.md)

## 团队技术栈

- **数据库**：MySQL 8.0 (InnoDB)
- **ORM**：MyBatis-Plus
- **缓存**：Redis
- **连接池**：HikariCP

## 文档贡献

欢迎团队成员补充踩坑经验和最佳实践：

1. 在 `lessons/` 目录添加新文档
2. 更新 `status.md` 的更新状态
3. 提交 PR 并通知 DBA（周嘉诚）审核

---

*知识库版本：v1.0*
*维护者：周嘉诚（DBA）*
*最后更新：2026-04-29*
