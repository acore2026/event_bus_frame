#!/bin/bash
# Docker Run Helper Script for Event Bus Framework

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="event-bus"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help
show_help() {
    cat << EOF
Event Bus Framework Docker Run Script

Usage: $0 [COMMAND]

Commands:
    up              Start all services with docker-compose
    up-build        Build and start all services
    down            Stop all services
    restart         Restart all services
    logs            Show logs from all services
    logs-f          Follow logs from all services
    ps              Show running containers
    status          Show service status
    test            Run API tests against running services
    shell           Open shell in event-bus container
    clean           Stop and remove all containers and volumes
    help            Show this help message

Examples:
    $0 up           # Start the system
    $0 logs-f       # Follow logs
    $0 test         # Run API tests
    $0 clean        # Clean up everything

Individual Service Commands:
    $0 start-server     # Start only event bus server
    $0 stop-server      # Stop event bus server
EOF
}

# Check if docker-compose is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose is not installed"
        exit 1
    fi
}

# Start all services
up() {
    log_info "Starting Event Bus Framework services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d
    log_success "Services started!"
    status

    echo ""
    log_info "Service URLs:"
    echo "  Event Bus Server: http://localhost:8000"
    echo "  Order Service:    http://localhost:8001"
    echo "  Payment Service:  http://localhost:8002"
    echo "  Inventory Service: http://localhost:8003"
    echo "  API Docs:         http://localhost:8000/docs"
}

# Build and start
up_build() {
    log_info "Building and starting services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up --build -d
    log_success "Services built and started!"
    status
}

# Stop all services
down() {
    log_info "Stopping services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down
    log_success "Services stopped"
}

# Restart services
restart() {
    log_info "Restarting services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart
    log_success "Services restarted"
    status
}

# Show logs
logs() {
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs
}

# Follow logs
logs_f() {
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f
}

# Show running containers
ps() {
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
}

# Show status
status() {
    echo ""
    echo "Service Status:"
    echo "---------------"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps

    # Check health endpoints
    echo ""
    echo "Health Checks:"
    echo "---------------"

    services=("8000:event-bus" "8001:order-service" "8002:payment-service" "8003:inventory-service")

    for service in "${services[@]}"; do
        port="${service%%:*}"
        name="${service##*:}"

        if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null | grep -q "200"; then
            echo -e "  $name (port $port): ${GREEN}✓ Healthy${NC}"
        else
            echo -e "  $name (port $port): ${YELLOW}✗ Not Ready${NC}"
        fi
    done
}

# Run API tests
test() {
    log_info "Running API tests..."

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 5

    # Check if event bus is accessible
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_error "Event Bus Server is not accessible at http://localhost:8000"
        log_info "Make sure services are running with: $0 up"
        exit 1
    fi

    # Run tests in docker or locally
    if [ -f "test_api.py" ]; then
        log_info "Running local test script..."
        python3 test_api.py --url http://localhost:8000
    else
        log_info "Running tests with curl..."

        # Test health
        echo ""
        echo "1. Health Check"
        curl -s http://localhost:8000/health | jq . 2>/dev/null || curl -s http://localhost:8000/health

        # Test subscribe
        echo ""
        echo "2. Subscribe"
        curl -s -X POST http://localhost:8000/api/v1/subscribe \
            -H "Content-Type: application/json" \
            -d '{"service_name":"test-service","service_url":"http://test:9000/webhook","event_types":["broadcast","topic"],"topics":["test"]}' | jq . 2>/dev/null || true

        # Test publish
        echo ""
        echo "3. Publish Event"
        curl -s -X POST http://localhost:8000/api/v1/publish \
            -H "Content-Type: application/json" \
            -d '{"event_type":"broadcast","payload":{"message":"Hello Docker!"}}' | jq . 2>/dev/null || true

        # Test stats
        echo ""
        echo "4. Stats"
        curl -s http://localhost:8000/api/v1/stats | jq . 2>/dev/null || curl -s http://localhost:8000/api/v1/stats

        echo ""
        log_success "Basic tests completed"
    fi
}

# Open shell in container
shell() {
    local service="${1:-event-bus}"
    log_info "Opening shell in $service container..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME exec $service /bin/bash || \
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME exec $service /bin/sh
}

# Clean everything
clean() {
    log_warn "This will remove all containers, networks, and volumes!"
    read -p "Are you sure? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down -v --remove-orphans
        docker system prune -f
        log_success "Cleanup complete"
    else
        log_info "Cancelled"
    fi
}

# Scale service
scale() {
    local service=$1
    local count=$2

    if [ -z "$service" ] || [ -z "$count" ]; then
        log_error "Usage: $0 scale <service> <count>"
        log_info "Example: $0 scale payment-service 3"
        exit 1
    fi

    log_info "Scaling $service to $count instances..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --scale $service=$count
    log_success "Scaled $service to $count instances"
}

# Main
case "${1:-help}" in
    up)
        check_docker
        up
        ;;
    up-build)
        check_docker
        up_build
        ;;
    down)
        check_docker
        down
        ;;
    restart)
        check_docker
        restart
        ;;
    logs)
        logs
        ;;
    logs-f)
        logs_f
        ;;
    ps)
        ps
        ;;
    status)
        status
        ;;
    test)
        test
        ;;
    shell)
        shell "$2"
        ;;
    clean)
        clean
        ;;
    scale)
        scale "$2" "$3"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
