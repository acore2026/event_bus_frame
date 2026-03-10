# Docker 部署指南

## 文件说明

| 文件 | 说明 |
|------|------|
| `Dockerfile` | Docker 镜像构建文件 |
| `.dockerignore` | 排除不需要打包的文件 |
| `docker-compose.yml` | Docker Compose 配置（含 RabbitMQ） |
| `scripts/build.sh` | 构建镜像脚本 |
| `scripts/run.sh` | 运行容器脚本 |
| `scripts/docker-compose-run.sh` | Docker Compose 管理脚本 |

## 快速开始

### 方法 1：使用 Docker Compose（推荐）

启动所有服务（包含 RabbitMQ）：

```bash
./scripts/docker-compose-run.sh up
```

访问 RabbitMQ 管理界面：
- URL: http://localhost:15672
- 用户名: guest
- 密码: guest

### 方法 2：使用独立容器

**构建镜像：**

```bash
./scripts/build.sh
```

**运行容器：**

```bash
./scripts/run.sh
```

## 常用命令

### Docker Compose 管理

```bash
# 启动服务（后台）
./scripts/docker-compose-run.sh up

# 启动服务（前台）
./scripts/docker-compose-run.sh up-fg

# 查看日志
./scripts/docker-compose-run.sh logs

# 停止服务
./scripts/docker-compose-run.sh down

# 重启服务
./scripts/docker-compose-run.sh restart

# 重新构建
./scripts/docker-compose-run.sh build

# 进入容器
./scripts/docker-compose-run.sh shell
```

### Docker 命令

```bash
# 构建镜像
docker build -t event-bus-frame:latest .

# 运行容器
docker run -d \
  -e RABBITMQ_HOST=localhost \
  -e RABBITMQ_PORT=5672 \
  -e RABBITMQ_USER=guest \
  -e RABBITMQ_PASS=guest \
  --name event-bus-frame \
  event-bus-frame:latest

# 查看日志
docker logs -f event-bus-frame

# 停止容器
docker stop event-bus-frame

# 删除容器
docker rm event-bus-frame
```

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `RABBITMQ_HOST` | localhost | RabbitMQ 主机地址 |
| `RABBITMQ_PORT` | 5672 | RabbitMQ 端口 |
| `RABBITMQ_USER` | guest | RabbitMQ 用户名 |
| `RABBITMQ_PASS` | guest | RabbitMQ 密码 |
| `RABBITMQ_VHOST` | / | RabbitMQ 虚拟主机 |

## 推送镜像到仓库

```bash
# 设置仓库地址
export REGISTRY=your-registry.com

# 构建镜像
./scripts/build.sh

# 推送镜像
docker push ${REGISTRY}/event-bus-frame:latest
```
