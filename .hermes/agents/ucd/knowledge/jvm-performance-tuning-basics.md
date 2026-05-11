# JVM 性能调优基础

> 作者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29

## 1. JVM 内存模型

### 1.1 堆内存结构

```
JVM 堆内存结构 (JDK 8+):

┌─────────────────────────────────────────────────────────┐
│                      Heap 堆内存                         │
├─────────────────────────────┬───────────────────────────┤
│         New Generation      │      Old Generation       │
│    ┌──────────┬─────────┐   │                           │
│    │  Eden    │ S0 S1   │   │      Tenured Space         │
│    │  Space   │(Survivor)│   │                           │
│    └──────────┴─────────┘   │                           │
│         1/3                 │         2/3                │
└─────────────────────────────┴───────────────────────────┘

Eden Space:  新生代伊甸园区，新对象分配区域
S0/S1:      Survivor From/To，存活对象轮换区
Tenured:    老年代，长期存活对象存储区
```

### 1.2 各区域详解

| 区域 | 大小比例 | 作用 | GC频率 |
|------|----------|------|--------|
| Eden | 1/3堆 | 新对象分配 | 高 |
| Survivor | 1/3堆 | 存活对象过渡 | 高 |
| Old Gen | 2/3堆 | 长期存活对象 | 低 |
| Metaspace | 动态 | 类元数据存储 | 极低 |

### 1.3 堆内存配置示例

```bash
# 常用堆内存配置
-Xms4g              # 初始堆大小 4GB
-Xmx4g              # 最大堆大小 4GB
-Xmn2g              # 新生代大小 2GB
-XX:MetaspaceSize=256m   # 元空间初始大小
-XX:MaxMetaspaceSize=512m # 元空间最大大小

# Survivor 比例配置
-XX:SurvivorRatio=8      # Eden:S0:S1 = 8:1:1 (默认8)

# 老年代比例配置
-XX:NewRatio=2           # 老年代:新生代 = 2:1
```

## 2. 垃圾回收（GC）机制

### 2.1 GC 分类

```
GC 类型:

┌─────────────────────────────────────────────────────┐
│                    Young GC (Minor GC)              │
│   频率: 高 (每分钟几次到几十次)                      │
│   范围: Eden + Survivor                            │
│   停顿: 短 (< 100ms)                               │
│   触发: Eden区满                                    │
├─────────────────────────────────────────────────────┤
│                    Old GC (Major GC)               │
│   频率: 低 (几小时到几天一次)                        │
│   范围: Old区                                       │
│   停顿: 中等 (100ms ~ 1s)                           │
│   触发: Old区空间不足                               │
├─────────────────────────────────────────────────────┤
│                    Full GC                          │
│   频率: 低                                         │
│   范围: 全部堆 + Metaspace                          │
│   停顿: 长 (> 1s, 可能数秒)                         │
│   触发: 多种条件触发                                │
└─────────────────────────────────────────────────────┘
```

### 2.2 垃圾回收器

```bash
# 1. Serial GC (单线程，适用于小内存)
-XX:+UseSerialGC

# 2. Parallel GC (并行GC，多线程，默认JDK8)
-XX:+UseParallelGC

# 3. CMS GC (并发标记清除，已废弃)
-XX:+UseConcMarkSweepGC

# 4. G1 GC (JDK 9+默认，推荐使用)
-XX:+UseG1GC

# 5. ZGC (低延迟，大内存场景)
-XX:+UseZGC

# 6. Shenandoah (低延迟)
-XX:+UseShenandoahGC
```

### 2.3 G1 GC 配置与调优

```bash
# G1 GC 完整配置
-Xms8g                    # 初始堆
-Xmx8g                    # 最大堆
-XX:+UseG1GC              # 使用G1

# 目标停顿时间
-XX:MaxGCPauseMillis=200  # 最大GC停顿目标 200ms

# Region大小
-XX:G1HeapRegionSize=4m   # Region大小 4MB

# GC阈值
-XX:InitiatingHeapOccupancyPercent=45  # 老年代使用率45%时开始并发GC

# 并行线程数
-XX:ParallelGCThreads=8    # 并行GC线程数
-XX:ConcGCThreads=4        # 并发GC线程数
```

## 3. GC 日志分析

### 3.1 GC 日志配置

```bash
# 开启GC日志
-XX:+PrintGCDetails              # 详细GC日志
-XX:+PrintGCDateStamps           # 日期时间戳
-Xloggc:/var/log/gc.log          # GC日志文件
-XX:+UseGCLogFileRotation         # 日志轮转
-XX:NumberOfGCLogFiles=5          # 日志文件数量
-XX:GCLogFileSize=10M             # 单个日志文件大小

# 示例配置
java -Xms4g -Xmx4g \
    -XX:+UseG1GC \
    -XX:MaxGCPauseMillis=200 \
    -XX:+PrintGCDetails \
    -XX:+PrintGCDateStamps \
    -Xloggc:/var/log/app-gc.log \
    -jar app.jar
```

