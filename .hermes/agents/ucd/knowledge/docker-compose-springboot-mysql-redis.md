# Docker Compose 编排 Spring Boot + MySQL + Redis

## 概述

本文档介绍如何使用 Docker Compose 编排完整的微服务运行环境，包括 Spring Boot 应用、MySQL 数据库和 Redis 缓存。

## 1. 基础 Docker Compose 配置

### 1.1 完整 docker-compose.yml

```yaml
version: '3.8'

services:
  # ============ MySQL 数据库 ============
  mysql:
    image: mysql:8.0
    container_name: myapp-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-Root@123456}
      MYSQL_DATABASE: myapp
      MYSQL_USER: myapp
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-MyApp@123456}
      TZ: Asia/Shanghai
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./mysql/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-authentication-plugin=mysql_native_password
      - --lower_case_table_names=1
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend
    mem_limit: 1024m

  # ============ Redis 缓存 ============
  redis:
    image: redis:7-alpine
    container_name: myapp-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: redis-server /usr/local/etc/redis/redis.conf
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - backend
    mem_limit: 512m

  # ============ Spring Boot 应用 ============
  app:
    build:
      context: ./app
      dockerfile: Dockerfile
    container_name: myapp-api
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      SPRING_PROFILES_ACTIVE: prod
      SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/myapp?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=Asia/Shanghai
      SPRING_DATASOURCE_USERNAME: myapp
      SPRING_DATASOURCE_PASSWORD: ${MYSQL_PASSWORD:-MyApp@123456}
      SPRING_REDIS_HOST: redis
      SPRING_REDIS_PORT: 6379
      JAVA_OPTS: "-Xms512m -Xmx1024m -XX:+UseG1GC"
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8080/actuator/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - backend
    volumes:
      - app_logs:/app/logs
    mem_limit: 1g

# ============ 网络配置 ============
networks:
  backend:
    driver: bridge

# ============ 持久化卷 ============
volumes:
  mysql_data:
    driver: local
  redis_data:
    driver: local
  app_logs:
    driver: local
```

## 2. MySQL 初始化脚本

```sql
-- init.sql
CREATE DATABASE IF NOT EXISTS myapp DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE myapp;

CREATE USER IF NOT EXISTS 'myapp'@'%' IDENTIFIED BY 'MyApp@123456';
GRANT ALL PRIVILEGES ON myapp.* TO 'myapp'@'%';
FLUSH PRIVILEGES;

CREATE TABLE IF NOT EXISTS `sys_user` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `username` VARCHAR(50) NOT NULL COMMENT '用户名',
    `password` VARCHAR(100) NOT NULL COMMENT '密码',
    `nickname` VARCHAR(50) DEFAULT NULL COMMENT '昵称',
    `status` TINYINT DEFAULT 1 COMMENT '状态',
    `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统用户表';
```

## 3. Redis 配置

```conf
# redis.conf
bind 0.0.0.0
port 6379
appendonly yes
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## 4. 常用命令

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app

# 进入 MySQL
docker-compose exec mysql mysql -uroot -p

# 进入 Redis
docker-compose exec redis redis-cli

# 停止服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

## 5. 生产环境注意事项

- [ ] 修改默认密码
- [ ] 生产环境启用 SSL
- [ ] 配置 Redis 密码认证
- [ ] 限制 MySQL 外部访问
- [ ] 使用 Docker Secrets 管理敏感信息
