# 数据库表设计规范

## 概述

规范的表设计是系统稳定、可维护的基础。本文详细说明命名规范、字段类型选择、约束设计等最佳实践。

## 命名规范

### 基本原则

```
1. 统一小写，使用下划线分隔
2. 可读性强，简短明了
3. 使用单数名词（除非业界通用复数）
4. 避免保留字和关键字
```

### 表命名

```sql
-- ✅ 正确示例
sys_user              -- 系统用户表
ord_order             -- 订单表（ord 前缀区分模块）
ord_order_item        -- 订单明细表
bas_product           -- 商品基础表（bas=基础数据）
biz_customer           -- 客户表（biz=业务数据）

-- ❌ 错误示例
UserInfo               -- 驼峰命名
T_USER                 -- T_ 前缀多余
order_detail_table    -- 过长
tbl_order              -- tbl_ 前缀多余
```

### 字段命名

```sql
-- ✅ 正确示例
user_id                -- 用户ID（_id 后缀表示外键）
user_name              -- 用户名
is_deleted             -- 是否删除（is_ 前缀表示布尔）
created_at             -- 创建时间
updated_at             -- 更新时间
status                 -- 状态
sort_order             -- 排序号
remark                 -- 备注

-- ❌ 错误示例
UserName               -- 驼峰
ID                     -- 全大写缩写
name_string            -- _string 后缀多余
userid                 -- 无下划线
```

### 索引命名

```sql
-- ✅ 正确示例
PRIMARY KEY (id)                           -- 主键
uk_order_no (order_no)                      -- 唯一索引 uk_
idx_user_status (user_id, status)          -- 普通索引 idx_
ft_product_name (name)                     -- 全文索引 ft_

-- ❌ 错误示例
index_user_status                          -- 缺少 idx_ 前缀
idx_a_b_c_d_e                               -- 超过5个字段
```

## 字段类型选择

### 整数类型

| 类型 | 字节 | 有符号范围 | 无符号范围 | 适用场景 |
|------|------|------------|------------|----------|
| TINYINT | 1 | -128~127 | 0~255 | 状态码 |
| SMALLINT | 2 | -32768~32767 | 0~65535 | 小数量 |
| INT | 4 | -21亿~21亿 | 0~42亿 | 默认选择 |
| BIGINT | 8 | 极大 | 0~极大 | 主键、大数量 |

```sql
-- ✅ 建议：主键使用 BIGINT UNSIGNED
CREATE TABLE sys_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ...
);

-- ❌ 避免：使用 INT 作为主键（有上限风险）
-- id INT NOT NULL AUTO_INCREMENT PRIMARY KEY
```

### 字符串类型

| 类型 | 最大长度 | 适用场景 |
|------|----------|----------|
| CHAR | 255 | 定长字符串（性别、状态码） |
| VARCHAR | 16383 | 变长字符串（用户名、标题） |
| TEXT | 64KB | 长文本（文章内容） |
| MEDIUMTEXT | 16MB | 中等文本（简历、描述） |
| LONGTEXT | 4GB | 大文本（日志、文件内容） |

```sql
-- ✅ 正确示例
nickname VARCHAR(32) NOT NULL COMMENT '昵称'
mobile VARCHAR(11) NOT NULL COMMENT '手机号'
email VARCHAR(100) COMMENT '邮箱'
content TEXT COMMENT '文章内容'
file_content MEDIUMTEXT COMMENT '文件内容'

-- ❌ 错误示例
name VARCHAR(1000)         -- 过长
content VARCHAR(65535)     -- 超过单行限制
desc VARCHAR(500)         -- 建议用 TEXT
```

### 日期时间类型

| 类型 | 格式 | 范围 | 适用场景 |
|------|------|------|----------|
| DATE | YYYY-MM-DD | 1000-9999 | 日期 |
| TIME | HH:MM:SS | -838:59:59 | 时间 |
| DATETIME | YYYY-MM-DD HH:MM:SS | 1000-9999 | 时间戳（固定值） |
| TIMESTAMP | YYYY-MM-DD HH:MM:SS | 1970-2038 | 时间戳（自动更新） |

```sql
-- ✅ 正确示例
birth_date DATE COMMENT '出生日期'
created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
expire_time DATETIME COMMENT '过期时间'

-- ❌ 错误示例
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
-- 原因：2038 年问题，DATETIME 更适合
```

### 小数类型

