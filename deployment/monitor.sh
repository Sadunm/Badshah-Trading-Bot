#!/bin/bash

# Badshah Trading Bot - Monitoring Script
# Monitor bot performance and health

echo "======================================"
echo "  BADSHAH TRADING BOT - MONITOR"
echo "======================================"
echo ""

# Navigate to deployment directory
cd "$(dirname "$0")"

# Check if bot is running
if ! docker-compose ps | grep -q "Up"; then
    echo "[ERROR] Trading bot is not running!"
    echo "Start it with: docker-compose up -d"
    exit 1
fi

echo "[OK] Trading bot is running"
echo ""

# Show resource usage
echo "Resource Usage:"
echo "---------------"
docker stats --no-stream badshah-trading-bot
echo ""

# Show recent logs
echo "Recent Logs (last 50 lines):"
echo "----------------------------"
docker-compose logs --tail=50 trading-bot
echo ""

# Check for errors in logs
ERROR_COUNT=$(docker-compose logs trading-bot | grep -i "error" | wc -l)
WARNING_COUNT=$(docker-compose logs trading-bot | grep -i "warning" | wc -l)

echo "Log Summary:"
echo "------------"
echo "Errors: $ERROR_COUNT"
echo "Warnings: $WARNING_COUNT"
echo ""

# Show latest report if exists
if [ -f "reports/daily_report.txt" ]; then
    echo "Latest Daily Report:"
    echo "--------------------"
    cat reports/daily_report.txt
    echo ""
fi

# Show disk usage
echo "Disk Usage:"
echo "-----------"
du -sh logs/ reports/ data/ 2>/dev/null || echo "No data yet"
echo ""

echo "For live logs, run: docker-compose logs -f trading-bot"


