# 分库分表方案对比与实践

## 概述

当单表数据量超过千万级、数据库 QPS 超过万级时，需要考虑分库分表方案。本文档对比 ShardingSphere 和 MyCat 两大主流方案。

## 分库分表场景判断

```sql
-- 判断是否需要分表
SELECT 
    table_name,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(index_length / 1024 / 1024, 2) AS index_mb,
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb,
    table_rows
FROM information_schema.tables
WHERE table_schema = 'your_database'
ORDER BY table_rows DESC;

-- 经验阈值
-- 单表 > 500 万条 → 考虑分表
-- 单表 > 1000 万条 → 必须分表
-- 单库 QPS > 5000 → 考虑分库
```

## ShardingSphere vs MyCat 对比

| 维度 | ShardingSphere | MyCat |
|------|-----------------|-------|
| 公司/社区 | Apache 基金会，活跃 | 早期开源，更新较少 |
| 架构 | 无中心化，客户端分片 | 代理层，服务端分片 |
| 部署复杂度 | 低（Java 应用集成） | 高（独立服务） |
| 语言支持 | 多语言（Java, Go, Python） | 需 MyCat 客户端 |
| 功能完整性 | 完整（读写分离、分布式事务） | 完整但版本老旧 |
| 性能损耗 | 较低 | 较高（多一跳） |
| 运维难度 | 低 | 高 |
| 推荐场景 | 新项目、微服务架构 | 遗留系统、异构语言 |

## ShardingSphere 实践

### Maven 依赖

```xml
<dependency>
    <groupId>org.apache.shardingsphere</groupId>
    <artifactId>shardingsphere-jdbc-core</artifactId>
    <version>5.3.2</version>
</dependency>
```

### 分库分表配置

```yaml
# application-sharding.yml
spring:
  datasource:
    ds-0:
      jdbc-url: jdbc:mysql://localhost:3306/sharding_0?useUnicode=true&characterEncoding=utf8
      driver-class-name: com.mysql.cj.jdbc.Driver
      username: root
      password: root
    ds-1:
      jdbc-url: jdbc:mysql://localhost:3306/sharding_1?useUnicode=true&characterEncoding=utf8
      driver-class-name: com.mysql.cj.jdbc.Driver
      username: root
      password: root
  
  shardingsphere:
    rules:
      sharding:
        tables:
          # t_order 表分片配置
          t_order:
            actual-data-nodes: ds-$->{0..1}.t_order_$->{0..3}
            # 分片算法
            table-strategy:
              standard:
                sharding-column: order_id
                sharding-algorithm-name: order_inline
            key-generate-strategy:
              column: order_id
              key-generator-name: snowflake
        
        # 分片算法定义
        sharding-algorithms:
          # 取模分片算法
          order_inline:
            type: INLINE
            props:
              algorithm-expression: t_order_$->{order_id % 4}
          # 时间分片算法
          order_time_inline:
            type: INLINE
            props:
              algorithm-expression: t_order_$->{Long.parseLong(date_format(created_at, 'yyyyMM')) % 12}
        
        # 主键生成策略
        key-generators:
          snowflake:
            type: SNOWFLAKE

    props:
      sql-show: true  # 打印 SQL
```

### 分片策略选择

```java
// 1. 哈希取模分片（最常用）
// 适用场景：用户订单、商品订单
// 优点：数据分布均匀
// 缺点：扩缩容需要迁移数据

// 2. 时间分片
// 适用场景：日志表、流水表
// 优点：冷热数据分离
// 缺点：热点数据集中在当前时间

// 3. 范围分片
// 适用场景：ID 连续的业务
// 优点：支持范围查询
// 缺点：可能出现热点

// 4. 绑定表（关联查询优化）
sharding:
  tables:
    t_order:
      actual-data-nodes: ds-$->{0..1}.t_order_$->{0..3}
      binding-tables:
        - t_order,t_order_item  # 同一分片的表绑定
```

### 关联查询配置

```java
// ❌ 错误：跨分片关联查询
@Select("SELECT o.*, i.* FROM t_order o " +
        "JOIN t_order_item i ON o.order_id = i.order_id " +
        "WHERE o.user_id = #{userId}")
List<OrderDetail> selectByUserId(Long userId);

// ✅ 正确：绑定表关联查询
@Select("SELECT o.*, i.* FROM t_order o " +
        "JOIN t_order_item i ON o.order_id = i.order_id " +
        "WHERE o.user_id = #{userId}")
@ShardingsphereTable("t_order")  // 指定分片表
List<OrderDetail> selectByUserId(Long userId);

// ✅ 正确：广播表（字典表）
sharding:
  tables:
    t_dict:
      actual-data-nodes: ds-0.t_dict  # 所有库都有
      type: BROADCAST  # 广播表
```

## MyCat 实践

### 安装配置

```bash
# 下载 MyCat
wget http://dl.mycat.org.cn/2.0/Mycat-server-2.0.0/Mycat-server-2.0.0-release.tar.gz
tar -xzf Mycat-server-2.0.0-release.tar.gz -C /usr/local/

# 配置环境变量
export MYCAT_HOME=/usr/local/mycat
export PATH=$PATH:$MYCAT_HOME/bin
```

### server.xml 配置

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mycat:server SYSTEM "server.dtd">
<mycat:server xmlns:mycat="http://io.mycat/">
    <system>
        <property name="serverPort">8066</property>
        <property name="managerPort">9066</property>
    </system>
    
    <user name="root">
        <property name="password">123456</property>
        <property name="schemas">shop</property>
    </user>
