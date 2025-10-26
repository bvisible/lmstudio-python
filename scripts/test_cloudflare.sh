#!/bin/bash
# Quick test script for Cloudflare WAF integration
#
# This script loads environment variables from .env and runs
# the Cloudflare integration test suite.
#
# Usage:
#   ./scripts/test_cloudflare.sh           # Run all Cloudflare tests
#   ./scripts/test_cloudflare.sh -v        # Verbose output
#   ./scripts/test_cloudflare.sh -k test_  # Run specific tests

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo ""
    echo "Please create .env from the template:"
    echo "  1. cp .env.example .env"
    echo "  2. Edit .env and fill in your credentials:"
    echo "     - LMSTUDIO_CLOUDFLARE_HOST=lmstudio.noraai.ch:443"
    echo "     - LMSTUDIO_X_API_KEY=<your-api-key>"
    echo ""
    exit 1
fi

# Load environment variables
echo -e "${YELLOW}Loading environment variables from .env...${NC}"
set -a  # automatically export all variables
source .env
set +a

# Check required variables
if [ -z "$LMSTUDIO_CLOUDFLARE_HOST" ]; then
    echo -e "${RED}Error: LMSTUDIO_CLOUDFLARE_HOST not set in .env${NC}"
    exit 1
fi

if [ -z "$LMSTUDIO_X_API_KEY" ]; then
    echo -e "${RED}Error: LMSTUDIO_X_API_KEY not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment variables loaded${NC}"
echo "  Host: $LMSTUDIO_CLOUDFLARE_HOST"
echo "  API Key: ${LMSTUDIO_X_API_KEY:0:10}... (masked)"
echo ""

# Quick connection test
echo -e "${YELLOW}Testing connection to Cloudflare instance...${NC}"
if python -c "
import os
import sys
try:
    from lmstudio import Client
    client = Client(
        os.environ['LMSTUDIO_CLOUDFLARE_HOST'],
        x_api_key=os.environ['LMSTUDIO_X_API_KEY']
    )
    print('✅ Successfully connected to', client.api_host)
    client.close()
    sys.exit(0)
except Exception as e:
    print('❌ Connection failed:', str(e))
    sys.exit(1)
" 2>&1; then
    echo -e "${GREEN}✓ Connection test passed${NC}"
    echo ""
else
    echo -e "${RED}✗ Connection test failed${NC}"
    echo ""
    echo "Please verify:"
    echo "  - Your host is correct: $LMSTUDIO_CLOUDFLARE_HOST"
    echo "  - Your API key is valid"
    echo "  - The server is running"
    echo ""
    exit 1
fi

# Check if tox is available
if command -v tox &> /dev/null; then
    echo -e "${YELLOW}Running tests with tox...${NC}"
    tox -m test -- tests/test_cloudflare_integration.py "$@"
elif command -v pytest &> /dev/null; then
    echo -e "${YELLOW}tox not found, using pytest directly...${NC}"
    pytest tests/test_cloudflare_integration.py "$@"
else
    echo -e "${RED}Error: Neither tox nor pytest found${NC}"
    echo "Please install test dependencies:"
    echo "  pip install tox tox-pdm"
    echo "  or"
    echo "  pip install pytest pytest-asyncio"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ All Cloudflare integration tests completed${NC}"
