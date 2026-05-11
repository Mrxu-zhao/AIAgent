# JMeter 高级用法指南

> 作者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29  
> 适用版本：JMeter 5.6+

## 1. 参数化（Parameterized）

参数化是性能测试中模拟真实用户行为的关键技术，让每个虚拟用户使用不同的数据。

### 1.1 CSV 数据文件配置

```xml
<!-- JMeter 中的 CSV Data Set Config 配置 -->
<CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="CSV Data Set Config">
  <stringProp name="delimiter">,</stringProp>
  <stringProp name="fileEncoding">UTF-8</stringProp>
  <boolProp name="ignoreFirstLine">true</boolProp>      <!-- 跳过表头 -->
  <boolProp name="quotedData">false</boolProp>
  <boolProp name="recycle">true</boolProp>              <!-- 数据循环 -->
  <stringProp name="shareMode">shareMode.all</stringProp>
  <boolProp name="stopThread">false</boolProp>          <!-- 线程组停止 -->
  <stringProp name="variableNames">username,password,userId</stringProp>
</CSVDataSet>
```

**配置要点：**
- `ignoreFirstLine=true`：CSV 文件第一行是表头时勾选
- `Recycle=true` + `StopThread=false`：数据用完继续循环
- `Recycle=false` + `StopThread=true`：数据用完线程停止
- `shareMode`：
  - `shareMode.all`：所有线程共享
  - `shareMode.group`：同线程组共享
  - `shareMode.thread`：仅当前线程独享

**CSV 示例（users.csv）：**
```csv
username,password,userId
user001,pass123,10001
user002,pass456,10002
user003,pass789,10003
```

### 1.2 用户定义的变量（User Defined Variables）

适用于不变化的配置数据：

```
BaseURL    | http://api.example.com
Port       | 8080
DB_Host    | 192.168.1.100
DB_Port    | 3306
```

### 1.3 函数助手参数化

| 函数 | 用途 | 示例 |
|------|------|------|
| `${__time()}` | 当前时间戳 | 1714300800000 |
| `${__time(Y-MM-dd)}` | 格式化时间 | 2026-04-29 |
| `${__Random(1,100)}` | 随机数 | 1~100 |
| `${__UUID}` | UUID | 550e8400-e29b... |
| `${__V(var${n})}` | 变量嵌套 | 动态变量 |
| `${__counter(TRUE)}` | 计数器 | 1,2,3... |
| `${__MD5(${password})}` | MD5加密 | - |

### 1.4 从数据库获取参数

```xml
<!-- JDBC Connection Configuration -->
<JDBCDataSource guiclass="TestBeanGUI" testclass="JDBCDataSource" testname="JDBC Config">
  <stringProp name="dataSource">mysql-db</stringProp>
  <stringProp name="poolMax">10</stringProp>
  <stringProp name="timeout">10000</stringProp>
  <stringProp name="driver">com.mysql.cj.jdbc.Driver</stringProp>
  <stringProp name="url">jdbc:mysql://localhost:3306/testdb</stringProp>
  <stringProp name="username">root</stringProp>
  <stringProp name="password">password</stringProp>
</JDBCDataSource>

<!-- JDBC Request 提取数据 -->
<JDBCSampler guiclass="TestBeanGUI" testclass="JDBCSampler" testname="JDBC Request">
  <stringProp name="dataSource">mysql-db</stringProp>
  <stringProp name="query">SELECT username, balance FROM user_accounts LIMIT 100</stringProp>
  <stringProp name="queryType">Select Statement</stringProp>
  <stringProp name="variableNames">db_username,db_balance</stringProp>
</JDBCSampler>
```

## 2. 关联（Correlation）

关联用于提取响应中的动态数据，传递给后续请求，是会话保持的核心。

### 2.1 正则表达式提取器

```xml
<RegexExtractor guiclass="RegexExtractorGui" testclass="RegexExtractor" testname="Regular Expression Extractor">
  <stringProp name="RegexExtractor.useHeaders">false</stringProp>
  <stringProp name="RegexExtractor.refname">sessionToken</stringProp>     <!-- 变量名 -->
  <stringProp name="RegexExtractor.regex">sessionToken\s*=\s*"(.+?)"</stringProp>  <!-- 正则 -->
  <stringProp name="RegexExtractor.template">$1$</stringProp>                <!-- 取第1组 -->
  <stringProp name="RegexExtractor.default">NOT_FOUND</stringProp>            <!-- 默认值 -->
  <stringProp name="RegexExtractor.matchNumber">1</stringProp>                 <!-- 匹配第1个 -->
</RegexExtractor>
```

