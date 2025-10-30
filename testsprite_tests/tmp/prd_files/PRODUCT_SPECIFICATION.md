# BADSHAH Trading Bot - Product Specification Document

## Overview
**Product Name:** BADSHAH Multi-Strategy Cryptocurrency Trading Bot  
**Version:** 2.0 (BUSS v2)  
**Type:** Automated Trading System (Backend + Dashboard)  
**Trading Mode:** Paper Trading (Simulation) & Live Trading  
**Target Market:** Binance Futures USDT Perpetuals  

---

## Core Purpose

An intelligent, multi-strategy cryptocurrency trading bot that:
1. **Automatically trades** multiple cryptocurrencies using proven strategies
2. **Manages risk** with dynamic stops, trailing stops, and position sizing
3. **Adapts to market conditions** using AI-driven regime detection
4. **Maximizes profits** through quick exits and auto-compounding
5. **Provides real-time monitoring** via web dashboard

---

## Key Features

### 1. Multi-Strategy System
**Feature:** Bot uses 3 active trading strategies simultaneously
- **SCALPING:** Quick 1-60 minute trades (target: 0.15-0.8% profit)
- **DAY_TRADING:** 1-8 hour holds (target: 0.8-2.0% profit)
- **MOMENTUM:** Ride strong trends (target: 2.0%+ profit)

**Expected Behavior:**
- Each strategy should generate signals independently
- Bot picks the BEST signal (highest confidence × opportunity score)
- Should open 10-20 trades per hour in ULTRA AGGRESSIVE mode
- Max 5 positions total at any time

**Current Issue:** 0 trades being opened despite signals being generated

---

### 2. Signal Generation & Validation

**Feature:** Technical analysis-based signal generation

**Indicators Used:**
- RSI (Relative Strength Index)
- EMA (9, 21, 50, 200 periods)
- ATR (Average True Range)
- Volume analysis
- Momentum (10-period price change)
- Support/Resistance levels

**Signal Confidence Calculation:**
- Base confidence: 20-25%
- Trend alignment: +10-15%
- Volume confirmation: +5-10%
- RSI extremes: +5-10%
- Final confidence: 20-60%

**Expected Behavior:**
- Generate signals for top 8 coins every 30 seconds
- Accept signals with 10%+ confidence (ULTRA AGGRESSIVE mode)
- Log all signal generation attempts (accepted & rejected)

**Current Issue:** Signals generated but not passing validation checks

---

### 3. Position Opening Logic

**Feature:** Intelligent position opening with safety checks

**Validation Steps:**
1. Check symbol cooldown (prevent spam trading)
2. Check symbol blacklist (avoid problematic coins)
3. Check max total positions (max 5)
4. Check duplicate symbol positions (1 per coin)
5. Check strategy existence
6. Calculate position size (volatility-adjusted)
7. Verify sufficient capital
8. Check confidence threshold (10-20% in EXTREME mode)
9. Execute order

**Expected Behavior:**
- Open 1-3 positions per scan cycle (every 30 seconds)
- Position size: 10-20% of capital per trade
- Should log reason if position NOT opened

**Current Issue:** All positions failing validation (need detailed logs to identify exact step)

---

### 4. BUSS v2 Adaptive System

**Feature:** AI-driven market adaptation and performance optimization

**Components:**

#### A. Market Health Index (MHI)
- Calculates market stability (0.0 = unstable, 2.0 = very stable)
- Based on: volatility, trend strength, price consistency
- Updates every cycle

#### B. Expected Profit per Risk Unit (EPRU)
- Tracks: (Avg Win / Avg Loss) × Win Rate
- Target: EPRU > 1.0 (profitable system)
- Auto-adjusts confidence threshold based on EPRU

#### C. Dynamic Exposure
- Formula: `base_exposure × regime_multiplier × mhi_factor × epru_bonus`
- Increases exposure in favorable conditions
- Reduces exposure in risky conditions

