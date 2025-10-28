#!/bin/bash

echo "🔥 Starting BADSHAH Trading Bot Build..."

# Clean old data to ensure fresh start
echo "🧹 Cleaning old trade history data..."
rm -f data/trade_history.csv
echo "✅ Old data cleaned!"

# Create fresh directories
echo "📁 Creating fresh directories..."
mkdir -p logs
mkdir -p data
echo "✅ Directories created!"

# Install Python dependencies
echo "📦 Installing dependencies..."
pip install -r requirements_render.txt
echo "✅ Dependencies installed!"

echo "🎉 Build complete! Bot ready to start fresh!"