### 3.2 GC 日志解读

```
GC日志示例:

2026-04-29T10:15:23.456+0800: [GC (Allocation Failure) 
  [PSYoungGen: 524288K->32768K(6291456K)] 
  524288K->32768K(8378368K), 
  0.0456789 secs] 
  [Times: user=0.12 sys=0.01, real=0.05 secs]

解析:
- Allocation Failure: GC触发原因（Eden区满）
- PSYoungGen: Parallel Scavenge 新生代
- 524288K->32768K: GC前后使用量
- (6291456K): 新生代总大小
- 0.0456789 secs: GC耗时
- user=0.12: 用户态CPU时间
- real=0.05: 实际墙钟时间
```

### 3.3 Full GC 日志分析

```
Full GC 日志示例:

2026-04-29T10:20:30.123+0800: [Full GC (Allocation Failure) 
  [CMS: 2097152K->1845496K(4194304K), 
  2.5678901 secs] 
  4194304K->1845496K(8378368K), 
  [Metaspace: 98765K->98765K(131072K)], 
  2.5678901 secs] 
  [Times: user=5.12 sys=0.23, real=2.57 secs]

关键指标:
- Old区: 2GB -> 1.8GB (回收了约200MB)
- Metaspace: 约100MB，稳定
- Full GC耗时: 2.57秒 (较长，需要优化)
```

## 4. GC 性能监控

### 4.1 jstat 命令

```bash
# 查看GC统计
jstat -gcutil <pid> 1000

# 输出:
S0     S1     E      O      M     YGC     YGCT    FGC    FGCT     GCT
0.00  65.42  45.23  78.56  92.34  1234   45.67  567    123.45  169.12

字段说明:
S0/S1: Survivor区使用率 (%)
E:      Eden区使用率 (%)
O:      Old区使用率 (%) ← 重点关注，超过80%需注意
M:      Metaspace使用率 (%)
YGC:    Young GC次数
YGCT:   Young GC总耗时 (秒)
FGC:    Full GC次数
FGCT:   Full GC总耗时 (秒)
GCT:    总GC耗时 (秒)

# 查看年轻代统计
jstat -gcnew <pid> 1000

# 查看老年代统计
jstat -gcold <pid> 1000
```

### 4.2 GC 健康标准

```yaml
GC健康检查标准:

指标                    | 健康值        | 警告值        | 危险值
------------------------|---------------|---------------|---------------
Old区使用率            | < 70%         | 70-85%        | > 85%
Full GC频率            | < 3次/小时    | 3-10次/小时   | > 10次/小时
Full GC耗时            | < 1秒        | 1-3秒         | > 3秒
Young GC耗时           | < 50ms       | 50-100ms      | > 100ms
GC总耗时占比           | < 5%         | 5-10%         | > 10%
元空间使用率           | < 80%        | 80-90%        | > 90%
```

## 5. 常见性能问题与解决方案

### 5.1 内存泄漏

```
问题现象:
- 内存使用率持续上升
- Full GC后内存不下降
- 堆内存逐渐耗尽

排查方法:
1. 查看对象内存占用
   jmap -histo <pid> | head -30
   
2. 导出堆内存快照
   jmap -dump:format=b,file=heap.hprof <pid>
   
3. 使用MAT分析堆转储
   分析Dominator Tree找出内存大户

常见原因:
- 静态集合类未清理
- 未关闭的资源（连接、流）
- 监听器未注销
- 缓存无限制增长
```

### 5.2 内存溢出 (OOM)

```
问题现象:
- 应用崩溃
- 日志出现 OutOfMemoryError
- 容器重启

OOM类型与原因:

┌─────────────────┬──────────────────────────────────┐
│ Java heap space │ 堆内存不足，GC后仍不够             │
├─────────────────┼──────────────────────────────────┤
│ GC overhead     │ GC消耗超过98%仍无法释放内存        │
├─────────────────┼──────────────────────────────────┤
│ Metaspace       │ 元空间不足，类加载过多             │
├─────────────────┼──────────────────────────────────┤
│ Direct buffer   │ 直接内存不足(NIO使用)             │
├─────────────────┼──────────────────────────────────┤
│ Unable to create│ 线程数超过限制                     │
│ new native thread│                                  │
└─────────────────┴──────────────────────────────────┘

解决方案:
- 增大堆内存: -Xmx
- 优化代码，减少对象创建
- 检查内存泄漏
- 限制元空间大小: -XX:MaxMetaspaceSize
```

