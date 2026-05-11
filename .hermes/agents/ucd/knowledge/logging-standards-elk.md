# 日志规范与 ELK 日志收集方案

## 概述

本文档介绍日志规范（SLF4J + Logback）、日志格式标准、以及 ELK 日志收集方案。

## 1. Logback 配置

### 1.1 pom.xml 依赖

```xml
<dependencies>
    <!-- Logback -->
    <dependency>
        <groupId>ch.qos.logback</groupId>
        <artifactId>logback-classic</artifactId>
        <version>1.4.14</version>
    </dependency>
    
    <!-- Logstash Logback Encoder（JSON 格式） -->
    <dependency>
        <groupId>net.logstash.logback</groupId>
        <artifactId>logstash-logback-encoder</artifactId>
        <version>7.4</version>
    </dependency>
</dependencies>
```

### 1.2 logback-spring.xml 配置

```xml
<!-- src/main/resources/logback-spring.xml -->
<configuration>
    
    <property name="LOG_HOME" value="/app/logs"/>
    <property name="APP_NAME" value="myapp"/>

    <!-- 控制台输出 -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
            <charset>UTF-8</charset>
        </encoder>
    </appender>

    <!-- JSON 格式（用于 ELK） -->
    <appender name="CONSOLE_JSON" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <includeMdcKeyName>traceId</includeMdcKeyName>
            <includeMdcKeyName>userId</includeMdcKeyName>
            <customFields>{"app":"${APP_NAME}"}</customFields>
        </encoder>
    </appender>

    <!-- 应用日志文件 -->
    <appender name="APP_FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_HOME}/${APP_NAME}.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
            <fileNamePattern>${LOG_HOME}/${APP_NAME}.%d{yyyy-MM-dd}.%i.log</fileNamePattern>
            <maxHistory>30</maxHistory>
            <timeBasedFileNamingAndTriggeringPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedFNATP">
                <maxFileSize>100MB</maxFileSize>
            </timeBasedFileNamingAndTriggeringPolicy>
        </rollingPolicy>
        <encoder class="net.logstash.logback.encoder.LogstashEncoder"/>
    </appender>

    <!-- 错误日志单独记录 -->
    <appender name="ERROR_FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_HOME}/${APP_NAME}-error.log</file>
        <filter class="ch.qos.logback.classic.filter.ThresholdFilter">
            <level>ERROR</level>
        </filter>
        <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
            <fileNamePattern>${LOG_HOME}/${APP_NAME}-error.%d{yyyy-MM-dd}.log</fileNamePattern>
            <maxHistory>90</maxHistory>
        </rollingPolicy>
        <encoder class="net.logstash.logback.encoder.LogstashEncoder"/>
    </appender>

    <!-- 开发环境 -->
    <springProfile name="dev">
        <root level="DEBUG">
            <appender-ref ref="CONSOLE"/>
        </root>
    </springProfile>

    <!-- 生产环境 -->
    <springProfile name="prod">
        <root level="INFO">
            <appender-ref ref="CONSOLE_JSON"/>
            <appender-ref ref="APP_FILE"/>
            <appender-ref ref="ERROR_FILE"/>
        </root>
    </springProfile>
</configuration>
```

## 2. 日志规范

### 2.1 日志级别使用

| 级别 | 使用场景 |
|------|---------|
| ERROR | 系统错误，需要处理的异常 |
| WARN | 潜在问题，不影响运行 |
| INFO | 业务流程关键节点 |
| DEBUG | 开发调试信息 |

### 2.2 日志格式规范

```json
{
  "@timestamp": "2026-04-29T12:00:00.000+08:00",
  "level": "INFO",
  "logger": "c.m.s.UserService",
  "message": "用户登录成功",
  "traceId": "abc123def456",
  "thread": "http-nio-8080-exec-1",
  "application": "myapp"
}
```

### 2.3 日志写法示例

```java
// ✅ 正确的日志写法
log.info("查询用户信息，userId={}", userId);
log.debug("查询结果，result={}", result);
log.error("查询失败", e);

// ❌ 错误的日志写法
log.info("查询用户");
log.error(e.toString());
```

## 3. Spring Boot 日志配置

```yaml
# application.yml
spring:
  application:
    name: myapp

logging:
  level:
    root: INFO
    com.mycompany: DEBUG
  file:
    path: /app/logs
    max-size: 100MB
    max-history: 30
```

## 4. ELK 架构

```
应用服务器                    ELK 服务器
┌─────────────┐             ┌─────────────┐
│ Spring Boot │ ── Filebeat ──▶│ Logstash    │
│ 日志文件     │             │ 清洗过滤     │
└─────────────┘             └──────┬──────┘
                                   │
                                   ▼
                              ┌─────────────┐
                              │ Elasticsearch│
                              │ 存储索引     │
                              └──────┬──────┘
                                   │
                                   ▼
                              ┌─────────────┐
                              │ Kibana      │
                              │ 可视化查询   │
                              └─────────────┘
```

## 5. Filebeat 配置

```yaml
# /etc/filebeat/filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /app/logs/myapp*.log
    json.keys_under_root: true
    json.add_error_key: true
    fields:
      type: application

processors:
  - add_host_metadata:
      when.not.contains.tags: forwarded

output.logstash:
  hosts: ["192.168.1.100:5044"]
```

## 6. Logstash 配置

```ruby
# /etc/logstash/conf.d/pipeline.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [type] == "application" {
    date {
      match => [ "@timestamp", "ISO8601" ]
      target => "@timestamp"
    }
  }
}

output {
  elasticsearch {
    hosts => ["http://localhost:9200"]
    index => "myapp-%{+YYYY.MM.dd}"
  }
}
```

## 7. Elasticsearch ILM 策略

```json
PUT _ilm/policy/myapp-policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "7d"
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

## 8. Kibana 查询示例

```kql
# 错误日志
level: ERROR

# 特定用户操作
userId: "10001"

# 链路追踪
traceId: "abc123def456"

# 慢请求
cost: > 1000
```
