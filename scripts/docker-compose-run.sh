#!/bin/bash

# 使用 Docker Compose 启动完整服务

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "========================================"
echo "Docker Compose 管理脚本"
echo "========================================"
echo ""

show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  up       - 启动所有服务（后台运行）"
    echo "  up-fg    - 启动所有服务（前台运行）"
    echo "  down     - 停止并删除所有服务"
    echo "  restart  - 重启所有服务"
    echo "  logs     - 查看日志"
    echo "  build    - 重新构建镜像"
    echo "  ps       - 查看运行状态"
    echo "  shell    - 进入容器 shell"
    echo ""
}

case "${1:-}" in
    up)
        echo "Starting services in background..."
        docker-compose up -d
        echo ""
        echo "Services started!"
        echo "RabbitMQ Management UI: http://localhost:15672"
        echo "  Username: guest"
        echo "  Password: guest"
        ;;
    up-fg)
        echo "Starting services in foreground..."
        echo "Press Ctrl+C to stop"
        echo ""
        docker-compose up
        ;;
    down)
        echo "Stopping services..."
        docker-compose down
        echo "✓ Services stopped"
        ;;
    restart)
        echo "Restarting services..."
        docker-compose restart
        echo "✓ Services restarted"
        ;;
    logs)
        docker-compose logs -f
        ;;
    build)
        echo "Rebuilding images..."
        docker-compose build --no-cache
        echo "✓ Build complete"
        ;;
    ps)
        docker-compose ps
        ;;
    shell)
        docker-compose exec event-service /bin/bash
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
