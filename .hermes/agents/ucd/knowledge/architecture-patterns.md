# 系统分层架构模式

## 概述

本文档对比两种主流后端架构模式，指导技术选型。

## 模式一：传统三层架构（Controller-Service-Mapper）

### 结构

```
├── controller/     # 控制层，处理HTTP请求
├── service/        # 业务逻辑层
├── mapper/        # 数据访问层（MyBatis-Plus）
├── entity/        # 实体类
├── dto/           # 数据传输对象
└── config/        # 配置类
```

### 适用场景

- 业务逻辑相对简单
- 快速迭代的中小型项目
- 团队对DDD不熟悉

### 代码示例

```java
// Controller
@RestController
@RequestMapping("/api/users")
public class UserController {
    @Autowired private UserService userService;
    
    @GetMapping("/{id}")
    public Result<UserDTO> getUser(@PathVariable Long id) {
        return Result.success(userService.getUserById(id));
    }
}

// Service
@Service
public class UserService {
    @Autowired private UserMapper userMapper;
    
    public UserDTO getUserById(Long id) {
        User user = userMapper.selectById(id);
        return convertToDTO(user);
    }
}
```

---

## 模式二：DDD领域驱动设计

### 核心概念

| 概念 | 说明 |
|------|------|
| 聚合根(Aggregate Root) | 领域实体的核心，负责维护内部一致性 |
| 领域事件(Domain Event) | 业务领域中发生的事件 |
| 仓储(Repository) | 领域对象持久化的抽象 |
| 应用服务(Application Service) | 编排领域服务，处理用例 |

### 项目结构（DDD四层）

```
├── interfaces/           # 接口层（Controller、DTO）
├── application/          # 应用层（Application Service、Command/Query）
├── domain/              # 领域层（Entity、Domain Service、Event）
│   ├── model/           # 聚合、实体、值对象
│   ├── service/         # 领域服务
│   └── event/           # 领域事件
└── infrastructure/      # 基础设施层（Repository实现、Mapper）
```

### 适用场景

- 业务复杂度高的企业系统
- 需要长期维护和演进的项目
- 团队有DDD经验

### 核心实践

```java
// 领域层 - 聚合根
@Entity
public class Order extends AggregateRoot {
    @Id private Long id;
    private OrderStatus status;
    private List<OrderItem> items;
    
    // 领域方法，保证业务规则
    public void addItem(Product product, int quantity) {
        if (status != OrderStatus.DRAFT) {
            throw new BusinessException("只有草稿状态可添加商品");
        }
        items.add(new OrderItem(product, quantity));
    }
    
    public void submit() {
        // 发布领域事件
        registerEvent(new OrderSubmittedEvent(this));
    }
}

// 应用层 - 命令处理器
@Service
public class OrderApplicationService {
    public void handle(CreateOrderCommand cmd) {
        Order order = new Order(cmd.getCustomerId());
        order.addItem(...);
        order.submit();
        orderRepository.save(order);
    }
}
```

---

## 模式选择指南

| 因素 | 三层架构 | DDD |
|------|---------|-----|
| 项目规模 | < 50个实体 | > 50个实体 |
| 业务复杂度 | 简单CRUD为主 | 复杂业务规则 |
| 团队经验 | 初学团队 | 有DDD经验 |
| 迭代速度 | 快速交付 | 长期演进 |
| 可维护性 | 中等 | 高 |

**团队建议**：对于徐钊团队管理的项目，初期推荐三层架构 + 初步的DDD思想（引入DTO、领域事件），随着业务复杂度的提升逐步演进到完整DDD。

---

## 混合架构实践

```
interfaces (Controller) 
        ↓
application (Service + Command)
        ↓
domain (Entity + Domain Service)
        ↓
infrastructure (MyBatis-Plus Mapper)
```

### 关键原则

1. **贫血模型 vs 充血模型**：初期可使用贫血模型，逐步引入业务逻辑到实体
2. **防腐层(ACL)**：在服务边界防止外部系统污染内部模型
3. **CQRS分离**：读操作用QueryDSL，写操作用Command

---

*文档类型：架构设计模式*
*适用范围：后端开发*
*最后更新：2026-04-29*