**常用正则模式：**

| 场景 | 正则表达式 | 说明 |
|------|-----------|------|
| JSON中的token | `"token"\s*:\s*"([^"]+)"` | 提取JSON字符串值 |
| HTML中的ID | `id="user_(\d+)"` | 提取数字ID |
| Set-Cookie | `JSESSIONID=(\w+)` | 提取Session ID |
| XML标签内容 | `<orderId>(\d+)</orderId>` | 提取标签内容 |

### 2.2 JSON 提取器（推荐）

```xml
<JsonExtractor guiclass="JsonExtractorGui" testclass="JsonExtractor" testname="JSON Extractor">
  <stringProp name="JsonExtractor.varName">userInfo</stringProp>
  <stringProp name="JsonExtractor.jsonPathExpr">$.data.userList[0].id</stringProp>
  <stringProp name="JsonExtractor.matchNumber">1</stringProp>
  <stringProp name="JsonExtractor.defaultValues">NOT_FOUND</stringProp>
</JsonExtractor>
```

**JSONPath 常用语法：**
```
$.data.users           # 根节点下的users
$.data.users[0].name   # 第一个用户的name
$.data.users[*].name   # 所有用户的name
$.data[?(@.age>18)]    # 过滤age>18的
$.data.items[-1]      # 最后一个元素
```

### 2.3 XPath 提取器

适用于 HTML/XML 响应：

```xml
<XPathExtractor guiclass="XPathExtractorGui" testclass="XPathExtractor" testname="XPath Extractor">
  <stringProp name="XPathExtractor.varName">csrfToken</stringProp>
  <stringProp name="XPathExtractor.xpathQuery">//input[@name='_csrf']/@value</stringProp>
  <stringProp name="XPathExtractor.default">NOT_FOUND</stringProp>
</XPathExtractor>
```

### 2.4 边界提取器（Boundary Extractor）

简单场景推荐使用，无需正则：

```
Left Boundary:  sessionToken="
Right Boundary: "
Variable Name:  sessionToken
Match No.:      1
Default Value:  NOT_FOUND
```

### 2.5 关联实战：完整登录流程

```
Thread Group
├── Login Request (POST /api/login)
│   └── JSON Extractor: 提取 token, userId
├── Get User Info (GET /api/user/${userId})
│   └── Header: Authorization=Bearer ${token}
├── Update Profile (POST /api/user/update)
│   └── JSON Extractor: 提取 newSessionId
└── Logout (POST /api/logout)
    └── Header: Cookie: SESSION=${newSessionId}
```

## 3. 集合点（Synchronizing Timer）

集合点用于模拟高并发场景，让多个线程同时执行。

### 3.1 同步定时器（Synchronizing Timer）

```xml<Timer guiclass="SynchronizingTimerGui" testclass="SynchronizingTimer" testname="Synchronizing Timer">
  <intProp name="GroupSize">50</intProp>          <!-- 模拟用户数，达到此数量才释放 -->
  <intProp name="TimeoutInMilliseconds">30000</intProp>  <!-- 超时时间，0=无限等待 -->
</Timer>
```

**配置说明：**
- `GroupSize = 线程数`：所有线程同时释放
- `GroupSize = 10`：每10个线程为一组释放
- `TimeoutInMilliseconds = 0`：必须等到足够线程才执行
- `TimeoutInMilliseconds = 5000`：超时后释放已积压的线程

### 3.2 常量吞吐定时器（Constant Throughput Timer）

按目标TPS控制发送速率：

```xml
<Timer guiclass="ConstantThroughputTimerGui" testclass="ConstantThroughputTimer" testname="Constant Throughput Timer">
  <stringProp name="Throughput">1000</stringProp>           <!-- 目标吞吐量 -->
  <intProp name="Throughput_sharing_mode">0</intProp>       <!-- 0=所有活动线程 -->
</Timer>
```

**计算公式：**
```
Target TPS = 期望QPS
Threads = Target TPS × Avg Response Time (秒)
```

例如：期望500 QPS，平均响应时间200ms，需要线程数：
```
500 × 0.2 = 100 线程
```

