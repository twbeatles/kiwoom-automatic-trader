import unittest
from config import TradingConfig
from strategy_manager import StrategyManager


class _DummyTrader:
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "price_history": [70000 + (i % 11) * 10 for i in range(80)],
                "daily_prices": [70000 + (i % 7) * 12 for i in range(80)],
                "minute_prices": [70000 + (i % 9) * 8 for i in range(80)],
                "high_history": [70200 + (i % 7) * 6 for i in range(80)],
                "low_history": [69800 - (i % 7) * 5 for i in range(80)],
                "current": 70300,
                "target": 70000,
                "current_volume": 1_000_000,
                "avg_volume_5": 900_000,
                "avg_volume_20": 850_000,
                "avg_value_20": 1_500_000_000,
                "ask_price": 70300,
                "bid_price": 70250,
                "open": 70000,
                "prev_close": 69900,
                "market_type": "KOSPI",
                "sector": "전기전자",
            }
        }
        self._log_cooldown_map = {}

    def log(self, _msg):
        pass


class TestStrategyDecisionCache(unittest.TestCase):
    def test_evaluate_buy_conditions_uses_cache_within_window(self):
        trader = _DummyTrader()
        cfg = TradingConfig(
            use_rsi=False,
            use_volume=False,
            use_liquidity=False,
            use_spread=False,
            use_macd=True,
            use_bb=False,
            use_dmi=False,
            use_stoch_rsi=False,
            use_mtf=False,
            use_gap=False,
            use_market_limit=False,
            use_sector_limit=False,
            use_ma=False,
            use_entry_scoring=False,
        )
        sm = StrategyManager(trader, cfg)

        calls = {"macd": 0}
        original_macd = sm.calculate_macd

        def _wrapped_macd(prices):
            calls["macd"] += 1
            return original_macd(prices)

        sm.calculate_macd = _wrapped_macd

        first = sm.evaluate_buy_conditions("005930", now_ts=1_000.0)
        second = sm.evaluate_buy_conditions("005930", now_ts=1_000.05)
        third = sm.evaluate_buy_conditions("005930", now_ts=1_000.2)

        self.assertEqual(calls["macd"], 2)
        self.assertEqual(first, second)
        self.assertEqual(first[0], third[0])


if __name__ == "__main__":
    unittest.main()