| 类型 | 格式 | 适用场景 |
|------|------|----------|
| DECIMAL | DECIMAL(10,2) | 金额（精确） |
| FLOAT | FLOAT(10,2) | 科学计算 |
| DOUBLE | DOUBLE(10,2) | 大数值科学计算 |

```sql
-- ✅ 正确示例
price DECIMAL(10,2) NOT NULL COMMENT '价格'
amount DECIMAL(15,2) COMMENT '金额'
rate DECIMAL(5,4) COMMENT '利率'

-- ❌ 错误示例
price FLOAT(10,2)         -- 金额不建议用浮点
amount DOUBLE             -- 不精确
```

### 枚举类型

```sql
-- ✅ 方式一：ENUM 类型
CREATE TABLE ord_order (
    status ENUM('pending', 'paid', 'shipped', 'completed', 'cancelled') DEFAULT 'pending',
    ...
);

-- ✅ 方式二：TINYINT + 字典表（推荐，便于扩展）
CREATE TABLE ord_order (
    status TINYINT NOT NULL DEFAULT 0 COMMENT '订单状态：0-待付款 1-已付款 2-已发货 3-已完成 4-已取消',
    ...
);
```

## 约束设计

### 主键设计

```sql
-- ✅ 推荐：自增 BIGINT 主键
CREATE TABLE ord_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ...
) ENGINE=InnoDB;

-- ✅ 业务场景：使用业务主键 + 自增 ID
CREATE TABLE ord_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    order_no VARCHAR(32) NOT NULL COMMENT '订单号',
    ...
    UNIQUE KEY uk_order_no (order_no),
    PRIMARY KEY (id)  -- InnoDB 必须有主键
) ENGINE=InnoDB;

-- ❌ 避免：复合主键
-- PRIMARY KEY (user_id, order_id)
-- 原因：维护困难，索引过大
```

### 外键约束

```sql
-- ✅ 外键命名规范
-- fk_[表名]_[引用表名]
ALTER TABLE ord_order_item 
ADD CONSTRAINT fk_order_item_order 
FOREIGN KEY (order_id) REFERENCES ord_order(id);

ALTER TABLE ord_order 
ADD CONSTRAINT fk_order_user 
FOREIGN KEY (user_id) REFERENCES sys_user(id);

-- ⚠️ 注意：分库分表场景下不建议使用外键
-- 建议：在应用层做数据校验
```

### 唯一约束

```sql
-- ✅ 唯一索引命名
CREATE TABLE sys_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    mobile VARCHAR(11),
    ...
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_email (email),
    UNIQUE KEY uk_mobile (mobile)
);
```

### 非空约束

```sql
-- ✅ 必须有值的字段
user_id BIGINT NOT NULL,
order_no VARCHAR(32) NOT NULL,
amount DECIMAL(10,2) NOT NULL,
status TINYINT NOT NULL DEFAULT 0,
created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

-- ✅ 可以为空的字段（注意索引影响）
email VARCHAR(100),          -- 可以为空，不影响索引
mobile VARCHAR(11),           -- 可以为空
remark VARCHAR(500),          -- 可以为空
deleted_at DATETIME,          -- 软删除时间
```

### 默认值

```sql
-- ✅ 常用默认值
status TINYINT NOT NULL DEFAULT 0,
is_deleted TINYINT NOT NULL DEFAULT 0,
created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
version INT NOT NULL DEFAULT 1,           -- 乐观锁版本号
sort_order INT NOT NULL DEFAULT 0,        -- 排序号
```

## 审计字段

```sql
-- ✅ 标准审计字段
CREATE TABLE xxx (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    
    -- 业务字段
    ...
    
    -- 审计字段
    created_by BIGINT UNSIGNED COMMENT '创建人ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT UNSIGNED COMMENT '更新人ID',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at DATETIME COMMENT '删除时间',          -- 软删除
    is_deleted TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除：0-否 1-是',
    version INT NOT NULL DEFAULT 1 COMMENT '版本号' -- 乐观锁
    
    -- 分库分表字段（如果需要）
    tenant_id BIGINT UNSIGNED NOT NULL COMMENT '租户ID',
    
    PRIMARY KEY (id),
    INDEX idx_created_at (created_at),
    INDEX idx_tenant_deleted (tenant_id, is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='表名';
```

## 索引设计规范

### 单表索引数量

