#!/bin/bash
# Event Bus Framework 测试运行脚本

set -e

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Event Bus Framework 测试套件${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python3 未安装${NC}"
    exit 1
fi

# 检查依赖
echo -e "${YELLOW}检查依赖...${NC}"
python3 -c "import httpx, fastapi" 2>/dev/null || {
    echo -e "${YELLOW}安装依赖...${NC}"
    pip install -q httpx fastapi uvicorn pydantic pydantic-settings 2>/dev/null || {
        echo -e "${RED}无法安装依赖，请手动运行: pip install -r requirements.txt${NC}"
        exit 1
    }
}

# 运行测试
echo -e "${YELLOW}运行测试...${NC}"
echo ""

if python3 test_event_bus.py "$@"; then
    echo ""
    echo -e "${GREEN}✓ 所有测试通过!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ 测试失败${NC}"
    exit 1
fi
