# 性能测试踩坑记录

> 作者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29

## 1. 测试设计类问题

### 1.1 场景设计问题

**坑1: 测试场景与实际业务不符**

```yaml
问题描述:
测试时使用均匀的TPS分布，但实际业务有明显的峰值谷值

错误做法:
- JMeter固定Ramp-Up时间
- 所有时间段使用相同并发数
- 忽略业务高峰时段

后果:
- 无法发现真实的性能问题
- 资源评估不准确
- 压测结果与生产实际差距大

正确做法:
# 1. 分析业务模型，设计真实业务场景
# 业务高峰通常在:
# - 工作日9:00-11:00, 14:00-17:00
# - 活动期间整点秒杀
# - 周末全天较为平稳

# 2. 使用真实业务配比
业务配比:
├── 浏览: 60% (低压力)
├── 下单: 20% (中等)
└── 支付: 20% (高压力)
```

**坑2: 忽视思考时间**

```yaml
问题描述:
测试时没有添加用户思考时间，导致并发数虚高

错误配置:
Thread Group:
  Number of Threads: 1000
  Ramp-Up Period: 0
  Loop Count: 1000
  Think Time: 0 ❌

后果:
- 并发数远超实际
- TPS远超实际
- 测试结果不可用

正确配置:
Thread Group:
  Number of Threads: 200
  Ramp-Up Period: 30
  Loop Count: Forever
  Duration: 3600
  Think Time: 3-8秒 (使用Uniform Random Timer)

业务思考时间参考:
├── 快速操作(点赞): 1-3秒
├── 普通浏览: 3-8秒
├── 复杂操作(下单): 5-15秒
└── 批量操作: 0秒
```

### 1.2 数据准备问题

**坑3: 测试数据量不足**

```yaml
问题描述:
测试数据库只有少量数据，无法真实模拟生产环境

错误情况:
- 用户表: 100条
- 商品表: 1000条
- 订单表: 10000条

实际生产:
- 用户表: 100万条
- 商品表: 500万条
- 订单表: 1亿条

后果:
- 索引失效，全表扫描
- 缓存效果无法验证
- 性能测试结果过于乐观

正确做法:
# 1. 准备足够的测试数据
# 通常要求:
# - 数据量 >= 10%生产数据量
# - 覆盖边界值和异常数据
# - 保持数据分布与生产一致

# 2. 每次测试前刷新数据
# 确保测试可重复
```

**坑4: 数据关联未考虑**

```yaml
问题描述:
测试时使用了不存在的数据关联

错误场景:
1. 查询订单，用户ID使用了不存在的ID
2. 更新商品，商品ID全部随机
3. 支付订单，订单状态错误

后果:
- 接口返回404/500错误
- 测试成功率虚低
- 无法测试完整业务流程

正确做法:
# 1. 先登录获取有效的用户token
# 2. 查询列表获取有效的ID
# 3. 关联提取关键数据
# 4. 按正确顺序执行业务流程
```

## 2. 工具使用类问题

### 2.1 JMeter配置问题

**坑5: 监听器保存过多数据**

```yaml
问题描述:
JMeter运行中开启多个监听器，保存大量响应数据

错误配置:
├── View Results Tree ✓ 开启 ❌
├── Save Response Data ✓ 开启 ❌
├── Save Sampler Data ✓ 开启 ❌
└── Aggregate Report ✓ 开启

后果:
- JMeter占用大量内存
- GC频繁
- 测试过程中卡顿
- 甚至导致OOM

正确配置:
# 1. 仅保留必要的监听器
View Results Tree: ✗ (关闭，或仅记录错误)
Save Response: ✗
Save Sampler: ✗
Aggregate Report: ✓ (轻量)

# 2. 使用命令行模式运行
jmeter -n -t test.jmx -l results.jtl -e -o report

# 3. 仅记录统计信息
保存配置:
- 响应状态: ✓
- 响应时间: ✓
- 响应数据: ✗
- 请求数据: ✗
```

**坑6: 参数化配置错误**

```yaml
问题描述:
CSV数据文件配置不当导致参数为空或错误

错误配置:
CSV Data Set Config:
  delimiter: ;
  Recycle: true
  Stop Thread: false
  variableNames: userId,token ❌ (顺序错误)

后果:
- 参数提取失败
- 关联失败
- 业务逻辑错误

正确配置:
CSV Data Set Config:
  delimiter: ,
  ignoreFirstLine: true (如果有表头)
  Recycle: false (数据只用一次)
  Stop Thread: true (用完停止)
  variableNames: username,password,userId (与CSV列顺序一致)

# CSV文件内容:
username,password,userId
user001,pass123,10001
user002,pass456,10002
```

