# 🚀 Cloud Deployment Guide - Badshah Trading Bot

## Overview
This guide will help you deploy the trading bot to the cloud for 24/7 operation.

## Supported Platforms
- ✅ AWS EC2
- ✅ DigitalOcean Droplets
- ✅ Google Cloud Compute Engine
- ✅ Microsoft Azure VMs
- ✅ Any Linux VPS

---

## Quick Start (Linux/Mac)

### 1. Install Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and log back in
```

### 2. Install Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 3. Deploy Bot
```bash
cd deployment
chmod +x deploy.sh
./deploy.sh
```

### 4. Monitor Bot
```bash
chmod +x monitor.sh
./monitor.sh
```

---

## Quick Start (Windows)

### 1. Install Docker Desktop
Download and install from: https://www.docker.com/products/docker-desktop

### 2. Deploy Bot
```bash
cd deployment
deploy.bat
```

### 3. Monitor Bot
```bash
monitor.bat
```

---

## Detailed Setup

### AWS EC2 Deployment

#### Step 1: Launch EC2 Instance
1. Go to AWS Console → EC2
2. Launch Instance:
   - **AMI**: Ubuntu 22.04 LTS
   - **Instance Type**: t3.medium (2 vCPU, 4GB RAM) - Recommended
   - **Storage**: 20GB gp3 SSD
3. Configure Security Group:
   - Allow SSH (port 22) from your IP
   - Allow HTTPS (port 443) if using API webhooks
4. Create and download keypair

#### Step 2: Connect to Instance
```bash
chmod 400 your-keypair.pem
ssh -i your-keypair.pem ubuntu@your-instance-ip
```

#### Step 3: Install Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in
exit
```

#### Step 4: Upload Bot Code
```bash
# From your local machine
scp -i your-keypair.pem -r BADSHAH\ TRADEINGGG ubuntu@your-instance-ip:~/
```

OR clone from Git:
```bash
# On EC2 instance
git clone <your-repo-url>
cd BADSHAH\ TRADEINGGG
```

#### Step 5: Configure API Keys
```bash
nano config/adaptive_config.json
# Update API keys (or keep testnet for paper trading)
```

#### Step 6: Deploy
```bash
cd deployment
chmod +x deploy.sh
./deploy.sh
```

---

### DigitalOcean Deployment

#### Step 1: Create Droplet
1. Go to DigitalOcean → Create → Droplets
2. Choose:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic - $24/month (2 vCPU, 4GB RAM)
   - **Datacenter**: Choose closest to you
3. Add SSH key
4. Create Droplet

#### Step 2: Connect and Deploy
```bash
ssh root@your-droplet-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Upload or clone code
git clone <your-repo-url>
cd BADSHAH\ TRADEINGGG/deployment

# Deploy
chmod +x deploy.sh
./deploy.sh
```

---

## Configuration

### Risk Management Settings
Edit `config/adaptive_config.json`:

```json
{
  "safety_limits": {
    "max_daily_trades": 20,
    "max_concurrent_positions": 5,
    "emergency_stop_loss": 0.05,  // 5% emergency stop
    "position_size_limit": 0.01    // 1% per trade
  },
  "trading_settings": {
    "risk_per_trade_pct": 0.01,     // 1% risk per trade
    "max_exposure_pct": 0.20,        // 20% max exposure
    "daily_stop_loss_pct": 0.02      // 2% daily loss limit
  }
}
```

### Trading Hours (Optional)
To run bot only during specific hours, edit `start_live_multi_coin_trading.py`:

```python
# Add at the start of trading loop
from datetime import datetime

current_hour = datetime.now().hour
if current_hour < 9 or current_hour > 21:  # Trade 9 AM - 9 PM
    logger.info("Outside trading hours, sleeping...")
    time.sleep(3600)  # Sleep 1 hour
    continue
```

---

## Management Commands

### View Live Logs
```bash
docker-compose logs -f trading-bot
```

### Stop Bot
```bash
docker-compose stop
```

### Start Bot
```bash
docker-compose start
```

### Restart Bot
```bash
docker-compose restart
```

### Update Bot (after code changes)
```bash
git pull  # If using git
docker-compose up -d --build
```

### Remove Bot Completely
```bash
docker-compose down
docker volume prune  # Remove old data
```

### View Performance Reports
```bash
cat reports/daily_report.txt
cat reports/weekly_report.txt
```

---

## Monitoring

### Check Bot Status
```bash
./monitor.sh  # Linux/Mac
monitor.bat   # Windows
```