```sql
-- ✅ 建议：单表索引不超过 5 个
-- 原因：写入性能影响、存储成本、维护成本

-- ❌ 避免：为所有字段建索引
CREATE TABLE bad_example (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100),
    mobile VARCHAR(11),
    INDEX idx_name (name),
    INDEX idx_email (email),
    INDEX idx_mobile (mobile),
    INDEX idx_name_email_mobile (name, email, mobile)
);
```

### 索引列顺序

```sql
-- ✅ 原则：区分度高的列放前面
-- 查询：WHERE status = 1 AND user_id = 1001
-- 正确索引
INDEX idx_status_user (status, user_id)      -- status=1 后 user_id 唯一
INDEX idx_user_status (user_id, status)      -- user_id 先唯一再 status

-- ⚠️ 范围查询列放最后
-- 查询：WHERE user_id = 1001 AND status > 0 AND created_at > '2024-01-01'
-- 正确索引
INDEX idx_user_status_date (user_id, status, created_at)
-- ❌ 错误：范围列在前面
INDEX idx_status_date (status, created_at, user_id)
```

### 前缀索引

```sql
-- ✅ 字符串长字段使用前缀索引
email VARCHAR(100),
INDEX idx_email (email(20))  -- 前 20 个字符

-- ✅ 计算合适的前缀长度
SELECT 
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) as sel10,
    COUNT(DISTINCT LEFT(email, 20)) / COUNT(*) as sel20,
    COUNT(DISTINCT LEFT(email, 30)) / COUNT(*) as sel30
FROM sys_user;
-- 选择选择性与完整列接近的最小长度
```

## 常见反模式

```sql
-- ❌ 反模式一：宽表（所有字段放一起）
CREATE TABLE bad_wide_table (
    id INT PRIMARY KEY,
    field1 VARCHAR(100),
    field2 VARCHAR(100),
    ...  -- 100+ 个字段
);

-- ✅ 正确：拆分为多个相关表
CREATE TABLE main_table (...);
CREATE TABLE ext_table (...);

-- ❌ 反模式二：保存 XML/JSON 在 TEXT 字段
CREATE TABLE bad_json (
    config TEXT COMMENT 'XML配置'
);

-- ✅ 正确：MySQL 8.0 使用 JSON 类型
CREATE TABLE good_json (
    config JSON COMMENT 'JSON配置'
);
-- 支持 JSON_EXTRACT、JSON_SET 等函数

-- ❌ 反模式三：时间戳用 INT 存储
CREATE TABLE bad_timestamp (
    created_at INT COMMENT '创建时间戳'
);

-- ✅ 正确：使用 DATETIME
CREATE TABLE good_timestamp (
    created_at DATETIME COMMENT '创建时间'
);
```

## 完整示例

```sql
-- 订单主表
CREATE TABLE ord_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单ID',
    order_no VARCHAR(32) NOT NULL COMMENT '订单号',
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    merchant_id BIGINT UNSIGNED NOT NULL COMMENT '商户ID',
    total_amount DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '订单总额',
    pay_amount DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '实付金额',
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '优惠金额',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '订单状态：0-待付款 1-已付款 2-已发货 3-已完成 4-已取消 5-已退款',
    pay_type TINYINT COMMENT '支付方式：1-微信 2-支付宝 3-银行卡',
    pay_time DATETIME COMMENT '支付时间',
    ship_time DATETIME COMMENT '发货时间',
    complete_time DATETIME COMMENT '完成时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at DATETIME COMMENT '删除时间',
    is_deleted TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除：0-否 1-是',
    version INT NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
    remark VARCHAR(500) COMMENT '备注',
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    INDEX idx_user_status (user_id, status),
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_merchant_created (merchant_id, created_at),
    INDEX idx_status_created (status, created_at),
    INDEX idx_pay_time (pay_time),
    INDEX idx_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订单主表';
```

## 踩坑经验汇总

| 坑点 | 问题 | 解决方案 |
|------|------|----------|
| 主键用 INT | 未来达到上限 | 改用 BIGINT UNSIGNED |
| VARCHAR(65535) | 超过单行限制 | 拆分字段或用 TEXT |
| TIMESTAMP | 2038 年问题 | 改用 DATETIME |
| 金额用 DOUBLE | 精度丢失 | 改用 DECIMAL |
| 无审计字段 | 查问题困难 | 添加 created_at/updated_at |
| 软删不用索引 | 查询变全表 | 索引 (is_deleted, deleted_at) |
| 字段命名混乱 | 维护困难 | 统一命名规范 |
| 无注释 | 字段含义不明 | 所有字段加 COMMENT |

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
