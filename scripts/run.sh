#!/bin/bash

# 运行 Docker 容器脚本

set -e

# 配置
IMAGE_NAME="${IMAGE_NAME:-event-bus-frame}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_NAME="${CONTAINER_NAME:-event-bus-frame-container}"

# RabbitMQ 连接配置
RABBITMQ_HOST="${RABBITMQ_HOST:-localhost}"
RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"
RABBITMQ_USER="${RABBITMQ_USER:-guest}"
RABBITMQ_PASS="${RABBITMQ_PASS:-guest}"
RABBITMQ_VHOST="${RABBITMQ_VHOST:-/}"

echo "========================================"
echo "Running Docker Container"
echo "========================================"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Container: $CONTAINER_NAME"
echo "RabbitMQ Host: $RABBITMQ_HOST"
echo ""

# 停止并删除已存在的容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

# 运行容器
echo "Starting container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -e RABBITMQ_HOST="$RABBITMQ_HOST" \
    -e RABBITMQ_PORT="$RABBITMQ_PORT" \
    -e RABBITMQ_USER="$RABBITMQ_USER" \
    -e RABBITMQ_PASS="$RABBITMQ_PASS" \
    -e RABBITMQ_VHOST="$RABBITMQ_VHOST" \
    --network host \
    "${IMAGE_NAME}:${IMAGE_TAG}"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Container started successfully!"
    echo ""
    echo "View logs:"
    echo "  docker logs -f $CONTAINER_NAME"
    echo ""
    echo "Stop container:"
    echo "  docker stop $CONTAINER_NAME"
else
    echo "✗ Failed to start container!"
    exit 1
fi
