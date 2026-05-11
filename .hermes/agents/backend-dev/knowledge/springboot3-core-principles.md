# Spring Boot 3.x 核心原理

## 1. 自动配置原理

### 1.1 核心机制

Spring Boot 自动配置通过 `@SpringBootApplication` 注解中的 `@EnableAutoConfiguration` 实现。

```java
@SpringBootApplication
// 等价于
@Configuration
@EnableAutoConfiguration
@ComponentScan
```

### 1.2 自动配置流程

1. `spring.factories` 文件定义配置类
2. `AutoConfigurationImportSelector` 读取配置
3. 通过 `@Conditional` 注解判断是否生效
4. 配置类注册 BeanDefinition

### 1.3 自定义 Starter

创建 `my-spring-boot-starter`：

```
my-spring-boot-starter/
├── pom.xml
└── src/main/resources/
    └── META-INF/
        └── spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
```

```java
// src/main/java/com/example/autoconfig/MyAutoConfig.java
@Configuration
@ConditionalOnClass(MyService.class)  // 条件：类存在时生效
@ConditionalOnProperty(prefix = "my.service", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(MyProperties.class)
public class MyAutoConfig {
    
    @Bean
    @ConditionalOnMissingBean
    public MyService myService(MyProperties properties) {
        return new MyService(properties);
    }
}
```

```properties
# MyProperties.java
@ConfigurationProperties(prefix = "my.service")
public class MyProperties {
    private String name = "default";
    private int timeout = 3000;
    // getter/setter
}
```

```properties
# resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
com.example.autoconfig.MyAutoConfig
```

### 1.4 常见条件注解

| 注解 | 作用 |
|------|------|
| `@ConditionalOnClass` |  클래스 존재 시生效 |
| `@ConditionalOnMissingBean` | 不存在 Bean 时生效 |
| `@ConditionalOnProperty` | 配置项满足条件时生效 |
| `@ConditionalOnWebApplication` | Web 应用时生效 |

## 2. Spring Boot 3.x 新特性

### 2.1 Jakarta EE 迁移

```java
// Spring Boot 2.x
import javax.servlet.*
import javax.annotation.*

// Spring Boot 3.x
import jakarta.servlet.*
import jakarta.annotation.*
```

### 2.2 GraalVM 原生支持

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.graalvm.buildtools</groupId>
    <artifactId>native-maven-plugin</artifactId>
</plugin>
```

### 2.3 候选配置机制

Spring Boot 3.x 使用 `AutoConfiguration.imports` 替代 `spring.factories`。

## 3. 启动流程

```java
// SpringApplication.run() 流程
public static void main(String[] args) {
    SpringApplication.run(Application.class, args);
}

// 内部执行
1. createBootstrapContext()      // 创建引导上下文
2. configureHeadlessProperty()    // 配置无头模式
3. getRunListeners(args)          // 获取监听器
4. prepareEnvironment()          // 准备环境
5. printBanner()                  // 打印Banner
6. createApplicationContext()     // 创建上下文
7. prepareContext()               // 准备上下文
8. refreshContext()               // 刷新上下文 ← 核心
9. afterRefresh()                 // 刷新后处理
```

## 4. 外部化配置

### 4.1 配置优先级（从高到低）

1. 命令行参数 `--server.port=9000`
2. OS 环境变量
3. application-{profile}.yml
4. application.yml
5. @PropertySource 注解
6. 默认配置

### 4.2 @ConfigurationProperties 绑定

```java
@ConfigurationProperties(prefix = "app.user")
@Validated
public class UserProperties {
    @NotBlank
    private String name;
    
    @Min(1) @Max(150)
    private int age;
    
    private List<String> roles;
    
    private Map<String, String> extra;
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
