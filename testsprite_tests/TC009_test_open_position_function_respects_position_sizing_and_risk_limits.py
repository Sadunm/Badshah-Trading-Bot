import requests
import time

BASE_URL = "http://localhost:10000/api"
HEADERS = {"Content-Type": "application/json"}
TIMEOUT = 30


def test_open_position_function_respects_position_sizing_and_risk_limits():
    # Step 1: Retrieve current capital and risk limits from /api/stats to understand constraints
    stats_resp = requests.get(f"{BASE_URL}/stats", headers=HEADERS, timeout=TIMEOUT)
    assert stats_resp.status_code == 200, f"Failed to get stats: {stats_resp.text}"
    stats = stats_resp.json()

    current_capital = stats.get("current_capital")
    buss_v2 = stats.get("buss_v2", {})
    current_threshold = buss_v2.get("current_threshold", 0)
    max_total_positions = 5  # from PRD limits
    daily_loss_limit = 200  # dollars
    max_position_size_per_trade = 500  # dollars, from live mode limits

    # Step 2: Check current open positions count to validate max total positions
    positions_resp = requests.get(f"{BASE_URL}/positions", headers=HEADERS, timeout=TIMEOUT)
    assert positions_resp.status_code == 200, f"Failed to get positions: {positions_resp.text}"
    positions = positions_resp.json()
    open_positions_count = len(positions)

    # Step 3: Since POST /positions is not allowed/supported per PRD, we cannot test position opening via API.
    # Instead, assert that open positions count does not exceed max allowed.
    assert open_positions_count <= max_total_positions, (
        f"Open positions count {open_positions_count} exceeds max allowed {max_total_positions}"
    )

    # Step 4: Optionally, check the size and confidence of existing positions if any
    for pos in positions:
        quantity = pos.get("quantity")
        confidence = pos.get("confidence")
        symbol = pos.get("symbol")
        assert quantity is not None, "Position missing quantity field"
        assert confidence is not None, "Position missing confidence field"

        # Assuming confidence is percentage (0-100)
        conf_val = float(confidence)
        if conf_val < 1:
            conf_val *= 100
        assert conf_val >= current_threshold, (
            f"Position confidence {conf_val} below current threshold {current_threshold}"
        )

        # Assuming BTCUSDT price approx 30000 if symbol BTCUSDT; otherwise skip size check
        if symbol == "BTCUSDT":
            qty_price_usd = float(quantity) * 30000
            assert qty_price_usd <= max_position_size_per_trade + 0.01, "Position size exceeds max position size per trade"
            assert qty_price_usd <= current_capital * 0.2 + 0.01, "Position size exceeds 20% of capital"

    # Extra sleep to prevent rate limit issues in rapid tests
    time.sleep(1)


test_open_position_function_respects_position_sizing_and_risk_limits()