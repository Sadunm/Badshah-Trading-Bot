from __future__ import annotations
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from .common.logging_utils import setup_logger, get_log_path
from .common.storage import load_latest_artifacts, atomic_write_json
from .common.utils import STRATS_DIR, RESULTS_DIR
from .common.validator import validate_environment
from .auto_market_observer import MarketObserver
from .auto_hyperopt_orchestrator import HyperoptOrchestrator
from .auto_backtest_runner import BacktestRunner
from .auto_refiner import StrategyRefiner
from .auto_live_executor import LiveExecutor


class CycleManager:
    def __init__(self):
        self.logger = setup_logger("auto_cycle_manager", get_log_path("auto_cycle_manager.log"))
        self.errlog = setup_logger("cycle_errors", get_log_path("cycle_errors.log"))
        self.cooldown_seconds = 3600
        self.last_maintenance = datetime.utcnow()

    def run_cycle_forever(self) -> None:
        validate_environment()
        while True:
            try:
                self._run_single_cycle()
            except Exception as e:
                self.errlog.exception(f"Cycle failed: {e}")
            self._maybe_maintenance()
            self.logger.info(f"Cooldown {self.cooldown_seconds}s before next cycle...")
            time.sleep(self.cooldown_seconds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=60))
    def _run_single_cycle(self) -> None:
        pairs = os.getenv("PAIR_WHITELIST", "BTC/USDT,ETH/USDT").split(",")
        mo = MarketObserver(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"), os.getenv("QUOTE", "USDT"), os.getenv("TIMEFRAME", "5m"), pairs)
        mo.fetch_snapshot()

        hp = HyperoptOrchestrator()
        hp.run()

        bt = BacktestRunner()
        bt.run()

        re = StrategyRefiner()
        re.run()

        self._promote_if_better()
        LiveExecutor().run()

    def _promote_if_better(self) -> None:
        arts = load_latest_artifacts("strategy", limit=3)
        if len(arts) < 1:
            return
        best = max(arts, key=lambda a: a.score)
        live_json = STRATS_DIR / "live_strategy.json"
        atomic_write_json(live_json, best.payload)
        src_py = STRATS_DIR / f"AutoGenStrategy.py"
        if src_py.exists():
            backup_name = f"AutoGenStrategy_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.py"
            shutil.copy2(src_py, STRATS_DIR / backup_name)
        self.logger.info(f"Promoted strategy with score={best.score:.4f}")

    def _maybe_maintenance(self) -> None:
        now = datetime.utcnow()
        if now - self.last_maintenance >= timedelta(days=7):
            self.logger.info("Weekly maintenance: purging old market shards")
            market_dir = RESULTS_DIR / "market"
            if market_dir.exists():
                for p in sorted(market_dir.glob("snapshot_*.json"))[:-20]:
                    try:
                        p.unlink()
                    except Exception:
                        pass
            self.last_maintenance = now


def main():
    CycleManager().run_cycle_forever()


if __name__ == "__main__":
    main()
