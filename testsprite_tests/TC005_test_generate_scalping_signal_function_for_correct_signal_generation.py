import requests
import time

BASE_URL = "http://localhost:10000/api/stats"
TIMEOUT = 30

def test_generate_scalping_signal_function_for_correct_signal_generation():
    """
    Test the generate_scalping_signal function to verify it generates valid trading signals 
    based on the scalping strategy using the appropriate technical indicators.
    Focus on:
      - confidence calculation bugs,
      - threshold validation bugs,
      - position opening validation bugs.
    Approach:
      - Poll /api/stats and /api/positions and /api/logs endpoints.
      - Validate that signals are being generated with confidence in the proper range (10-20% adaptive threshold).
      - Validate trades are opening accordingly.
      - Check logs for any error messages related to confidence calculation or position opening.
    """

    headers = {'Accept': 'application/json'}
    start_time = time.time()
    timeout_seconds = 120  # Wait up to 2 minutes to observe signal generation and trade openings

    # We expect that during this time the bot will generate scalping signals and open positions accordingly.
    while time.time() - start_time < timeout_seconds:
        try:
            # Step 1: Check stats including BUSS v2 confidence thresholds
            stats_resp = requests.get(BASE_URL, headers=headers, timeout=TIMEOUT)
            assert stats_resp.status_code == 200, f"/api/stats returned HTTP {stats_resp.status_code}"
            stats_json = stats_resp.json()

            buss_v2 = stats_json.get("buss_v2", {})
            current_threshold = buss_v2.get("current_threshold", None)
            base_threshold = buss_v2.get("base_threshold", None)

            # Validate adaptive threshold in expected fixed range (10-20%)
            assert current_threshold is not None, "current_threshold missing in /api/stats buss_v2"
            assert 10 <= current_threshold <= 20, f"Adaptive confidence threshold out of range: {current_threshold}"

            # Step 2: Get open positions and verify at least the bot is opening positions (scalping likely among them)
            positions_resp = requests.get("http://localhost:10000/api/positions", headers=headers, timeout=TIMEOUT)
            assert positions_resp.status_code == 200, f"/api/positions returned HTTP {positions_resp.status_code}"
            positions = positions_resp.json()
            # Positions list expected to be a list of position dicts with keys including strategy and confidence or pnl

            # At least one position opened by the bot from scalping strategy theoretically during test window
            has_scalping_position = False
            for pos in positions:
                # We cannot absolutely confirm strategy here but we check if confidence present and > threshold
                confidence = pos.get("confidence", None)
                if confidence is not None:
                    # Confidence might be 0-100 scale; ensure it's >= threshold
                    if confidence >= current_threshold:
                        has_scalping_position = True
                        break

            # Step 3: Check logs for errors related to confidence calculation or position opening validation bugs
            logs_resp = requests.get("http://localhost:10000/api/logs", headers=headers, timeout=TIMEOUT)
            assert logs_resp.status_code == 200, f"/api/logs returned HTTP {logs_resp.status_code}"
            logs = logs_resp.json()

            error_indicators = [
                "confidence calculation error",
                "threshold validation failed",
                "position opening rejected",
                "bug",
                "exception",
                "error"
            ]
            log_text = "\n".join([str(line).lower() for line in logs])

            # We assert no known error or bug keywords in logs
            for phrase in error_indicators:
                assert phrase not in log_text, f"Found error indicator in logs: {phrase}"

            # Final assert: must have at least one open position matching scalping confidence conditions
            assert has_scalping_position, "No scalping signal generated position with confidence meeting threshold found within time limit."

            # Success if reached here
            return

        except (requests.RequestException, AssertionError) as e:
            last_exception = e
            # Wait a short delay before retrying
            time.sleep(5)

    # If here, timed out without success
    raise AssertionError(f"Test timed out waiting for scalping signal generation and correct position open: {last_exception}")

test_generate_scalping_signal_function_for_correct_signal_generation()