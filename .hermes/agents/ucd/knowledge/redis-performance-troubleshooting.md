# Redis 性能问题排查

> 作者：孙美玲（性能测试工程师）  
> 创建时间：2026-04-29

## 1. Redis 性能监控

### 1.1 基础命令

```bash
# 查看Redis状态
redis-cli info

# 分段查看
redis-cli info memory      # 内存信息
redis-cli info stats       # 统计信息
redis-cli info clients     # 客户端信息
redis-cli info cpu         # CPU信息
redis-cli info persistence # 持久化信息
redis-cli info replication # 复制信息
redis-cli info cluster     # 集群信息
redis-cli info keyspace    # key数量
```

### 1.2 关键指标

```yaml
INFO 关键指标:

Memory:
├── used_memory: 5242880          # 内存使用量 (字节)
├── used_memory_human: 5.00M      # 人类可读格式
├── used_memory_rss: 8388608       # 物理内存占用
├── maxmemory: 2147483648         # 最大内存限制
├── maxmemory_policy: allkeys-lru # 内存淘汰策略
└── mem_fragmentation_ratio: 1.60 # 内存碎片率

Stats:
├── total_connections_received: 1000   # 总连接数
├── total_commands_processed: 50000    # 总命令数
├── instantaneous_ops_per_sec: 100     # QPS
├── keyspace_hits: 45000               # key命中
├── keyspace_misses: 5000              # key未命中
└── hit_rate: 90%                      # 命中率

Stats (延迟相关):
├── latency_percentiles_usec_p50      # P50延迟
├── latency_percentiles_usec_p99      # P99延迟
└── latency_percentiles_usec_p99.9   # P99.9延迟
```

## 2. BigKey 问题

### 2.1 识别 BigKey

```bash
# 使用 Redis-CLI 扫描
redis-cli --bigkeys

# 使用 SCAN 遍历 (生产环境推荐)
redis-cli --scan | while read key; do 
  echo "KEY:$key SIZE:$(redis-cli memory usage $key)"; 
done | sort -t: -k2 -rn | head -20

# 使用 redis-cli info memory 分析
redis-cli memory usage <key>

# Python 脚本检测
#!/usr/bin/env python3
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
cursor = 0
big_keys = []

while True:
    cursor, keys = r.scan(cursor, count=100)
    for key in keys:
        key_type = r.type(key)
        if key_type == 'string':
            size = r.memory_usage(key)
        elif key_type == 'list':
            size = r.memory_usage(key) * r.llen(key)
        elif key_type == 'hash':
            size = r.memory_usage(key) * r.hlen(key)
        elif key_type == 'set':
            size = r.memory_usage(key) * r.scard(key)
        elif key_type == 'zset':
            size = r.memory_usage(key) * r.zcard(key)
        
        if size > 10 * 1024 * 1024:  # > 10MB
            big_keys.append((key, size))
    
    if cursor == 0:
        break

big_keys.sort(key=lambda x: x[1], reverse=True)
for key, size in big_keys[:20]:
    print(f"{key}: {size/1024/1024:.2f}MB")
```

### 2.2 BigKey 阈值标准

```yaml
BigKey 判定标准:

String类型:
├── 警告: > 10KB
├── 严重: > 100KB
└── 极度严重: > 1MB

List/Set/Hash/ZSet类型:
├── 警告: > 10000元素
├── 严重: > 50000元素
└── 极度严重: > 100000元素

内存大小:
├── 警告: > 1MB
├── 严重: > 10MB
└── 极度严重: > 100MB
```

### 2.3 BigKey 解决方案

```bash
# 1. 拆分大Key
# 原始: user:10000:orders (List, 100万条)
# 拆分: user:10000:orders:2026_01 (按月分桶)
#      user:10000:orders:2026_02

# 2. 使用Hash字段拆分
# 原始: order:1000000 (Hash, 1万字段)
# 拆分: order:1000000:base (基本信息)
#      order:1000000:items (商品列表)
#      order:1000000:logs (日志)

# 3. 使用Pipeline减少操作
redis-cli --pipe-timeout 3 --pipe <<EOF
SMEMBERS big_set
EOF

# 4. 异步删除 (避免阻塞)
UNLINK key1 key2 key3
# 或
redis-cli ASYNC key1
```

## 3. HotKey 问题

### 3.1 识别 HotKey

```bash
# 使用 Redis-CLI 实时统计
redis-cli --latency-history

# 使用 MONITOR (生产慎用，短时间采样)
redis-cli monitor --limit 100 > monitor.log &

# 使用 redis-cli --intrinsic-latency
redis-cli --intrinsic-latency 10

# 使用 Redis-Faina (Facebook工具)
python redis-faina.py --redis-host=localhost --redis-port=6379 < slowlog.txt

# 使用阿里云Redis诊断
redis-cli SLOWLOG GET | python slowlog_analyzer.py
```

