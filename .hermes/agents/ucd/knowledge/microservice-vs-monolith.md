# 微服务 vs 单体模块化 架构选型模式

> 来源: mall4j-bbc (单体模块化) vs xzmeto_resource (微服务) 对比分析
> 沉淀时间: 2026-04-29

## 模式定义

| 维度 | 微服务架构 | 单体模块化 |
|------|-----------|-----------|
| 团队规模 | 5人以上多团队 | 1-5人小团队 |
| 扩展需求 | 按模块独立扩展 | 统一扩展 |
| 部署复杂度 | 高（需CI/CD/K8s） | 低（单项目部署） |
| 事务控制 | 分布式事务 | 本地事务 |
| 运维成本 | 高 | 低 |
| 数据库 | 多库分离 | 单库 |
| 推荐技术 | Nacos + Gateway + OAuth2 | Spring Boot + Maven多模块 |

## 典型案例

### 微服务案例: xzmeto_resource

```
xzmetro-register  → Nacos客户端
xzmetro-gateway   → API网关 (:8080)
xzmetro-auth      → 认证授权 (:3000, Spring Security OAuth2)
xzmetro-upms      → 用户权限 (:4000)
xzmetro-app-server→ 业务服务 (:5000)
xzmetro-flow      → 工作流引擎
xzmetro-common    → 公共模块
xzmetro-visual    → 可视化/监控
```

技术栈: Spring Boot 3.5.3 + Spring Cloud 2025.0.0 + Spring Cloud Alibaba 2023.0.3.3 + Java 17 + MySQL 8.0 + Nacos + Redis + Flowable

### 单体模块化案例: mall4j-bbc

```
yami-shop-api        # API层
yami-shop-bean       # DTO/VO/Entity
yami-shop-common     # 公共工具
yami-shop-activity   # 活动
yami-shop-coupon     # 优惠券
yami-shop-delivery   # 配送
yami-shop-discount   # 折扣
yami-shop-distribution # 分销
yami-shop-groupbuy   # 拼团
yami-shop-live       # 直播
yami-shop-order      # 订单
yami-shop-payment    # 支付
yami-shop-product    # 商品
yami-shop-seckill    # 秒杀
yami-shop-shop       # 店铺
yami-shop-user       # 用户
```

技术栈: Spring Boot 3.5.7 + MyBatis-Plus 3.5.14 + Java 17 + MySQL + Redis + ES + XXL-Job + Sa-Token

## 选型决策树

```
新项目开始
    ↓
团队规模 ≤ 5人?
    ↓ Yes                    ↓ No
单体模块化              业务模块 ≥ 5个独立域?
                            ↓ Yes              ↓ No
                       微服务架构           单体模块化
                       (可先用单体，        + 预留微服务拆
                        后期按需拆分)        分边界
```

## 关键教训

1. **微服务边界要清晰**: 代码模块和数据库表归属要一致，避免"假微服务真单体"
2. **多租户是微服务标配**: 管理系统优先考虑微服务架构 + 多租户隔离
3. **电商优先选单体**: 电商链路强事务，单体模块化更易控制
