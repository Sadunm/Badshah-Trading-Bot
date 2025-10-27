# 🚂 Railway.app Deployment Guide - Badshah Trading Bot

## Why Railway?
- ✅ **Super Easy** - Deploy in 5 minutes
- ✅ **Free Tier** - $5 free credits per month
- ✅ **Auto-Deploy** - Push to Git → Auto deploys
- ✅ **24/7 Running** - Automatic restarts
- ✅ **Logs Built-in** - View logs in dashboard
- ✅ **No Credit Card** - Start free (credit card optional for more credits)

---

## 🚀 Method 1: Deploy from GitHub (Recommended)

### Step 1: Push Code to GitHub

```bash
# If you haven't already, initialize git
cd "BADSHAH TRADEINGGG"
git init
git add .
git commit -m "Ready for Railway deployment"

# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Railway

1. Go to: **https://railway.app**
2. Click **"Start a New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository
5. Railway will automatically detect the `Dockerfile`
6. Click **"Deploy"**

**That's it! Bot will start automatically!** 🎉

---

## 🚀 Method 2: Deploy with Railway CLI

### Step 1: Install Railway CLI

```bash
# Windows (PowerShell as Admin)
iwr https://railway.app/install.ps1 | iex

# Mac/Linux
curl -fsSL https://railway.app/install.sh | sh
```

### Step 2: Login
```bash
railway login
```
This will open your browser to authenticate.

### Step 3: Deploy
```bash
cd "BADSHAH TRADEINGGG"

# Initialize Railway project
railway init

# Link to project (if already created on dashboard)
# OR it will create a new one

# Deploy
railway up
```

**Done! Bot is now live!** 🚀

---

## 📊 Monitor Your Bot on Railway

### View Logs
1. Go to Railway dashboard: https://railway.app/dashboard
2. Click your project
3. Click **"Deployments"** tab
4. Click **"View Logs"**

You'll see live logs like:
```
2025-10-27 12:49:15 - INFO - [START] Trading for 7 coins...
2025-10-27 12:49:18 - INFO - [BUY] 0.4900 SOLUSDT @ $204.14
2025-10-27 12:49:18 - INFO - [CAPITAL] $9321.46 | Portfolio: $9999.53
```

### Check Status
Railway dashboard shows:
- ✅ **Status**: Running / Stopped / Failed
- 📊 **CPU Usage**: Real-time
- 💾 **Memory Usage**: Real-time
- 🔄 **Restarts**: Automatic on crash
- 📈 **Metrics**: Built-in monitoring

---

## 💰 Railway Pricing

### Free Tier (Starter Plan)
- **$5 free credits per month**
- **500 hours execution time** (~20 days of 24/7)
- **Perfect for testing!**

### Hobby Plan ($5/month)
- **$5 credits included**
- **Additional usage billed**
- **Typically costs $5-10/month for 24/7 bot**

### Pro Plan ($20/month)
- **$20 credits included**
- **Priority support**
- **More resources**

**Your bot will likely cost: $0-10/month** depending on usage!

---

## ⚙️ Railway Configuration

Railway will automatically read these files:
- `Dockerfile` - How to build your app
- `railway.toml` - Railway-specific config
- `railway.json` - Alternative config format

**Already created for you!** ✅

---

## 🔧 Advanced: Environment Variables

If you want to store API keys as environment variables (more secure):

### 1. On Railway Dashboard:
- Go to your project
- Click **"Variables"** tab
- Add:
  - `BINANCE_API_KEY` = your_key_here
  - `BINANCE_SECRET_KEY` = your_secret_here

### 2. Update Python Code:
Edit `start_live_multi_coin_trading.py`:
```python
import os

# Instead of hardcoded keys:
API_KEY = os.getenv('BINANCE_API_KEY', 'default_testnet_key')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', 'default_testnet_secret')
```

**But for testnet, hardcoded keys are fine!**

---

## 📱 Railway CLI Commands

```bash
# View logs
railway logs

# View status
railway status

# Restart service
railway restart

# Stop service
railway down

# Redeploy (after code changes)
railway up

# Open dashboard
railway open

