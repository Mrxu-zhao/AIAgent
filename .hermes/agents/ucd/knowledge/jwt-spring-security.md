# JWT + Spring Security 认证授权方案

## 整体架构

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  前端   │───▶│ Gateway │───▶│ Auth    │───▶│ 业务    │
│         │    │ (Filter)│    │ Service │    │ Service │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                    │              │
                    │         ┌────┴────┐
                    │         │ JWT     │
                    │         │ Tokens  │
                    │         └─────────┘
```

## JWT Token 结构

```java
// Token payload
public class JwtPayload {
    private Long userId;
    private String username;
    private String roles;
    private Long exp;        // 过期时间
    private Long iat;        // 签发时间
}
```

### Token 配置

```yaml
jwt:
  secret: your-256-bit-secret-key-here
  access-token-validity: 3600        # 1小时
  refresh-token-validity: 604800     # 7天
```

## Spring Security 6.x 配置

### SecurityConfig

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    
    @Autowired private JwtAuthenticationFilter jwtFilter;
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**", "/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class);
        
        return http.build();
    }
}
```

### JWT Filter

```java
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    
    @Autowired private JwtService jwtService;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                     HttpServletResponse response,
                                     FilterChain chain) {
        String authHeader = request.getHeader("Authorization");
        
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            String token = authHeader.substring(7);
            
            if (jwtService.validateToken(token)) {
                JwtPayload payload = jwtService.parseToken(token);
                
                UserDetails user = User.builder()
                    .username(payload.getUsername())
                    .password("")
                    .authorities(RoleType.getAuthorities(payload.getRoles()))
                    .build();
                
                SecurityContextHolder.getContext().setAuthentication(
                    new UsernamePasswordAuthenticationToken(user, null, user.getAuthorities())
                );
            }
        }
        
        chain.doFilter(request, response);
    }
}
```

## 认证流程

### 登录

```java
@PostMapping("/login")
public Result<LoginResponse> login(@RequestBody @Valid LoginRequest request) {
    // 1. 验证用户名密码
    User user = userService.authenticate(request.getUsername(), request.getPassword());
    
    // 2. 生成Token
    String accessToken = jwtService.generateAccessToken(user);
    String refreshToken = jwtService.generateRefreshToken(user);
    
    return Result.success(LoginResponse.builder()
        .accessToken(accessToken)
        .refreshToken(refreshToken)
        .expiresIn(3600)
        .tokenType("Bearer")
        .build());
}
```

### Token 刷新

```java
@PostMapping("/refresh")
public Result<LoginResponse> refresh(@RequestBody RefreshRequest request) {
    if (jwtService.validateToken(request.getRefreshToken())) {
        JwtPayload payload = jwtService.parseToken(request.getRefreshToken());
        User user = userService.getById(payload.getUserId());
        
        String newAccessToken = jwtService.generateAccessToken(user);
        return Result.success(LoginResponse.builder()
            .accessToken(newAccessToken)
            .refreshToken(request.getRefreshToken())
            .expiresIn(3600)
            .build());
    }
    return Result.error(401, "Token已过期");
}
```

## 权限控制

### 注解方式

```java
@RestController
@RequestMapping("/api/users")
public class UserController {
    
    @PreAuthorize("hasAuthority('USER_READ')")
    @GetMapping("/{id}")
    public Result<UserDTO> getUser(@PathVariable Long id) {
        return Result.success(userService.getUserById(id));
    }
    
    @PreAuthorize("hasAuthority('USER_CREATE')")
    @PostMapping
    public Result<UserDTO> createUser(@RequestBody @Valid CreateUserRequest request) {
        return Result.success(userService.createUser(request));
    }
}
```

### 按钮级权限（前端）

```javascript
// 权限判断
const hasCreatePermission = permissions.includes('USER_CREATE');
const hasDeletePermission = permissions.includes('USER_DELETE');

// 渲染控制
{hasCreatePermission && <Button type="primary">新增</Button>}
```

## 安全最佳实践

1. **Token 存储**：HttpOnly Cookie 或内存存储，避免XSS
2. **传输安全**：强制HTTPS
3. **短期Token**：Access Token 有效期 ≤ 1小时
4. **Token 黑名单**：实现Logout机制
5. **敏感操作**：二次验证（如支付）

---

*文档类型：后端技术规范*
*适用范围：后端开发*
*最后更新：2026-04-29*
