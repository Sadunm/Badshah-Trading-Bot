# Badshah Trading Bot - Railway Deployment
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    ldconfig && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements_render.txt .
RUN pip install --no-cache-dir -r requirements_render.txt

# Copy application files
COPY start_live_multi_coin_trading.py .
COPY performance_tracker.py .
COPY config/ config/
COPY src/ src/
COPY strategies/ strategies/

# Create necessary directories with clean state
RUN mkdir -p /app/logs /app/reports /app/data && \
    rm -f /app/data/*.csv && \
    echo "✅ Fresh data directories created"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Run the bot with fresh start
CMD ["sh", "-c", "rm -f /app/data/*.csv /app/logs/*.log && python -u start_live_multi_coin_trading.py"]


