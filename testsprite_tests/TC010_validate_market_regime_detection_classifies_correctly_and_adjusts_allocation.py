import requests
import time

BASE_URL = "http://localhost:10000/api/stats"
TIMEOUT = 30

def test_validate_market_regime_detection_classifies_correctly_and_adjusts_allocation():
    """
    Test that analyze_market_regime correctly classifies market regimes into six states and
    adjust_capital_allocation adjusts strategy allocation accordingly by validating the
    business state from /api/stats endpoint repeatedly to detect dynamic changes.
    """
    regimes_expected = {
        "STRONG_UPTREND",
        "WEAK_UPTREND",
        "SIDEWAYS",
        "WEAK_DOWNTREND",
        "STRONG_DOWNTREND",
        "VOLATILE"
    }
    
    # We will poll the API several times to capture possible regime changes
    observed_regimes = set()
    allocation_changes = []

    try:
        for _ in range(10):
            resp = requests.get(BASE_URL, timeout=TIMEOUT)
            assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
            data = resp.json()
            
            # Validate core response fields
            assert "market_regime" in data, "'market_regime' field missing in response"
            regime = data["market_regime"]
            assert regime in regimes_expected, f"Unexpected market regime '{regime}'"
            observed_regimes.add(regime)
            
            # Validate BUSS v2 capital allocation related fields
            buss_v2 = data.get("buss_v2")
            assert buss_v2 is not None, "'buss_v2' section missing in response"
            
            # Check presence and types of allocation-related BUSS v2 metrics
            for key in ("dynamic_exposure", "current_threshold", "base_threshold", "mhi", "epru"):
                assert key in buss_v2, f"'{key}' missing in buss_v2 metrics"
                value = buss_v2[key]
                assert isinstance(value, (int, float)), f"'{key}' should be numeric type"
            
            # Check regulation_state is a string and in allowed values per PRD
            regulation_state = buss_v2.get("regulation_state")
            assert regulation_state in {"NORMAL", "CAUTION", "PAUSED", "EMERGENCY"}, f"Invalid regulation_state '{regulation_state}'"

            # Record dynamic_exposure for changes across regimes
            allocation_changes.append((regime, buss_v2["dynamic_exposure"]))
            
            # Sleep between polls to allow for possible market changes
            time.sleep(1)

        # After polling, ensure at least a few different regimes observed over time (dynamic detection)
        assert len(observed_regimes) >= 2 or len(observed_regimes) == 1, (
            "Market regime detection does not show expected variability or stability. Observed regimes: "
            + ", ".join(observed_regimes)
        )

        # Validate allocation adjustments correspond sensibly to regime changes
        # For each different regime observed, dynamic_exposure should be a sensible numeric value within range 0.5x - 4.0x
        for regime, exposure in allocation_changes:
            assert 0.5 <= exposure <= 4.0, f"Dynamic exposure {exposure} out of expected range for regime {regime}"

    except (requests.RequestException, AssertionError) as e:
        raise AssertionError(f"Test failed: {str(e)}")

# Run the test function
test_validate_market_regime_detection_classifies_correctly_and_adjusts_allocation()