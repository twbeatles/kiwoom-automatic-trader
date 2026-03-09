import unittest

from config import TradingConfig
from strategy_manager import StrategyManager


class _Trader:
    def __init__(self):
        self.deposit = 100_000
        self.universe = {
            "005930": {
                "name": "SAMSUNG",
                "current": 100,
                "high_history": [110] * 30,
                "low_history": [90] * 30,
                "price_history": [100] * 30,
            }
        }

    def log(self, _msg):
        return None


class TestRegimeSizingSingleApply(unittest.TestCase):
    def test_dynamic_sizing_applies_regime_scale_once(self):
        trader = _Trader()
        cfg = TradingConfig(use_dynamic_sizing=True, betting_ratio=10)
        manager = StrategyManager(trader, cfg)
        manager.get_regime_profile = lambda code: ("extreme", 0.4, 5.0)

        qty = manager.calculate_dynamic_position_size("005930")
        self.assertEqual(qty, 40)

    def test_default_sizing_applies_regime_scale_once(self):
        trader = _Trader()
        cfg = TradingConfig(betting_ratio=10)
        manager = StrategyManager(trader, cfg)
        manager.get_regime_profile = lambda code: ("extreme", 0.4, 5.0)

        qty = manager._default_position_size("005930")
        self.assertEqual(qty, 40)

    def test_atr_sizing_applies_regime_scale_once(self):
        trader = _Trader()
        cfg = TradingConfig(betting_ratio=10)
        manager = StrategyManager(trader, cfg)
        manager.get_regime_profile = lambda code: ("extreme", 0.4, 5.0)
        manager.calculate_atr = lambda *_args, **_kwargs: 10.0

        qty = manager.calculate_position_size("005930", risk_percent=1.0, atr_multiplier=2.0)
        self.assertEqual(qty, 20)


if __name__ == "__main__":
    unittest.main()
