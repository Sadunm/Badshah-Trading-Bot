import requests

def test_check_logs_api_returns_last_200_log_lines():
    base_url = "http://localhost:10000"
    logs_endpoint = f"{base_url}/api/logs"
    headers = {
        "Accept": "application/json"
    }
    try:
        response = requests.get(logs_endpoint, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request to /api/logs failed: {e}"

    try:
        logs_response = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # If response is a dict with a list under a key, extract it, else if list, use directly
    if isinstance(logs_response, dict):
        # Attempt to find the key where logs list is stored
        possible_lists = [v for v in logs_response.values() if isinstance(v, (list, tuple))]
        assert possible_lists, "No list found in logs response dict"
        logs = possible_lists[0]
    else:
        logs = logs_response

    assert isinstance(logs, (list, tuple)), f"Expected logs to be a list, got {type(logs)}"
    assert len(logs) <= 200, f"Expected at most 200 log lines, got {len(logs)}"

    for line in logs:
        assert isinstance(line, (str, dict)), "Each log line should be a string or dict"

    logs_text = " ".join(line if isinstance(line, str) else str(line) for line in logs).lower()
    keywords = ["trade", "signal", "confidence", "threshold", "position", "error", "bug"]
    assert any(keyword in logs_text for keyword in keywords), "Expected log lines to contain relevant bot operation keywords"


test_check_logs_api_returns_last_200_log_lines()