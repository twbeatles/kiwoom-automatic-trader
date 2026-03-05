import datetime
import unittest
from collections import deque

from app.mixins.order_sync import OrderSyncMixin
from config import TradingConfig


class _Harness(OrderSyncMixin):
    def __init__(self):
        self.config = TradingConfig(
            use_order_health_guard=True,
            order_health_fail_count=2,
            order_health_window_sec=60,
            order_health_cooldown_sec=1,
        )
        self._order_fail_events = deque(maxlen=100)
        self._order_health_mode = "normal"
        self._order_health_until = None
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class TestOrderHealthDegrade(unittest.TestCase):
    def test_degrade_and_auto_recover(self):
        trader = _Harness()

        trader._record_order_failure("BUY_ERROR", code="005930")
        trader._record_order_failure("BUY_ERROR", code="005930")

        self.assertEqual(trader._order_health_mode, "degraded")
        self.assertIsNotNone(trader._order_health_until)

        trader._update_order_health_mode(datetime.datetime.now() + datetime.timedelta(seconds=2))
        self.assertEqual(trader._order_health_mode, "normal")


if __name__ == "__main__":
    unittest.main()