### Set Up Alerts (Optional)

#### Email Alerts on Errors
Install and configure `mailx`:
```bash
sudo apt install mailutils -y

# Add to crontab
crontab -e

# Add this line (checks every hour):
0 * * * * docker-compose -f ~/BADSHAH\ TRADEINGGG/deployment/docker-compose.yml logs trading-bot | grep -i error | mail -s "Trading Bot Errors" your-email@example.com
```

#### Telegram Alerts
Edit `start_live_multi_coin_trading.py` and add:

```python
import requests

def send_telegram(message):
    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})

# Call when needed:
# send_telegram(f"🚨 Emergency stop triggered! Loss: ${loss:.2f}")
```

---

## Backup & Recovery

### Backup Trading Data
```bash
# Create backup
tar -czf backup_$(date +%Y%m%d).tar.gz logs/ reports/ data/

# Download to local machine
scp -i your-keypair.pem ubuntu@your-instance-ip:~/backup_*.tar.gz ./
```

### Restore from Backup
```bash
tar -xzf backup_20251027.tar.gz
docker-compose restart
```

---

## Cost Estimation

### AWS EC2 (t3.medium)
- Instance: ~$30/month
- Storage (20GB): ~$2/month
- **Total: ~$32/month**

### DigitalOcean
- Basic Droplet (2 vCPU, 4GB): $24/month
- **Total: $24/month**

### Google Cloud (e2-medium)
- Instance: ~$25/month
- Storage: ~$2/month
- **Total: ~$27/month**

---

## Troubleshooting

### Bot Not Starting
```bash
# Check logs
docker-compose logs trading-bot

# Rebuild container
docker-compose down
docker-compose up -d --build
```

### Out of Memory
```bash
# Check memory
free -h

# Upgrade instance or reduce number of coins
nano config/adaptive_config.json
# Remove some coins from "symbols" array
```

### Connection Errors
```bash
# Check internet connectivity
ping -c 4 api.binance.com

# Check firewall
sudo ufw status
sudo ufw allow out 443/tcp  # Allow HTTPS
```

### High CPU Usage
```bash
# Check CPU
top

# Increase trading interval in config
# Or reduce number of coins
```

---

## Security Best Practices

1. **Never commit API keys to Git**
   ```bash
   # Add to .gitignore
   config/adaptive_config.json
   *.env
   ```

2. **Use environment variables for sensitive data**
   ```bash
   # In docker-compose.yml
   environment:
     - BINANCE_API_KEY=${BINANCE_API_KEY}
     - BINANCE_SECRET_KEY=${BINANCE_SECRET_KEY}
   ```

3. **Enable firewall**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow https
   ```

4. **Keep system updated**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

5. **Use SSH keys, not passwords**

---

## Performance Optimization

### For Extended Trading (1-2 weeks)

1. **Increase logging retention**
   Edit `docker-compose.yml`:
   ```yaml
   logging:
     options:
       max-size: "50m"  # Increase from 10m
       max-file: "10"   # Increase from 5
   ```

2. **Add automatic daily reports**
   Add to `start_live_multi_coin_trading.py`:
   ```python
   def generate_daily_report(self):
       report = f"""
       Daily Trading Report - {datetime.now().strftime('%Y-%m-%d')}
       ================================================
       Initial Capital: ${self.initial_capital:.2f}
       Current Capital: ${self.current_capital:.2f}
       Total PnL: ${self.current_capital - self.initial_capital:.2f}
       Total Trades: {len(self.trades)}
       Win Rate: {self.get_win_rate():.1f}%
       """
       with open('reports/daily_report.txt', 'w') as f:
           f.write(report)
   ```

3. **Schedule automatic restarts**
   Add to crontab:
   ```bash
   0 0 * * * docker-compose -f ~/BADSHAH\ TRADEINGGG/deployment/docker-compose.yml restart
   ```

---

## Support

If you encounter any issues:
1. Check logs: `docker-compose logs trading-bot`
2. Check system resources: `htop` or `docker stats`
3. Verify configuration: `cat config/adaptive_config.json`
4. Test API connectivity: `curl https://testnet.binance.vision/api/v3/ping`

---

## Next Steps

After deployment:
1. ✅ Monitor for first hour
2. ✅ Check daily reports
3. ✅ Analyze performance after 3-5 days
4. ✅ Optimize based on results
5. ✅ Consider switching to live trading (with real API keys)

**Good luck with your trading! 🚀📈**


