# 性能测试场景设计方法

> 作者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29

## 1. 测试场景分类

性能测试场景分为四大类型，每种场景有明确的目标和指标：

```
性能测试
├── 基准测试 (Benchmark Test)
├── 负载测试 (Load Test)
├── 压力测试 (Stress Test)
└── 稳定性测试 (Stability Test)
```

## 2. 基准测试 (Benchmark Test)

### 2.1 目的
确定系统在正常负载下的性能基准值，为其他测试提供参考标准。

### 2.2 特征
- 单用户或少量用户
- 稳定、重复执行
- 测试核心业务功能
- 确定性能基线

### 2.3 配置示例

```yaml
基准测试配置:
  目标: 确定单用户响应时间基线
  
  线程配置:
    线程数: 1
     Ramp-Up时间: 0
    循环次数: 10
    持续时间: 无
    
  监控指标:
    - 平均响应时间
    - 最小响应时间
    - 最大响应时间
    - 标准差
    
  预期结果:
    平均响应时间 < 500ms (业务要求)
    成功率 = 100%
```

### 2.4 JMeter 配置

```
Thread Group:
├── Number of Threads: 1
├── Ramp-Up Period: 0
├── Loop Count: 10
└── Duration: (留空)

监控内容:
├── Response Time Average
├── Response Time Min/Max
├── Throughput (TPS)
└── Error %
```

## 3. 负载测试 (Load Test)

### 3.1 目的
验证系统在预期正常负载下的性能表现，发现性能瓶颈。

### 3.2 场景设计原则

| 维度 | 说明 |
|------|------|
| 并发用户数 | 预估高峰用户数的 80% |
| 思考时间 | 模拟真实用户操作间隔 |
| 测试时长 | 至少 15-30 分钟 |
| 递增策略 | 逐步加压，观察拐点 |

### 3.3 负载模型设计

```yaml
负载测试场景:
  场景1: 预期负载测试
    目标: 验证系统能否达到预期性能指标
    
    负载模式:
      起始用户: 10
      增量: 10
      增量间隔: 30秒
      最大用户: 100
      
    业务配比:
      - 浏览商品: 40%
      - 搜索查询: 30%
      - 下单支付: 20%
      - 用户登录: 10%
      
    监控指标:
      TPS: > 100
      平均响应时间: < 2s
      错误率: < 1%
      
  场景2: 峰值负载测试
    目标: 验证系统峰值处理能力
    
    负载模式:
      用户数: 200 (峰值预估)
      持续时间: 30分钟
      
    业务配比:
      与场景1相同
      
    验收标准:
      系统稳定运行
      无性能急剧下降
```

### 3.4 业务比例配置 (JMeter)

```xml
<!-- 业务比例控制器 -->
<SwitchController testname="Business Mix Controller">
  <stringProp name="SwitchController.value">${__chooseRandom(1-10,)}</stringProp>
  
  <hashTree>
    <!-- 1-4: 浏览商品 (40%) -->
    <HTTPSamplerProxy testname="Browse Product">
      <stringProp name="HTTPSampler.domain">api.example.com</stringProp>
      <stringProp name="HTTPSampler.path">/product/list</stringProp>
    </HTTPSamplerProxy>
    
    <!-- 5-7: 搜索查询 (30%) -->
    <HTTPSamplerProxy testname="Search Product">
      <stringProp name="HTTPSampler.domain">api.example.com</stringProp>
      <stringProp name="HTTPSampler.path">/product/search</stringProp>
    </HTTPSamplerProxy>
    
    <!-- 8-9: 下单支付 (20%) -->
    <HTTPSamplerProxy testname="Create Order">
      <stringProp name="HTTPSampler.domain">api.example.com</stringProp>
      <stringProp name="HTTPSampler.path">/order/create</stringProp>
    </HTTPSamplerProxy>
    
    <!-- 10: 用户登录 (10%) -->
    <HTTPSamplerProxy testname="User Login">
      <stringProp name="HTTPSampler.domain">api.example.com</stringProp>
      <stringProp name="HTTPSampler.path">/user/login</stringProp>
    </HTTPSamplerProxy>
  </hashTree>
</SwitchController>
```

## 4. 压力测试 (Stress Test)

### 4.1 目的
验证系统超过正常负载极限时的表现，找出系统崩溃点。

### 4.2 压力测试策略

```
压力强度等级:
├── L1 轻度压力: 预期负载的 120%
├── L2 中度压力: 预期负载的 150%
├── L3 重度压力: 预期负载的 200%
├── L4 极限压力: 逐步加压直到系统崩溃
└── L5 破坏性测试: 突然大流量冲击
```

### 4.3 配置示例

```yaml
压力测试场景:
  场景: 逐步加压测试
    目标: 找出系统性能拐点和最大承载能力
    
    加压策略:
      Step 1:
        用户数: 50
        持续: 5分钟
        预期: 正常
        
      Step 2:
        用户数: 100
        持续: 5分钟
        预期: 正常或轻微下降
        
      Step 3:
        用户数: 150
        持续: 5分钟
        预期: 性能下降
        
      Step 4:
        用户数: 200
        持续: 5分钟
        预期: 明显性能下降
        
      Step 5:
        用户数: 250
        持续: 5分钟
        预期: 达到瓶颈或崩溃
        
    关键监控点:
      - TPS 变化趋势
      - 响应时间增长趋势
      - 错误率变化
      - 服务器资源使用率
```

### 4.4 突发压力测试

