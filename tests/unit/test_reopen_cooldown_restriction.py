import datetime
import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from config import TradingConfig


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.config = TradingConfig(use_vi_guard=True)
        self._sync_failed_codes = set()
        self._global_risk_mode = "normal"
        self._global_risk_until = None
        self._order_health_mode = "normal"
        self._order_health_until = None
        self._recent_slippage_bps = []


class TestReopenCooldownRestriction(unittest.TestCase):
    def test_reopen_cooldown_blocks_entry(self):
        trader = _Harness()
        info = {
            "status": "watch",
            "market_state": "reopen_cooldown",
            "ask_price": 100,
            "bid_price": 100,
            "avg_value_20": 0,
        }

        ok, reason = trader._can_enter_trade("005930", info, datetime.datetime.now())

        self.assertFalse(ok)
        self.assertEqual(reason, "vi_guard")


if __name__ == "__main__":
    unittest.main()
