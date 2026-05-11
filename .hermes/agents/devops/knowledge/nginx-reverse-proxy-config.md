# Nginx 反向代理配置实战

## 概述

本文档详细介绍 Nginx 反向代理的实战配置，包括负载均衡、SSL 证书配置、限流等。

## 1. 基础反向代理配置

```nginx
upstream backend_servers {
    server 127.0.0.1:8080 weight=5;
    server 127.0.0.1:8081 weight=3 backup;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://backend_servers;
        proxy_http_version 1.1;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

## 2. 负载均衡算法

```nginx
# 1. 轮询（默认）
upstream backend { server 127.0.0.1:8080; server 127.0.0.1:8081; }

# 2. 加权轮询
upstream backend {
    server 127.0.0.1:8080 weight=5;
    server 127.0.0.1:8081 weight=3;
}

# 3. 最少连接
upstream backend { least_conn; server 127.0.0.1:8080; server 127.0.0.1:8081; }

# 4. IP Hash（会话保持）
upstream backend { ip_hash; server 127.0.0.1:8080; server 127.0.0.1:8081; }
```

## 3. SSL 证书配置

### 3.1 Let's Encrypt 免费证书

```bash
# 安装 certbot
yum install -y certbot python3-certbot-nginx

# 申请证书
certbot --nginx -d your-domain.com -d www.your-domain.com

# 自动续期
certbot renew --dry-run
```

### 3.2 HTTPS 配置

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    # 安全响应头
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location / {
        proxy_pass http://backend_servers;
        # ...
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## 4. 限流配置

### 4.1 请求限流

```nginx
# 定义限流区域
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    location /api/ {
        limit_req zone=api_limit burst=50 nodelay;
        proxy_pass http://backend;
    }
}
```

### 4.2 连接数限流

```nginx
limit_conn_zone $binary_remote_addr zone=addr:10m;

server {
    limit_conn addr 10;
    # 每个 IP 最大 10 个连接
}
```

## 5. 缓存配置

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m 
                 max_size=1g inactive=60m;

server {
    location /api/ {
        proxy_pass http://backend;
        proxy_cache my_cache;
        proxy_cache_valid 200 60m;
        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

## 6. WebSocket 支持

```nginx
location /ws/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
}
```

## 7. 常用命令

```bash
# 测试配置
nginx -t

# 重载配置
nginx -s reload

# 重新打开日志
nginx -s reopen

# 优雅停止
nginx -s quit

# 强制停止
nginx -s stop
```
