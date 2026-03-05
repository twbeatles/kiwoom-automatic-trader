import datetime
import unittest

from config import TradingConfig
from app.mixins.execution_engine import ExecutionEngineMixin


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.config = TradingConfig()
        self._global_risk_mode = "shock"
        self._global_risk_until = datetime.datetime.now() + datetime.timedelta(minutes=5)
        self._order_health_mode = "normal"
        self._order_health_until = None
        self._sync_failed_codes = set()
        self._recent_slippage_bps = []


class TestShockGuardEntryBlock(unittest.TestCase):
    def test_shock_guard_blocks_entry(self):
        trader = _Harness()
        info = {
            "status": "watch",
            "market_state": "normal",
            "ask_price": 100,
            "bid_price": 100,
            "avg_value_20": 0,
        }

        ok, reason = trader._can_enter_trade("005930", info, datetime.datetime.now())

        self.assertFalse(ok)
        self.assertEqual(reason, "shock_guard")


if __name__ == "__main__":
    unittest.main()
