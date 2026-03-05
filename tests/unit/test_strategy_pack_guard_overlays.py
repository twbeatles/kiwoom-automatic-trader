import datetime
import unittest
from collections import deque

from config import TradingConfig
from strategy_manager import StrategyManager


class _Trader:
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "SAMSUNG",
                "price_history": [70000 + i for i in range(80)],
                "daily_prices": [70000 + i for i in range(80)],
                "minute_prices": [70000 + i for i in range(80)],
                "high_history": [70100 + i for i in range(80)],
                "low_history": [69900 + i for i in range(80)],
                "current": 70500,
                "target": 70400,
                "current_volume": 1_500_000,
                "avg_volume_5": 1_000_000,
                "avg_volume_20": 900_000,
                "avg_value_20": 50_000_000,
                "ask_price": 71000,
                "bid_price": 70000,
                "market_state": "vi",
                "open": 70000,
                "prev_close": 69900,
                "market_type": "KOSPI",
                "sector": "전기전자",
            }
        }
        self._log_cooldown_map = {}
        self._holding_or_pending_count = 0
        self.daily_realized_profit = 0
        self.daily_initial_deposit = 100_000_000
        self.initial_deposit = 100_000_000
        self.deposit = 100_000_000
        self.total_realized_profit = 0
        self._global_risk_mode = "shock"
        self._global_risk_until = datetime.datetime.now() + datetime.timedelta(minutes=5)
        self._order_health_mode = "degraded"
        self._order_health_until = datetime.datetime.now() + datetime.timedelta(minutes=5)
        self._recent_slippage_bps = deque([20.0, 18.0, 16.0], maxlen=20)

    def log(self, _msg):
        pass


class TestStrategyPackGuardOverlays(unittest.TestCase):
    def test_guard_overlays_fail_closed(self):
        trader = _Trader()
        cfg = TradingConfig(
            use_rsi=False,
            use_volume=False,
            use_liquidity=False,
            use_spread=False,
            use_macd=False,
            use_bb=False,
            use_dmi=False,
            use_stoch_rsi=False,
            use_mtf=False,
            use_gap=False,
            use_entry_scoring=False,
            max_slippage_bps=10.0,
        )
        cfg.strategy_pack = {
            "primary_strategy": "volatility_breakout",
            "entry_filters": [],
            "risk_overlays": [
                "shock_guard",
                "vi_guard",
                "liquidity_stress_guard",
                "slippage_guard",
                "order_health_guard",
            ],
            "exit_overlays": [],
        }
        cfg.feature_flags["use_modular_strategy_pack"] = True
        sm = StrategyManager(trader, cfg)

        passed, conditions, metrics = sm.evaluate_buy_conditions("005930", now_ts=1000.0)

        self.assertFalse(passed)
        self.assertFalse(conditions["risk:shock_guard"])
        self.assertFalse(conditions["risk:vi_guard"])
        self.assertFalse(conditions["risk:liquidity_stress_guard"])
        self.assertFalse(conditions["risk:slippage_guard"])
        self.assertFalse(conditions["risk:order_health_guard"])
        self.assertEqual(metrics["guard_blocked"], 1.0)


if __name__ == "__main__":
    unittest.main()
