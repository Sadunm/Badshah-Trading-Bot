#!/bin/bash

# Badshah Trading Bot - Cloud Deployment Script
# Supports: AWS EC2, DigitalOcean, Google Cloud, any Linux VPS

set -e  # Exit on error

echo "============================================"
echo "  BADSHAH TRADING BOT - CLOUD DEPLOYMENT"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first:"
    echo "  curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first:"
    echo "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "  sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"
echo ""

# Navigate to deployment directory
cd "$(dirname "$0")"

# Create necessary directories
echo "Creating directories..."
mkdir -p logs reports data
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Build the Docker image
echo "Building Docker image..."
if docker-compose build; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build Docker image${NC}"
    exit 1
fi
echo ""

# Start the trading bot
echo "Starting trading bot..."
if docker-compose up -d; then
    echo -e "${GREEN}✓ Trading bot started successfully${NC}"
else
    echo -e "${RED}✗ Failed to start trading bot${NC}"
    exit 1
fi
echo ""

# Show status
echo "============================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================"
echo ""
echo "Container status:"
docker-compose ps
echo ""
echo -e "${GREEN}Trading bot is now running in the background${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:        docker-compose logs -f trading-bot"
echo "  Stop bot:         docker-compose stop"
echo "  Start bot:        docker-compose start"
echo "  Restart bot:      docker-compose restart"
echo "  Remove bot:       docker-compose down"
echo "  Update bot:       git pull && docker-compose up -d --build"
echo ""
echo "Log files are saved in: ./logs/"
echo "Reports are saved in: ./reports/"
echo ""

