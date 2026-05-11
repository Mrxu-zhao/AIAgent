# 后端代码分层规范

## 1. 传统三层架构

### 1.1 架构图

```
┌─────────────────────────────────────┐
│           Controller                │
│  (接收请求、参数校验、调用Service)    │
├─────────────────────────────────────┤
│            Service                  │
│  (业务逻辑、事务管理)                │
├─────────────────────────────────────┤
│           Mapper/Repository         │
│  (数据库访问、数据封装)              │
└─────────────────────────────────────┘
```

### 1.2 Controller 层

```java
@RestController
@RequestMapping("/v1/users")
@RequiredArgsConstructor
@Slf4j
public class UserController {
    
    private final UserService userService;
    
    @GetMapping("/{id}")
    public ApiResponse<UserVO> getUser(@PathVariable Long id) {
        return ApiResponse.success(userService.getById(id));
    }
    
    @GetMapping
    public ApiResponse<PageResult<UserVO>> list(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String keyword) {
        return ApiResponse.success(
            userService.page(page, size, keyword));
    }
    
    @PostMapping
    public ApiResponse<Long> create(
            @RequestBody @Valid UserCreateDTO dto) {
        return ApiResponse.success(userService.create(dto));
    }
    
    @PutMapping("/{id}")
    public ApiResponse<Void> update(
            @PathVariable Long id,
            @RequestBody @Valid UserUpdateDTO dto) {
        dto.setId(id);
        userService.update(dto);
        return ApiResponse.success();
    }
    
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        userService.delete(id);
    }
}
```

### 1.3 Service 层

```java
@Service
@RequiredArgsConstructor
@Transactional(rollbackFor = Exception.class)
@Slf4j
public class UserServiceImpl implements UserService {
    
    private final UserMapper userMapper;
    private final UserCacheService userCacheService;
    private final PasswordEncoder passwordEncoder;
    
    @Override
    public UserVO getById(Long id) {
        // 先查缓存
        UserVO cached = userCacheService.get(id);
        if (cached != null) {
            return cached;
        }
        
        // 查数据库
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(
                BusinessExceptionCode.USER_NOT_FOUND);
        }
        
        UserVO vo = toVO(user);
        userCacheService.put(id, vo);
        return vo;
    }
    
    @Override
    public PageResult<UserVO> page(Integer page, Integer size, 
            String keyword) {
        Page<User> pageResult = userMapper.selectPage(
            new Page<>(page, size),
            new LambdaQueryWrapper<User>()
                .like(StringUtils.hasText(keyword), 
                    User::getUsername, keyword)
                .orderByDesc(User::getCreateTime)
        );
        
        return PageResult.of(
            pageResult.getRecords().stream()
                .map(this::toVO)
                .collect(Collectors.toList()),
            pageResult.getTotal(),
            pageResult.getSize(),
            pageResult.getCurrent()
        );
    }
    
    @Override
    public Long create(UserCreateDTO dto) {
        // 检查重复
        User exist = userMapper.selectByUsername(dto.getUsername());
        if (exist != null) {
            throw new BusinessException(
                BusinessExceptionCode.USER_ALREADY_EXISTS);
        }
        
        // 密码加密
        String encodedPassword = passwordEncoder.encode(dto.getPassword());
        
        // 保存
        User user = new User();
        user.setUsername(dto.getUsername());
        user.setPassword(encodedPassword);
        user.setEmail(dto.getEmail());
        user.setStatus(1);
        userMapper.insert(user);
        
        return user.getId();
    }
    
    private UserVO toVO(User user) {
        UserVO vo = new UserVO();
        vo.setId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setEmail(user.getEmail());
        vo.setCreateTime(user.getCreateTime());
        return vo;
    }
}
```

### 1.4 Mapper 层

```java
@Mapper
public interface UserMapper extends BaseMapper<User> {
    
    User selectByUsername(@Param("username") String username);
    
    IPage<User> selectPage(IPage<User> page, 
            @Param("ew") Wrapper<User> wrapper);
    
    @Select("SELECT * FROM sys_user WHERE id = #{id}")
    User selectByIdCustom(@Param("id") Long id);
}
```

## 2. DDD 领域驱动设计（充血模型）

### 2.1 架构图

```
┌─────────────────────────────────────┐
│        Application (应用层)          │
│  (用例编排、事务边界)                │
├─────────────────────────────────────┤
│           Domain (领域层)            │
│  ┌─────────┐  ┌─────────────────┐  │
│  │  Entity │  │ Domain Service  │  │
│  │ (实体)  │  │  (领域服务)     │  │
│  └─────────┘  └─────────────────┘  │
│  ┌─────────┐  ┌─────────────────┐  │
│  │  VO     │  │ Domain Event   │  │
│  │ (值对象)│  │  (领域事件)     │  │
│  └─────────┘  └─────────────────┘  │
├─────────────────────────────────────┤
│     Infrastructure (基础设施层)      │
│  (持久化、外部服务)                  │
└─────────────────────────────────────┘
```

### 2.2 领域实体

