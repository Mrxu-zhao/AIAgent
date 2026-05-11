# 读写分离方案与主从复制优化

## 概述

读写分离是数据库扩展的入门方案，通过将读请求分流到从库提升系统吞吐量。本文详解 MySQL 主从复制原理、配置及常见问题处理。

## 主从复制原理

### 原理图

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ Master  │ ──binlog dump──> │ Slave   │ <──IO_THREAD── │ Slave   │
│  (写)   │                    │ (读1)   │                    │ (读2)   │
└─────────┘                    └─────────┘                    └─────────┘
                                    │                               │
                              SQL_THREAD                          SQL_THREAD
                                    │                               │
                              relay-log                           relay-log
                                    │                               │
                              replay                             replay
```

### 复制流程

```
1. Master: UPDATE 语句写入 binlog
2. Master: IO_THREAD 将 binlog 发送到 Slave
3. Slave: IO_THREAD 接收写入 relay-log
4. Slave: SQL_THREAD 重放 relay-log 中的事件
```

### 复制类型

| 类型 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 异步复制 | 主库提交后立即返回，不等待从库 | 性能高 | 可能丢数据 |
| 半同步复制 | 等待至少一个从库确认 | 数据安全性高 | 有延迟 |
| 全同步复制 | 等待所有从库完成 | 强一致性 | 性能差 |

## 配置实践

### Master 配置

```ini
[mysqld]
server-id = 1                    # 唯一 ID
log-bin = mysql-bin             # 开启 binlog
binlog_format = ROW             # 推荐 ROW 格式
binlog_expire_logs_seconds = 604800  # binlog 保留 7 天
max_binlog_size = 1G            # 单个 binlog 文件大小
sync_binlog = 1                 # 每次事务同步 binlog（安全但性能低）
innodb_flush_log_at_trx_commit = 1  # 事务日志刷盘策略

# GTID 模式（MySQL 5.7+ 推荐）
gtid_mode = ON
enforce_gtid_consistency = ON
```

### Slave 配置

```ini
[mysqld]
server-id = 2                    # 唯一 ID，与 Master 不同
relay-log = relay-log           # 中继日志
relay-log-index = relay-log.index
read_only = ON                  # 从库只读
super_read_only = ON            # 禁止 SUPER 权限写（MySQL 8.0+）
log_replica_updates = ON        # 从库记录 binlog（级联复制需要）
slave_parallel_workers = 8      # 并行复制线程数
slave_parallel_type = LOGICAL_CLOCK  # 并行复制类型
```

### 创建复制账号

```sql
-- Master 执行
CREATE USER 'repl'@'%' IDENTIFIED WITH mysql_native_password BY 'repl_password';
GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
```

### 启动复制

```sql
-- 获取 Master 位置
SHOW MASTER STATUS;
-- +------------------+----------+--------------+------------------+
-- | File             | Position | Binlog_Do_DB | Binlog_Ignore_DB |
-- +------------------+----------+--------------+------------------+
-- | mysql-bin.000001 |     1234 |              |                  |
-- +------------------+----------+--------------+------------------+

-- Slave 执行
CHANGE MASTER TO
    MASTER_HOST = '192.168.1.100',
    MASTER_PORT = 3306,
    MASTER_USER = 'repl',
    MASTER_PASSWORD = 'repl_password',
    MASTER_LOG_FILE = 'mysql-bin.000001',
    MASTER_LOG_POS = 1234,
    GET_MASTER_PUBLIC_KEY = 1;

START SLAVE;
SHOW SLAVE STATUS\G
```

## Spring Boot + MyBatis-Plus 配置

### 数据源配置

```yaml
# application.yml
spring:
  datasource:
    # 主库（写）
    master:
      jdbc-url: jdbc:mysql://192.168.1.100:3306/shop?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=Asia/Shanghai
      username: root
      password: root
      driver-class-name: com.mysql.cj.jdbc.Driver
      hikari:
        minimum-idle: 5
        maximum-pool-size: 20
        connection-timeout: 30000
    # 从库（读）
    slave:
      jdbc-url: jdbc:mysql://192.168.1.101:3306/shop?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=Asia/Shanghai
      username: root
      password: root
      driver-class-name: com.mysql.cj.jdbc.Driver
      hikari:
        minimum-idle: 10
        maximum-pool-size: 50
        connection-timeout: 30000
