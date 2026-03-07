import datetime
import unittest

from api.models import Position
from app.mixins.order_sync import OrderSyncMixin


class _DummySignal:
    def emit(self):
        return None


class _DummyLogger:
    def warning(self, _msg):
        return None

    def error(self, _msg):
        return None


class _StrategyStub:
    def update_market_investment(self, *_args, **_kwargs):
        return None

    def update_sector_investment(self, *_args, **_kwargs):
        return None

    def update_consecutive_results(self, *_args, **_kwargs):
        return None


class _Harness(OrderSyncMixin):
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "SAMSUNG",
                "status": "watch",
                "held": 0,
                "buy_price": 0,
                "invest_amount": 0,
                "current": 1000,
            }
        }
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._last_exec_event = {}
        self._sync_failed_codes = set()
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self._reserved_cash_by_code = {}
        self._log_cooldown_map = {}
        self.virtual_deposit = 0
        self.strategy = _StrategyStub()
        self.sound = None
        self.telegram = None
        self.logger = _DummyLogger()
        self.sig_update_table = _DummySignal()

    def _add_trade(self, _record):
        return None

    def log(self, _msg):
        return None

    def _diag_touch(self, _code, **_fields):
        return None

    def _diag_clear_pending(self, _code):
        return None


class TestOrderSyncPendingStateMachine(unittest.TestCase):
    def test_partial_fill_consumes_only_filled_reservation(self):
        trader = _Harness()
        trader._set_pending_order("005930", "buy", "BUY", expected_price=1000, submitted_qty=10, order_no="A1")
        trader._reserved_cash_by_code["005930"] = 10_000

        trader._on_position_sync_result(
            {"005930"},
            [Position(code="005930", quantity=4, buy_price=1000, buy_amount=4000)],
        )

        pending = trader._pending_order_state["005930"]
        self.assertEqual(pending["state"], "partial")
        self.assertEqual(pending["filled_qty"], 4)
        self.assertEqual(pending["remaining_qty"], 6)
        self.assertEqual(trader._reserved_cash_by_code.get("005930"), 6000)

        trader._on_position_sync_result(
            {"005930"},
            [Position(code="005930", quantity=10, buy_price=1000, buy_amount=10000)],
        )

        self.assertNotIn("005930", trader._pending_order_state)
        self.assertNotIn("005930", trader._reserved_cash_by_code)
        self.assertEqual(trader.universe["005930"]["held"], 10)

    def test_pending_timeout_does_not_auto_clear(self):
        trader = _Harness()
        trader._set_pending_order("005930", "buy", "BUY", expected_price=1000, submitted_qty=5, order_no="A2")
        trader._pending_order_state["005930"]["until"] = datetime.datetime.now() - datetime.timedelta(seconds=30)
        trader.universe["005930"]["status"] = "buy_submitted"

        trader._on_position_sync_result({"005930"}, [])

        self.assertIn("005930", trader._pending_order_state)
        self.assertEqual(trader._pending_order_state["005930"]["state"], "submitted")
        self.assertEqual(trader.universe["005930"]["status"], "buy_submitted")

    def test_cancel_or_reject_refunds_remaining_reservation(self):
        trader = _Harness()
        trader._set_pending_order("005930", "buy", "BUY", expected_price=1000, submitted_qty=5, order_no="A3")
        trader._reserved_cash_by_code["005930"] = 5000

        trader._on_order_execution(
            {
                "code": "005930",
                "order_type": "1",
                "order_status": "cancel",
                "ord_qty": "5",
                "order_no": "A3",
            }
        )

        self.assertNotIn("005930", trader._pending_order_state)
        self.assertEqual(trader.virtual_deposit, 5000)
        self.assertEqual(trader.universe["005930"]["status"], "watch")


if __name__ == "__main__":
    unittest.main()
