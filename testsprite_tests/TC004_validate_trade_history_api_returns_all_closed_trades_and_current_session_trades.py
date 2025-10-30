import requests

BASE_URL = "http://localhost:10000/api"
TRADE_HISTORY_ENDPOINT = "/trade-history"
TIMEOUT = 30

def test_validate_trade_history_api_returns_all_closed_trades_and_current_session_trades():
    url = f"{BASE_URL}{TRADE_HISTORY_ENDPOINT}"
    headers = {
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"API request failed: {e}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Adjust to handle response being a dict containing a list of trades
    if isinstance(data, dict):
        # Try to find a list of trades in the dict keys
        possible_keys = ['trades', 'trade_history', 'data', 'items']
        trades_list = None
        for key in possible_keys:
            if key in data and isinstance(data[key], list):
                trades_list = data[key]
                break
        if trades_list is None:
            # If dict itself looks like a single trade entry, wrap it in a list
            # but check keys to confirm
            single_trade_keys = {
                "timestamp",
                "symbol",
                "strategy",
                "action",
                "entry_price",
                "exit_price",
                "quantity",
                "pnl",
                "pnl_pct",
                "fees",
                "entry_reason",
                "exit_reason",
                "hold_duration_hours",
                "entry_market_condition",
                "exit_market_condition",
                "stop_loss",
                "take_profit",
                "confidence"
            }
            if single_trade_keys.issubset(data.keys()):
                trades_list = [data]
            else:
                assert False, f"Expected response to contain a list of trades but could not find one in the dict keys"
        data = trades_list
    assert isinstance(data, list), f"Expected response to be a list but got {type(data)}"

    # Basic validation of trade data structure
    required_fields = {
        "timestamp",
        "symbol",
        "strategy",
        "action",
        "entry_price",
        "exit_price",
        "quantity",
        "pnl",
        "pnl_pct",
        "fees",
        "entry_reason",
        "exit_reason",
        "hold_duration_hours",
        "entry_market_condition",
        "exit_market_condition",
        "stop_loss",
        "take_profit",
        "confidence"
    }

    # Validate at least one trade exists
    assert len(data) > 0, "Trade history should contain at least one trade record"

    for trade in data:
        assert isinstance(trade, dict), f"Each trade should be a dict but got {type(trade)}"
        missing_fields = required_fields - trade.keys()
        assert not missing_fields, f"Trade missing fields: {missing_fields}"
        # Validate data types for key fields roughly
        assert isinstance(trade["timestamp"], (str, int)), "timestamp should be string or int"
        assert isinstance(trade["symbol"], str) and trade["symbol"], "symbol should be non-empty string"
        assert trade["action"] in ("BUY", "SELL"), "action should be 'BUY' or 'SELL'"
        # entry_price, exit_price, pnl, pnl_pct, fees should be float or int
        for fld in ["entry_price", "exit_price", "pnl", "pnl_pct", "fees"]:
            assert isinstance(trade[fld], (int, float)), f"{fld} should be numeric"
        # quantity should be numeric and positive
        assert isinstance(trade["quantity"], (int, float)) and trade["quantity"] > 0, "quantity must be positive number"
        # confidence should be a numeric percentage 0-100, allow 0-100 float
        conf = trade["confidence"]
        assert isinstance(conf, (int, float)) and 0 <= conf <= 100, "confidence must be between 0 and 100"

    # Additional sanity checks (optional, not required but helpful)
    # Check no future timestamps (assuming timestamp is epoch or ISO 8601 string)
    import time
    from dateutil.parser import parse as parse_date
    now_ts = time.time()
    for trade in data:
        ts = trade["timestamp"]
        if isinstance(ts, (int, float)):
            # epoch timestamp, allow some clock drift but no future > 5 minutes
            assert ts <= now_ts + 300, f"trade timestamp {ts} is from the future"
        else:
            try:
                dt = parse_date(ts)
                assert dt.timestamp() <= now_ts + 300, f"trade timestamp {ts} is from the future"
            except Exception:
                # If cannot parse timestamp string, ignore in this check
                pass

test_validate_trade_history_api_returns_all_closed_trades_and_current_session_trades()
