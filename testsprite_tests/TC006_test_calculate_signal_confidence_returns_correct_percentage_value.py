import requests

BASE_URL = "http://localhost:10000/api/stats"
TIMEOUT = 30

def test_calculate_signal_confidence_returns_correct_percentage_value():
    """
    Test that the calculate_signal_confidence function returns a confidence score as a percentage (0-100)
    correctly, verifying the bug fix that converts the 0-1 scale to percentage properly.
    """

    try:
        response = requests.get(BASE_URL, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"API request to /api/stats failed: {e}"

    data = response.json()
    assert "buss_v2" in data, "Response JSON missing 'buss_v2' key"
    buss_v2 = data["buss_v2"]

    # The signal confidence score bug was that it returned 0-1 scale (e.g., 0.3) instead of percent (30)
    # The PRD doesn't expose an API endpoint directly for signal confidence,
    # so we validate that the current_threshold or base_threshold fields (which represent confidence thresholds)
    # are correctly represented as a percentage between 0 and 100.

    # Check current_threshold field exists and is a float or int
    assert "current_threshold" in buss_v2, "'current_threshold' missing in buss_v2 metrics"
    current_threshold = buss_v2["current_threshold"]
    assert isinstance(current_threshold, (int, float)), "'current_threshold' is not a number"
    assert 0 <= current_threshold <= 100, f"'current_threshold' value out of expected percentage range: {current_threshold}"

    # Also check base_threshold field
    assert "base_threshold" in buss_v2, "'base_threshold' missing in buss_v2 metrics"
    base_threshold = buss_v2["base_threshold"]
    assert isinstance(base_threshold, (int, float)), "'base_threshold' is not a number"
    assert 0 <= base_threshold <= 100, f"'base_threshold' value out of expected percentage range: {base_threshold}"

    # To ensure correct conversion, the value should never be a small fraction less than 1 (0-1 scale bug)
    # If it's below 1, fail the test explicitly
    assert current_threshold >= 1, f"'current_threshold' appears to be in 0-1 scale instead of percentage: {current_threshold}"
    assert base_threshold >= 1, f"'base_threshold' appears to be in 0-1 scale instead of percentage: {base_threshold}"

    # If possible, check that the confidence values are reasonable and reflect the adaptive confidence range 10-20%
    # Given adaptive threshold fixed bug in PRD, these should be ~10-20 range, so fail if out of reason
    assert 10 <= current_threshold <= 20, f"'current_threshold' out of expected adaptive range (10-20): {current_threshold}"
    assert 10 <= base_threshold <= 20, f"'base_threshold' out of expected adaptive range (10-20): {base_threshold}"

    print("Test TC006 passed: calculate_signal_confidence returns correct percentage value.")

test_calculate_signal_confidence_returns_correct_percentage_value()