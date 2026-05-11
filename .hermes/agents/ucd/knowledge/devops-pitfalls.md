# DevOps 踩坑记录

## 概述

本文档记录运维实践中遇到的常见问题及解决方案。

## 1. Docker 相关问题

### 1.1 容器无法启动：No such image

**问题现象**：`Error: No such image: myapp:latest`

**解决方案**：
```bash
# 重新构建镜像
docker build -t myapp:1.0.0 .

# 推送镜像
docker push registry/mycompany/myapp:1.0.0

# 在服务器拉取
docker pull registry/mycompany/myapp:1.0.0
```

### 1.2 端口已被占用

**问题现象**：`Bind for 0.0.0.0:8080 failed: port is already allocated`

**解决方案**：
```bash
# 查看端口占用
lsof -i:8080

# 停止旧容器
docker stop <container_id>
docker rm <container_id>
```

### 1.3 Docker 磁盘空间不足

**问题现象**：`no space left on device`

**解决方案**：
```bash
# 清理未使用的资源
docker system prune -a

# 清理构建缓存
docker builder prune -a

# 清理日志
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### 1.4 容器内存溢出（OOMKilled）

**问题现象**：`Killed`

**解决方案**：
```bash
# 增加内存限制
docker run -d --memory=2g myapp:latest

# 调整 JVM 堆内存
docker run -d -e JAVA_OPTS="-Xmx768m" --memory=1g myapp:latest
```

## 2. MySQL 相关问题

### 2.1 连接被拒绝

**问题现象**：`Connection refused: mysql:3306`

**解决方案**：
```bash
# 检查 MySQL 状态
docker ps | grep mysql

# 检查网络连通性
docker exec app ping mysql

# 检查用户权限
docker exec -it mysql mysql -uroot -p
mysql> SHOW GRANTS FOR 'myapp'@'%';
```

### 2.2 时区问题

**问题现象**：数据库记录时间与实际时间差 8 小时

**解决方案**：
```yaml
mysql:
  environment:
    TZ: Asia/Shanghai
  command:
    - --default-time-zone=+08:00
```

### 2.3 字符集乱码

**问题现象**：中文显示为问号或乱码

**解决方案**：
```yaml
mysql:
  command:
    - --character-set-server=utf8mb4
    - --collation-server=utf8mb4_unicode_ci
```
或 JDBC 连接字符串添加：`characterEncoding=utf8`

## 3. Redis 相关问题

### 3.1 连接失败

**问题现象**：`Redis connection refused`

**解决方案**：
```bash
# 检查 Redis 状态
docker ps | grep redis
docker exec redis redis-cli ping

# 检查网络
docker exec app ping redis
```

### 3.2 内存不足导致写入失败

**问题现象**：`OOM command not allowed when used memory`

**解决方案**：
```conf
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## 4. Nginx 相关问题

### 4.1 502 Bad Gateway

**问题现象**：访问返回 502 错误

**解决方案**：
```bash
# 检查后端服务
docker ps | grep app
curl http://localhost:8080/actuator/health

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log
```

### 4.2 upstream timed out

**问题现象**：`upstream timed out (110: Connection timed out)`

**解决方案**：
```nginx
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
```

## 5. JVM 相关问题

### 5.1 堆内存设置过大

**问题现象**：`Could not reserve enough space for 2097152KB object heap`

**解决方案**：确保 JVM 堆内存小于容器内存限制
```bash
docker run -d --memory=1g myapp:latest \
  -e JAVA_OPTS="-Xms256m -Xmx512m"
```

### 5.2 GC 频繁导致响应慢

**解决方案**：
```bash
# 调整堆内存大小
-XX:Xmn256m

# 切换 GC 收集器
-XX:+UseG1GC
```

## 6. 华为云部署问题

### 6.1 镜像拉取失败

**问题现象**：`Error response from daemon: pull access denied`

**解决方案**：
```bash
# 重新登录 SWR
docker login -u "cn-north-4@AK" -p "SK" swr.cn-north-4.myhuaweicloud.com

# 检查镜像是否存在
docker images | grep myapp
```

### 6.2 ECS 安全组未放通端口

**解决方案**：
```
1. 华为云控制台 → ECS → 安全组
2. 添加入站规则：TCP 端口 80,443,8080
```

## 7. 常见错误总结

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| No such image | 镜像不存在 | 重新构建和推送 |
| Port already allocated | 端口占用 | 停止旧容器或改端口 |
| OOM Killed | 内存不足 | 增加内存限制 |
| Connection refused | 服务未启动 | 启动服务 |
| 502 Bad Gateway | 后端异常 | 检查后端服务 |
| Permission denied | 权限不足 | 检查文件权限 |
| Disk full | 磁盘满 | 清理磁盘 |

## 8. 预防措施

### 8.1 部署前检查

```bash
# 检查磁盘空间
df -h

# 检查内存
free -h

# 检查端口占用
netstat -tlnp

# 检查 Docker 空间
docker system df
```

### 8.2 监控告警

```yaml
- alert: DiskSpaceLow
  expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.15
  annotations:
    summary: "磁盘空间不足"

- alert: MemoryUsageHigh
  expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.85
  annotations:
    summary: "内存使用率超过 85%"
```
