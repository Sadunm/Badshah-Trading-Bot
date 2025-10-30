import requests

def test_verify_dashboard_stats_api_returns_correct_buss_v2_metrics():
    url = "http://localhost:10000/api/stats"
    headers = {
        "Accept": "application/json"
    }
    timeout = 30
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"API request failed: {e}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate top-level keys existence and types
    expected_keys = [
        "trading_mode",
        "open_positions",
        "total_trades",
        "total_pnl",
        "win_rate",
        "current_capital",
        "market_regime",
        "buss_v2"
    ]
    for key in expected_keys:
        assert key in data, f"Missing key in response: {key}"

    # trading_mode should be PAPER or LIVE
    assert data["trading_mode"] in ("PAPER", "LIVE"), f"Unexpected trading_mode: {data['trading_mode']}"

    # open_positions, total_trades should be integers >= 0
    assert isinstance(data["open_positions"], int) and data["open_positions"] >= 0, "Invalid open_positions"
    assert isinstance(data["total_trades"], int) and data["total_trades"] >= 0, "Invalid total_trades"

    # total_pnl, win_rate, current_capital should be numbers (int or float), win_rate between 0 and 100
    for key in ["total_pnl", "current_capital"]:
        assert isinstance(data[key], (int, float)), f"{key} is not a number"
    assert isinstance(data["win_rate"], (int, float)), "win_rate is not a number"
    assert 0 <= data["win_rate"] <= 100, "win_rate out of expected range 0-100"

    # market_regime should be one of the known 6 regimes
    valid_regimes = {
        "STRONG_UPTREND",
        "WEAK_UPTREND",
        "SIDEWAYS",
        "WEAK_DOWNTREND",
        "STRONG_DOWNTREND",
        "VOLATILE"
    }
    assert data["market_regime"] in valid_regimes, f"Unexpected market_regime: {data['market_regime']}"

    # Validate buss_v2 subfields
    buss_v2 = data["buss_v2"]
    assert isinstance(buss_v2, dict), "buss_v2 is not a dict"

    expected_buss_v2_keys = [
        "mhi",
        "epru",
        "base_threshold",
        "current_threshold",
        "dynamic_exposure",
        "regulation_state"
    ]
    for key in expected_buss_v2_keys:
        assert key in buss_v2, f"Missing buss_v2 key: {key}"

    # Validate MHI (Market Health Index): number expected 0-2
    mhi = buss_v2["mhi"]
    assert isinstance(mhi, (int, float)), "mhi is not a number"
    assert 0 <= mhi <= 2, f"mhi out of range 0-2: {mhi}"

    # Validate EPRU (Expected Profit per Risk Unit), target > 1.0
    epru = buss_v2["epru"]
    assert isinstance(epru, (int, float)), "epru is not a number"
    assert epru >= 0, f"epru should be non-negative: {epru}"

    # base_threshold and current_threshold should be numbers (typically percentages 0-100 or 0-1)
    base_threshold = buss_v2["base_threshold"]
    current_threshold = buss_v2["current_threshold"]
    for val, name in [(base_threshold, "base_threshold"), (current_threshold, "current_threshold")]:
        assert isinstance(val, (int, float)), f"{name} is not a number"
        assert 0 <= val <= 100, f"{name} out of range 0-100: {val}"

    # dynamic_exposure: Position size multiplier (0.5x to 4.0x)
    dynamic_exposure = buss_v2["dynamic_exposure"]
    assert isinstance(dynamic_exposure, (int, float)), "dynamic_exposure is not a number"
    assert 0.5 <= dynamic_exposure <= 4.0, f"dynamic_exposure out of expected range 0.5-4.0: {dynamic_exposure}"

    # regulation_state should be one of NORMAL, CAUTION, PAUSED, EMERGENCY
    regulation_state = buss_v2["regulation_state"]
    valid_reg_states = {"NORMAL", "CAUTION", "PAUSED", "EMERGENCY"}
    assert regulation_state in valid_reg_states, f"Unexpected regulation_state: {regulation_state}"

test_verify_dashboard_stats_api_returns_correct_buss_v2_metrics()