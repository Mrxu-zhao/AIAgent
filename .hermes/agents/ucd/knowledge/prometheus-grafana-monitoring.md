# Prometheus + Grafana 监控入门

## 概述

本文档介绍如何使用 Prometheus 和 Grafana 构建服务器监控系统。

## 1. Docker Compose 部署

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.47.0
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'

  grafana:
    image: grafana/grafana:10.1.0
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: Admin@123456

  node-exporter:
    image: prom/node-exporter:v1.6.1
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro

volumes:
  prometheus_data:
  grafana_data:
```

## 2. Prometheus 配置

### 2.1 prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Prometheus 自身
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Node Exporter
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # Spring Boot 应用
  - job_name: 'spring-boot-app'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['app:8080']
```

### 2.2 告警规则

```yaml
groups:
  - name: server-alerts
    rules:
      # 服务器离线
      - alert: InstanceDown
        expr: up{job="node"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "服务器 {{ $labels.instance }} 离线"

      # CPU 使用率过高
      - alert: HighCPU
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        annotations:
          summary: "服务器 CPU 使用率超过 80%"

      # 内存使用率过高
      - alert: HighMemory
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 5m
        annotations:
          summary: "服务器内存使用率超过 85%"

      # 磁盘使用率过高
      - alert: HighDisk
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 15
        for: 5m
        annotations:
          summary: "服务器磁盘空间不足"
```

## 3. Spring Boot 集成

### 3.1 添加依赖

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>
    <dependency>
        <groupId>io.micrometer</groupId>
        <artifactId>micrometer-registry-prometheus</artifactId>
    </dependency>
</dependencies>
```

### 3.2 配置

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  metrics:
    tags:
      application: ${spring.application.name}
```

## 4. Grafana 仪表盘

### 4.1 常用查询

```promql
# CPU 使用率
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 内存使用率
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# 磁盘使用率
(node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100

# 网络流量
rate(node_network_receive_bytes_total[5m])

# JVM 堆内存使用
jvm_memory_used_bytes{area="heap"} / jvm_memory_max_bytes{area="heap"} * 100

# HTTP 请求延迟 P99
histogram_quantile(0.99, sum(rate(http_server_requests_seconds_bucket[5m])) by (le, uri))
```

### 4.2 数据源配置

```yaml
# /etc/grafana/provisioning/datasources/datasource.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

## 5. Alertmanager 配置

```yaml
global:
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alertmanager@example.com'

route:
  group_by: ['alertname', 'instance']
  group_wait: 30s
  repeat_interval: 4h
  receiver: 'default-receiver'

receivers:
  - name: 'default-receiver'
    email_configs:
      - to: 'admin@example.com'
        send_resolved: true
```

## 6. 常用命令

```bash
# Prometheus
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml

# 查看 targets
curl http://localhost:9090/api/v1/targets

# 查看告警规则
curl http://localhost:9090/api/v1/rules

# Grafana 重置密码
docker exec grafana grafana-cli admin reset-admin-password Admin@123456
```

## 7. 监控指标说明

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| CPU 使用率 | 系统 CPU 占用 | >80% |
| 内存使用率 | 物理内存占用 | >85% |
| 磁盘使用率 | 磁盘空间占用 | >85% |
| 网络流量 | 网卡收/发速率 | >100MB/s |
| JVM 堆内存 | Java 堆内存使用 | >90% |
| HTTP 延迟 | 请求响应时间 P99 | >2s |