# SSH into container (advanced)
railway shell
```

---

## 🔄 Auto-Deploy on Git Push

If deployed from GitHub:

1. Make changes to your code locally
2. Commit and push:
   ```bash
   git add .
   git commit -m "Updated strategy"
   git push
   ```
3. **Railway automatically rebuilds and redeploys!** 🎉

No manual deploy needed!

---

## 📊 View Reports on Railway

Railway doesn't have persistent storage by default, but you can:

### Option 1: Check Logs
Reports are logged, visible in Railway dashboard logs.

### Option 2: Add Railway Volume (Persistent Storage)
1. Railway Dashboard → Your Project
2. Click **"Variables"** → **"Volumes"**
3. Add volume: `/app/reports` (10GB free)
4. Reports will persist across deployments

### Option 3: Download Reports via API
We can add a simple web endpoint to download reports.

---

## 🐛 Troubleshooting

### Build Failed?
**Check build logs** in Railway dashboard:
- Usually TA-Lib installation issue
- Or missing dependency

**Solution**: Railway Dockerfile is already optimized! Should work first try.

### Bot Not Trading?
1. Check logs: Railway Dashboard → Logs
2. Look for errors
3. Verify Binance testnet is accessible

### Out of Memory?
Railway free tier has limited RAM. If needed:
- Reduce number of coins in `config/adaptive_config.json`
- OR upgrade to Hobby plan

### Credits Running Out?
- Free tier: $5/month
- Bot uses ~$0.30-0.50 per day
- **Upgrade to Hobby plan for continuous running**

---

## 🎯 Complete Railway Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Railway account created (https://railway.app)
- [ ] Project created from GitHub repo
- [ ] Deployment succeeded (check logs)
- [ ] Bot is running (see logs: "[START] Trading...")
- [ ] Trades are happening (see "[BUY]" / "[SELL]" in logs)
- [ ] Monitor for 24 hours
- [ ] Check Railway credits usage
- [ ] Upgrade to Hobby plan if needed ($5/month)

---

## 🚀 Quick Start Commands

### Deploy Now:
```bash
# Option A: From GitHub
# 1. Push to GitHub
# 2. Go to railway.app
# 3. Deploy from repo

# Option B: Railway CLI
railway login
cd "BADSHAH TRADEINGGG"
railway init
railway up
```

### Monitor:
```bash
# View logs
railway logs

# Open dashboard
railway open
```

### Update:
```bash
# Make changes, then:
git add .
git commit -m "Update"
git push
# Railway auto-deploys!
```

---

## 📈 Expected Timeline

1. **Minute 1-2**: Sign up on Railway
2. **Minute 3-5**: Connect GitHub repo
3. **Minute 6-10**: Railway builds Docker image
4. **Minute 11**: Bot starts trading!

**Total: ~10 minutes from start to live trading!** ⚡

---

## 🎉 Advantages of Railway

vs AWS:
- ✅ **10x easier** to set up
- ✅ No complex EC2/security groups
- ✅ Auto-scaling built-in
- ✅ Better UI/UX

vs DigitalOcean:
- ✅ No manual Docker setup
- ✅ Auto-deploy from Git
- ✅ Built-in monitoring
- ✅ Cheaper for small projects

vs Running Locally:
- ✅ 24/7 operation
- ✅ No PC needed
- ✅ Auto-restart on crash
- ✅ Professional setup

---

## 💡 Pro Tips

1. **Start with Free Tier**: Test for a few days
2. **Monitor Credits**: Railway dashboard shows usage
3. **Use GitHub**: Auto-deploy is amazing
4. **Check Logs Daily**: Catch issues early
5. **Upgrade When Ready**: Hobby plan ($5/month) for continuous trading

---

## 🔗 Useful Links

- **Railway**: https://railway.app
- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: Support community
- **Your Dashboard**: https://railway.app/dashboard

---

## 📞 Support

If deployment fails:
1. Check Railway logs (dashboard)
2. Verify `Dockerfile` exists
3. Ensure `requirements.txt` is correct
4. Try `railway logs` in CLI
5. Ask on Railway Discord (very helpful!)

---

## ✅ You're Ready for Railway!

Everything is configured:
- ✅ `Dockerfile` - Optimized for Railway
- ✅ `railway.toml` - Railway config
- ✅ `.railwayignore` - Exclude unnecessary files
- ✅ All dependencies listed

**Just deploy and you're live!** 🚀

---

**Next Steps:**
1. Create Railway account: https://railway.app
2. Deploy from GitHub (easiest)
3. Monitor logs in dashboard
4. Let it run for 7-14 days
5. Analyze performance
6. Optimize based on results

**Railway আসলে খুব সহজ! GitHub এ push করো, Railway তে connect করো, আর সব automatic! 🚂💨**

Good luck! 🎉📈


