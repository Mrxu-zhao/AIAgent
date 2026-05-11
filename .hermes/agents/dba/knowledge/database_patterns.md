# 数据库设计模式库

> 从项目中提炼的数据库设计模式

## 模式1: 电商单库设计模式

- **分类**: 业务数据库
- **来源**: mall4j-bbc (218张表单库设计)
- **适用场景**: 中小型电商、B2C商城
- **模式描述**:

### 表分类（按业务域）

| 业务域 | 表数量 | 代表性表 |
|--------|--------|----------|
| 用户会员 | 8-10 | user、user_addr、user_grade、point_log、balance_log |
| 店铺商户 | 5-8 | shop、shop_category |
| 商品管理 | 30-40 | product、sku、attr、brand、category、tag |
| 订单交易 | 15-20 | order、order_item、cart |
| 物流配送 | 8-10 | delivery、delivery_company、pickup_point |
| 营销活动 | 20-30 | coupon、coupon_user、seckill、group_buy、discount |
| 分销体系 | 5-8 | distribution_user、distribution_order |
| 退款售后 | 5-8 | aftersale、refund |
| 评价客服 | 5-8 | product_comment、message |
| 系统配置 | 10+ | area、sys_config |

### 设计要点

1. **SKU多规格设计**: 通过 `sku` 表存储所有规格组合，`attr` 表存储属性，`product_attr` 关联属性
2. **促销规则**: 独立促销表，促销商品关联表（避免促销信息耦合商品表）
3. **订单状态机**: 独立 `order_status_log` 表记录状态变更流水
4. **金额字段**: 使用 DECIMAL(10,2) 避免浮点精度问题
5. **软删除**: 使用 `del` 或 `deleted` 字段标记删除，而非物理删除
6. **自动填充**: 使用 MyBatis-Plus `MetaObjectHandler` 自动填充 create_time、update_time、create_user

## 模式2: 微服务多库设计模式

- **分类**: 业务数据库
- **来源**: xzmeto_resource (微服务多库)
- **适用场景**: 中大型管理系统、微服务架构
- **模式描述**:

### 按服务分离数据库

| 服务 | 数据库 | 典型表 |
|------|--------|--------|
| xzmetro-upms | 系统库 | sys_user、sys_role、sys_menu、sys_dept、sys_dict |
| xzmetro-app-server | 业务库 | 资源、合同、认购、支付等业务表 |
| xzmetro-flow | 流程库 | act_ru_*、act_ge_* (Flowable表) |

### 多租户隔离设计

```sql
-- 所有表共享租户字段
ALTER TABLE xxx ADD COLUMN tenant_id BIGINT DEFAULT 0;

-- 查询时自动过滤
SELECT * FROM table WHERE tenant_id = #{tenantId}
-- (通常在框架层统一处理，如 MyBatis-Plus 插件)
```

### 设计要点

1. **系统库 vs 业务库分离**: 用户权限等系统表单独库，与业务数据解耦
2. **租户字段统一**: 所有业务表必须有 `tenant_id` 字段
3. **字典表设计**: 使用 `sys_dict` + `sys_dict_item` 实现动态字典
4. **日志表设计**: 操作日志表使用分表策略（按月/按天）
5. **Flowable表**: 工作流引擎表独立管理，业务表通过 `business_key` 关联

## 模式3: 索引设计规范

- **分类**: 设计规范
- **来源**: mall4j-bbc + xzmeto_resource 综合
- **适用场景**: 通用数据库设计

### 索引设计原则

| 场景 | 索引策略 |
|------|----------|
| 主键 | 唯一索引，使用 BIGINT 自增或 UUID |
| 外键关联 | 常用查询字段加索引 |
| 状态筛选 | status、del 等字段加索引 |
| 时间范围 | create_time 常用范围查询，加索引 |
| 组合查询 | 多字段频繁组合查询，建组合索引 |
| 避免过多 | 单表索引不超过5个，避免写性能下降 |

### 常见索引命名

```
idx_{表名}_{字段}     -- 普通索引
uk_{表名}_{字段}      -- 唯一索引
fk_{表名}_{字段}      -- 外键索引（通常在应用层维护）
```

## 待积累

- [ ] 分库分表设计模式
- [ ] 历史数据归档设计
- [ ] 数据权限设计模式