```

### 动态数据源切换

```java
@Configuration
public class DataSourceConfig {
    
    @Bean
    @Primary
    public DataSource masterDataSource() {
        return DataSourceBuilder.create()
            .url("jdbc:mysql://192.168.1.100:3306/shop")
            .username("root")
            .password("root")
            .driverClassName(com.mysql.cj.jdbc.Driver.class)
            .build();
    }
    
    @Bean
    public DataSource slaveDataSource() {
        return DataSourceBuilder.create()
            .url("jdbc:mysql://192.168.1.101:3306/shop")
            .username("root")
            .password("root")
            .driverClassName(com.mysql.cj.jdbc.Driver.class)
            .build();
    }
}
```

### 读写分离策略

```java
// 方案一：注解方式（推荐）
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ReadOnly {
}

// 切面实现
@Component
@Aspect
public class DataSourceAspect {
    
    @Around("@annotation(readOnly)")
    public Object switchDataSource(ProceedingJoinPoint point, ReadOnly readOnly) throws Throwable {
        DynamicDataSource.setDataSource("slave");
        try {
            return point.proceed();
        } finally {
            DynamicDataSource.clearDataSource();
        }
    }
}

// 使用示例
@Service
public class OrderService {
    
    @Autowired private OrderMapper orderMapper;
    
    // 读方法使用从库
    @ReadOnly
    public List<Order> listByUserId(Long userId) {
        return orderMapper.selectList(Wrappers.lambdaQuery()
            .eq(Order::getUserId, userId));
    }
    
    // 写方法使用主库
    @Transactional
    public void createOrder(Order order) {
        orderMapper.insert(order);  // 主库写入
    }
}

// 方案二：MyBatis-Plus 动态数据源插件
@Configuration
public class MyBatisPlusConfig {
    
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        // 动态表名插件（可选）
        // 乐观锁插件（可选）
        return interceptor;
    }
}
```

### ShardingSphere 读写分离

```yaml
# application.yml
spring:
  shardingsphere:
    rules:
      readwrite-splitting:
        data-sources:
          ds_master:
            write-data-source-name: master
            read-data-source-names: slave-0, slave-1
            load-balancer-name: round_robin
        load-balancers:
          round_robin:
            type: ROUND_ROBIN
          random:
            type: RANDOM
```

## 延迟优化

### 查看复制延迟

```sql
-- 方法一：SHOW SLAVE STATUS
SHOW SLAVE STATUS\G
-- Seconds_Behind_Master: 0  表示无延迟
-- ⚠️ 这个值不准确，可能显示负数或 NULL

-- 方法二：performance_schema（更准确）
SELECT 
    slave_name,
    last_error_number,
    last_error_message,
    last_error_timestamp
FROM performance_schema.replication_connection_status;

-- 方法三：监控 GTID 位置
SHOW SLAVE STATUS\G
-- Retrieved_Gtid_Set: 接收到的 GTID
-- Executed_Gtid_Set: 已执行的 GTID
```

### 延迟原因分析

```sql
-- 查看从库执行慢的 SQL
SELECT 
    DIGEST_TEXT AS sql,
    COUNT_STAR AS exec_count,
    SUM_TIMER_WAIT/1000000000000 AS total_time
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST_TEXT LIKE '%orders%'
ORDER BY SUM_TIMER_WAIT DESC;
```

### 延迟优化策略

```sql
-- 1. 从库参数优化
-- 增加并行复制线程
SET GLOBAL slave_parallel_workers = 16;
SET GLOBAL slave_parallel_type = 'LOGICAL_CLOCK';

-- 2. 大事务拆分
-- ❌ 错误：大事务
BEGIN;
INSERT INTO orders ... VALUES (),(),(),...;  -- 10000条
COMMIT;

-- ✅ 正确：分批小事务
for batch in batches(1000):
    INSERT INTO orders ... VALUES ();
    COMMIT;

