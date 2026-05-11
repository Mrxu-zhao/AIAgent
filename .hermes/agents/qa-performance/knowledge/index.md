# QA 性能测试知识库

> 维护者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29  
> 版本：v1.0

---

## 知识库概览

本知识库涵盖性能测试工程师需要掌握的核心知识和最佳实践，适用于基于 Java Spring Boot + MySQL + Redis + 华为云 ECS 技术栈的团队。

```
性能测试知识体系:
├── 测试工具
│   └── JMeter 高级用法
├── 测试方法
│   └── 性能测试场景设计
├── 性能分析
│   ├── TPS/响应时间/并发数关系
│   └── 性能测试报告分析
├── 中间件调优
│   ├── JVM 性能调优基础
│   ├── MySQL 慢查询分析
│   └── Redis 性能问题排查
├── 测试模板
│   ├── 性能测试计划模板
│   └── 性能测试报告模板
└── 经验教训
    └── 性能测试踩坑记录
```

---

## 文档目录

### 核心模式 (patterns/qa/performance/)

| 序号 | 文档 | 说明 |
|------|------|------|
| 1 | [JMeter 高级用法](./jmeter-advanced-usage.md) | 参数化、关联、集合点、断言 |
| 2 | [性能测试场景设计](./performance-test-scenario-design.md) | 基准/负载/压力/稳定性测试 |
| 3 | [TPS 响应时间并发数分析](./tps-response-time-concurrency-analysis.md) | 核心指标关系和分析方法 |
| 4 | [性能测试报告分析](./performance-test-report-analysis.md) | 慢接口定位、瓶颈分析方法 |
| 5 | [JVM 性能调优基础](./jvm-performance-tuning-basics.md) | 内存模型、GC 策略、调优方法 |
| 6 | [MySQL 慢查询分析](./mysql-slow-query-analysis.md) | 慢查询日志、执行计划分析 |
| 7 | [Redis 性能问题排查](./redis-performance-troubleshooting.md) | BigKey、HotKey、内存淘汰 |

### 模板 (templates/)

| 序号 | 文档 | 说明 |
|------|------|------|
| 1 | [性能测试计划模板](../templates/performance-test-plan-template.md) | 完整的测试计划文档 |
| 2 | [性能测试报告模板](../templates/performance-test-report-template.md) | 规范的测试报告格式 |

### 踩坑记录 (lessons/)

| 序号 | 文档 | 说明 |
|------|------|------|
| 1 | [性能测试踩坑记录](../lessons/performance-testing-pitfalls.md) | 常见误区和避坑指南 |

---

## 学习路径

### 新人入门 (1-2周)

```
1. 了解 JMeter 基础用法
   └─ jmeter-advanced-usage.md (第1-4章)
   
2. 掌握性能测试场景设计
   └─ performance-test-scenario-design.md (第1-5章)
   
3. 学习性能指标基础知识
   └─ tps-response-time-concurrency-analysis.md (第1-2章)
   
4. 使用模板完成首次测试
   └─ templates/performance-test-plan-template.md
```

### 进阶提升 (1-2月)

```
1. 深入理解瓶颈分析方法
   └─ performance-test-report-analysis.md
   
2. 学习 JVM 调优基础
   └─ jvm-performance-tuning-basics.md
   
3. 掌握数据库性能分析
   └─ mysql-slow-query-analysis.md
   └─ redis-performance-troubleshooting.md
   
4. 复盘常见踩坑经验
   └─ lessons/performance-testing-pitfalls.md
```

### 专家级 (持续学习)

```
1. 深入研究 GC 调优
2. 学习全链路压测
3. 掌握容量规划
4. 学习性能测试自动化
5. 研究 AIOps 智能运维
```

---

## 快速参考

### 常用公式

```yaml
核心公式:
├── TPS = 并发数 / 平均响应时间
├── 响应时间 = 网络时间 + 服务器时间 + 数据库时间
├── 并发用户数 = TPS × 平均响应时间 × 并发因子
└── 有效TPS = TPS × (1 - 错误率)

性能基线:
├── 优秀: 平均RT < 200ms, P99 < 500ms
├── 良好: 平均RT < 500ms, P99 < 1s
├── 可接受: 平均RT < 1s, P99 < 2s
└── 需优化: 平均RT > 1s 或 P99 > 2s
```

### 常用命令

```bash
# JMeter
jmeter -n -t test.jmx -l results.jtl -e -o report  # 无GUI运行
jmeter -g results.jtl -o report                      # 生成HTML报告

# JVM
jstat -gcutil <pid> 1000                             # GC统计
jstack <pid>                                          # 线程堆栈
jmap -dump:format=b,file=heap.hprof <pid>            # 堆转储

# MySQL
EXPLAIN <SQL>                                         # 执行计划
SHOW PROCESSLIST                                     # 连接状态
SHOW INDEX FROM <table>                               # 索引信息

# Redis
redis-cli info stats                                  # 统计信息
redis-cli --bigkeys                                  # 大Key扫描
redis-cli slowlog get 10                             # 慢查询日志
```

---

## 贡献指南

### 新增文档

```yaml
新增文档流程:
1. 在对应目录下创建 .md 文件
2. 遵循文档模板格式
3. 包含必要的配置示例
4. 更新本文档索引
5. 通知团队成员
```

### 文档规范

```yaml
文档格式:
├── 文件名: 使用kebab-case命名
├── 标题: 使用中文，清晰描述
├── 元信息: 包含作者、创建时间
├── 章节: 使用## 和 ### 分级
├── 代码: 使用具体示例
├── 表格: 对比和总结用表格
└── 参考: 标注相关文档链接
```

---

## 更新日志

```yaml
2026-04-29 v1.0 初始版本
├── 新增 7 个核心模式文档
├── 新增 2 个测试模板
├── 新增 1 个踩坑记录
└── 建立性能测试知识库框架
```

---

*返回：[团队知识库索引](../../index.md)*  
*上一版本：[QA 功能测试知识库](../functional/index.md)*  
*下一版本：[运维知识库](../devops/index.md) (规划中)*