### 2.2 关联问题

**坑7: 正则表达式匹配失败**

```yaml
问题描述:
正则提取器匹配不到响应数据

错误正则:
正则: "token"\s*:"(.+)"
响应: {"token":"abc123"} ✓ 可能匹配
响应: {token:"abc123"} ✗ 不匹配(无引号)

后果:
- 变量为空
- 后续请求失败
- 成功率下降

正确做法:
# 1. 先查看实际响应格式
# 使用View Results Tree查看

# 2. 使用更通用的正则
# JSON: "token"\s*:\s*"([^"]+)"
# HTML: name="token"[^>]*value="([^"]+)"
# 通用: token[=:]\s*"?([^",}\s]+)

# 3. 优先使用JSON Extractor
JSON Extractor:
  jsonPathExpr: $.data.token
  matchNumber: 1
  defaultValue: NOT_FOUND
```

**坑8: 关联变量作用域错误**

```yaml
问题描述:
提取的变量在后续请求中无法使用

错误结构:
Thread Group
├── Login Request
│   └── JSON Extractor: sessionToken ✓
├── Category A
│   ├── Request 1: ${sessionToken} ✓
│   └── Request 2: ${sessionToken} ✓
└── Category B
    └── Request 3: ${sessionToken} ✗ (无法获取)

原因:
- 变量在子线程组中定义
- 或者线程组配置了错误的作用域

正确做法:
# 1. 将公共变量提取放到顶层
Test Plan
├── User Defined Variables (全局变量)
└── Thread Group
    └── ...

# 2. 或者使用正确的作用域
# JMeter变量默认在线程组内有效

# 3. 检查变量是否为空
Debug Sampler:
  ${sessionToken} = abc123 ✓
  ${sessionToken} = ${sessionToken} ✗ (未提取)
```

## 3. 环境问题

### 3.1 网络环境问题

**坑9: 压测机带宽不足**

```yaml
问题描述:
压测机网络带宽成为瓶颈，测试结果不准确

现象:
- JMeter TPS上不去
- 响应时间分布异常
- JMeter机器CPU/内存使用率低

诊断:
# 查看网络带宽使用
vmstat 1
sar -n DEV 1

后果:
- TPS被人为限制
- 无法压出真实性能
- 资源评估错误

解决方案:
# 1. 使用多台压测机分布式压测
Master: 192.168.1.100
Slave1: 192.168.1.101
Slave2: 192.168.1.102

# 2. JMeter分布式配置
# jmeter.properties:
remote_hosts=192.168.1.101,192.168.1.102

# 3. 启动分布式
jmeter -n -t test.jmx -r

# 4. 或使用云压测服务
```

**坑10: DNS解析问题**

```yaml
问题描述:
压测时使用域名，导致DNS解析开销计入响应时间

错误配置:
HTTPSamplerProxy:
  domain: api.example.com ❌
  protocol: https

正确配置:
# 方案1: 使用IP直接访问
HTTPSamplerProxy:
  domain: 192.168.1.101
  protocol: http

# 方案2: 如果必须用域名，添加DNS缓存
# JMeter启动参数:
java -Djava.net.preferIPv4Stack=true

# 方案3: 在hosts文件中配置
/etc/hosts:
192.168.1.101 api.example.com
```

### 3.2 测试环境问题

**坑11: 测试环境不稳定**

```yaml
问题描述:
测试环境与其他任务共用，导致测试结果波动

现象:
- TPS忽高忽低
- 响应时间分布不规则
- 错误率不稳定

诊断:
# 1. 检查环境共用情况
# 2. 查看其他任务的影响
# 3. 监控服务器资源

后果:
- 测试结果不可信
- 无法定位真正问题
- 需要反复测试

正确做法:
# 1. 使用隔离的测试环境
# 2. 记录环境状态快照
# 3. 测试前确认环境干净
# 4. 设置环境检查点
```

## 4. 分析类问题

### 4.1 结果分析问题

**坑12: 只看平均响应时间**

