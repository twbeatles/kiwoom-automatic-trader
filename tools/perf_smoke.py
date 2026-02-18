"""Simple local performance smoke test for strategy/UI sync paths."""

import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import TradingConfig
from strategy_manager import StrategyManager


class _Trader:
    def __init__(self):
        self.deposit = 100000000
        self._log_cooldown_map = {}
        self.universe = {}
        base_codes = [f"{5930 + i:06d}" for i in range(20)]
        for idx, code in enumerate(base_codes):
            prices = [70000 + ((j + idx) % 13) * 5 for j in range(220)]
            self.universe[code] = {
                "name": code,
                "price_history": prices[:],
                "daily_prices": prices[:],
                "minute_prices": prices[-120:],
                "high_history": [p + 50 for p in prices],
                "low_history": [p - 50 for p in prices],
                "current": prices[-1],
                "target": prices[-1] - 100,
                "current_volume": 1200000,
                "avg_volume_5": 900000,
                "avg_volume_20": 800000,
                "avg_value_20": 1500000000,
                "ask_price": prices[-1] + 5,
                "bid_price": prices[-1] - 5,
                "open": prices[-1] - 40,
                "prev_close": prices[-1] - 60,
                "market_type": "KOSPI",
                "sector": "전기전자",
            }

    def log(self, _msg):
        return None


def main():
    trader = _Trader()
    cfg = TradingConfig(
        use_rsi=True,
        use_volume=True,
        use_liquidity=True,
        use_spread=True,
        use_macd=True,
        use_bb=True,
        use_dmi=True,
        use_stoch_rsi=True,
        use_mtf=True,
        use_gap=True,
        use_market_limit=False,
        use_sector_limit=False,
        use_entry_scoring=True,
    )
    sm = StrategyManager(trader, cfg)

    codes = list(trader.universe.keys())
    rounds = 200

    start = time.perf_counter()
    for i in range(rounds):
        now_ts = start + i * 0.01
        for code in codes:
            sm.evaluate_buy_conditions(code, now_ts=now_ts)
    elapsed = time.perf_counter() - start

    total_calls = rounds * len(codes)
    avg_ms = (elapsed / total_calls) * 1000
    print(f"codes={len(codes)} total_calls={total_calls}")
    print(f"elapsed_sec={elapsed:.3f} avg_eval_ms={avg_ms:.4f}")


if __name__ == "__main__":
    main()
