# Java 单元测试最佳实践

## 1. JUnit 5 核心注解

```java
import org.junit.jupiter.api.*;

@DisplayName("用户服务测试")
class UserServiceTest {
    
    @BeforeAll
    static void beforeAll() {
        // 所有测试前执行一次
    }
    
    @BeforeEach
    void beforeEach() {
        // 每个测试前执行
    }
    
    @Test
    @DisplayName("测试创建用户")
    void testCreateUser() {
        // 测试代码
    }
    
    @AfterEach
    void afterEach() {
        // 每个测试后执行
    }
    
    @AfterAll
    static void afterAll() {
        // 所有测试后执行一次
    }
}
```

## 2. Mockito 常用用法

### 2.1 基本 Mock

```java
import org.mockito.Mockito;

class UserServiceTest {
    
    private UserMapper userMapper;
    private UserService userService;
    
    @BeforeEach
    void setUp() {
        userMapper = Mockito.mock(UserMapper.class);
        userService = new UserServiceImpl(userMapper);
    }
    
    @Test
    void testGetById() {
        User user = new User();
        user.setId(1L);
        user.setUsername("test");
        
        Mockito.when(userMapper.selectById(1L)).thenReturn(user);
        
        User result = userService.getById(1L);
        
        Assertions.assertNotNull(result);
        Assertions.assertEquals("test", result.getUsername());
        Mockito.verify(userMapper).selectById(1L);
    }
}
```

### 2.2 使用 @Mock 和 @InjectMocks

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    
    @Mock
    private UserMapper userMapper;
    
    @Mock
    private UserCacheService userCacheService;
    
    @InjectMocks
    private UserServiceImpl userService;
    
    @Test
    void testGetByIdWithCache() {
        User user = new User();
        user.setId(1L);
        
        Mockito.when(userCacheService.get(1L)).thenReturn(null);
        Mockito.when(userMapper.selectById(1L)).thenReturn(user);
        
        User result = userService.getById(1L);
        
        Assertions.assertNotNull(result);
        Mockito.verify(userCacheService).put(1L, user);
    }
}
```

### 2.3 常用 Mockito 方法

```java
// 返回固定值
Mockito.when(mock.method()).thenReturn(value);

// 抛出异常
Mockito.when(mock.method()).thenThrow(new RuntimeException("error"));

// 使用 Answer
Mockito.when(mock.method(anyString()))
    .thenAnswer(invocation -> {
        String arg = invocation.getArgument(0);
        return "Hello " + arg;
    });

// 匹配参数
Mockito.when(mock.method(anyLong())).thenReturn(user);
Mockito.when(mock.method(eq(1L))).thenReturn(user);
Mockito.when(mock.method(argThat(name -> name.length() > 3))).thenReturn(user);

// 验证调用次数
Mockito.verify(mock, Mockito.times(2)).method();
Mockito.verify(mock, Mockito.never()).method();
Mockito.verify(mock, Mockito.atLeastOnce()).method();
```

## 3. Spring Boot 测试

### 3.1 Service 层测试

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    
    @Mock
    private UserMapper userMapper;
    
    @Spy
    private PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    
    @InjectMocks
    private UserServiceImpl userService;
    
    @Test
    @DisplayName("注册用户成功")
    void testRegisterSuccess() {
        Mockito.when(userMapper.selectByUsername("test"))
            .thenReturn(null);
        Mockito.when(userMapper.insert(Mockito.any(User.class)))
            .thenReturn(1);
        
        UserRegisterDTO dto = new UserRegisterDTO();
        dto.setUsername("test");
        dto.setPassword("123456");
        
        Boolean result = userService.register(dto);
        
        Assertions.assertTrue(result);
        Mockito.verify(passwordEncoder).encode("123456");
    }
    
    @Test
    @DisplayName("用户名已存在")
    void testUsernameExists() {
        Mockito.when(userMapper.selectByUsername("test"))
            .thenReturn(new User());
        
        UserRegisterDTO dto = new UserRegisterDTO();
        dto.setUsername("test");
        
        Assertions.assertThrows(BusinessException.class, 
            () -> userService.register(dto));
    }
}
```

