# 设计模式在后端的应用

## 1. 单例模式 (Singleton)

### 应用场景

- 配置类（全局配置）
- 连接池（数据库连接池、Redis连接池）
- 缓存管理器

### 实现方式

```java
// 枚举方式（推荐，线程安全，防反射）
public enum ConfigManager {
    INSTANCE;
    
    private Map<String, String> config = new HashMap<>();
    
    public String get(String key) {
        return config.get(key);
    }
}

// Spring中使用@Service默认单例，无需特殊处理
@Service
public class CacheManager {
    private Map<String, Object> cache = new ConcurrentHashMap<>();
}
```

---

## 2. 工厂模式 (Factory)

### 应用场景

- 创建不同类型的支付渠道
- 创建不同格式的文档导出器
- 创建不同类型的消息发送者

### 实现示例

```java
// 工厂接口
public interface MessageSender {
    void send(String to, String content);
}

// 具体实现
public class EmailSender implements MessageSender {
    @Override
    public void send(String to, String content) {
        // 发送邮件
    }
}

public class SmsSender implements MessageSender {
    @Override
    public void send(String to, String content) {
        // 发送短信
    }
}

// 工厂
public class MessageSenderFactory {
    public static MessageSender getSender(String type) {
        return switch (type) {
            case "EMAIL" -> new EmailSender();
            case "SMS" -> new SmsSender();
            default -> throw new IllegalArgumentException("未知类型");
        };
    }
}

// Spring集成
@Configuration
public class SenderConfig {
    @Bean
    public Map<String, MessageSender> senderMap() {
        Map<String, MessageSender> map = new HashMap<>();
        map.put("EMAIL", new EmailSender());
        map.put("SMS", new SmsSender());
        return map;
    }
}

@Service
public class NotificationService {
    @Autowired
    private Map<String, MessageSender> senderMap;
    
    public void notify(String type, String to, String content) {
        MessageSender sender = senderMap.get(type);
        if (sender != null) {
            sender.send(to, content);
        }
    }
}
```

---

## 3. 策略模式 (Strategy)

### 应用场景

- 不同的折扣计算方式
- 不同的排序算法
- 不同的支付方式

### 实现示例

```java
// 策略接口
@FunctionalInterface
public interface DiscountStrategy {
    BigDecimal calculate(BigDecimal originalPrice);
}

// 策略实现
public class NoDiscountStrategy implements DiscountStrategy {
    @Override
    public BigDecimal calculate(BigDecimal originalPrice) {
        return originalPrice;
    }
}

public class PercentDiscountStrategy implements DiscountStrategy {
    private final double percent;
    
    public PercentDiscountStrategy(double percent) {
        this.percent = percent;
    }
    
    @Override
    public BigDecimal calculate(BigDecimal originalPrice) {
        return originalPrice.multiply(BigDecimal.valueOf(percent));
    }
}

// 策略上下文
public class DiscountContext {
    private DiscountStrategy strategy;
    
    public void setStrategy(DiscountStrategy strategy) {
        this.strategy = strategy;
    }
    
    public BigDecimal execute(BigDecimal price) {
        return strategy.calculate(price);
    }
}

// Spring使用
@Service
public class OrderService {
    @Autowired
    private Map<String, DiscountStrategy> strategies;
    
    public BigDecimal calculatePrice(Order order) {
        DiscountStrategy strategy = strategies.get(order.getDiscountType());
        return strategy.calculate(order.getOriginalPrice());
    }
}
```

---

## 4. 模板方法模式 (Template Method)

### 应用场景

- 数据导入导出流程
- 接口调用前后处理
- 业务流程编排

### 实现示例

```java
// 抽象模板
public abstract class AbstractDataExport {
    
    // 模板方法（final防止重写）
    public final void export() {
        // 1. 校验权限
        checkPermission();
        
        // 2. 查询数据
        List<?> data = queryData();
        
        // 3. 转换格式
        List<?> transformed = transform(data);
        
        // 4. 写入文件（钩子方法）
        writeToFile(transformed);
        
        // 5. 发送通知（钩子方法）
        sendNotification(transformed.size());
    }
    
    protected abstract List<?> queryData();
    
    protected abstract List<?> transform(List<?> data);
    
    protected void writeToFile(List<?> data) {
        // 默认实现
    }
    
    protected void sendNotification(int count) {
        // 默认空实现
    }
}

// 具体实现
@Service
public class UserExportService extends AbstractDataExport {
    
    @Override
    protected List<?> queryData() {
        return userMapper.selectAll();
    }
    
    @Override
    protected List<UserExcelVO> transform(List<?> data) {
        return data.stream()
            .map(u -> (User) u)
            .map(u -> new UserExcelVO(u.getName(), u.getEmail()))
            .collect(Collectors.toList());
    }
    
    @Override
    protected void sendNotification(int count) {
        log.info("导出完成，共{}条记录", count);
        emailService.sendToAdmin("导出完成");
    }
}
```

---

## 5. 责任链模式 (Chain of Responsibility)

### 应用场景

- 过滤器链（Web Filter）
- 审批流程
- 日志切面

### 实现示例

```java
// 处理器接口
public abstract class AuthHandler {
    protected AuthHandler next;
    
    public void setNext(AuthHandler next) {
        this.next = next;
    }
    
    public final void handle(AuthContext context) {
        if (doHandle(context)) {
            if (next != null) {
                next.handle(context);
            }
        }
    }
    
    protected abstract boolean doHandle(AuthContext context);
}

// 具体处理器
public class TokenHandler extends AuthHandler {
    @Override
    protected boolean doHandle(AuthContext context) {
        if (context.getToken() == null) {
            context.setError("缺少Token");
            return false;
        }
        return true;
    }
}

public class RoleHandler extends AuthHandler {
    @Override
    protected boolean doHandle(AuthContext context) {
        if (!context.hasRole("ADMIN")) {
            context.setError("权限不足");
            return false;
        }
        return true;
    }
}
```

---

## 设计模式使用原则

| 原则 | 说明 |
|------|------|
| 开闭原则 | 对扩展开放，对修改关闭 |
| 依赖倒置 | 依赖抽象而非具体实现 |
| 单一职责 | 一个类只做一件事 |
| 里氏替换 | 子类可替换父类 |

**注意**：不要过度设计，小项目优先考虑简单实现。

---

*文档类型：后端技术规范*
*适用范围：后端开发*
*最后更新：2026-04-29*
