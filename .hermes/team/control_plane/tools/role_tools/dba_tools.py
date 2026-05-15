from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_ddl_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    table_name = str(payload.get("table_name", "example"))
    columns = payload.get("columns", [])
    business_indexes = []
    for column in columns[:2]:
        column_name = str(column.get("name", "")).strip()
        if not column_name:
            continue
        business_indexes.append(f"    INDEX `idx_{table_name}_{column_name}` (`{column_name}`),")
    column_defs = "\n".join([
        f'    `{c["name"]}` {c["type"]} {"NOT NULL" if c.get("required") else "NULL"} COMMENT \'{c.get("comment", "")}\',' 
        for c in columns
    ])
    index_defs = "\n".join(business_indexes)
    ddl = f'''CREATE TABLE `{table_name}` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
{column_defs}
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '删除标记',
{index_defs}
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{payload.get("table_comment", "")}';
'''
    return ToolResult.ok_result(
        content=ddl,
        structured_data={"table_name": table_name, "columns_count": len(columns)},
        artifacts=[],
    )


def analyze_slow_query_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    sql = str(payload.get("sql", ""))
    explain = str(payload.get("explain", ""))
    analysis = f'''# 慢查询分析报告

## SQL

```sql
{sql}
```

## EXPLAIN 结果

```
{explain}
```

## 分析结论

### 1. 索引使用
- [ ] 是否使用了索引？
- [ ] 是否存在全表扫描？
- [ ] 索引选择性如何？

### 2. 优化建议

| 问题 | 建议 |
|---|---|
| 全表扫描 | 添加复合索引 |
| 文件排序 | 优化 ORDER BY 字段 |
| 临时表 | 简化查询逻辑 |

### 3. 推荐索引

```sql
ALTER TABLE table_name ADD INDEX idx_xxx (column1, column2);
```
'''
    return ToolResult.ok_result(
        content=analysis,
        structured_data={"sql": sql},
        artifacts=[],
    )