### 3.2 HotKey 识别脚本

```python
#!/usr/bin/env python3
import redis
from collections import defaultdict
import time

r = redis.Redis(host='localhost', port=6379)
cmd_counts = defaultdict(int)
start_time = time.time()
duration = 60  # 监控60秒

cursor = 0
while time.time() - start_time < duration:
    cursor, keys = r.scan(cursor, count=1000)
    
    if keys:
        # 随机采样部分key检查访问频率
        for key in keys[:10]:
            # 使用 OBJECT FREQ 获取访问频率
            try:
                freq = r.object("FREQ", key)
                if freq and freq > 100:  # 高频访问
                    cmd_counts[key] = freq
            except:
                pass
    
    if cursor == 0:
        break
    time.sleep(0.1)

# 排序输出
sorted_keys = sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True)
for key, count in sorted_keys[:20]:
    print(f"{key}: {count}")
```

### 3.3 HotKey 解决方案

```yaml
HotKey 解决方案:

1. 本地缓存
   - 使用本地缓存(Caffeine/Guava Cache)
   - 减少Redis访问
   
2. 多副本分散负载
   - 使用 Redis Cluster 读写分离
   - 主从复制分散读压力
   
3. 使用热点key探测
   - 提前探测热点key
   - 主动缓存热点数据
   
4. 请求分散
   - 批量查询改为Pipeline
   - 使用随机key后缀分散
   
5. Redis集群
   # 客户端热点key本地缓存
   JedisPoolConfig config = new JedisPoolConfig();
   config.setLifo(true);
   config.setMaxTotal(200);
   config.setMaxIdle(50);
   config.setMinIdle(10);
   
   JedisPool pool = new JedisPool(config, "localhost", 6379);
```

## 4. 内存淘汰策略

### 4.1 淘汰策略类型

```bash
# 查看当前淘汰策略
redis-cli config get maxmemory-policy

# 设置淘汰策略
redis-cli config set maxmemory-policy allkeys-lru
```

```yaml
Redis 内存淘汰策略:

noeviction (默认):
- 不淘汰，返回错误
- 适合写多读少场景

volatile-lru:
- 从设置过期时间的key中LRU淘汰
- 适合有明确过期时间的数据

allkeys-lru:
- 从所有key中LRU淘汰
- 适合无明确过期时间的数据

volatile-random:
- 从设置过期时间的key中随机淘汰

allkeys-random:
- 从所有key中随机淘汰

volatile-ttl:
- 从设置过期时间的key中淘汰TTL最短的

volatile-lfu:
- 从设置过期时间的key中LFU淘汰

allkeys-lfu:
- 从所有key中LFU淘汰
```

### 4.2 内存监控与报警

```bash
# 设置内存报警
redis-cli config set notify-keyspace-events Ex

# Python 内存监控脚本
#!/usr/bin/env python3
import redis
import time
import smtplib
from email.mime.text import MIMEText

r = redis.Redis(host='localhost', port=6379)
ALERT_THRESHOLD = 0.85  # 85%

def check_memory():
    info = r.info('memory')
    used = info['used_memory']
    maxmemory = info['maxmemory']
    
    if maxmemory > 0:
        usage = used / maxmemory
        print(f"Redis内存使用率: {usage*100:.2f}%")
        
        if usage > ALERT_THRESHOLD:
            send_alert(usage)
    
    return usage

def send_alert(usage):
    print(f"警告: Redis内存使用率 {usage*100:.2f}% 超过阈值!")

if __name__ == '__main__':
    while True:
        check_memory()
        time.sleep(60)
```

## 5. 慢查询排查

### 5.1 慢查询日志

```bash
# 查看慢查询配置
redis-cli config get slowlog-log-slower-than
redis-cli config get slowlog-max-len

# 设置慢查询阈值 (微秒)
redis-cli config set slowlog-log-slower-than 1000  # 1ms

# 设置慢查询日志长度
redis-cli config set slowlog-max-len 1000

# 查看慢查询日志
redis-cli slowlog get 10

# 输出格式:
# 1) 1) (integer) 12345           # 日志ID
#    2) (integer) 1609459200      # 时间戳
#    3) (integer) 1500            # 执行时间(微秒)
#    4) 1) "GET"                  # 命令
#       2) "user:10000:profile"   # key
#    5) "127.0.0.1:54321"         # 客户端
#    6) ""                         # 客户端名称
```

### 5.2 延迟问题排查

