# Docker 部署 Spring Boot 项目实战

## 概述

本文档详细介绍如何使用 Docker 容器化 Spring Boot 项目，涵盖多阶段构建优化、Dockerfile 最佳实践、以及生产环境部署注意事项。

## 1. 多阶段构建 Dockerfile

### 1.1 基础多阶段构建模板

```dockerfile
# ===== Stage 1: Build =====
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /build

# 复制 pom.xml 并下载依赖（利用 Docker 缓存）
COPY pom.xml .
RUN mvn dependency:go-offline -B

# 复制源代码并构建
COPY src ./src
RUN mvn clean package -DskipTests -B

# ===== Stage 2: Runtime =====
FROM eclipse-temurin:21-jre-alpine

# 安全加固：创建非 root 用户
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# 从构建阶段复制 jar 文件
COPY --from=builder /build/target/*.jar app.jar

# 设置文件权限
RUN chown -R appuser:appgroup /app

USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget -q --spider http://localhost:8080/actuator/health || exit 1

# 暴露端口
EXPOSE 8080

# JVM 优化参数
ENV JAVA_OPTS="-Xms512m -Xmx1024m -XX:+UseG1GC -XX:+HeapDumpOnOutOfMemoryError"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
```

### 1.2 构建优化要点

#### 利用 Docker 层缓存

```dockerfile
# 错误的写法：每次代码变更都会重新下载依赖
COPY . .
RUN mvn package

# 正确的写法：分离依赖和代码，利用 Docker 缓存
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn package
```

#### 多架构镜像构建（可选）

```dockerfile
# 使用 buildx 构建多平台镜像
# docker buildx build --platform linux/amd64,linux/arm64 -t myapp:latest .
```

## 2. Spring Boot 特定配置

### 2.1 application-prod.yml 配置

```yaml
server:
  port: 8080
  shutdown: graceful  # 优雅关闭

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
  
  # 生产环境数据源
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
  
  # Redis 配置
  redis:
    lettuce:
      pool:
        max-active: 20
        max-idle: 10
        min-idle: 5

# Actuator 生产环境配置
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
```

### 2.2 JVM 生产环境参数

```bash
# 推荐的生产环境 JVM 参数
JAVA_OPTS="
  -server
  -Xms1024m -Xmx1024m          # 固定堆大小，避免动态调整
  -XX:+UseG1GC                 # G1 垃圾收集器，适合大内存
  -XX:MaxGCPauseMillis=200     # 最大 GC 停顿时间
  -XX:+UseStringDeduplication   # 字符串去重
  -XX:+OptimizeStringConcat    # 优化字符串拼接
  -XX:+PrintGCDetails          # 打印 GC 详情（生产可关闭）
  -XX:+HeapDumpOnOutOfMemoryError
  -XX:HeapDumpPath=/app/logs/heapdump.hprof
  -Djava.security.egd=file:/dev/./urandom  # 加速随机数生成
"
```

## 3. Docker 镜像安全加固

### 3.1 基础镜像选择原则

| 镜像类型 | 推荐 | 说明 |
|---------|------|------|
| 基础镜像 | `eclipse-temurin` | Eclipse 官方维护，完全开源 |
| 标签 | `21-jre-alpine` | 指定具体版本，避免 latest |
| 漏洞扫描 | Trivy/Clair | 定期扫描镜像漏洞 |

### 3.2 安全检查清单

```dockerfile
# 1. 使用非 root 用户
RUN adduser -S appuser -G appgroup
USER appuser

# 2. 只读文件系统（可选）
# 需要预先创建目录并授权
RUN mkdir -p /app/logs /app/config && chown -R appuser:appgroup /app

# 3. 不使用 root 运行
# 4. 最小化安装（Alpine）
# 5. 敏感信息不写入镜像
```

## 4. 日志配置

### 4.1 Docker 日志驱动配置

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5",
    "compress": "true"
  }
}
```

### 4.2 Spring Boot 日志输出到 Docker

```yaml
# application.yml
logging:
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"
  level:
    root: INFO
    com.yourcompany: DEBUG
```

## 5. 构建和运行命令

```bash
# 构建镜像
docker build -t myapp:1.0.0 .

# 运行容器
docker run -d \
  --name myapp \
  -p 8080:8080 \
  -v /data/myapp/logs:/app/logs \
  -v /data/myapp/config:/app/config:ro \
  -e SPRING_PROFILES_ACTIVE=prod \
  -e JAVA_OPTS="-Xms512m -Xmx1024m" \
  --restart unless-stopped \
  --memory=1g \
  --memory-swap=2g \
  --cpus=1 \
  myapp:1.0.0

# 查看日志
docker logs -f --tail=100 myapp

# 进入容器调试
docker exec -it myapp sh
```

## 6. 生产环境检查清单

- [ ] 使用多阶段构建减小镜像体积
- [ ] 指定具体的基础镜像版本（非 latest）
- [ ] 运行非 root 用户
- [ ] 配置健康检查（HEALTHCHECK）
- [ ] 设置资源限制（--memory, --cpus）
- [ ] 配置日志轮转（max-size, max-file）
- [ ] 使用 volume 挂载配置文件和日志目录
- [ ] 设置重启策略（--restart unless-stopped）
- [ ] 配置优雅关闭（spring.lifecycle.timeout-per-shutdown-phase）
- [ ] 开启 Actuator 健康检查端点

## 7. 常见问题

### Q1: 镜像体积太大
**解决方案**：使用多阶段构建 + Alpine 基础镜像，最终镜像可控制在 150MB 以内。

### Q2: 容器启动失败
**排查步骤**：
```bash
docker logs myapp
docker inspect myapp
docker run -it --rm myapp:tag sh  # 交互式调试
```

### Q3: 内存溢出
**排查步骤**：
```bash
docker stats myapp
docker exec myapp jcmd
docker exec myapp jmap -heap
```
