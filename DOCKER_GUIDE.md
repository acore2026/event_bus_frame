# Event Bus Framework - Docker 操作指南

本文档介绍如何使用 Docker 和 Docker Compose 部署 Event Bus Framework。

## 目录

- [快速开始](#快速开始)
- [Docker 镜像构建](#docker-镜像构建)
- [Docker Compose 部署](#docker-compose-部署)
- [生产环境部署](#生产环境部署)
- [常见问题](#常见问题)

---

## 快速开始

### 1. 环境要求

- Docker Engine >= 20.10
- Docker Compose >= 1.29
- (可选) Make >= 4.0

### 2. 一键启动

```bash
# 使用帮助脚本
./docker-run.sh up

# 或使用 docker-compose 直接启动
docker-compose up -d
```

启动后访问：
- 事件总线服务: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 订单服务: http://localhost:8001
- 支付服务: http://localhost:8002
- 库存服务: http://localhost:8003

---

## Docker 镜像构建

### 构建脚本使用

我们提供了 `docker-build.sh` 脚本用于构建镜像。

```bash
# 显示帮助
./docker-build.sh help

# 构建所有镜像（本地使用）
./docker-build.sh all

# 构建指定版本
./docker-build.sh -v 1.0.0 all

# 推送到远程仓库
./docker-build.sh -r docker.io/username -v 1.0.0 all
./docker-build.sh push

# 构建单个服务
./docker-build.sh server
./docker-build.sh examples

# 清理镜像
./docker-build.sh clean

# 多平台构建
./docker-build.sh --platform linux/amd64,linux/arm64 all
```

### 手动构建

#### 构建事件总线服务器

```bash
docker build -f Dockerfile.server -t event-bus-server:latest .
```

#### 构建示例服务

```bash
# 订单服务
docker build -f examples/Dockerfile.service \
  --build-arg SERVICE_NAME=order-service \
  --build-arg SERVICE_PORT=8001 \
  --build-arg SERVICE_MODULE=examples.order_service \
  -t event-bus-order-service:latest .

# 支付服务
docker build -f examples/Dockerfile.service \
  --build-arg SERVICE_NAME=payment-service \
  --build-arg SERVICE_PORT=8002 \
  --build-arg SERVICE_MODULE=examples.payment_service \
  -t event-bus-payment-service:latest .

# 库存服务
docker build -f examples/Dockerfile.service \
  --build-arg SERVICE_NAME=inventory-service \
  --build-arg SERVICE_PORT=8003 \
  --build-arg SERVICE_MODULE=examples.inventory_service \
  -t event-bus-inventory-service:latest .
```

---

## Docker Compose 部署

### 基础部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f event-bus

# 停止服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

### 使用帮助脚本

```bash
# 启动系统
./docker-run.sh up

# 构建并启动
./docker-run.sh up-build

# 查看状态
./docker-run.sh status

# 查看日志
./docker-run.sh logs
./docker-run.sh logs-f

# 运行测试
./docker-run.sh test

# 重启服务
./docker-run.sh restart

# 进入容器
./docker-run.sh shell event-bus
./docker-run.sh shell order-service

# 停止并清理
./docker-run.sh down
./docker-run.sh clean
```

### 扩展服务实例

```bash
# 扩展支付服务为3个实例
docker-compose up -d --scale payment-service=3

# 或使用脚本
./docker-run.sh scale payment-service 3
```

---

## 生产环境部署

### 1. 环境变量配置

创建 `.env` 文件：

```bash
# .env
EVENT_BUS_HOST=0.0.0.0
EVENT_BUS_PORT=8000
EVENT_BUS_LOG_LEVEL=INFO
EVENT_BUS_SUBSCRIPTION_TIMEOUT=120
EVENT_BUS_HEARTBEAT_INTERVAL=30

# 客户端配置
EVENT_CLIENT_EVENT_BUS_URL=http://event-bus:8000
EVENT_CLIENT_HEARTBEAT_INTERVAL=30
```

### 2. 使用 Docker Compose 生产配置

创建 `docker-compose.prod.yml`：

```yaml
version: '3.8'

services:
  event-bus:
    image: ${REGISTRY}/event-bus-server:${VERSION:-latest}
    container_name: event-bus-server
    ports:
      - "8000:8000"
    environment:
      - EVENT_BUS_HOST=0.0.0.0
      - EVENT_BUS_PORT=8000
      - EVENT_BUS_LOG_LEVEL=INFO
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    networks:
      - event-bus-network
    restart: always
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  event-bus-network:
    driver: bridge
```

### 3. 部署命令

```bash
# 加载环境变量并部署
docker-compose -f docker-compose.prod.yml --env-file .env up -d

# 滚动更新
docker-compose -f docker-compose.prod.yml up -d --no-deps --build event-bus

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps
```

### 4. 负载均衡配置（Nginx）

创建 `nginx.conf`：

```nginx
upstream event_bus {
    least_conn;
    server event-bus-1:8000;
    server event-bus-2:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://event_bus;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 镜像管理

### 标签策略

| 标签 | 说明 |
|------|------|
| `latest` | 最新稳定版 |
| `v1.0.0` | 语义化版本 |
| `v1.0` | 次要版本 |
| `v1` | 主版本 |
| `git-sha` | Git 提交哈希 |

### 推送镜像到仓库

```bash
# 登录仓库
docker login docker.io

# 构建并打标签
./docker-build.sh -r docker.io/username -v 1.0.0 all

# 推送
./docker-build.sh -r docker.io/username push

# 或手动推送
docker tag event-bus-server:latest docker.io/username/event-bus-server:1.0.0
docker push docker.io/username/event-bus-server:1.0.0
```

### 多平台构建

```bash
# 创建 buildx 构建器
docker buildx create --use --name multiplatform

# 多平台构建并推送
./docker-build.sh --platform linux/amd64,linux/arm64 -r docker.io/username -v 1.0.0 all
```

---

## 监控和日志

### 查看日志

```bash
# 所有服务日志
docker-compose logs

# 实时跟踪
docker-compose logs -f

# 最近100行
docker-compose logs --tail=100 event-bus

# 带时间戳
docker-compose logs -f -t event-bus
```

### 健康检查

```bash
# 检查单个服务
curl http://localhost:8000/health

# 检查所有服务
./docker-run.sh status
```

### 资源监控

```bash
# 查看容器资源使用
docker stats

# 查看特定服务
docker stats event-bus-server
```

---

## 常见问题

### Q: 服务启动失败，提示端口被占用

```bash
# 查找占用端口的进程
sudo lsof -i :8000

# 或使用脚本指定其他端口
EVENT_BUS_PORT=8080 ./docker-run.sh up
```

### Q: 服务间无法通信

确保服务在同一个 Docker 网络中：

```bash
# 查看网络
docker network ls
docker network inspect event-bus-network

# 检查服务名解析
docker-compose exec order-service ping event-bus
```

### Q: 如何修改代码后重新部署

```bash
# 重新构建并启动
./docker-run.sh up-build

# 或仅重建特定服务
docker-compose up -d --build event-bus
```

### Q: 数据持久化

如需持久化数据，添加 volumes：

```yaml
services:
  event-bus:
    volumes:
      - event-bus-data:/app/data

volumes:
  event-bus-data:
```

### Q: 如何进入容器调试

```bash
# 使用脚本
./docker-run.sh shell event-bus

# 或手动
docker-compose exec event-bus /bin/bash
docker-compose exec event-bus python -c "from event_bus import *"
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `Dockerfile.server` | 事件总线服务器镜像 |
| `examples/Dockerfile.service` | 通用服务镜像模板 |
| `docker-compose.yml` | 开发环境编排配置 |
| `docker-compose.prod.yml` | 生产环境编排配置 |
| `docker-build.sh` | 镜像构建脚本 |
| `docker-run.sh` | 容器运行管理脚本 |
| `.dockerignore` | Docker 构建忽略文件 |

---

## 更多资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Event Bus Framework README](./README.md)
