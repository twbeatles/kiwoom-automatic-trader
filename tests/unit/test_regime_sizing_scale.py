import unittest

from config import TradingConfig
from strategy_manager import StrategyManager


class _Trader:
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "SAMSUNG",
                "current": 100,
                "price_history": [100, 120, 80, 130, 70, 125, 75, 120, 80, 118, 82, 116, 84, 114, 86, 112],
                "high_history": [110, 130, 90, 140, 80, 135, 85, 130, 90, 128, 92, 126, 94, 124, 96, 122],
                "low_history": [90, 110, 70, 120, 60, 115, 65, 110, 70, 108, 72, 106, 74, 104, 76, 102],
            }
        }

    def log(self, _msg):
        pass


class TestRegimeSizingScale(unittest.TestCase):
    def test_extreme_regime_scales_down_size(self):
        trader = _Trader()
        cfg = TradingConfig(
            use_regime_sizing=True,
            regime_elevated_atr_pct=2.0,
            regime_extreme_atr_pct=3.0,
            regime_size_scale_elevated=0.7,
            regime_size_scale_extreme=0.4,
        )
        manager = StrategyManager(trader, cfg)

        regime, scale, atr_pct = manager.get_regime_profile("005930")
        sized = manager.apply_regime_size_scale("005930", 100)

        self.assertEqual(regime, "extreme")
        self.assertGreaterEqual(atr_pct, 3.0)
        self.assertAlmostEqual(scale, 0.4)
        self.assertEqual(sized, 40)


if __name__ == "__main__":
    unittest.main()
