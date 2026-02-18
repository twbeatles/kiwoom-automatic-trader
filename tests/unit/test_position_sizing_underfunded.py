import unittest

from config import TradingConfig
from strategy_manager import StrategyManager


class _DummyTrader:
    def __init__(self):
        self.deposit = 1000
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "current": 5000,
                "price_history": [5000 + (i % 3) for i in range(30)],
                "high_history": [5005 + (i % 3) for i in range(30)],
                "low_history": [4995 - (i % 2) for i in range(30)],
            }
        }
        self._log_cooldown_map = {}

    def log(self, _msg):
        return None


class TestPositionSizingUnderfunded(unittest.TestCase):
    def test_position_size_returns_zero_when_underfunded(self):
        trader = _DummyTrader()
        cfg = TradingConfig(betting_ratio=10.0, use_dynamic_sizing=False)
        sm = StrategyManager(trader, cfg)

        self.assertEqual(sm._default_position_size("005930"), 0)
        self.assertEqual(sm.calculate_dynamic_position_size("005930"), 0)
        self.assertEqual(sm.calculate_position_size("005930", risk_percent=1.0), 0)


if __name__ == "__main__":
    unittest.main()
