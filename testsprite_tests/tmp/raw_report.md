
# TestSprite AI Testing Report(MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** BADSHAH TRADEINGGG
- **Date:** 2025-10-30
- **Prepared by:** TestSprite AI Team

---

## 2️⃣ Requirement Validation Summary

#### Test TC001
- **Test Name:** verify_dashboard_stats_api_returns_correct_buss_v2_metrics
- **Test Code:** [TC001_verify_dashboard_stats_api_returns_correct_buss_v2_metrics.py](./TC001_verify_dashboard_stats_api_returns_correct_buss_v2_metrics.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/8ea8db66-2788-4ab7-9a0c-be3f0fd2095b
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC002
- **Test Name:** validate_positions_api_returns_current_open_positions_with_unrealized_pnl
- **Test Code:** [TC002_validate_positions_api_returns_current_open_positions_with_unrealized_pnl.py](./TC002_validate_positions_api_returns_current_open_positions_with_unrealized_pnl.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 47, in <module>
  File "<string>", line 29, in test_validate_positions_api_returns_current_open_positions_with_unrealized_pnl
AssertionError: Position missing 'unrealized_pnl' field.

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/d66eb737-0a60-487e-b093-4c83bdf806c2
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC003
- **Test Name:** check_logs_api_returns_last_200_log_lines
- **Test Code:** [TC003_check_logs_api_returns_last_200_log_lines.py](./TC003_check_logs_api_returns_last_200_log_lines.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/51fa71f6-c740-4234-9ca6-541fea610944
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC004
- **Test Name:** validate_trade_history_api_returns_all_closed_trades_and_current_session_trades
- **Test Code:** [TC004_validate_trade_history_api_returns_all_closed_trades_and_current_session_trades.py](./TC004_validate_trade_history_api_returns_all_closed_trades_and_current_session_trades.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 122, in <module>
  File "<string>", line 85, in test_validate_trade_history_api_returns_all_closed_trades_and_current_session_trades
AssertionError: Trade history should contain at least one trade record

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/7c880f59-85b7-4331-b815-1d90d80ebb5e
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC005
- **Test Name:** test_generate_scalping_signal_function_for_correct_signal_generation
- **Test Code:** [TC005_test_generate_scalping_signal_function_for_correct_signal_generation.py](./TC005_test_generate_scalping_signal_function_for_correct_signal_generation.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/0e229e8b-bb88-4fe6-a27c-cd0d6c6e591a
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC006
- **Test Name:** test_calculate_signal_confidence_returns_correct_percentage_value
- **Test Code:** [TC006_test_calculate_signal_confidence_returns_correct_percentage_value.py](./TC006_test_calculate_signal_confidence_returns_correct_percentage_value.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/d711e04e-a954-40a5-b15e-a1dbcd63fea4
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC007
- **Test Name:** validate_risk_management_limits_are_enforced_correctly
- **Test Code:** [TC007_validate_risk_management_limits_are_enforced_correctly.py](./TC007_validate_risk_management_limits_are_enforced_correctly.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 102, in <module>
  File "<string>", line 49, in validate_risk_management_limits_are_enforced_correctly
AttributeError: 'str' object has no attribute 'get'

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/1820de7b-b12f-4499-bf5d-a089c19eff82
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC008
- **Test Name:** verify_adaptive_confidence_threshold_adjusts_with_win_rate
- **Test Code:** [TC008_verify_adaptive_confidence_threshold_adjusts_with_win_rate.py](./TC008_verify_adaptive_confidence_threshold_adjusts_with_win_rate.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 48, in <module>
  File "<string>", line 38, in test_verify_adaptive_confidence_threshold_adjusts_with_win_rate
AssertionError: Adaptive confidence threshold 10% not matching expected 20% for win rate 0%

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/ba597aac-15b2-415c-bb2c-679e3869d6f5
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC009
- **Test Name:** test_open_position_function_respects_position_sizing_and_risk_limits
- **Test Code:** [TC009_test_open_position_function_respects_position_sizing_and_risk_limits.py](./TC009_test_open_position_function_respects_position_sizing_and_risk_limits.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/330f97d7-ba98-4dcc-8fc4-1f2ab1d90833
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC010
- **Test Name:** validate_market_regime_detection_classifies_correctly_and_adjusts_allocation
- **Test Code:** [TC010_validate_market_regime_detection_classifies_correctly_and_adjusts_allocation.py](./TC010_validate_market_regime_detection_classifies_correctly_and_adjusts_allocation.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/39c0c459-e05f-4534-8de9-0fee8d29e144/7d8d4559-8ee5-42ee-bca4-8c9d84e83877
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---


## 3️⃣ Coverage & Matching Metrics

- **60.00** of tests passed

| Requirement        | Total Tests | ✅ Passed | ❌ Failed  |
|--------------------|-------------|-----------|------------|
| ...                | ...         | ...       | ...        |
---


## 4️⃣ Key Gaps / Risks
{AI_GNERATED_KET_GAPS_AND_RISKS}
---