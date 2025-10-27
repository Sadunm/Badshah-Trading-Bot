import os
import time
import yaml
import argparse
from loguru import logger
from collections import deque
from typing import Dict
from src.runtime.paths import ensure_dirs, get_paths
from src.runtime.strategy_loader import ensure_strategy_or_warn, load_strategy
from src.runtime.datafeed import LiveDataFeed
from src.runtime.broker import DemoBroker
from src.runtime.performance import PerformanceTracker, should_trigger_reopt
from src.runtime.trigger import trigger_hyperopt_ml
from src.backtest import run_walk_forward, discover_datasets
from src.runtime.monitor import ResourceMonitor


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--max-ticks", type=int, default=0, help="Stop after N ticks if > 0")
    p.add_argument("--simulate", action="store_true", help="Run with offline simulated ticks")
    p.add_argument("--money-mode", type=str, default="simulated", choices=["simulated", "real"], help="Money mode gating")
    p.add_argument("--no-connectivity-check", action="store_true", help="Disable connectivity/cooldown checks entirely")
    return p.parse_args()


def main():
    args = parse_args()
    paths = get_paths()
    ensure_dirs(paths)

    with open(paths["config"], "r", encoding="utf-8") as f:
        config: Dict = yaml.safe_load(f)

    if args.simulate:
        config["simulate"] = True
        config["websocket_enabled"] = False

    logger.add(os.path.join(paths["log_dir"], "dry_trade.log"), rotation="10 MB")
    logger.info("Starting live dry trading engine")

    if not ensure_strategy_or_warn(paths):
        return

    # Pre-trade backtest verification: always run a check
    try:
        datasets = discover_datasets(paths)
        if datasets:
            bt_res = run_walk_forward(datasets, n_slices=int(config.get("wfo_slices", 6)), top_n=int(config.get("wfo_top_n", 5)))
            logger.info(f"Backtest verification complete: {bt_res.get('reports_root')}")
        else:
            logger.warning("No historical datasets found; running without WFO reports")
    except Exception as e:
        logger.warning(f"Backtest check failed or unavailable: {e}")

    # Money mode gating
    if args.money_mode == "real":
        confirm_path = os.path.join(paths["root"], "user_data", "confirm_real_trading.txt")
        os.makedirs(os.path.dirname(confirm_path), exist_ok=True)
        if not os.path.exists(confirm_path):
            logger.error("Real-money mode requested but not confirmed. Create user_data/confirm_real_trading.txt with 'APPROVED'.")
            return
        try:
            with open(confirm_path, "r", encoding="utf-8") as cf:
                ok = "APPROVED" in cf.read().upper()
        except Exception:
            ok = False
        if not ok:
            logger.error("Real-money confirmation file exists but not approved. Aborting.")
            return

    strategy = load_strategy(paths)
    datafeed = LiveDataFeed(config)
    broker = DemoBroker(config)
    perf = PerformanceTracker(paths, window_trades=config.get("performance_window_trades", 300))

    # Live reporting session dir
    session_dir = os.path.join(paths["root"], "src", "data", "live_reports", f"session_{int(time.time())}")
    os.makedirs(session_dir, exist_ok=True)

    # Resource monitor
    disable_conn = bool(args.no_connectivity_check or (not bool(config.get("connectivity_check", True))))
    monitor = None
    if not disable_conn:
        monitor = ResourceMonitor(
            paths["log_dir"],
            cpu_limit=float(config.get("cpu_limit_pct", 90.0)),
            ram_limit=float(config.get("ram_limit_pct", 90.0)),
            net_url=str(config.get("net_check_url", "https://www.google.com")),
            interval_sec=float(config.get("resource_check_interval_sec", 5.0)),
        )
        monitor.start()

    # Re-optimization debounce / controls
    min_ticks_between_reopt = int(config.get("min_ticks_between_reopt", 500))
    min_seconds_between_reopt = int(config.get("min_seconds_between_reopt", 60))
    min_trades_for_reopt = int(config.get("min_trades_for_reopt", 100))
    last_reopt_tick = -min_ticks_between_reopt
    last_reopt_time = 0

    ticks_processed = 0
    # Trade symmetry control (BUY/SELL exposure gap <= 5%) over rolling window
    symmetry_window = int(config.get("symmetry_window_trades", 500))
    symmetry_max_gap_pct = float(config.get("symmetry_max_gap_pct", 5.0)) / 100.0
    recent_sides: deque[str] = deque(maxlen=symmetry_window)

    try:
        # Start receiving ticks (websocket or REST fallback)
        tick_iter = datafeed.stream_ticks()
        volatility_acc = []
        for tick in tick_iter:
            # tick: {symbol, price, ts}
            if monitor is not None and monitor.should_cooldown():
                logger.warning("Cooldown triggered by resource monitor; stopping trading loop.")
                break
            action = strategy.generate_signal(tick=tick, broker_state=broker.get_state())

            # Enforce directional balance: if one side exceeds allowed gap, skip further orders on that side
            if action in ("BUY", "SELL") and len(recent_sides) >= max(10, int(symmetry_window * 0.2)):
                buy_ct = sum(1 for s in recent_sides if s == "BUY")
                sell_ct = sum(1 for s in recent_sides if s == "SELL")
                total_ct = max(1, buy_ct + sell_ct)
                gap = abs(buy_ct - sell_ct) / float(total_ct)
                over_side = "BUY" if buy_ct > sell_ct else "SELL"
                if gap > symmetry_max_gap_pct and action == over_side:
                    # Throttle over-represented side
                    action = "HOLD"
            order = None
            if action in ("BUY", "SELL"):
                order = broker.execute(tick["symbol"], action, tick["price"]) 
            if order is not None:
                perf.record_trade(order)
                # Record side for symmetry window
                if order.get("side") in ("BUY", "SELL"):
                    recent_sides.append(order.get("side"))

            # Track simple volatility proxy from tick-to-tick returns (per symbol aggregated)
            if len(volatility_acc) > 1000:
                volatility_acc.pop(0)
            volatility_acc.append(tick["price"])  # reuse list for price series
            volatility = 0.0
            if len(volatility_acc) >= 2:
                last = volatility_acc[-1]
                prev = volatility_acc[-2]
                if prev > 0:
                    volatility = abs((last - prev) / prev) * 100.0

            if perf.num_trades % 10 == 0 and perf.num_trades > 0:
                metrics = perf.compute_metrics()
                logger.info(
                    f"Trades={perf.num_trades} PnL={metrics['total_profit']:.2f} MDD={metrics['max_drawdown']:.2f} Win%={metrics['winrate_pct']:.1f} Sharpe={metrics['sharpe']:.2f}"
                )
                # Adaptive risk reduction on deep drawdown
                try:
                    start_bal = float(getattr(broker, "start_balance", 0.0) or 0.0)
                    mdd_rel = (metrics.get("max_drawdown", 0.0) / start_bal) if start_bal > 0 else 0.0
                except Exception:
                    mdd_rel = 0.0
                if mdd_rel > 0.12:  # 12% equity drawdown threshold
                    old_risk = broker.risk_per_trade_pct
                    broker.risk_per_trade_pct = max(0.10 / 100.0, old_risk * 0.7)
                    logger.warning(f"Adaptive risk reduction engaged: risk_per_trade_pct {old_risk*100:.3f}% -> {broker.risk_per_trade_pct*100:.3f}%")
                # Debounced, stricter re-optimization trigger
                elapsed_ticks = ticks_processed - last_reopt_tick
                elapsed_seconds = time.time() - last_reopt_time
                if (
                    perf.num_trades >= min_trades_for_reopt
                    and elapsed_ticks >= min_ticks_between_reopt
                    and elapsed_seconds >= min_seconds_between_reopt
                    and should_trigger_reopt(metrics, config, volatility=volatility)
                ):
                    logger.warning("Performance/volatility trigger fired (debounced); running hyperopt+ML...")
                    trigger_hyperopt_ml(paths)
                    strategy = load_strategy(paths)
                    last_reopt_tick = ticks_processed
                    last_reopt_time = time.time()

            ticks_processed += 1
            if args.max_ticks and ticks_processed >= args.max_ticks:
                break

    except KeyboardInterrupt:
        logger.info("Stopping dry trading by user request.")
    finally:
        perf.flush()
        # Persist session artifacts
        try:
            import shutil
            # copy trades.csv and metrics.json to session dir
            shutil.copy2(os.path.join(paths["log_dir"], "trades.csv"), os.path.join(session_dir, "trades.csv"))
            shutil.copy2(os.path.join(paths.get("reports_dir", paths["log_dir"]), "metrics.json"), os.path.join(session_dir, "metrics.json"))
        except Exception:
            pass
        try:
            if monitor is not None:
                monitor.stop()
        except Exception:
            pass
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
