---
name: jicai-mall-performance-test
description: 集采商城微服务系统性能测试完整方案，包含JMeter脚本、监控脚本、测试计划模板
category: qa-performance
---

# 集采商城性能测试

## 概述
集采商城B2B微服务系统的完整性能测试方案，基于Spring Cloud微服务架构。

## 项目信息
- 项目路径: `/workspace/projects/jicai-mall-backend`
- 技术栈: Spring Boot 3.x + MySQL 8.0 + Redis + Nacos
- 端口: 网关(8080)、auth(3000)、admin(4000)、mall(5000)、order(6000)、supplier(7000)

## 性能测试目录结构
```
test/performance/
├── 性能测试计划.md           # 测试计划文档
├── jmeter/
│   ├── jicai-mall-test-plan.jmx    # JMeter测试脚本 (7个场景)
│   ├── user.properties             # JMeter配置
│   ├── test-data.csv               # 测试数据
│   ├── product-ids.csv            # 商品ID数据
│   └── search-keywords.csv        # 搜索关键字
├── scripts/
│   ├── run-test.sh                 # 测试执行脚本
│   ├── monitor.sh                  # 监控脚本
│   └── generate-report.sh          # 报告生成脚本
└── report/
    └── 性能测试报告模板.md         # 报告模板
```

## 快速开始

### 1. 执行基准测试
```bash
cd /workspace/projects/jicai-mall-backend/test/performance
./scripts/run-test.sh baseline
```

### 2. 执行负载测试 (50并发10分钟)
```bash
./scripts/run-test.sh load 50 600
```

### 3. 执行压力测试
```bash
./scripts/run-test.sh stress
```

### 4. 监控测试执行
```bash
./scripts/monitor.sh monitor
```

### 5. 生成HTML报告
```bash
./scripts/generate-report.sh dashboard
```

## 测试场景

| 场景 | 线程数 | 持续时间 | 说明 |
|-----|-------|---------|------|
| 场景1 | 1 | 100次 | 基准测试 |
| 场景2 | 50 | 10分钟 | 用户浏览负载测试 |
| 场景3 | 30 | 10分钟 | 交易流程负载测试 |
| 场景4 | 100 | 10分钟 | 高并发下单压力测试 |
| 场景5 | 20 | 10分钟 | 供应商操作场景 |
| 场景6 | 20 | 10分钟 | 管理后台场景 |
| 场景7 | 50 | 8小时 | 稳定性测试 |

## 核心接口

### 商城端
- GET /api/category/list - 分类列表
- GET /api/product/list - 商品列表
- GET /api/product/detail/{id} - 商品详情
- GET /api/product/search - 商品搜索
- POST /api/cart/add - 添加购物车
- GET /api/cart/list - 购物车列表
- POST /api/order/create - 创建订单
- GET /api/order/list - 订单列表

### 认证接口
- POST /api/auth/login - 管理员登录
- POST /api/member/login - 会员登录
- POST /api/supplier/login - 供应商登录

## 测试账号

| 账号 | 密码 | 说明 |
|-----|------|------|
| admin | admin123 | 管理员 |
| test001 | 123456 | 测试会员 |
| SUP001 | 123456 | 测试供应商 |

## 性能指标目标

| 指标 | 目标值 |
|-----|-------|
| 响应时间 | < 2秒 |
| TPS | > 100 |
| CPU | < 80% |
| 内存 | < 80% |
| 错误率 | < 1% |

## JMeter安装检查
```bash
# 检查JMeter
./scripts/run-test.sh check

# 或手动检查
which jmeter || echo "需要安装JMeter"
```