```bash
# 1. Redis延迟测试
redis-cli --latency

# 2. 延迟历史
redis-cli --latency-history

# 3. 延迟分布
redis-cli --latency-dist

# 4. 内部延迟统计
redis-cli CONFIG GET latency-monitor-threshold
redis-cli LATENCY LATEST

# 5. 诊断延迟问题
redis-cli --intrinsic-latency 10
```

### 5.3 常见延迟原因

```yaml
延迟原因分析:

1. 大操作 (BigKey)
   - KEYS/SCAN 遍历
   - SMEMBERS 获取大集合
   - GET 获取大字符串
   
2. 持久化阻塞
   - AOF fsync 阻塞
   - RDB save 阻塞
   - 主从同步阻塞
   
3. 内存相关
   - 内存碎片整理
   - 大内存申请
   - swap使用
   
4. 网络相关
   - 连接数过多
   - 大数据帧
   - 短连接频繁
   
5. CPU相关
   - 单核CPU跑满
   - 复杂Lua脚本
   - 大Key序列化
```

## 6. 连接问题

### 6.1 连接池配置

```yaml
Jedis连接池配置:

spring:
  redis:
    host: localhost
    port: 6379
    password: 
    database: 0
    
    jedis:
      pool:
        max-active: 100       # 最大连接数
        max-idle: 50          # 最大空闲连接
        min-idle: 10          # 最小空闲连接
        max-wait: 3000ms      # 最大等待时间(ms)
        test-on-borrow: true  # 借用时测试
        test-while-idle: true # 空闲时测试
```

### 6.2 连接问题排查

```bash
# 查看客户端连接
redis-cli client list

# 输出示例:
# addr=127.0.0.1:54321 fd=6 idle=0 flags=N db=0
# addr=127.0.0.1:54322 fd=7 idle=10 flags=N db=0

# 查看连接统计
redis-cli info clients

# 输出:
# connected_clients:50           # 当前连接数
# client_longest_output_list:0    # 最大输出缓冲区
# client_biggest_input_buf:0      # 最大输入缓冲区
# blocked_clients:0              # 阻塞客户端数

# 杀掉空闲连接
redis-cli client kill <addr>

# 查看最大连接数
redis-cli config get maxclients
```

### 6.3 连接泄漏问题

```yaml
连接泄漏排查:

现象:
- 连接数持续增长
- 出现 "Cannot assign requested address"
- 应用报连接超时

原因:
- Jedis未正确关闭
- 连接池配置过小
- 长连接未释放

解决:
1. 使用try-with-resources
   try (Jedis jedis = pool.getResource()) {
       jedis.get("key");
   }

2. 正确处理异常
   Jedis jedis = null;
   try {
       jedis = pool.getResource();
       jedis.get("key");
   } finally {
       if (jedis != null) {
           jedis.close();  // 归还连接池
       }
   }

3. 增大连接池
4. 添加连接监控报警
```

## 7. Redis 性能测试

### 7.1 基准测试

```bash
# redis-benchmark 基本测试
redis-benchmark -h localhost -p 6379

# 指定测试项目
redis-benchmark -h localhost -p 6379 -t set,get -n 100000

# 指定并发数
redis-benchmark -h localhost -p 6379 -c 100 -n 100000

# 指定数据大小
redis-benchmark -h localhost -p 6379 -d 1024

# 测试特定key
redis-benchmark -h localhost -p 6379 -r 100000 -t set,get

# 输出示例:
# ===== SET =====
#   100000 requests completed in 2.34 seconds
#   50 parallel clients
#   3 bytes payload
#   99.92% <= 1 milliseconds
#   100.00% <= 2 milliseconds
#   42735.04 requests per second
```

### 7.2 性能测试脚本

```python
#!/usr/bin/env python3
import redis
import time
from concurrent.futures import ThreadPoolExecutor

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def test_set(n):
    start = time.time()
    for i in range(n):
        r.set(f"key:{i}", f"value:{i}")
    return time.time() - start

def test_get(n):
    start = time.time()
    for i in range(n):
        r.get(f"key:{i}")
    return time.time() - start

# 测试SET
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(test_set, 10000) for _ in range(10)]
    total_time = sum([f.result() for f in futures])
    print(f"SET: {100000/total_time:.2f} ops/sec")

# 测试GET
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(test_get, 10000) for _ in range(10)]
    total_time = sum([f.result() for f in futures])
    print(f"GET: {100000/total_time:.2f} ops/sec")
```

---

*相关文档：[MySQL 慢查询分析](./mysql-slow-query-analysis.md)*  
*返回：[QA 性能测试知识库索引](../index.md)*
