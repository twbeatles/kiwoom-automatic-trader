import datetime
import unittest
from collections import deque

from app.mixins.execution_engine import ExecutionEngineMixin
from config import TradingConfig


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.config = TradingConfig(use_slippage_guard=True, max_slippage_bps=10.0, slippage_window_trades=3)
        self._sync_failed_codes = set()
        self._global_risk_mode = "normal"
        self._global_risk_until = None
        self._order_health_mode = "normal"
        self._order_health_until = None
        self._recent_slippage_bps = deque([15.0, 20.0, 25.0], maxlen=100)


class TestSlippageGuardPolicySwitch(unittest.TestCase):
    def test_slippage_guard_blocks_then_can_be_disabled(self):
        trader = _Harness()
        info = {
            "status": "watch",
            "market_state": "normal",
            "ask_price": 100,
            "bid_price": 100,
            "avg_value_20": 0,
        }

        blocked, reason = trader._can_enter_trade("005930", info, datetime.datetime.now())
        self.assertFalse(blocked)
        self.assertEqual(reason, "slippage_guard")

        trader.config.use_slippage_guard = False
        allowed, reason2 = trader._can_enter_trade("005930", info, datetime.datetime.now())
        self.assertTrue(allowed)
        self.assertEqual(reason2, "")


if __name__ == "__main__":
    unittest.main()
