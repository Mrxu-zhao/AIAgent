# 电商 vs 管理系统 数据库设计模式对比

> 来源: mall4j-bbc (电商, 218表) vs xzmeto_resource (管理系统, 40+表)
> 沉淀时间: 2026-04-29

## 电商数据库设计 (mall4j)

### 表分类（13个业务域，218张表）

| 业务域 | 表数量 | 核心表 |
|--------|--------|--------|
| 用户会员 | 8-10 | user, user_addr, user_grade, point_log, balance_log |
| 店铺商户 | 5-8 | shop, shop_category |
| 商品管理 | 30-40 | product, sku, attr, brand, category, tag |
| 订单交易 | 15-20 | order, order_item, cart |
| 物流配送 | 8-10 | delivery, delivery_company, pickup_point |
| 营销活动 | 20-30 | coupon, coupon_user, seckill, group_buy, discount |
| 分销体系 | 5-8 | distribution_user, distribution_order |
| 退款售后 | 5-8 | aftersale, refund |
| 评价客服 | 5-8 | product_comment, message |
| 虚拟卡券 | 5 | coupon_code |
| 系统配置 | 10+ | area, sys_config |
| 统计分析 | 5+ | stat_* |

### 设计特点

1. **SKU多规格**: `product` (SPU) + `sku` (SKU) + `attr` (属性) + `product_attr` (关联)
2. **促销规则表**: coupon/seckill/group_buy/discount 独立表，促销商品关联表
3. **订单状态机**: `order` + `order_status_log` 记录完整状态流转
4. **金额字段**: DECIMAL(10,2) 避免浮点精度问题
5. **软删除**: del 字段标记删除
6. **自动填充**: MyBatis-Plus MetaObjectHandler

## 管理系统数据库设计 (xzmeto)

### 表分类（7个业务域，40+核心表）

| 业务域 | 核心表 |
|--------|--------|
| 资源管理 | resource, floor, unit, room, shop, parking |
| 合同管理 | contract, contract_template, contract_attachment |
| 土地项目 | land_project, project_phase, subscription |
| 系统管理 | sys_user, sys_role, sys_menu, sys_dept, sys_dict |
| 支付 | pay_record, refund_record |
| 定时任务 | sys_job, sys_job_log |
| BI报表 | report_* |

### 设计特点

1. **多库分离**: 系统库(sys_*) 独立，业务库(资源/合同/认购) 独立，流程库(Flowable act_*) 独立
2. **多租户隔离**: 所有业务表有 `tenant_id` 字段
3. **资源层级**: 土地→分期→楼栋→单元→房间 层级关系
4. **字典表**: `sys_dict` + `sys_dict_item` 实现动态字典
5. **日志分表**: 操作日志按月分表

## 关键教训

1. **表数量不是衡量标准**: mall4j 218表但单库，xzmeto 40+核心表但多库分离
2. **电商重促销**: 促销表多且关系复杂（叠加/互斥/门槛）
3. **管理重权限**: sys_user/role/menu/dept 是标配
4. **多租户必加 tenant_id**: 所有业务表都要加，框架层统一过滤