-- 3. 索引优化
-- 从库创建专门优化读性能的索引
CREATE INDEX idx_user_status_date ON orders(user_id, status, created_at);

-- 4. 避免主从复制热点
-- ❌ 错误：自增锁竞争
INSERT INTO counter (id, value) VALUES (NULL, 1);

-- ✅ 正确：使用批量自增或应用生成
INSERT INTO counter (id, value) VALUES (1001, 1), (2001, 1);
```

### 应用层延迟处理

```java
// 方案一：强制读主库（适合强一致性场景）
@Service
public class OrderService {
    
    @Transactional(propagation = Propagation.REQUIRED)
    public Order getOrderDetail(Long orderId) {
        // 事务内强制读主库
        return orderMapper.selectById(orderId);
    }
}

// 方案二：延迟阈值跳过（适合最终一致场景）
@Component
public class ReadWriteConfig {
    
    @Value("${db.slave.lag.threshold:3000}")
    private int lagThreshold;  // 毫秒
    
    @Around("execution(* com.xxx.mapper.*.select*())")
    public Object checkSlaveLag(ProceedingJoinPoint point) throws Throwable {
        // 检查从库延迟
        Long lag = getSlaveLag();
        if (lag > lagThreshold) {
            // 延迟过高，读主库
            DynamicDataSource.setDataSource("master");
        }
        try {
            return point.proceed();
        } finally {
            DynamicDataSource.clearDataSource();
        }
    }
}

// 方案三：同一条数据读主库（同一次请求内）
// 使用 ThreadLocal 缓存当前请求读取的数据源
public class DataSourceContext {
    private static final ThreadLocal<String> context = new ThreadLocal<>();
    
    public static void set(String ds) { context.set(ds); }
    public static String get() { return context.get(); }
    public static void clear() { context.remove(); }
}
```

## HA 高可用配置

### Keepalived + MySQL

```bash
# Master 配置 /etc/keepalived/keepalived.conf
vrrp_instance VI_1 {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 100
    advert_int 1
    authentication {
        auth_type PASS
        auth_pass 1111
    }
    virtual_ipaddress {
        192.168.1.200  # VIP
    }
}
virtual_server 192.168.1.200 3306 {
    delay_loop 6
    lb_algo rr
    lb_kind DR
    persistence_timeout 50
    protocol TCP
    real_server 192.168.1.100 3306 {
        weight 1
        TCP_CHECK {
            connect_timeout 3
            nb_get_retry 3
            delay_before_retry 3
            connect_port 3306
        }
    }
}
```

### MHA（MySQL High Availability）

```bash
# 安装 MHA Node
yum install mha4mysql-node -y

# Manager 配置 /etc/app1.cnf
[server default]
manager_workdir=/var/log/masterha/app1
manager_log=/var/log/masterha/app1/manager.log
remote_workdir=/var/log/masterha
ssh_user=root
ssh_port=22
repl_user=repl
repl_password=repl_password
master_binlog_dir=/var/lib/mysql
ping_interval=3
secondary_check_script=masterha_secondary_check -s 192.168.1.102 -s 192.168.1.103

[server1]
hostname=192.168.1.100
candidate_master=1

[server2]
hostname=192.168.1.101
candidate_master=1

[server3]
hostname=192.168.1.102
candidate_master=0
```

## 踩坑经验汇总

| 坑点 | 问题描述 | 解决方案 |
|------|----------|----------|
| 延迟过大 | 从库延迟几十秒 | 优化从库查询、增加并行复制 |
| 数据不一致 | 主从不一致 | 使用 GTID 复制、检查 binlog 格式 |
| 切换丢数据 | 切换时丢失未同步数据 | 使用半同步复制 |
| 连接池耗尽 | 读从库连接不够 | 合理配置主从连接池比例 |
| 读写混乱 | 未区分读写库 | 使用注解或拦截器控制 |
| 自增主键冲突 | 多从库自增重复 | 使用全局自增服务或改用 UUID |
| 时区不一致 | 数据时间错乱 | 统一时区（推荐 UTC） |
| 密码加密 | 新版 MySQL 加密方式 | 使用 mysql_native_password |

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
