import unittest
from unittest.mock import patch

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
        self.universe = {"005930": {"name": "SAMSUNG", "status": "watch", "held": 0, "current": 1000}}
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._pending_order_state = {}
        self._last_exec_event = {}
        self._sync_failed_codes = set()
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self._reserved_cash_by_code = {"005930": 1000}
        self.virtual_deposit = 0
        self.logger = _DummyLogger()
        self.strategy = _StrategyStub()
        self.sound = None
        self.telegram = None
        self.sig_update_table = _DummySignal()
        self.diag = {}

    def _diag_touch(self, code, **fields):
        row = self.diag.get(code, {})
        row.update(fields)
        self.diag[code] = row

    def _diag_clear_pending(self, code):
        row = self.diag.get(code, {})
        row["pending_side"] = ""
        row["pending_reason"] = ""
        row["pending_until"] = None
        self.diag[code] = row

    def _add_trade(self, _record):
        return None

    def log(self, _msg):
        return None


class TestDiagnosticsState(unittest.TestCase):
    def test_pending_sync_failed_and_recovery_updates_diagnostics(self):
        trader = _Harness()
        trader._set_pending_order("005930", "buy", "BUY")
        self.assertEqual(trader.diag["005930"]["pending_side"], "buy")

        with patch("app.mixins.order_sync.Config.POSITION_SYNC_MAX_RETRIES", 1), patch(
            "app.mixins.order_sync.QTimer.singleShot", side_effect=lambda *_args, **_kwargs: None
        ):
            trader._on_position_sync_error({"005930"}, Exception("boom1"))
            trader._position_sync_scheduled = False
            trader._on_position_sync_error({"005930"}, Exception("boom2"))

        self.assertEqual(trader.universe["005930"]["status"], "sync_failed")
        self.assertEqual(trader.diag["005930"]["sync_status"], "sync_failed")
        self.assertEqual(trader.virtual_deposit, 1000)  # reservation refunded on sync_failed

        positions = [Position(code="005930", quantity=1, buy_price=1000, buy_amount=1000)]
        trader._on_position_sync_result({"005930"}, positions)

        self.assertEqual(trader.universe["005930"]["status"], "holding")
        self.assertEqual(trader.diag["005930"]["sync_status"], "holding")
        self.assertEqual(trader.diag["005930"]["retry_count"], 0)


if __name__ == "__main__":
    unittest.main()