### 3.2 Controller 层测试

```java
@WebMvcTest(UserController.class)
class UserControllerTest {
    
    @Autowired
    private MockMvc mockMvc;
    
    @MockBean
    private UserService userService;
    
    @Test
    void testGetUser() throws Exception {
        UserVO userVO = new UserVO();
        userVO.setId(1L);
        userVO.setUsername("test");
        
        Mockito.when(userService.getById(1L)).thenReturn(userVO);
        
        mockMvc.perform(MockMvcRequestBuilders.get("/v1/users/1"))
            .andExpect(MockMvcResultMatchers.status().isOk())
            .andExpect(jsonPath("$.code").value(200))
            .andExpect(jsonPath("$.data.username").value("test"));
    }
    
    @Test
    void testCreateUserValidation() throws Exception {
        mockMvc.perform(MockMvcRequestBuilders.post("/v1/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"\",\"email\":\"invalid\"}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(jsonPath("$.code").value(400));
    }
}
```

### 3.3 数据库测试

```java
@DataJpaTest
@TestPropertySource(properties = {
    "spring.datasource.url=jdbc:h2:mem:testdb",
    "spring.jpa.hibernate.ddl-auto=create-drop"
})
class UserRepositoryTest {
    
    @Autowired
    private UserRepository userRepository;
    
    @Test
    void testFindByUsername() {
        User user = new User();
        user.setUsername("test");
        userRepository.save(user);
        
        Optional<User> found = userRepository.findByUsername("test");
        
        Assertions.assertTrue(found.isPresent());
        Assertions.assertEquals("test", found.get().getUsername());
    }
}
```

## 4. 测试最佳实践

### 4.1 测试结构 (AAA)

```java
@Test
void testSomething() {
    // Arrange - 准备测试数据
    User user = createTestUser();
    Mockito.when(userMapper.selectById(1L)).thenReturn(user);
    
    // Act - 执行被测方法
    User result = userService.getById(1L);
    
    // Assert - 验证结果
    Assertions.assertNotNull(result);
    Assertions.assertEquals("test", result.getUsername());
}
```

### 4.2 测试命名规范

```java
// 推荐：方法名_场景_预期结果
@Test
void getUserById_existingUser_returnsUser() { }

@Test  
void createUser_nullInput_throwsException() { }

// 不推荐
@Test
void test1() { }
@Test
void testGetUser() { }
```

### 4.3 测试数据准备

```java
public class TestDataFactory {
    
    public static User createUser(Long id, String username) {
        User user = new User();
        user.setId(id);
        user.setUsername(username);
        user.setEmail(username + "@test.com");
        user.setStatus(1);
        user.setCreateTime(LocalDateTime.now());
        return user;
    }
    
    public static List<User> createUserList(int count) {
        return IntStream.rangeClosed(1, count)
            .mapToObj(i -> createUser((long) i, "user" + i))
            .collect(Collectors.toList());
    }
}
```

### 4.4 常用断言

```java
import static org.junit.jupiter.api.Assertions.*;
import static org.assertj.core.api.Assertions.*;

// JUnit 5
assertEquals(expected, actual);
assertNotNull(result);
assertTrue(condition);
assertThrows(Exception.class, () -> method());

// AssertJ（更流畅）
assertThat(user.getName())
    .isNotNull()
    .isEqualTo("test")
    .startsWith("te");
    
assertThatThrownBy(() -> method())
    .isInstanceOf(RuntimeException.class)
    .hasMessageContaining("error");
```

## 5. 覆盖率目标

| 层次 | 建议覆盖率 |
|------|-----------|
| 核心业务逻辑 | 80%+ |
| Service 层 | 70%+ |
| Controller 层 | 60%+ |
| Mapper 层 | 视情况 |

---

*作者: 陈启明*
*更新: 2026-04-29*
