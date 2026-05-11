# 后端调试指南

## 1. 日志调试技巧

### 1.1 日志级别使用

```java
@Slf4j
public class UserService {
    
    public void process() {
        log.trace("入口参数: {}", param);  // 详细跟踪
        log.debug("中间状态: {}", state);   // 调试信息
        log.info("处理完成: {}", result);    // 一般信息
        log.warn("警告信息: {}", warning);  // 警告
        log.error("错误详情", e);            // 错误
    }
}
```

### 1.2 请求链路日志

```java
@Component
public class RequestLogFilter extends OncePerRequestFilter {
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
            HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        
        String requestId = UUID.randomUUID().toString();
        request.setAttribute("requestId", requestId);
        
        long start = System.currentTimeMillis();
        
        try {
            chain.doFilter(request, response);
        } finally {
            long duration = System.currentTimeMillis() - start;
            log.info("requestId={}, uri={}, method={}, "
                + "status={}, duration={}ms",
                requestId, request.getRequestURI(),
                request.getMethod(), response.getStatus(), duration);
        }
    }
}
```

## 2. 常见调试方法

### 2.1 SQL 日志

```yaml
# application.yml
mybatis-plus:
  configuration:
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl  # 开发环境
    # 生产环境: org.apache.ibatis.logging.slf4j.Slf4jImpl
```

### 2.2 接口调试

```java
// 使用 @GetMapping("/debug/...") 临时调试接口
@GetMapping("/debug/users/{id}")
public String debugUser(@PathVariable Long id) {
    User user = userMapper.selectById(id);
    return JSON.toJSONString(user, 
        SerializerFeature.PrettyFormat);
}
```

---

*作者: 陈启明*
*更新: 2026-04-29*