### 5.3 GC 频繁

```
问题现象:
- Young GC频率极高（每秒几次）
- Full GC频繁（每小时几十次）
- 响应时间周期性波动

排查方法:
1. 分析GC日志，找出发起原因
2. 检查对象分配率
3. 检查Survivor区是否太小

解决方案:

# 方案1: 增大堆内存
-Xms4g -Xmx4g → -Xms8g -Xmx8g

# 方案2: 增大Survivor区
-XX:SurvivorRatio=8 → -XX:SurvivorRatio=4

# 方案3: 调整对象年龄阈值
-XX:MaxTenuringThreshold=15 → -XX:MaxTenuringThreshold=5

# 方案4: 使用G1 GC
-XX:+UseG1GC -XX:MaxGCPauseMillis=200
```

## 6. JVM 性能监控工具

### 6.1 命令行工具

```bash
# 1. jps - 查看Java进程
jps -lm

# 2. jinfo - 查看/修改JVM参数
jinfo -flags <pid>          # 查看所有参数
jinfo -flag MaxHeapFreeRatio <pid>  # 查看单个参数

# 3. jmap - 内存分析
jmap -heap <pid>            # 堆内存概况
jmap -histo <pid>           # 对象统计
jmap -dump:format=b,file=xxx.hprof <pid>  # 堆转储

# 4. jstack - 线程堆栈
jstack <pid>                # 线程堆栈
jstack -l <pid>             # 包含锁信息

# 5. jcmd - 多功能命令
jcmd <pid> GC.heap_info     # GC堆信息
jcmd <pid> Thread.print     # 线程信息
```

### 6.2 Arthas 常用命令

```bash
# 1. 启动Arthas
java -jar arthas-boot.jar <pid>

# 2. dashboard - 实时仪表盘
dashboard

# 3. thread - 线程分析
thread                        # 所有线程
thread -n 5                   # CPU最高的5个线程
thread -b                     # 死锁线程

# 4. jvm - JVM信息
jvm

# 5. gc - GC分析
gc                            # GC统计
```

### 6.3 推荐监控方案

```yaml
监控体系:

1. 轻量级监控
   ├── jstat + shell脚本定时采集
   ├── 日志文件监控
   └── 简单但有效

2. Arthas在线诊断
   ├── 实时分析
   ├── 热更新
   └── 生产环境可用

3. 专业APM工具
   ├── SkyWalking (推荐国产)
   ├── Pinpoint
   ├── Jaeger
   └── 全链路追踪

4. 商业监控
   ├── Alibaba Arthas Cloud
   ├── 阿里云JVM监控
   └── Prometheus + Grafana
```

## 7. JVM 调优最佳实践

### 7.1 调优步骤

```
JVM调优流程:

1. 基准测试
   ├─ 确定性能基线
   ├─ 记录当前JVM参数
   └─ 确定优化目标

2. 监控收集
   ├─ 开启GC日志
   ├─ 监控内存使用
   └─ 记录GC频率和耗时

3. 分析问题
   ├─ 识别问题类型
   ├─ 确定优化方向
   └─ 制定调优策略

4. 参数调整
   ├─ 小幅调整
   ├─ 多次迭代
   └─ 记录变化

5. 验证效果
   ├─ 对比优化前后
   ├─ 稳定性测试
   └─ 回归测试
```

### 7.2 推荐配置

```bash
# Spring Boot 应用推荐配置
JAVA_OPTS="
  -server
  -Xms4g -Xmx4g                    # 堆内存
  -Xmn2g                           # 新生代
  -XX:MetaspaceSize=256m
  -XX:MaxMetaspaceSize=512m
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=200
  -XX:InitiatingHeapOccupancyPercent=45
  -XX:+HeapDumpOnOutOfMemoryError
  -XX:HeapDumpPath=/var/log/heap.hprof
  -Xlog:gc*:file=/var/log/gc.log:time:filecount=5,filesize=10M
  -XX:+UseStringDeduplication
"
```

### 7.3 容器环境配置

```bash
# Kubernetes 环境配置
env:
  - name: JAVA_OPTS
    value: >-
      -Xms2g -Xmx2g
      -XX:+UseG1GC
      -XX:MaxGCPauseMillis=200
      -XX:InitiatingHeapOccupancyPercent=45
      -XX:+UseContainerSupport
      -XX:MaxRAMPercentage=75.0
      
# 容器资源限制
resources:
  limits:
    memory: "4Gi"
    cpu: "2"
  requests:
    memory: "2Gi"
    cpu: "1"
```

---

*相关文档：[性能测试报告分析](./performance-test-report-analysis.md)*  
*返回：[QA 性能测试知识库索引](../index.md)*
