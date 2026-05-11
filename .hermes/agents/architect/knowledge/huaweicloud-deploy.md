# 华为云部署方案

## 华为云核心服务

| 服务 | 说明 | 适用场景 |
|------|------|---------|
| ECS | 云服务器 | 传统部署、自建数据库 |
| CCE | 云容器引擎 | 容器化微服务 |
| SWR | 容器镜像服务 | Docker镜像仓库 |
| RDS | 关系型数据库 | MySQL托管服务 |
| Redis | 缓存服务 | 分布式缓存 |
| ELB | 负载均衡 | 流量分发 |
| VPC | 虚拟私有云 | 网络隔离 |

---

## 方案一：ECS 部署（适合中小项目）

### 架构

```
用户请求 → ELB → ECS集群 → RDS + Redis
```

### 部署步骤

```bash
# 1. 连接ECS
ssh -i key.pem root@ecs-ip

# 2. 安装Docker
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# 3. 编写Dockerfile
FROM openjdk:17-slim
COPY target/app.jar /app/app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

# 4. 构建并运行
docker build -t app:v1 .
docker run -d -p 8080:8080 --name app -e SPRING_PROFILES_ACTIVE=prod app:v1
```

### 应用配置

```yaml
# application-prod.yml
spring:
  datasource:
    url: jdbc:mysql://rds-endpoint:3306/dbname
    username: ${DB_USER}
    password: ${DB_PASSWORD}
  redis:
    host: redis-host
    port: 6379
    password: ${REDIS_PASSWORD}
```

---

## 方案二：CCE 容器化部署（推荐生产环境）

### 架构

```
Internet → ELB → CCE(NodePool) → Pods → RDS + Redis
              ↓
           SWR (镜像仓库)
```

### SWR 镜像推送

```bash
# 1. 登录SWR
docker login -u your-username swr.cn-south-1.myhuaweicloud.com

# 2. 标签镜像
docker tag app:v1 swr.cn-south-1.myhuaweicloud.com/namespace/app:v1

# 3. 推送镜像
docker push swr.cn-south-1.myhuaweicloud.com/namespace/app:v1
```

### Helm Chart 部署

```yaml
# values.yaml
replicaCount: 2

image:
  repository: swr.cn-south-1.myhuaweicloud.com/namespace/app
  tag: v1
  pullPolicy: IfNotPresent

env:
  - name: SPRING_PROFILES_ACTIVE
    value: prod

service:
  type: ClusterIP
  port: 8080

ingress:
  enabled: true
  className: nginx
  annotations:
    kubernetes.io/ingress.class: nginx
  hosts:
    - host: api.example.com
      paths:
        - path: /
          pathType: Prefix
```

```bash
# 部署命令
helm install myapp ./chart -f values.yaml -n production

# 更新
helm upgrade myapp ./chart -f values.yaml -n production
```

---

## 配置管理

### ConfigMap 和 Secret

```yaml
# application-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  db-password: your-db-password
  redis-password: your-redis-password
```

```bash
kubectl create secret generic app-secrets \
  --from-literal=db-password=xxx \
  --from-literal=redis-password=yyy \
  -n production
```

### 配置挂载

```yaml
# deployment.yaml
spec:
  containers:
    - name: app
      env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: db-password
```

---

## 弹性伸缩配置

```yaml
# HPA配置
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## CI/CD 流水线

```yaml
# Jenkinsfile (华为云DevCloud)
pipeline {
    stages {
        stage('Build') {
            steps {
                sh 'mvn clean package -DskipTests'
            }
        }
        stage('Docker Build') {
            steps {
                sh 'docker build -t app:${BUILD_NUMBER} .'
                sh 'docker tag app:${BUILD_NUMBER} swr.cn-south-1.myhuaweicloud.com/namespace/app:${BUILD_NUMBER}'
            }
        }
        stage('Push to SWR') {
            steps {
                sh 'docker push swr.cn-south-1.myhuaweicloud.com/namespace/app:${BUILD_NUMBER}'
            }
        }
        stage('Deploy to CCE') {
            steps {
                sh 'kubectl set image deployment/app app=swr.cn-south-1.myhuaweicloud.com/namespace/app:${BUILD_NUMBER}'
            }
        }
    }
}
```

---

## 网络配置

### VPC 配置

```
VPC: 172.16.0.0/16
├─ Subnet1: 172.16.1.0/24 (应用层)
├─ Subnet2: 172.16.2.0/24 (数据层)
└─ Subnet3: 172.16.3.0/24 (DMZ层)
```

### 安全组规则

| 方向 | 协议 | 端口 | 来源 |
|------|------|------|------|
| 入站 | TCP | 80,443 | 0.0.0.0/0 |
| 入站 | TCP | 22 | 办公IP |
| 出站 | TCP | 3306 | Subnet2 |
| 出站 | TCP | 6379 | Subnet2 |

---

*文档类型：架构设计模式*
*适用范围：运维、后端开发*
*最后更新：2026-04-29*
