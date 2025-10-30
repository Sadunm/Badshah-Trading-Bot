import requests

def test_verify_adaptive_confidence_threshold_adjusts_with_win_rate():
    base_url = "http://localhost:10000/api/stats"
    timeout = 30

    try:
        response = requests.get(base_url, timeout=timeout)
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        data = response.json()

        # Validate required fields exist
        assert "win_rate" in data, "win_rate not present in response"
        assert "buss_v2" in data, "buss_v2 metrics missing"
        buss_v2 = data["buss_v2"]
        assert "current_threshold" in buss_v2, "current_threshold missing in buss_v2 metrics"

        win_rate = data["win_rate"]
        current_threshold = buss_v2["current_threshold"]

        # Validate win_rate type and range
        assert isinstance(win_rate, (int, float)), "win_rate should be a number"
        assert 0 <= win_rate <= 100, f"win_rate out of expected range 0-100: {win_rate}"

        # Validate current_threshold type
        assert isinstance(current_threshold, (int, float)), "current_threshold should be a number"

        # Validate against fixed thresholds according to win_rate mapping
        if win_rate >= 65:
            expected_threshold = 10
        elif 55 <= win_rate < 65:
            expected_threshold = 12
        elif 45 <= win_rate < 55:
            expected_threshold = 15
        else:  # win_rate < 45
            expected_threshold = 20

        assert abs(current_threshold - expected_threshold) < 0.1, (
            f"Adaptive confidence threshold {current_threshold}% not matching expected {expected_threshold}% for win rate {win_rate}%"
        )

    except requests.RequestException as e:
        assert False, f"HTTP request failed: {e}"
    except ValueError as e:
        assert False, f"Response content decoding failed or invalid JSON: {e}"


test_verify_adaptive_confidence_threshold_adjusts_with_win_rate()