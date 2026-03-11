#!/bin/bash
# Docker Build Script for Event Bus Framework

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="${REGISTRY:-}"  # e.g., docker.io/username or gcr.io/project
IMAGE_PREFIX="${IMAGE_PREFIX:-event-bus}"
VERSION="${VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo 'latest')}"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

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

# Help function
show_help() {
    cat << EOF
Event Bus Framework Docker Build Script

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    all         Build all images (default)
    server      Build only the event bus server
    examples    Build example services
    push        Push images to registry
    clean       Remove local images
    help        Show this help message

Options:
    -r, --registry REGISTRY    Docker registry (default: empty, local only)
    -p, --prefix PREFIX        Image name prefix (default: event-bus)
    -v, --version VERSION      Image version tag (default: git describe or latest)
    -n, --no-cache             Build without cache
    --platform PLATFORM        Target platform (e.g., linux/amd64,linux/arm64)

Examples:
    $0                          # Build all images locally
    $0 server                   # Build only server
    $0 -r docker.io/myuser all  # Build and tag for docker.io
    $0 push                     # Push to registry

Environment Variables:
    REGISTRY        Docker registry URL
    IMAGE_PREFIX    Image name prefix
    VERSION         Image version tag
EOF
}

# Parse arguments
NO_CACHE=""
PLATFORM=""
COMMAND="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -p|--prefix)
            IMAGE_PREFIX="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -n|--no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        all|server|examples|push|clean)
            COMMAND="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Set platform flag if specified
PLATFORM_FLAG=""
if [ -n "$PLATFORM" ]; then
    PLATFORM_FLAG="--platform $PLATFORM"
fi

# Full image name helper
get_image_name() {
    local name="$1"
    if [ -n "$REGISTRY" ]; then
        echo "${REGISTRY}/${IMAGE_PREFIX}-${name}:${VERSION}"
    else
        echo "${IMAGE_PREFIX}-${name}:${VERSION}"
    fi
}

# Build server image
build_server() {
    log_info "Building Event Bus Server image..."

    local image_name=$(get_image_name "server")

    docker build \
        $NO_CACHE \
        $PLATFORM_FLAG \
        --file Dockerfile.server \
        --tag "$image_name" \
        --tag "${image_name%:*}:latest" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VERSION="$VERSION" \
        .

    log_success "Server image built: $image_name"
}

# Build example services
build_examples() {
    log_info "Building example service images..."

    # Order Service
    log_info "Building Order Service..."
    docker build \
        $NO_CACHE \
        $PLATFORM_FLAG \
        --file examples/Dockerfile.service \
        --tag "$(get_image_name order-service)" \
        --tag "${IMAGE_PREFIX}-order-service:latest" \
        --build-arg SERVICE_NAME=order-service \
        --build-arg SERVICE_PORT=8001 \
        --build-arg SERVICE_MODULE=examples.order_service \
        .

    # Payment Service
    log_info "Building Payment Service..."
    docker build \
        $NO_CACHE \
        $PLATFORM_FLAG \
        --file examples/Dockerfile.service \
        --tag "$(get_image_name payment-service)" \
        --tag "${IMAGE_PREFIX}-payment-service:latest" \
        --build-arg SERVICE_NAME=payment-service \
        --build-arg SERVICE_PORT=8002 \
        --build-arg SERVICE_MODULE=examples.payment_service \
        .

    # Inventory Service
    log_info "Building Inventory Service..."
    docker build \
        $NO_CACHE \
        $PLATFORM_FLAG \
        --file examples/Dockerfile.service \
        --tag "$(get_image_name inventory-service)" \
        --tag "${IMAGE_PREFIX}-inventory-service:latest" \
        --build-arg SERVICE_NAME=inventory-service \
        --build-arg SERVICE_PORT=8003 \
        --build-arg SERVICE_MODULE=examples.inventory_service \
        .

    log_success "Example services built successfully"
}

# Push images
push_images() {
    log_info "Pushing images to registry..."

    if [ -z "$REGISTRY" ]; then
        log_warn "No registry specified, skipping push"
        return
    fi

    # Push server
    docker push "$(get_image_name server)"
    docker push "${IMAGE_PREFIX}-server:latest"

    # Push examples
    docker push "$(get_image_name order-service)"
    docker push "$(get_image_name payment-service)"
    docker push "$(get_image_name inventory-service)"

    log_success "All images pushed to $REGISTRY"
}

# Clean images
clean_images() {
    log_info "Removing local images..."

    docker rmi -f "$(get_image_name server)" 2>/dev/null || true
    docker rmi -f "${IMAGE_PREFIX}-server:latest" 2>/dev/null || true
    docker rmi -f "$(get_image_name order-service)" 2>/dev/null || true
    docker rmi -f "$(get_image_name payment-service)" 2>/dev/null || true
    docker rmi -f "$(get_image_name inventory-service)" 2>/dev/null || true

    # Clean dangling images
    docker image prune -f

    log_success "Images cleaned"
}

# Main execution
case $COMMAND in
    all)
        log_info "Building all images (version: $VERSION)..."
        build_server
        build_examples
        log_success "All images built successfully!"
        ;;
    server)
        build_server
        ;;
    examples)
        build_examples
        ;;
    push)
        push_images
        ;;
    clean)
        clean_images
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