```java
// 领域实体 - 包含业务逻辑
public class Order extends AggregateRoot {
    
    private OrderId id;
    private CustomerId customerId;
    private OrderStatus status;
    private List<OrderItem> items;
    private Money totalAmount;
    private ShippingAddress shippingAddress;
    
    // 工厂方法
    public static Order create(CustomerId customerId, 
            List<OrderItem> items, ShippingAddress address) {
        Order order = new Order();
        order.id = OrderId.generate();
        order.customerId = customerId;
        order.items = new ArrayList<>(items);
        order.shippingAddress = address;
        order.status = OrderStatus.DRAFT;
        order.totalAmount = Money.ZERO;
        
        // 领域逻辑
        order.calculateTotalAmount();
        order.validate();
        
        // 发布领域事件
        order.registerEvent(new OrderCreatedEvent(order));
        
        return order;
    }
    
    // 领域行为
    public void confirm() {
        if (status != OrderStatus.DRAFT) {
            throw new OrderException("订单状态不允许确认");
        }
        this.status = OrderStatus.CONFIRMED;
        registerEvent(new OrderConfirmedEvent(this));
    }
    
    public void cancel(String reason) {
        if (!status.canCancel()) {
            throw new OrderException("订单状态不允许取消");
        }
        this.status = OrderStatus.CANCELLED;
        registerEvent(new OrderCancelledEvent(this, reason));
    }
    
    public void pay(PaymentInfo paymentInfo) {
        // 支付逻辑
        if (!validatePayment(paymentInfo)) {
            throw new OrderException("支付信息验证失败");
        }
        this.status = OrderStatus.PAID;
        registerEvent(new OrderPaidEvent(this, paymentInfo));
    }
    
    private void calculateTotalAmount() {
        this.totalAmount = items.stream()
            .map(OrderItem::getSubtotal)
            .reduce(Money.ZERO, Money::add);
    }
    
    private void validate() {
        if (items.isEmpty()) {
            throw new OrderException("订单项不能为空");
        }
    }
}
```

### 2.3 值对象

```java
// 值对象 - 不可变、用于描述特征
@Value
public class Money {
    public static final Money ZERO = new Money(BigDecimal.ZERO);
    
    private final BigDecimal amount;
    private final Currency currency;
    
    public Money(BigDecimal amount) {
        this(amount, Currency.getInstance("CNY"));
    }
    
    public Money add(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("货币单位不一致");
        }
        return new Money(this.amount.add(other.amount));
    }
    
    public Money multiply(int factor) {
        return new Money(this.amount.multiply(
            BigDecimal.valueOf(factor)));
    }
}
```

### 2.4 仓储接口

```java
// 仓储接口 - 定义在领域层
public interface OrderRepository {
    Order findById(OrderId id);
    void save(Order order);
    void delete(OrderId id);
    Page<Order> findByCustomer(CustomerId customerId, PageRequest page);
}

// 持久化适配器 - 实现仓储接口
@Repository
public class JpaOrderRepository implements OrderRepository {
    
    private final OrderJpaRepository jpaRepository;
    
    @Override
    public Order findById(OrderId id) {
        return jpaRepository.findById(id.getValue())
            .map(this::toDomain)
            .orElse(null);
    }
    
    @Override
    public void save(Order order) {
        OrderEntity entity = toEntity(order);
        jpaRepository.save(entity);
    }
}
```

### 2.5 应用服务

```java
// 应用服务 - 用例编排
@Service
@RequiredArgsConstructor
@Transactional
public class OrderApplicationService {
    
    private final OrderRepository orderRepository;
    private final CustomerRepository customerRepository;
    private final DomainEventPublisher eventPublisher;
    
    public OrderId createOrder(CreateOrderCommand command) {
        // 获取客户
        Customer customer = customerRepository
            .findById(command.getCustomerId())
            .orElseThrow(() -> new CustomerNotFoundException());
        
        // 创建订单（领域逻辑）
        List<OrderItem> items = command.getItems().stream()
            .map(this::toOrderItem)
            .collect(Collectors.toList());
        
        Order order = Order.create(
            customer.getId(),
            items,
            command.getShippingAddress()
        );
        
        // 保存
        orderRepository.save(order);
        
        // 发布事件
        eventPublisher.publish(order.pullEvents());
        
        return order.getId();
    }
}
```

## 3. 两种模式对比

| 维度 | 三层架构 | DDD 充血模型 |
|------|----------|--------------|
| 适用场景 | CRUD 为主、管理系统 | 复杂业务、核心域 |
| 学习成本 | 低 | 高 |
| 代码量 | 少 | 多 |
| 可维护性 | 业务简单时好 | 业务复杂时好 |
| 性能 | 好 | 需注意 |
| 团队要求 | 普通开发 | 需要 DDD 经验 |

**推荐**：
- 业务简单（增删改查为主）：使用三层架构
- 业务复杂（核心业务逻辑）：考虑 DDD
- 混合使用：核心域用 DDD，周边用三层

## 4. 代码组织规范

### 4.1 包结构

```
com.example.project
├── controller          # Controller 层
├── service             # Service 层
│   ├── impl
│   └── dto
├── mapper              # Mapper/Repository 层
├── entity              # 实体类
├── vo                  # 视图对象
├── dto                 # 数据传输对象
├── enums               # 枚举
├── config              # 配置类
├── exception           # 异常定义
└── util                # 工具类
```

### 4.2 类命名规范

| 类型 | 后缀 | 示例 |
|------|------|------|
| Controller | Controller | UserController |
| Service | Service/ServiceImpl | UserService/UserServiceImpl |
| Mapper | Mapper | UserMapper |
| Entity | (无) | User |
| VO | VO | UserVO |
| DTO | DTO | UserDTO |
| Query | QueryDTO | UserQueryDTO |

---

*作者: 陈启明*
*更新: 2026-04-29*
