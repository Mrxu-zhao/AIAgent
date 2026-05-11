# 华为云 ECS + SWR 部署实战

## 概述

本文档介绍如何在华为云上部署 Spring Boot 应用，包括 ECS 云服务器配置、SWR 容器镜像服务使用、以及生产环境部署流程。

## 1. 华为云资源规划

| 资源类型 | 规格 | 说明 |
|---------|------|------|
| ECS | 2核4G | 最小生产配置 |
| 磁盘 | 40GB SSD云硬盘 | 系统盘 |
| 安全组 | 22/80/443/3306/6379/8080 | 端口放通 |
| SWR | 企业版/基础版 | 容器镜像仓库 |

## 2. ECS 云服务器初始化

### 2.1 系统初始化脚本

```bash
#!/bin/bash
# init_ecs.sh - ECS 初始化脚本

set -e

echo "========== 开始初始化 ECS =========="

# 1. 更新系统
yum update -y

# 2. 安装基础软件
yum install -y wget curl vim git unzip net-tools

# 3. 安装 Docker
yum install -y yum-utils device-mapper-persistent-data lvm2
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io

# 4. 启动 Docker
systemctl start docker
systemctl enable docker

# 5. 配置 Docker
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["https://f0f3859b.m.daocloud.io"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  }
}
EOF

systemctl daemon-reload
systemctl restart docker

# 6. 创建数据目录
mkdir -p /data/{mysql,redis,logs,backups}
chmod -R 777 /data

echo "========== ECS 初始化完成 =========="
```

## 3. SWR 容器镜像服务

### 3.1 SWR 控制台操作

1. 登录华为云控制台 → 容器镜像服务 SWR
2. 创建组织（命名空间）
3. 获取登录凭证

### 3.2 登录 SWR

```bash
REGISTRY_ENDPOINT="swr.cn-north-4.myhuaweicloud.com"

docker login -u "cn-north-4@YOUR_ACCESS_KEY_ID" \
  -p "YOUR_SECRET_ACCESS_KEY" \
  $REGISTRY_ENDPOINT
```

### 3.3 构建并推送镜像

```bash
# 构建镜像
docker build -t myapp:1.0.0 ./app

# 打标签
REGISTRY_ENDPOINT="swr.cn-north-4.myhuaweicloud.com"
ORGANIZATION="mycompany"
docker tag myapp:1.0.0 ${REGISTRY_ENDPOINT}/${ORGANIZATION}/myapp:1.0.0

# 推送镜像
docker push ${REGISTRY_ENDPOINT}/${ORGANIZATION}/myapp:1.0.0
```

## 4. 部署脚本

```bash
#!/bin/bash
# deploy.sh - 一键部署脚本

set -e

REGION="cn-north-4"
REGISTRY_ENDPOINT="swr.cn-north-4.myhuaweicloud.com"
ORGANIZATION="mycompany"
IMAGE_NAME="myapp"
IMAGE_TAG="${1:-latest}"
CONTAINER_NAME="myapp"

echo "========== 开始部署应用 =========="

# 1. 登录镜像仓库
docker login -u "cn-north-4@${ACCESS_KEY_ID}" \
  -p "${ACCESS_KEY_SECRET}" \
  ${REGISTRY_ENDPOINT}

# 2. 拉取镜像
docker pull ${REGISTRY_ENDPOINT}/${ORGANIZATION}/${IMAGE_NAME}:${IMAGE_TAG}

# 3. 停止旧容器
docker stop ${CONTAINER_NAME} 2>/dev/null || true
docker rm ${CONTAINER_NAME} 2>/dev/null || true

# 4. 运行新容器
docker run -d \
  --name ${CONTAINER_NAME} \
  --restart unless-stopped \
  -p 8080:8080 \
  -v /data/logs:/app/logs \
  -e SPRING_PROFILES_ACTIVE=prod \
  -e JAVA_OPTS="-Xms512m -Xmx1024m" \
  --memory=1g \
  ${REGISTRY_ENDPOINT}/${ORGANIZATION}/${IMAGE_NAME}:${IMAGE_TAG}

# 5. 健康检查
echo "等待应用启动..."
for i in {1..30}; do
    if curl -sf http://localhost:8080/actuator/health > /dev/null 2>&1; then
        echo "✅ 健康检查通过"
        exit 0
    fi
    echo "等待... ($i/30)"
    sleep 2
done

echo "❌ 健康检查超时"
exit 1
```

## 5. 华为云 ECS 安全组配置

```
1. 登录华为云控制台 → 弹性云服务器 ECS
2. 选择目标 ECS → 安全组 → 配置规则
3. 添加入站规则：
   - 协议：TCP
   - 端口：80,443,8080
   - 来源：0.0.0.0/0
4. 保存规则
```

## 6. Nginx 配置

```nginx
upstream backend {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 7. 常见问题排查

### 7.1 镜像拉取失败

```bash
# 检查登录状态
docker login -u "cn-north-4@AK" -p "SK" swr.cn-north-4.myhuaweicloud.com

# 检查镜像是否存在
docker images | grep myapp
```

### 7.2 端口无法访问

```bash
# 检查安全组配置
# 控制台 → ECS → 安全组 → 添加入站规则

# 检查防火墙
firewall-cmd --list-all
```
