import unittest

from app.mixins.order_sync import OrderSyncMixin


class _DummyLogger:
    def error(self, _msg):
        return None


class _Harness(OrderSyncMixin):
    def __init__(self):
        self.universe = {"005930": {"name": "삼성전자", "status": "watch", "held": 0}}
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._last_exec_event = {}
        self._position_sync_batch = set()
        self._dirty_codes = set()
        self._log_cooldown_map = {}
        self.logger = _DummyLogger()
        self.sync_calls = 0

    def log(self, _msg):
        return None

    def _sync_position_from_account(self, _code):
        self.sync_calls += 1


class TestNonFillEventSyncSuppression(unittest.TestCase):
    def test_ord_qty_only_event_does_not_trigger_position_sync(self):
        trader = _Harness()
        trader._on_order_execution(
            {
                "code": "005930",
                "order_type": "1",
                "order_status": "접수",
                "ord_qty": "10",
                "ord_prc": "70000",
            }
        )

        self.assertEqual(trader.sync_calls, 0)
        self.assertEqual(trader._last_exec_event, {})
        self.assertEqual(trader._position_sync_batch, set())


if __name__ == "__main__":
    unittest.main()