#### D. Market Regime Detection
- 6 regimes: STRONG_UPTREND, WEAK_UPTREND, SIDEWAYS, WEAK_DOWNTREND, STRONG_DOWNTREND, VOLATILE
- Adjusts strategy allocation based on regime
- Detects transitions and auto-adjusts

#### E. Feedback Loop (every 20 trades)
- Reviews performance
- Adjusts confidence threshold (±2%)
- Adjusts exposure (±10%)

**Expected Behavior:**
- MHI updates every cycle
- EPRU updates after each trade closes
- Threshold stays in 10-25% range (EXTREME mode)
- Logs all adjustments

**Current Issue:** System not getting enough trades to trigger feedback loop

---

### 5. Exit Logic (Profit Taking)

**Feature:** Multi-tier profit locking system

**Exit Tiers:**

#### Tier 1: INSTANT EXIT (0.15% net profit)
- **Trigger:** Net profit ≥ 0.15% (after 0.19% fees)
- **Action:** Exit immediately, no other checks
- **Priority:** HIGHEST
- **Example:** Entry $100 → Exit $100.34 → Profit $0.15

#### Tier 2: BREAK-EVEN STOP (0.3% profit)
- **Trigger:** Profit ≥ 0.3%
- **Action:** Move stop-loss to entry + fees
- **Result:** Position becomes risk-free

#### Tier 3: TRAILING STOP (0.8% profit)
- **Trigger:** Profit ≥ 0.8%
- **Action:** Trail stop-loss 0.4% below highest price
- **Result:** Protects profits as price rises

#### Tier 4: CONFIDENCE-BASED EXIT (0.5%+ profit)
- Small profit (0.5-1.2%): Lock if confidence < 50%
- Medium profit (1.2-2.0%): Lock if confidence < 45%
- Good profit (2.0%+): Lock if confidence < 40%

#### Tier 5: TRADITIONAL STOPS
- Stop-loss hit (ATR-based)
- Take-profit hit (ATR-based)
- Time limit exceeded

**Expected Behavior:**
- Check exits every cycle (30 seconds)
- Minimum hold: 30 seconds
- Log all exit decisions
- Should close 10-20 positions per hour (matching open rate)

**Current Issue:** No exits because no positions opened

---

### 6. Risk Management

**Feature:** Comprehensive risk protection

**Components:**

#### A. Position Sizing
- Base: 10-20% of capital per strategy
- Volatility-adjusted: ×0.7 (high vol), ×1.2 (low vol)
- BUSS v2 exposure: ×0.5 to ×4.0 multiplier

#### B. Stop-Loss (ATR-based)
- Regime-dependent multipliers
- STRONG_UPTREND: 1.5× ATR
- WEAK_UPTREND: 1.2× ATR
- SIDEWAYS: 0.8× ATR
- WEAK_DOWNTREND: 0.8× ATR
- STRONG_DOWNTREND: 1.0× ATR

#### C. Take-Profit (ATR-based)
- STRONG_UPTREND: 3.0× ATR
- WEAK_UPTREND: 2.5× ATR
- SIDEWAYS: 1.5× ATR
- Downtrends: 1.5-2.0× ATR

#### D. Daily Loss Limit
- Max loss: $200 per day (including unrealized)
- Pauses new trades if hit

#### E. Consecutive Loss Protection
- 3 losses in a row → 30-minute pause

#### F. Daily Trade Limit
- Max 20 trades per day (quality over quantity)

**Expected Behavior:**
- All checks execute before opening position
- Logs risk calculations
- Respects all limits

**Current Issue:** Risk checks may be TOO strict (preventing trades)

---

### 7. Auto-Compounding

**Feature:** Position sizes grow with profits, shrink with losses

**Formula:**
```
current_equity = current_capital + reserved_capital
compounding_multiplier = current_equity / initial_capital
position_size = base_size × compounding_multiplier
```

