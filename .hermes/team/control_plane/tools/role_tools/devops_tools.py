from __future__ import annotations

from typing import Dict

from tools.spec import ToolExecutionContext, ToolResult


def generate_dockerfile_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    app_type = str(payload.get("app_type", "spring-boot"))
    app_name = str(payload.get("app_name", "app"))
    port = int(payload.get("port", 8080))
    
    if app_type == "spring-boot":
        dockerfile = f'''FROM eclipse-temurin:17-jdk-alpine AS builder
WORKDIR /app
COPY . .
RUN ./mvnw clean package -DskipTests

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar
EXPOSE {port}
ENTRYPOINT ["java", "-jar", "app.jar"]
'''
    elif app_type == "vue":
        dockerfile = f'''FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE {port}
CMD ["nginx", "-g", "daemon off;"]
'''
    else:
        dockerfile = f'''FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["python", "app.py"]
'''
    
    return ToolResult.ok_result(
        content=dockerfile,
        structured_data={"app_type": app_type, "port": port},
        artifacts=[],
    )


def generate_k8s_manifests_handler(context: ToolExecutionContext, payload: Dict[str, object]) -> ToolResult:
    service_name = str(payload.get("service_name", "example"))
    image = str(payload.get("image", f"{service_name}:latest"))
    port = int(payload.get("port", 8080))
    replicas = int(payload.get("replicas", 3))
    
    manifest = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {service_name}
  template:
    metadata:
      labels:
        app: {service_name}
    spec:
      containers:
      - name: {service_name}
        image: {image}
        ports:
        - containerPort: {port}
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: {service_name}
spec:
  selector:
    app: {service_name}
  ports:
  - port: {port}
    targetPort: {port}
  type: ClusterIP
'''
    return ToolResult.ok_result(
        content=manifest,
        structured_data={"service_name": service_name, "replicas": replicas},
        artifacts=[],
    )
