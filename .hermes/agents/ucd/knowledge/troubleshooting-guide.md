# 常见故障排查流程

## 概述

本文档介绍 Linux 服务器常见故障的排查流程。

## 1. CPU 100% 排查

### 1.1 排查命令

```bash
# 查看 CPU 使用情况
top
# 按 P 查看 CPU 排序
# 按 M 查看内存排序

# 查看进程树
ps aux --sort=-%cpu | head -20

# 查看 Java 进程线程
top -Hp <pid>

# 导出线程堆栈
jstack <pid> > /tmp/threaddump.log
```

### 1.2 Java 应用 CPU 高排查

```bash
# 1. 找到 Java 进程
jps -l

# 2. 查看线程 CPU 使用
top -Hp <pid>

# 3. 导出线程堆栈
jstack <pid> > /tmp/threaddump.log

# 4. 查找高 CPU 线程
# top -Hp 输出中找到 CPU 最高的线程 TID
printf "%x\n" <thread_id>

# 5. 在线程 dump 中查找
grep -A 20 "nid=0x3039" /tmp/threaddump.log

# 6. 使用 Arthas
java -jar arthas-boot.jar
dashboard
thread -n 10
```

### 1.3 常见原因

| 原因 | 特征 | 解决方案 |
|------|------|---------|
| 死循环 | 单线程 CPU 100% | 优化代码 |
| GC 频繁 | GC 线程占用高 | 调整 JVM 参数 |
| 正则表达式 | 低效匹配 | 优化正则 |
| 频繁 Full GC | 老年代满 | 增加堆内存 |
| SQL 全表扫描 | 数据库负载高 | 优化索引 |

## 2. 内存泄漏排查

### 2.1 排查命令

```bash
# 查看内存使用
free -h

# 查看进程内存
ps aux --sort=-%mem | head -20

# 查看 OOM 日志
dmesg | grep -i "out of memory"
dmesg | grep -i "killed process"

# 查看虚拟内存
vmstat 1 10
```

### 2.2 Java 内存泄漏排查

```bash
# 查看 JVM 内存
jstat -gc <pid> 1000 10

# 导出堆内存
jmap -dump:format=b,file=/tmp/heap.hprof <pid>

# 使用 Arthas
dashboard
memory
heapdump
```

### 2.3 常见内存泄漏场景

```java
// 1. 静态集合类持有对象引用
private static Map<String, Object> cache = new HashMap<>();

// 2. 未关闭的资源
Connection conn = ds.getConnection();
// 未在 finally 中关闭

// 3. 监听器未注销
component.addListener(listener);
// 未 removeListener

// 4. ThreadLocal 未清理
ThreadLocal<Map> tl = new ThreadLocal<>();
tl.set(map);
// 需要 remove()
```

## 3. 磁盘占满排查

### 3.1 排查命令

```bash
# 查看磁盘使用
df -h
df -i  # 查看 inode

# 查找大目录
du -sh /* 2>/dev/null | sort -rh | head -10

# 查找大文件
find / -type f -size +100M -exec ls -lh {} \;

# 清理 Docker 日志
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### 3.2 日志清理

```bash
# 清理日志文件
> /var/log/messages

# 清理历史日志
find /var/log -name "*.gz" -mtime +30 -delete

# Docker 日志配置
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  }
}
```

## 4. 网络不通排查

### 4.1 排查命令

```bash
# 检查网络连接
ip addr
netstat -tunlp

# 检查连通性
ping -c 4 8.8.8.8
ping -c 4 www.baidu.com

# 检查 DNS
nslookup www.baidu.com

# 检查路由
traceroute www.baidu.com

# 检查端口
telnet <ip> <port>
lsof -i:<port>

# 检查防火墙
firewall-cmd --list-all
iptables -L -n
```

### 4.2 常见问题处理

```bash
# DNS 故障
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

# 防火墙阻止
systemctl stop firewalld

# 端口被占用
lsof -i:8080
```

## 5. 服务无法启动排查

### 5.1 排查命令

```bash
# 查看系统日志
journalctl -u nginx -n 100 --no-pager

# 查看 Docker 日志
docker logs <container>
docker logs --tail 100 -f <container>

# 检查配置语法
nginx -t
redis-server --test-memory 1024 --test-configuration

# 检查端口占用
netstat -tlnp | grep 8080
```

## 6. 故障处理流程

```
发现问题
    ↓
立即止血
├── 停止异常进程
├── 切换备份服务
└── 扩大资源限额
    ↓
分析根因
├── 查看日志
├── 分析监控
└── 复现问题
    ↓
制定修复方案
    ↓
实施修复
    ↓
验证修复
```

## 7. 常用巡检脚本

```bash
#!/bin/bash
echo "============================================"
echo "系统巡检报告 - $(date)"
echo "============================================"

echo ""
echo "【系统负载】"
uptime

echo ""
echo "【CPU 使用】"
top -bn1 | head -5

echo ""
echo "【内存使用】"
free -h

echo ""
echo "【磁盘使用】"
df -h | grep -v tmpfs

echo ""
echo "【网络连接统计】"
ss -s

echo ""
echo "【CPU 最高的进程】"
ps aux --sort=-%cpu | head -6

echo ""
echo "【内存最高的进程】"
ps aux --sort=-%mem | head -6

echo ""
echo "【监听端口】"
netstat -tlnp | grep -v "127.0.0.1"
```
