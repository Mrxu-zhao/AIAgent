# 术语表

> 积累业务和技术术语

## 电商领域

| 术语 | 解释 | 来源 |
|------|------|------|
| SKU | 库存量单位，即商品的规格变体（如颜色+尺码的具体商品） | mall4j |
| SPU | 标准化产品单元，一个SPU对应多个SKU | mall4j |
| 购物车项 | CartItem，用户加入购物车的商品记录 | mall4j |
| 订单项 | OrderItem，订单中的单个商品记录 | mall4j |
| 售后单 | AftersaleItem，用户申请退换货的记录 | mall4j |
| 满减 | 满N元减M元的促销活动 | mall4j |
| 优惠券 | Coupon，分满减券和折扣券 | mall4j |
| 分销商 | DistributionUser，参与分销推广的用户 | mall4j |
| 自提点 | PickupPoint，用户可自行取货的线下门店 | mall4j |
| 同城配送 | CityDistribution，类似于达达/美团配送 | mall4j |

## 微服务/系统架构

| 术语 | 解释 | 来源 |
|------|------|------|
| Nacos | 阿里开源的注册中心和配置中心 | xzmeto |
| Spring Cloud Gateway | 微服务API网关 | xzmeto |
| Flowable | 开源工作流引擎（类Activiti） | xzmeto |
| 多租户 | Multi-tenancy，一个系统服务多个租户，数据隔离 | xzmeto |
| tenant_id | 租户隔离字段，所有表共享此字段实现数据隔离 | xzmeto |
| OAuth2 | 开放授权协议，JWT Token 实现无状态认证 | xzmeto |
| SM4 | 国密算法，对称加密，用于请求参数加密 | xzmeto |
| pinia-plugin-persist | Pinia状态持久化插件，刷新页面不丢失状态 | xzmeto |

## 待补充

- [ ] 更多电商术语
- [ ] 更多微服务术语
- [ ] 业务领域术语
