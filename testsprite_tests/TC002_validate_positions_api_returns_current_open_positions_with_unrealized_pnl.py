import requests


def test_validate_positions_api_returns_current_open_positions_with_unrealized_pnl():
    base_url = "http://localhost:10000/api/stats"
    positions_url = base_url.rsplit('/', 1)[0] + "/positions"
    headers = {
        "Accept": "application/json"
    }
    timeout = 30

    try:
        # Send GET request to /api/positions endpoint
        response = requests.get(positions_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        # The response should be a list (array) of positions
        assert isinstance(data, list), "Response is not a list of positions."

        for position in data:
            # Each position must be a dict/object
            assert isinstance(position, dict), "Position item is not an object."

            # Check essential keys presence
            # Accept possible variants of unrealized pnl field name
            assert "symbol" in position, "Position missing 'symbol' field."
            assert ("unrealized_pnl" in position or "unrealizedPnL" in position or "unrealizedPnl" in position), "Position missing 'unrealized_pnl' field."

            # Validate that unrealized_pnl is a number (int or float)
            pnl = (position.get("unrealized_pnl") 
                   if "unrealized_pnl" in position else 
                   position.get("unrealizedPnL", position.get("unrealizedPnl")))
            assert isinstance(pnl, (int, float)), f"Unrealized PnL is not numeric: {pnl}"

        # Additional sanity check: if positions list is empty, it's allowed
        # But log count for visibility
        print(f"Number of open positions returned: {len(data)}")

    except requests.exceptions.RequestException as e:
        assert False, f"HTTP request to positions API failed: {e}"
    except ValueError:
        assert False, "Response content is not valid JSON."


test_validate_positions_api_returns_current_open_positions_with_unrealized_pnl()