```yaml
问题描述:
只关注平均值，忽视分位数和分布

错误分析:
✓ 平均响应时间: 150ms
✗ 但实际上...
✗ P99: 5000ms
✗ P99.9: 10000ms
✗ 有1%的用户等了10秒!

后果:
- 用户体验差的请求被忽视
- 长尾问题未发现
- SLA可能不达标

正确分析:
# 必须查看多维度指标:
├── 平均响应时间 (ART)
├── 中位数 (Median)
├── P50/P90/P95/P99/P99.9
├── 最小值/最大值
├── 标准差
└── 错误率

# JMeter聚合报告示例:
Label        Samples   Average   Median   90%   95%   99%   Min   Max   Error%
/api/list    100000    150ms     100ms   200ms 300ms 500ms  50ms  10s   0.5%
```

**坑13: TPS高就是好**

```yaml
问题描述:
只追求TPS数字，不关注业务正确性

错误认知:
✓ TPS达到5000 ✗ 但实际上...
✗ 错误率5%
✗ 很多请求返回500错误
✗ 业务根本没成功!

后果:
- 压出的是无效TPS
- 系统状态可能已异常
- 误导性能评估

正确认知:
# 有效TPS才是真正的性能指标
有效TPS = TPS × (1 - 错误率)

# 验证业务正确性:
# 1. 检查数据库状态
# 2. 验证数据一致性
# 3. 确认业务流程完整
# 4. 对比压测前后数据
```

### 4.2 瓶颈定位问题

**坑14: 瓶颈定位方向错误**

```yaml
问题描述:
发现性能问题后，盲目优化非瓶颈点

错误案例:
现象: 响应时间从100ms上升到500ms
错误排查:
✗ 增加JVM堆内存 - 无效
✗ 升级Redis配置 - 无效
✗ 扩容服务器 - 无效

正确排查:
# 1. 确定瓶颈在哪一层
top / htop                    # CPU?
free -m                       # 内存?
iostat -x 1                   # IO?
netstat -an | grep ESTABLISHED  # 连接?

# 2. 分层定位
应用层: jstack, Arthas
数据库层: show processlist, EXPLAIN
缓存层: Redis MONITOR, INFO stats
系统层: vmstat, iostat, netstat

# 3. 使用APM工具
SkyWalking, Pinpoint, Jaeger
```

## 5. 常见误区总结

### 5.1 认知误区

```yaml
误区1: 压测环境越接近生产越好
真相: 压测环境可以适当简化，关键是数据量和业务模型

误区2: TPS越高越好
真相: TPS必须结合成功率，有效TPS才有意义

误区3: 响应时间越短越好
真相: 满足业务需求即可，过度优化是浪费

误区4: 性能测试只需要做一次
真相: 每次重大变更后都需要回归性能测试

误区5: 性能测试是测试人员的事
真相: 性能优化需要开发、运维、测试共同参与
```

### 5.2 行动误区

```yaml
误区1: 测试前不检查环境
→ 每次测试前必须确认环境状态

误区2: 测试后不分析数据
→ 测试数据必须详细分析，才能发现问题

误区3: 发现问题立即优化
→ 先确认问题可复现，再分析根因

误区4: 优化后不验证效果
→ 必须重新测试验证优化效果

误区5: 不记录测试过程
→ 测试过程、结果、问题都要记录，便于复盘
```

---

## 6. 经验总结清单

### 6.1 测试前检查清单

```
□ 测试环境已隔离
□ 测试数据已准备完成
□ JMeter脚本已调试通过
□ 监控工具已部署
□ 相关人员已通知
□ 回滚方案已准备
□ 测试数据已备份
□ 网络延迟已验证
□ 无其他任务占用资源
□ 应急联系人已确认
```

### 6.2 测试中检查清单

```
□ TPS稳定在目标范围
□ 响应时间符合预期
□ 错误率在可接受范围
□ 服务器资源使用正常
□ 数据库连接池正常
□ Redis运行正常
□ 无异常日志
□ 监控数据正常采集
□ 关键业务指标正常
□ 每隔30分钟检查状态
```

### 6.3 测试后检查清单

```
□ 保存完整的测试数据
□ 生成测试报告
□ 对比性能基线
□ 分析异常情况
□ 记录问题和建议
□ 清理测试环境
□ 通知相关人员
□ 归档测试脚本和配置
□ 更新性能测试文档
□ 制定优化计划
```

---

*相关文档：[性能测试场景设计](../patterns/qa/performance/performance-test-scenario-design.md)*  
*返回：[QA 知识库索引](../index.md)*
