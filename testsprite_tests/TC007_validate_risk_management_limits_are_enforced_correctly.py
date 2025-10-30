import requests
import time

BASE_URL = "http://localhost:10000/api"
TIMEOUT = 30

def validate_risk_management_limits_are_enforced_correctly():
    session = requests.Session()
    headers = {"Accept": "application/json"}

    # Step 1: Get current stats to check current open positions and total trades
    stats_resp = session.get(f"{BASE_URL}/stats", headers=headers, timeout=TIMEOUT)
    assert stats_resp.status_code == 200, f"Failed to get stats: {stats_resp.text}"
    stats = stats_resp.json()

    # Extract key risk info from stats and buss_v2
    open_positions = stats.get("open_positions", None)
    total_trades = stats.get("total_trades", None)
    buss_v2 = stats.get("buss_v2", None)

    assert open_positions is not None, "open_positions missing in stats"
    assert total_trades is not None, "total_trades missing in stats"
    assert isinstance(buss_v2, dict), f"buss_v2 field must be a dict, got {type(buss_v2)}"

    regulation_state = buss_v2.get("regulation_state", "").upper()

    assert regulation_state in ("NORMAL", "CAUTION", "PAUSED", "EMERGENCY"), f"Unknown regulation state: {regulation_state}"

    # 1. Validate max total positions limit (should not exceed max_total_positions=5)
    MAX_TOTAL_POSITIONS = 5
    assert open_positions <= MAX_TOTAL_POSITIONS, f"Open positions ({open_positions}) exceed max allowed {MAX_TOTAL_POSITIONS}"

    # 2. Validate max daily trades limit (should not exceed max_daily_trades=20)
    MAX_DAILY_TRADES = 20
    assert total_trades <= MAX_DAILY_TRADES, f"Total trades today ({total_trades}) exceed max allowed {MAX_DAILY_TRADES}"

    # 3. Validate daily loss limit enforcement
    # Get trade history to calculate realized daily loss
    trade_history_resp = session.get(f"{BASE_URL}/trade-history", headers=headers, timeout=TIMEOUT)
    assert trade_history_resp.status_code == 200, f"Failed to get trade history: {trade_history_resp.text}"
    trades = trade_history_resp.json()
    # Trades expected as list of dicts with pnl field representing profit/loss per trade
    # Sum pnl of trades today (assume timestamp field in ISO8601 or epoch milliseconds)
    from datetime import datetime, timedelta, timezone
    now_utc = datetime.now(timezone.utc)
    day_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    total_loss = 0.0
    for trade in trades:
        timestamp_str = trade.get("timestamp")
        pnl = trade.get("pnl")
        if pnl is None or timestamp_str is None:
            continue
        try:
            # Try to parse timestamp assuming ISO8601 with timezone
            trade_time = datetime.fromisoformat(timestamp_str.rstrip('Z')).replace(tzinfo=timezone.utc)
        except Exception:
            # Fallback parsing; skip if fails
            continue
        if trade_time >= day_start and trade_time <= now_utc:
            if pnl < 0:
                total_loss += abs(pnl)
    DAILY_LOSS_LIMIT = 200
    assert total_loss <= DAILY_LOSS_LIMIT, f"Daily loss limit breached: {total_loss} > {DAILY_LOSS_LIMIT}"

    # 4. Validate consecutive loss pause enforcement
    # We expect regulation_state to transit to PAUSED or EMERGENCY if consecutive losses limit breached
    # Check logs for consecutive loss pause message or check regulation_state
    # Since logs endpoint gives last 200 lines, check for related messages
    logs_resp = session.get(f"{BASE_URL}/logs", headers=headers, timeout=TIMEOUT)
    assert logs_resp.status_code == 200, f"Failed to get logs: {logs_resp.text}"
    logs_text = logs_resp.text.lower()
    # Check for keywords indicating consecutive loss pause
    consecutive_loss_pause_detected = \
        ("consecutive loss pause" in logs_text) or ("regulation_state: paused" in logs_text) or ("regulation_state: emergency" in logs_text)

    # If consecutive losses >=3, regulation_state must reflect pause or emergency
    # Inspect losses streak from performance analytics if available in stats
    win_rate = stats.get("win_rate", None)
    # If regulation_state is PAUSED or EMERGENCY, validate pauses enforced
    loss_pause_states = {"PAUSED", "EMERGENCY"}
    if regulation_state in loss_pause_states:
        assert consecutive_loss_pause_detected, "Regulation state indicates pause/emergency but no log found for consecutive loss pause"
    else:
        # If regulation normal, then no consecutive loss pause detected is OK
        pass

    # 5. Validate that new signals do not open positions beyond risk limits:
    # We'll simulate by checking that no new positions opened when limits reached
    # For this, if open_positions == max allowed, no new positions should be opened as per logs or stats
    # Wait briefly for bot to generate signals and verify no new trades open beyond limit
    # Here, just reuse stats after short sleep to see if open_positions stable
    pos_before = open_positions
    time.sleep(5)
    stats_resp_2 = session.get(f"{BASE_URL}/stats", headers=headers, timeout=TIMEOUT)
    assert stats_resp_2.status_code == 200, f"Failed to get stats second time: {stats_resp_2.text}"
    open_positions_2 = stats_resp_2.json().get("open_positions")
    assert open_positions_2 == pos_before, f"Open positions changed after wait despite max limit: {pos_before} -> {open_positions_2}"

    # 6. Summary assert passed: Risk management limits enforced properly
    print("All risk management limits enforced correctly.")

validate_risk_management_limits_are_enforced_correctly()