### 3.3 思考时间定时器（Uniform Random Timer）

模拟真实用户的操作间隔：

```xml
<Timer guiclass="UniformRandomTimerGui" testclass="UniformRandomTimer" testname="Uniform Random Timer">
  <stringProp name="ConstantTimer.delay">1000</stringProp>     <!-- 固定延迟(毫秒) -->
  <stringProp name="RandomTimer.range">2000</stringProp>       <!-- 随机范围(毫秒) -->
</Timer>
```

实际延迟 = 1000 + random(0~2000) = 1000~3000ms

### 3.4 高斯随机定时器

```xml
<Timer guiclass="GaussianRandomTimerGui" testclass="GaussianRandomTimer" testname="Gaussian Random Timer">
  <stringProp name="ConstantTimer.delay">1000</stringProp>
  <stringProp name="RandomTimer.range">500</stringProp>
</Timer>
```

延迟分布符合正态分布，大部分请求集中在平均值附近。

## 4. 断言（Assertions）

断言用于验证响应结果是否符合预期，是自动化的质量保障。

### 4.1 响应断言（Response Assertion）

```xml
<ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="Response Assertion">
  <stringProp name="PatternStringsToTest">200</stringProp>    <!-- 要匹配的字符串 -->
  <stringProp name="TestFieldResponseCode">\d+</stringProp>    <!-- 检查响应码 -->
  <intProp name="AssumeSuccess">0</intProp>
  <boolProp name="TestType">2</boolProp>    <!-- 1=包含, 2=匹配, 3=Equals -->
</ResponseAssertion>
```

**Pattern Matching Rules：**
| 模式 | 含义 | 示例 |
|------|------|------|
| Contains | 包含 | "success" 包含 "succ" ✓ |
| Matches | 正则匹配 | "\d{3}" 匹配 "200" ✓ |
| Equals | 完全相等 | "200" equals "200" ✓ |
| Substring | 子串 | 同Contains |

### 4.2 JSON 断言

```xml
<JsonAssertion guiclass="JsonAssertionGui" testclass="JsonAssertion" testname="JSON Assertion">
  <stringProp name="JSON_PATH">$.code</stringProp>
  <stringProp name="EXPECTED_VALUE">0</stringProp>
  <boolProp name="EXPECT_NULL">false</boolProp>
  <boolProp name="INVERT">false</boolProp>
</JsonAssertion>
```

**常用 JSONPath 断言：**
```
$.code == 0                    # 状态码为0
$.data.balance >= 0           # 余额非负
$.data.userList.length() > 0 # 用户列表非空
"${username}" == $.data.name  # 验证用户名
```

### 4.3 Size Assertion

```xml
<SizeAssertion guiclass="SizeAssertionGui" testclass="SizeAssertion" testname="Size Assertion">
  <stringProp name="SizeTracker">8192</stringProp>       <!-- 预期字节数 -->
  <intProp name="SizeOperator">0</intProp>                <!-- 0=等于 -->
</SizeAssertion>
```

**SizeOperator 选项：**
- 0: = 等于
- 1: != 不等于
- 2: > 大于
- 3: >= 大于等于
- 4: < 小于
- 5: <= 小于等于

### 4.4 Duration Assertion（响应时间断言）

```xml
<DurationAssertion guiclass="DurationAssertionGui" testclass="DurationAssertion" testname="Duration Assertion">
  <intProp name="DurationAssertion.duration">2000</intProp>  <!-- 2秒超时 -->
</DurationAssertion>
```

### 4.5 XPath 断言

```xml
<XPathAssertion guiclass="XPathAssertionGui" testclass="XPathAssertion" testname="XPath Assertion">
  <stringProp name="XPath">//result[@status='success']</stringProp>
  <boolProp name="Tolerant">true</boolProp>
  <boolProp name="Whitespace">true</boolProp>
</XPathAssertion>
```

### 4.6 断言实战：完整的响应验证

```
POST /api/order/create
├── Response Code: 200 (响应断言)
├── Response Body Contains: "code":0 (JSON包含检查)
├── JSON Path: $.code == 0 (JSON断言)
├── JSON Path: $.data.orderId matches "\d+" (订单ID是数字)
├── Response Size: > 100 bytes (Size断言)
└── Duration: < 1000ms (响应时间断言)
```

## 5. 高级技巧

### 5.1 IF 控制器（Conditional Controller）