</mycat:server>
```

### schema.xml 配置

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mycat:schema SYSTEM "schema.dtd">
<mycat:schema xmlns:mycat="http://io.mycat/">
    
    <!-- 数据表配置 -->
    <schema name="shop" checkSQLschema="false" sqlMaxLimit="100">
        <!-- 逻辑表，绑定数据节点 -->
        <table name="t_order" 
               dataNode="dn$1-2" 
               rule="mod-long"
               primaryKey="order_id"/>
        
        <!-- 全局表（字典表） -->
        <table name="t_dict" 
               dataNode="dn$1-2" 
               type="global"/>
        
        <!-- ER 分片表 -->
        <table name="t_order_item" 
               dataNode="dn$1-2" 
               rule="mod-long"
               parentKey="order_id"/>
    </schema>
    
    <!-- 数据节点配置 -->
    <dataNode name="dn1" dataHost="localhost1" database="shop_0"/>
    <dataNode name="dn2" dataHost="localhost1" database="shop_1"/>
    
    <!-- 数据源配置 -->
    <dataHost name="localhost1" maxCon="1000" minCon="10" 
              balance="1" writeType="0" dbType="mysql">
        <heartbeat>select user()</heartbeat>
        <writeHost host="hostM1" url="localhost:3306" user="root" password="root">
            <readHost host="hostS1" url="localhost:3307" user="root" password="root"/>
        </writeHost>
    </dataHost>
</mycat:schema>
```

### rule.xml 分片规则

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mycat:rule SYSTEM "rule.dtd">
<mycat:rule xmlns:mycat="http://io.mycat/">
    
    <!-- 取模分片规则 -->
    <tableRule name="mod-long">
        <rule>
            <columns>order_id</columns>
            <algorithm>mod-long</algorithm>
        </rule>
    </tableRule>
    
    <!-- 分片算法 -->
    <function name="mod-long" class="io.mycat.route.function.PartitionByMod">
        <property name="count">4</property>
    </function>
    
    <!-- 哈希分片 -->
    <function name="mod-long-hash" 
              class="io.mycat.route.function.PartitionByHashMod">
        <property name="count">4</property>
    </function>
</mycat:rule>
```

## 分库分表最佳实践

### 分片键选择原则

```sql
-- ✅ 好的分片键
-- 1. 查询高频字段
user_id      -- 用户中心，按用户查询
customer_id  -- 多租户系统，按租户隔离
order_date   -- 日志系统，按时间归档

-- ❌ 差的分片键
-- 1. 更新频繁字段
status       -- 状态更新导致数据迁移
balance      -- 余额变动

-- 2. 低选择性字段
gender       -- 只有男女，数据不均
province     -- 数据分布不均

-- 3. 非整数字段（需扩展支持）
order_no     -- 订单号，不能直接取模
```

### 分片数规划

```sql
-- 计算公式
-- 预期数据量 / 单表容量（100万）= 初始分片数
-- 考虑 3 年增长 × 2 倍冗余

-- 示例：订单表预计 3 年 1 亿条
-- 初始分片数 = 100000000 / 1000000 × 2 = 200 片
-- 建议：分成 16 或 32 个表，留足扩展空间
```

### SQL 限制

```sql
-- ❌ 跨分片查询无法支持
SELECT * FROM t_order 
WHERE order_id IN (1, 1001, 2001, 3001)  -- 可能跨多个分片

-- ❌ 跨分片排序分页（深度分页）
SELECT * FROM t_order ORDER BY created_at LIMIT 10000, 20

-- ✅ 正确做法：先查分片键，再查询
-- 1. 使用业务 ID 查询主表
-- 2. 关联查询使用分片键

-- ✅ 范围查询尽量使用分片键
SELECT * FROM t_order 
WHERE user_id = 1001 
  AND created_at BETWEEN '2024-01-01' AND '2024-12-31'
```

### 分布式 ID 生成

```java
// 方案一：ShardingSphere 内置雪花算法
@Configuration
public class ShardingConfig {
    @Bean
    public KeyGenerateAlgorithm snowflakeKeyGenerator() {
        return new SnowflakeKeyGenerateAlgorithm();
    }
}

// 方案二：号段模式（推荐高并发）
@Configuration
public class IdGeneratorConfig {
    @Bean
    public IDS snowflakeIdGenerator() {
        return new Snowflake(1, 1);
    }
}

// 方案三：Leaf（美团开源）
// 支持号段模式和雪花模式，有监控
```

## 踩坑经验汇总

| 坑点 | 问题描述 | 解决方案 |
|------|----------|----------|
| 分片键变更 | 需要重新分布数据 | 设计初期充分考虑，避免变更 |
| 关联查询 | 跨分片 JOIN 性能差 | 使用绑定表或 ES |
| 分页排序 | 全局分页无法优化 | 使用游标或先聚合后分页 |
| 分布式事务 | 跨库事务一致性 | 使用 Seata/TCC |
| 数据迁移 | 停机迁移风险高 | 使用双写方案（binlog） |
| 扩缩容 | 数据迁移困难 | 使用一致性哈希 |
| 全局表 | 字典表同步延迟 | 使用缓存或最终一致 |
| 自增主键 | 多节点自增冲突 | 使用分布式 ID |

---

*本文档由 DBA 周嘉诚 创建*
*最后更新: 2026-04-29*
