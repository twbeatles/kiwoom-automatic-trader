import datetime
import unittest

from config import Config, TradingConfig
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
                "market_intel": {
                    **Config.DEFAULT_MARKET_INTEL_STATE,
                    "status": "fresh",
                    "intel_status": "fresh",
                    "intel_updated_at": datetime.datetime.now(),
                    "theme_score": 75.0,
                    "macro_regime": "neutral",
                },
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


class TestMarketIntelligenceStrategyPack(unittest.TestCase):
    def _config(self):
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
        cfg.feature_flags["use_modular_strategy_pack"] = True
        cfg.market_intelligence = dict(Config.DEFAULT_MARKET_INTELLIGENCE_CONFIG)
        return cfg

    def test_pack_blocks_on_negative_news_guard(self):
        trader = _DummyTrader()
        trader.universe["005930"]["market_intel"]["news_score"] = -80.0
        cfg = self._config()
        cfg.strategy_pack = {
            "primary_strategy": "volatility_breakout",
            "entry_filters": [],
            "risk_overlays": ["news_risk_guard"],
            "exit_overlays": [],
        }
        sm = StrategyManager(trader, cfg)

        passed, conditions, metrics = sm.evaluate_buy_conditions("005930", now_ts=1000.0)

        self.assertFalse(passed)
        self.assertFalse(conditions["risk:news_risk_guard"])
        self.assertLessEqual(metrics["news_score"], -60.0)

    def test_pack_accepts_theme_and_fresh_filters_when_state_is_fresh(self):
        trader = _DummyTrader()
        trader.universe["005930"]["market_intel"]["news_score"] = 20.0
        cfg = self._config()
        cfg.strategy_pack = {
            "primary_strategy": "volatility_breakout",
            "entry_filters": ["theme_heat_filter", "intel_fresh_guard"],
            "risk_overlays": [],
            "exit_overlays": [],
        }
        sm = StrategyManager(trader, cfg)

        passed, conditions, metrics = sm.evaluate_buy_conditions("005930", now_ts=2000.0)

        self.assertIsInstance(passed, bool)
        self.assertTrue(conditions["filter:theme_heat_filter"])
        self.assertTrue(conditions["filter:intel_fresh_guard"])
        self.assertGreaterEqual(metrics["theme_score"], 60.0)


if __name__ == "__main__":
    unittest.main()