```yaml
突发压力测试:
  目的: 模拟突然的流量高峰
  
  场景设计:
    基础负载: 50用户 (持续)
    突发负载: 500用户 (持续30秒)
    
  执行步骤:
    1. 基础负载预热: 2分钟
    2. 突发高峰: 30秒 (500用户)
    3. 恢复观察: 2分钟
    4. 观察恢复时间和系统状态
    
  验收标准:
    - 系统能承受突发压力
    - 突发结束后能恢复正常
    - 恢复时间 < 60秒
```

## 5. 稳定性测试 (Stability Test)

### 5.1 目的
验证系统在长时间运行下的稳定性，发现内存泄漏、连接泄漏等问题。

### 5.2 测试时长设计

| 系统类型 | 最小测试时长 | 推荐时长 |
|----------|--------------|----------|
| 短周期系统 | 8 小时 | 24 小时 |
| 24/7 系统 | 24 小时 | 72-168 小时 |
| 金融系统 | 72 小时 | 7x24 小时 |
| 互联网应用 | 12 小时 | 48 小时 |

### 5.3 配置示例

```yaml
稳定性测试配置:
  目标: 验证 24x7 运行能力
  
  负载配置:
    模式: 稳定负载 (峰值50%)
    用户数: 80 (峰值200的40%)
    思考时间: 正常 (3-8秒)
    
  测试时长:
    持续时间: 72小时
    
  监控指标:
    - 24小时内存使用趋势
    - 连接池使用情况
    - GC 频率和耗时
    - 错误率趋势
    - TPS 稳定性
    
  验收标准:
    - 无内存泄漏
    - 无连接泄漏
    - 错误率 < 0.1%
    - TPS 无明显下降
    - 响应时间无明显增长
```

### 5.4 稳定性测试监控点

```
关键指标监控:

1. 内存监控
   ├── Heap Memory 使用趋势
   ├── Old Gen 使用率 (< 80%)
   ├── Full GC 频率 (< 3次/小时)
   └── Metaspace 使用率

2. 连接池监控
   ├── 数据库连接活跃数
   ├── 连接等待时间
   ├── Redis 连接数
   └── HTTP 连接池状态

3. 业务指标
   ├── TPS 稳定性 (波动 < 10%)
   ├── 响应时间趋势 (无持续上升)
   ├── 错误率趋势 (无持续上升)
   └── 成功率 (始终 > 99.9%)
```

## 6. 混合场景测试

### 6.1 场景矩阵

```yaml
混合场景测试矩阵:
  
  场景A: 正常业务混合
    用户配比:
      - 普通用户: 70% (浏览、查询)
      - 活跃用户: 20% (下单、评论)
      - 管理员: 10% (审核、配置)
      
  场景B: 业务高峰期
    用户配比:
      - 抢购用户: 30% (高并发下单)
      - 普通用户: 50%
      - 查询用户: 20%
      
  场景C: 数据处理场景
    用户配比:
      - 数据导入: 10%
      - 批量查询: 40%
      - 报表生成: 30%
      - 常规操作: 20%
```

### 6.2 JMeter 多线程组配置

```xml
<TestPlan>
  <!-- 普通用户场景 -->
  <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Normal Users">
    <stringProp name="ThreadGroup.num_threads">70</stringProp>
    <stringProp name="ThreadGroup.ramp_time">60</stringProp>
    <stringProp name="ThreadGroup.duration">3600</stringProp>
  </ThreadGroup>
  
  <!-- 活跃用户场景 -->
  <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Active Users">
    <stringProp name="ThreadGroup.num_threads">20</stringProp>
    <stringProp name="ThreadGroup.ramp_time">30</stringProp>
    <stringProp name="ThreadGroup.duration">3600</stringProp>
  </ThreadGroup>
  
  <!-- 管理员场景 -->
  <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Admin Users">
    <stringProp name="ThreadGroup.num_threads">10</stringProp>
    <stringProp name="ThreadGroup.ramp_time">60</stringProp>
    <stringProp name="ThreadGroup.duration">3600</stringProp>
  </ThreadGroup>
</TestPlan>
```

## 7. 场景执行策略

### 7.1 执行顺序

```
推荐执行顺序:
1. 单业务基准测试 (Baseline)
2. 单用户基准测试 (Single User)
3. 预期负载测试 (Expected Load)
4. 峰值负载测试 (Peak Load)
5. 压力测试 (Stress Test)
6. 稳定性测试 (Stability Test)
7. 混合场景测试 (Mixed Scenario)
```

### 7.2 环境要求

| 测试类型 | 环境要求 | 数据量要求 |
|----------|----------|------------|
| 基准测试 | 可用测试环境 | 少量测试数据 |
| 负载测试 | 接近生产环境 | 10%生产数据量 |
| 压力测试 | 可用测试环境 | 10%生产数据量 |
| 稳定性测试 | 隔离环境 | 完整测试数据集 |

### 7.3 数据准备

```yaml
测试数据准备:
  
  数据量要求:
    - 用户数据: > 10000条
    - 订单数据: > 100000条
    - 商品数据: > 50000条
    
  数据质量:
    - 数据分布符合真实场景
    - 包含边界值和异常数据
    - 准备数据隔离策略
    
  数据刷新:
    - 每次大测试前刷新数据
    - 记录数据快照
    - 确保测试可重复
```

---

*相关文档：[JMeter 高级用法](./jmeter-advanced-usage.md)*  
*返回：[QA 性能测试知识库索引](../index.md)*
