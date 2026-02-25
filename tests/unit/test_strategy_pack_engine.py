import unittest

import datetime

from config import TradingConfig
from strategy_manager import StrategyManager


class _DummyTrader:
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
                "avg_value_20": 2_000_000_000,
                "ask_price": 70510,
                "bid_price": 70500,
                "open": 70000,
                "prev_close": 69900,
                "market_type": "KOSPI",
                "sector": "전기전자",
            }
        }
        self._log_cooldown_map = {}
        self.deposit = 100_000_000
        self.initial_deposit = 100_000_000
        self.daily_initial_deposit = 100_000_000
        self.daily_realized_profit = 0
        self.total_realized_profit = 0
        self._holding_or_pending_count = 0

    def log(self, _msg):
        pass


class TestStrategyPackEngine(unittest.TestCase):
    def test_modular_pack_path_runs(self):
        trader = _DummyTrader()
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
        )
        cfg.strategy_pack = {
            "primary_strategy": "volatility_breakout",
            "entry_filters": [],
            "risk_overlays": [],
            "exit_overlays": [],
        }
        cfg.feature_flags["use_modular_strategy_pack"] = True
        sm = StrategyManager(trader, cfg)

        passed, conditions, metrics = sm.evaluate_buy_conditions("005930", now_ts=1000.0)

        self.assertTrue(passed)
        self.assertIn("primary:volatility_breakout", conditions)
        self.assertIn("current", metrics)

    def test_legacy_path_when_flag_disabled(self):
        trader = _DummyTrader()
        cfg = TradingConfig(use_entry_scoring=False)
        cfg.feature_flags["use_modular_strategy_pack"] = False
        sm = StrategyManager(trader, cfg)

        passed, conditions, _ = sm.evaluate_buy_conditions("005930", now_ts=2000.0)

        self.assertIn("rsi", conditions)
        self.assertIsInstance(passed, bool)

    def test_daily_loss_overlay_uses_daily_realized_metrics(self):
        trader = _DummyTrader()
        trader.daily_realized_profit = -4_000_000  # -4.0%
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
            max_daily_loss=3.0,
        )
        cfg.strategy_pack = {
            "primary_strategy": "volatility_breakout",
            "entry_filters": [],
            "risk_overlays": ["daily_loss_limit"],
            "exit_overlays": [],
        }
        cfg.feature_flags["use_modular_strategy_pack"] = True
        sm = StrategyManager(trader, cfg)

        passed, conditions, _ = sm.evaluate_buy_conditions("005930", now_ts=3000.0)

        self.assertFalse(passed)
        self.assertFalse(conditions["risk:daily_loss_limit"])

    def test_external_dependent_primary_is_blocked_when_external_data_disabled(self):
        trader = _DummyTrader()
        trader.universe["005930"]["investor_net"] = 100
        trader.universe["005930"]["program_net"] = 200
        trader.universe["005930"]["external_updated_at"] = datetime.datetime.now()
        trader.universe["005930"]["external_status"] = "fresh"
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
        )
        cfg.strategy_pack = {
            "primary_strategy": "investor_program_flow",
            "entry_filters": [],
            "risk_overlays": [],
            "exit_overlays": [],
        }
        cfg.feature_flags["use_modular_strategy_pack"] = True
        cfg.feature_flags["enable_external_data"] = False
        sm = StrategyManager(trader, cfg)

        passed, conditions, _ = sm.evaluate_buy_conditions("005930", now_ts=4000.0)

        self.assertFalse(passed)
        self.assertFalse(conditions["external_data_enabled"])


if __name__ == "__main__":
    unittest.main()