**Expected Behavior:**
- Start: $10,000 capital → $200 position size
- After +10% profit: $11,000 capital → $220 position size (+10%)
- After -10% loss: $9,000 capital → $180 position size (-10%)

---

### 8. API & Data Management

**Feature:** Efficient Binance API usage

**Components:**

#### A. API Key Rotation
- 3 API keys
- Rotates on rate limit errors
- Tracks usage per key

#### B. Price Caching
- Caches prices for 30 seconds
- Reduces API calls by 80%

#### C. Symbol Info Caching
- Caches precision, filters, lot size
- Permanent cache (doesn't change)

#### D. Thread Safety
- `threading.Lock` for all shared data
- Prevents race conditions

**Expected Behavior:**
- Max 1200 requests/minute per key
- Graceful handling of rate limits
- No API errors under normal load

---

### 9. Web Dashboard (Flask)

**Feature:** Real-time monitoring interface

**Endpoints:**

#### `/` - Dashboard HTML
- Shows current status
- Open positions
- Recent trades
- Performance metrics

#### `/api/stats` - System Statistics
```json
{
  "trading_mode": "PAPER",
  "open_positions": 0,
  "total_trades": 0,
  "total_pnl": 0,
  "win_rate": 0,
  "current_capital": 10000,
  "market_regime": "WEAK_DOWNTREND",
  "buss_v2": {
    "mhi": 1.036,
    "epru": 1.0,
    "base_threshold": 10,
    "current_threshold": 10,
    "dynamic_exposure": 3.92,
    "regulation_state": "NORMAL"
  }
}
```

#### `/api/positions` - Open Positions
#### `/api/logs` - Recent Logs (last 200 lines)
#### `/api/trade-history` - All Trades (from CSV)

**Expected Behavior:**
- Auto-updates every 5 seconds
- Shows real-time P&L
- Displays strategy performance
- Mobile-responsive

---

## Critical Issues to Test

### Issue #1: NO TRADES OPENING (HIGHEST PRIORITY)
**Symptom:**
- Bot running for 45+ minutes
- Signals generated (logged)
- 0 positions opened
- 0 trades executed

**Possible Causes:**
1. Adaptive confidence threshold too high (40-60% instead of 10-20%)
2. Signal confidence too low (20-25% vs required threshold)
3. Validation checks too strict (volume, ATR, RSI filters)
4. Capital allocation issues
5. Max position limits hit incorrectly
6. Symbol cooldowns preventing trades
7. Market regime blocking certain strategies

**Test Cases:**
- Verify signal generation logs show confidence levels
- Verify adaptive threshold calculation
- Verify position opening validation logs
- Test with EXTREME AGGRESSIVE settings (volume: 0.1x, ATR: 0.01%, threshold: 10%)

---

### Issue #2: Adaptive System Not Lowering Threshold
**Symptom:**
- Base threshold: 10% ✅
- Current threshold: Should be 10-20% in EXTREME mode
- Actual: May be 40-60% (old code)

**Test Cases:**
- Check `update_adaptive_confidence()` function
- Verify recent_trades_window logic
- Test threshold calculation with 0 trades (should use base)

---

### Issue #3: Signal Filters Too Strict
**Symptom:**
- Volume ratio filter: Rejects if < 0.1x (was 0.3x)
- ATR filter: Rejects if < 0.01% (was 0.1%)
- RSI overlap: Wide ranges but may still reject

**Test Cases:**
- Log all filter rejections
- Count signals generated vs accepted
- Identify most common rejection reason

---

### Issue #4: Position Validation Failing
**Symptom:**
- Signals pass confidence check
- Position opening fails silently

**Test Cases:**
- Add debug logs to every validation step in `open_position()`
- Verify symbol cooldown dict
- Verify blacklist
- Verify max_positions check
- Verify capital calculation

---

## Success Metrics

### Immediate Success (Next 30 minutes):
- ✅ 10+ trades opened
- ✅ Positions cycling (open → close → open)
- ✅ At least 1 profitable trade (+0.15% or more)
- ✅ No API errors
- ✅ Dashboard updating correctly

### Short-term Success (24 hours):
- ✅ 100+ trades executed
- ✅ Win rate: 55-65%
- ✅ P&L: +2% to +5%
- ✅ EPRU: > 1.0
- ✅ No system crashes
- ✅ All safety limits working

### Long-term Success (7 days):
- ✅ 500+ trades executed
- ✅ Win rate: 60%+
- ✅ P&L: +10% to +20%
- ✅ EPRU: > 1.3
- ✅ Drawdown: < 5%
- ✅ Auto-compounding working
- ✅ Feedback loop adjustments working

---

## Technical Stack

**Backend:**
- Python 3.8+
- Flask (web server)
- ccxt (Binance API)
- NumPy, Pandas (data analysis)
- TA-Lib (technical indicators)

**Frontend:**
- HTML/CSS/JavaScript
- Auto-refresh (5 seconds)
- Responsive design

**Deployment:**
- Local: Windows PC
- Cloud: Render.com (Docker)
- Port: 5000 (local), 10000 (cloud)

---

## Test Scenarios

### Scenario 1: Fresh Start (Paper Trading)
1. Start bot with $10,000 capital
2. Wait 5 minutes
3. Expected: 5-10 positions opened
4. Expected: At least 1-2 trades closed with profit

### Scenario 2: ULTRA AGGRESSIVE Mode
1. Settings: threshold=10%, volume=0.1x, ATR=0.01%
2. Start bot
3. Expected: 10-20 trades per hour
4. Expected: Quick exits at 0.15% profit

### Scenario 3: Market Regime Change
1. Start in WEAK_DOWNTREND
2. Market shifts to STRONG_UPTREND
3. Expected: Strategy allocation changes
4. Expected: Position sizes adjust
5. Expected: Stops/targets recalculated

### Scenario 4: Consecutive Losses
1. Bot hits 3 losses in a row
2. Expected: 30-minute pause activated
3. Expected: Existing positions still managed
4. Expected: No new positions opened
5. After 30 minutes: Resume trading

### Scenario 5: Daily Loss Limit
1. Bot loses $200 in a day
2. Expected: New trades paused
3. Expected: Existing positions closed if losing
4. Expected: Winners allowed to run
5. Next day: Reset and resume

---

## API Endpoints to Test

### GET /api/stats
**Expected Response:**
```json
{
  "trading_mode": "PAPER",
  "open_positions": 2,
  "total_trades": 15,
  "total_pnl": 25.50,
  "win_rate": 60,
  "current_capital": 10025.50,
  "market_regime": "WEAK_DOWNTREND",
  "buss_v2": {
    "mhi": 1.036,
    "epru": 1.2,
    "base_threshold": 10,
    "current_threshold": 12,
    "dynamic_exposure": 3.5,
    "regulation_state": "NORMAL"
  }
}
```

### GET /api/positions
**Expected Response:**
```json
{
  "positions": [
    {
      "symbol": "BTCUSDT",
      "strategy": "SCALPING",
      "action": "BUY",
      "entry_price": 67500.00,
      "current_price": 67580.00,
      "quantity": 0.0148,
      "unrealized_pnl": 1.18,
      "unrealized_pnl_pct": 0.12,
      "stop_loss": 67350.00,
      "take_profit": 68200.00,
      "entry_time": "2025-10-30T19:15:30"
    }
  ]
}
```

### GET /api/trade-history
**Expected Response:**
```json
{
  "trades": [
    {
      "symbol": "ETHUSDT",
      "strategy": "DAY_TRADING",
      "action": "BUY",
      "entry_price": 2650.00,
      "exit_price": 2658.00,
      "pnl": 4.50,
      "pnl_pct": 0.30,
      "win": true,
      "exit_reason": "Low-Cap Quick Exit (+0.19% net profit)"
    }
  ]
}
```

---

## Logging Requirements

**Must Log:**
1. Every signal generation attempt (symbol, strategy, confidence)
2. Every signal rejection (reason)
3. Every signal acceptance
4. Every position open attempt
5. Every position open failure (reason)
6. Every position open success
7. Every exit check
8. Every position close (reason)
9. All adaptive threshold adjustments
10. All BUSS v2 calculations (MHI, EPRU, exposure)
11. All risk limit triggers
12. All API errors

**Log Levels:**
- DEBUG: Signal details, calculations
- INFO: Trades opened/closed, regime changes
- WARNING: Risk limits, cooldowns, rejections
- ERROR: API errors, crashes, failures

---

## Configuration

**Environment Variables:**
- `LIVE_TRADING_MODE=False` (paper trading)
- `INITIAL_CAPITAL=10000`
- `BINANCE_API_KEY_1`, `_2`, `_3`
- `BINANCE_API_SECRET_1`, `_2`, `_3`

**Hardcoded Settings (start_live_multi_coin_trading.py):**
- `base_confidence_threshold = 10`
- `ULTRA_AGGRESSIVE_STRATEGIES = ['SCALPING', 'DAY_TRADING', 'MOMENTUM']`
- `SCAN_INTERVAL = 30` seconds
- `MAX_TOTAL_POSITIONS = 5`
- `DAILY_LOSS_LIMIT = 200`
- `MAX_DAILY_TRADES = 20`

---

## Expected User Flow

1. User starts bot: `python start_live_multi_coin_trading.py`
2. Bot initializes: Loads API keys, connects to Binance
3. Bot scans: Every 30 seconds, analyzes 64 coins
4. Bot generates signals: Top 8 coins, 3 strategies each
5. Bot picks best signal: Highest confidence × score
6. Bot opens position: If passes all validations
7. Bot manages position: Checks exits every 30 seconds
8. Bot closes position: On profit target or stop-loss
9. Bot logs trade: Updates CSV, analytics, dashboard
10. Bot adapts: BUSS v2 adjusts thresholds/exposure
11. User monitors: Dashboard at http://localhost:10000

---

## Known Issues (Pre-Testing)

1. **0 trades opening** - Main issue to investigate
2. **Adaptive threshold may be too high** - Check calculation
3. **Signal filters may be too strict** - Verify volume/ATR checks
4. **Position validation may be failing silently** - Add debug logs
5. **Capital allocation may be incorrect** - Verify math
6. **Symbol cooldowns may be blocking trades** - Check cooldown dict

---

## Testing Priorities

### Priority 1 (CRITICAL): Fix Trade Execution
- Why are signals not opening positions?
- Add comprehensive debug logging
- Test each validation step independently
- Identify exact failure point

### Priority 2 (HIGH): Verify Adaptive System
- Is threshold being calculated correctly?
- Is it staying in 10-20% range?
- Are adjustments working?

### Priority 3 (MEDIUM): Verify Exit Logic
- Once trades open, do they close correctly?
- Are profit tiers working?
- Is trailing stop working?

### Priority 4 (LOW): Performance Optimization
- API call efficiency
- Memory usage
- CPU usage

---

## Success Criteria for TestSprite

✅ **Identify exact reason** why trades not opening  
✅ **Verify** all 9 validation steps in `open_position()`  
✅ **Test** adaptive confidence calculation  
✅ **Test** signal generation filters  
✅ **Test** capital allocation logic  
✅ **Verify** API endpoints return correct data  
✅ **Check** for race conditions or threading issues  
✅ **Validate** BUSS v2 calculations  
✅ **Test** exit logic (if trades can be opened)  
✅ **Generate** comprehensive bug report  
✅ **Provide** specific fixes for each issue found  

---

**End of Product Specification**

