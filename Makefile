# Event Bus Framework - Makefile
# 简化 Docker 和 Docker Compose 操作

.PHONY: help build build-server build-examples up down restart logs test clean push

# 变量
REGISTRY ?=
VERSION ?= latest
IMAGE_PREFIX ?= event-bus
COMPOSE_FILE = docker-compose.yml
PROJECT_NAME = event-bus

# 默认目标
help: ## 显示帮助信息
	@echo "Event Bus Framework - 可用命令:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "环境变量:"
	@echo "  REGISTRY    - Docker 仓库地址 (默认: 空)"
	@echo "  VERSION     - 镜像版本标签 (默认: latest)"
	@echo "  IMAGE_PREFIX - 镜像名前缀 (默认: event-bus)"

# 构建
build: ## 构建所有镜像
	./docker-build.sh -v $(VERSION) all

build-server: ## 仅构建服务器镜像
	./docker-build.sh -v $(VERSION) server

build-examples: ## 构建示例服务镜像
	./docker-build.sh -v $(VERSION) examples

# 运行
up: ## 启动所有服务
	./docker-run.sh up

up-build: ## 构建并启动所有服务
	./docker-run.sh up-build

down: ## 停止所有服务
	./docker-run.sh down

restart: ## 重启所有服务
	./docker-run.sh restart

# 监控
logs: ## 查看日志
	./docker-run.sh logs

logs-f: ## 实时跟踪日志
	./docker-run.sh logs-f

status: ## 查看服务状态
	./docker-run.sh status

ps: ## 列出运行中的容器
	./docker-run.sh ps

# 测试
test: ## 运行 API 测试
	./docker-run.sh test

# 清理
clean: ## 清理容器和镜像
	./docker-run.sh clean

# 推送
push: ## 推送镜像到仓库
	./docker-build.sh -r $(REGISTRY) -v $(VERSION) push

# 开发命令
shell: ## 进入 event-bus 容器
	./docker-run.sh shell event-bus

fmt: ## 格式化代码
	black event_bus/ examples/ --line-length 100

lint: ## 代码检查
	flake8 event_bus/ examples/ --max-line-length 100

# CI/CD 命令
ci-build: ## CI 构建
	./docker-build.sh -v $(VERSION) all

ci-test: ## CI 测试
	./docker-run.sh up
	./docker-run.sh test
	./docker-run.sh down

ci-push: ## CI 推送
	./docker-build.sh -r $(REGISTRY) -v $(VERSION) push
