import unittest

from app.mixins.dialogs_profiles import DialogsProfilesMixin
from app.mixins.order_sync import OrderSyncMixin


class _OrderResult:
    def __init__(self, success=True, order_no="1001", message=""):
        self.success = bool(success)
        self.order_no = str(order_no)
        self.message = str(message)


class _Harness(DialogsProfilesMixin, OrderSyncMixin):
    def __init__(self):
        self.universe = {"005930": {"name": "삼성전자"}}
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._holding_or_pending_count = 0
        self._log_cooldown_map = {}
        self.sync_calls = 0
        self.logs = []

    def _sync_position_from_account(self, _code):
        self.sync_calls += 1

    def log(self, msg):
        self.logs.append(str(msg))


class TestManualOrderExternalPending(unittest.TestCase):
    def test_external_manual_order_uses_manual_pending_map_only(self):
        trader = _Harness()
        trader._on_manual_order_result(_OrderResult(success=True), "매수", "123456")

        self.assertIn("123456", trader._manual_pending_state)
        self.assertNotIn("123456", trader._pending_order_state)
        self.assertEqual(trader._holding_or_pending_count, 0)
        self.assertEqual(trader.sync_calls, 0)


if __name__ == "__main__":
    unittest.main()