```xml
<IfController guiclass="IfControllerGui" testclass="IfController" testname="If Controller">
  <stringProp name="IfController.condition">${isVIP} == "true"</stringProp>
  <boolProp name="IfController.evaluateAll">false</boolProp>
</IfController>
```

### 5.2 ForEach 控制器

处理提取的列表数据：

```xml
<ForeachController guiclass="ForeachControllerGui" testclass="ForeachController" testname="ForEach Controller">
  <stringProp name="ForeachController.inputVal">userId_list_</stringProp>   <!-- 输入变量前缀 -->
  <stringProp name="ForeachController.returnVal">currentUserId</stringProp>   <!-- 输出变量名 -->
  <boolProp name="ForeachController.useSeparator">true</boolProp>
</ForeachController>
```

### 5.3 吞吐量控制器（Throughput Controller）

控制各请求的执行比例：

```xml
<ThroughputController guiclass="ThroughputControllerGui" testclass="ThroughputController" testname="Throughput Controller">
  <stringProp name="ThroughputController.percentThroughput">30</stringProp>  <!-- 30%概率执行 -->
  <boolProp name="ThroughputController.perThread">false</boolProp>
</ThroughputController>
```

### 5.4 后置处理器提取多个值

```xml
<JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="JSON Extractor">
  <stringProp name="JSONPostProcessor.jsonPathExpr">$.data.items[*]</stringProp>
  <stringProp name="JSONPostProcessor.matchNumbers">-1</stringProp>   <!-- -1=匹配所有 -->
  <stringProp name="JSONPostProcessor.refname">item</stringProp>
</JSONPostProcessor>
```

输出：
```
item_1={"id":1,"name":"item1"}
item_2={"id":2,"name":"item2"}
item_matchNr=3
```

### 5.5 BeanShell 脚本处理复杂逻辑

```java
// 字符串处理
String token = vars.get("token");
String newToken = token.replace("Bearer ", "");
vars.put("authToken", newToken);

// 日期时间处理
import java.text.SimpleDateFormat;
SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
String timestamp = sdf.format(new Date());
vars.put("timestamp", timestamp);

// 条件逻辑
int balance = Integer.parseInt(vars.get("balance"));
if (balance < 100) {
    vars.put("status", "low");
} else {
    vars.put("status", "normal");
}
```

## 6. 性能测试最佳实践

### 6.1 测试计划结构

```
Test Plan
├── HTTP Cookie Manager          # 全局Cookie管理
├── HTTP Header Manager          # 全局请求头
├── User Defined Variables       # 全局变量
├── Setup Thread Group           # 前置准备（清理数据）
│   └── 初始化测试数据
├── Main Thread Group            # 主测试
│   ├── Transaction Controller: 登录
│   │   ├── Login Request
│   │   └── JSON Extractor
│   ├── Transaction Controller: 业务操作
│   │   ├── Search Request
│   │   ├── Detail Request
│   │   └── Order Request
│   └── Transaction Controller: 登出
└── Teardown Thread Group         # 后置清理
    └── 清理测试数据
```

### 6.2 性能监控配置

```xml
<!-- 监听器配置 -->
<ResultCollector guiclass="TableVisualizer" testname="View Results in Table">
  <boolProp name="saveAssertionResultsFailureMessage">true</boolProp>
  <boolProp name="saveResponseData">false</boolProp>      <!-- 关闭响应保存 -->
  <boolProp name="saveSamplerData">false</boolProp>       <!-- 减少内存占用 -->
</ResultCollector>

<!-- 聚合报告配置 -->
<ResultCollector guiclass="StatVisualizer" testname="Aggregate Report">
  <boolProp name="saveResponseData">false</boolProp>
  <boolProp name="saveRequestHeaders">false</boolProp>
</ResultCollector>
```

### 6.3 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 响应超时 | 服务器处理慢 | 分析慢接口，增加超时时间 |
| 关联失败 | 正则不匹配 | 检查响应格式，调整正则 |
| 参数化为空 | CSV路径错误 | 使用绝对路径，检查文件名 |
| TPS为0 | 集合点死锁 | 调整GroupSize或Timeout |
| 内存溢出 | 监听器保存过多 | 关闭响应数据保存 |

---

*相关文档：[JMeter 性能测试场景设计](./jmeter-scenario-design.md)*  
*返回：[QA 性能测试知识库索引](../index.md)*
