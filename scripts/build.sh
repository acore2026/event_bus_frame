#!/bin/bash

# 构建 Docker 镜像脚本

set -e

# 镜像配置
IMAGE_NAME="${IMAGE_NAME:-event-bus-frame}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-}"

# 完整镜像名称
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
fi

echo "========================================"
echo "Building Docker Image"
echo "========================================"
echo "Image Name: $FULL_IMAGE_NAME"
echo ""

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 切换到项目根目录
cd "$PROJECT_DIR"

# 构建镜像
echo "Building..."
docker build -t "$FULL_IMAGE_NAME" -f Dockerfile .

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Build successful!"
    echo "Image: $FULL_IMAGE_NAME"
    echo ""
    echo "To run the container:"
    echo "  docker run --rm $FULL_IMAGE_NAME"
    echo ""
    echo "To push to registry:"
    echo "  docker push $FULL_IMAGE_NAME"
else
    echo "✗ Build failed!"
    exit 1
fi
