import unittest

from api.models import Position
from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin
from app.mixins.trading_session import TradingSessionMixin


class _DummySignal:
    def emit(self):
        return None


class _DummyStrategy:
    def update_market_investment(self, *_args, **_kwargs):
        return None

    def update_sector_investment(self, *_args, **_kwargs):
        return None


class _Harness(OrderSyncMixin, TradingSessionMixin, ExecutionEngineMixin):
    def __init__(self):
        self.universe = {}
        self.external_positions = {}
        self._pending_order_state = {}
        self._manual_pending_state = {
            "123456": {
                "side": "buy",
                "reason": "manual",
                "state": "submitted",
                "order_no": "M1",
                "submitted_qty": 2,
                "filled_qty": 0,
                "remaining_qty": 2,
                "reserved_cash": 2000,
            }
        }
        self._reserved_cash_by_code = {"123456": 2000}
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._last_exec_event = {}
        self._dirty_codes = set()
        self._diagnostics_dirty_codes = set()
        self._sync_failed_codes = set()
        self._holding_or_pending_count = 0
        self._guard_reason_by_code = {}
        self._log_cooldown_map = {}
        self.strategy = _DummyStrategy()
        self.sound = None
        self.telegram = None
        self.sig_update_table = _DummySignal()

    def _diag_touch(self, *_args, **_kwargs):
        return None

    def _diag_clear_pending(self, *_args, **_kwargs):
        return None

    def log(self, _msg):
        return None


class TestExternalPositionPromotion(unittest.TestCase):
    def test_manual_external_position_is_promoted_on_account_sync(self):
        trader = _Harness()

        trader._on_position_sync_result(
            {"123456"},
            [Position(code="123456", name="외부종목", quantity=2, available_qty=2, buy_price=1000, buy_amount=2000)],
        )

        self.assertIn("123456", trader.external_positions)
        self.assertTrue(trader.external_positions["123456"]["read_only"])
        self.assertEqual(trader.external_positions["123456"]["held"], 2)
        self.assertEqual(trader._holding_or_pending_count, 1)


if __name__ == "__main__":
    unittest.main()
