import datetime
import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from config import TradingConfig


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.config = TradingConfig(use_liquidity_stress_guard=True, stress_spread_pct=1.0)
        self._sync_failed_codes = set()
        self._global_risk_mode = "normal"
        self._global_risk_until = None
        self._order_health_mode = "normal"
        self._order_health_until = None
        self._recent_slippage_bps = []


class TestLiquidityStressGuard(unittest.TestCase):
    def test_spread_stress_blocks_entry(self):
        trader = _Harness()
        info = {
            "status": "watch",
            "market_state": "normal",
            "ask_price": 101,
            "bid_price": 99,
            "avg_value_20": 2_000_000_000,
        }

        ok, reason = trader._can_enter_trade("005930", info, datetime.datetime.now())

        self.assertFalse(ok)
        self.assertEqual(reason, "liquidity_stress_guard")


if __name__ == "__main__":
    unittest.main()
