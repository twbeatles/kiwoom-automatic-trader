import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin
from app.mixins.trading_session import TradingSessionMixin
from api.models import OrderResult


class _REST:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def cancel_order(self, account, order_no, code, quantity):
        self.calls.append((account, order_no, code, quantity))
        return OrderResult(success=self.success, order_no=order_no, code=code, message="ok" if self.success else "fail")


class _Harness(TradingSessionMixin, OrderSyncMixin, ExecutionEngineMixin):
    def __init__(self, rest):
        self.rest_client = rest
        self.current_account = "ACC"
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._reserved_cash_by_code = {}
        self.virtual_deposit = 0
        self.universe = {"005930": {"held": 0}}
        self._holding_or_pending_count = 0
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))

    def _diag_touch(self, *_args, **_kwargs):
        return None

    def _diag_clear_pending(self, *_args, **_kwargs):
        return None


class TestStopTradingCancelPolicy(unittest.TestCase):
    def test_cancel_success_clears_pending_and_releases_reserved_cash(self):
        rest = _REST(success=True)
        trader = _Harness(rest)
        trader._set_pending_order("005930", "buy", "BUY", expected_price=1000, submitted_qty=3, order_no="O1")
        trader._reserved_cash_by_code["005930"] = 3000

        trader._cancel_pending_orders_before_stop()

        self.assertEqual(rest.calls, [("ACC", "O1", "005930", 3)])
        self.assertNotIn("005930", trader._pending_order_state)
        self.assertNotIn("005930", trader._reserved_cash_by_code)
        self.assertEqual(trader.virtual_deposit, 3000)

    def test_cancel_failure_keeps_pending_and_reserved_cash(self):
        rest = _REST(success=False)
        trader = _Harness(rest)
        trader._set_pending_order("005930", "buy", "BUY", expected_price=1000, submitted_qty=3, order_no="O1")
        trader._reserved_cash_by_code["005930"] = 3000

        trader._cancel_pending_orders_before_stop()

        self.assertIn("005930", trader._pending_order_state)
        self.assertEqual(trader._pending_order_state["005930"]["state"], "sync_failed")
        self.assertEqual(trader._reserved_cash_by_code["005930"], 3000)
        self.assertEqual(trader.virtual_deposit, 0)


if __name__ == "__main__":
    unittest.main()
