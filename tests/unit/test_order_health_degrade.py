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
        self.universe = {"005930": {"name": "Samsung", "held": 0, "status": "watch"}}
        self.external_positions = {}
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._position_sync_batch = set()
        self._last_exec_event = {}
        self._dirty_codes = set()
        self.logs = []
        self.logger = type("Logger", (), {"error": lambda *_args, **_kwargs: None})()

    def log(self, msg):
        self.logs.append(str(msg))

    def _sync_position_from_account(self, *_args, **_kwargs):
        return None

    def _diag_touch(self, *_args, **_kwargs):
        return None

    def _diag_clear_pending(self, *_args, **_kwargs):
        return None


class TestOrderHealthDegrade(unittest.TestCase):
    def test_degrade_and_auto_recover(self):
        trader = _Harness()

        trader._record_order_failure("BUY_ERROR", code="005930")
        trader._record_order_failure("BUY_ERROR", code="005930")

        self.assertEqual(trader._order_health_mode, "degraded")
        self.assertIsNotNone(trader._order_health_until)

        trader._update_order_health_mode(datetime.datetime.now() + datetime.timedelta(seconds=2))
        self.assertEqual(trader._order_health_mode, "normal")

    def test_cancel_event_does_not_count_as_order_failure(self):
        trader = _Harness()

        trader._on_order_execution({"code": "005930", "order_status": "취소", "order_no": "O1", "ord_qty": "1"})

        self.assertEqual(len(trader._order_fail_events), 0)

    def test_reject_event_counts_as_order_failure(self):
        trader = _Harness()

        trader._on_order_execution({"code": "005930", "order_status": "거부", "order_no": "O1", "ord_qty": "1"})

        self.assertEqual(len(trader._order_fail_events), 1)


if __name__ == "__main__":
    unittest.main()
