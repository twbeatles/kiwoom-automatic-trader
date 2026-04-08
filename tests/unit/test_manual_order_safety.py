import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QDialog

from app.mixins.dialogs_profiles import DialogsProfilesMixin
from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin


class _DummyResult:
    def __init__(self, success=True, order_no="A1", message=""):
        self.success = bool(success)
        self.order_no = str(order_no)
        self.message = str(message)


class _DummyREST:
    def buy_market(self, *_args):
        return _DummyResult(True, "B1")

    def sell_market(self, *_args):
        return _DummyResult(True, "S1")

    def get_stock_quote(self, _code):
        return None


class _DummyThreadPool:
    def start(self, worker):
        worker.run()


class _DummySignal:
    def emit(self):
        return None


class _DummyCheck:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return bool(self._checked)


class _Harness(DialogsProfilesMixin, OrderSyncMixin, ExecutionEngineMixin):
    def __init__(self):
        self.is_connected = True
        self.current_account = "12345678"
        self.rest_client = _DummyREST()
        self.threadpool = _DummyThreadPool()
        self.chk_mock = _DummyCheck(False)
        self.universe = {"005930": {"name": "삼성전자", "current": 1000, "held": 0, "status": "watch"}}
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._reserved_cash_by_code = {}
        self._holding_or_pending_count = 0
        self.deposit = 100000
        self.virtual_deposit = self.deposit
        self._dirty_codes = set()
        self.sig_update_table = _DummySignal()
        self.logs = []
        self.guard_calls = 0

    def log(self, msg):
        self.logs.append(str(msg))

    def _confirm_live_trading_guard(self):
        self.guard_calls += 1
        return True

    def _sync_position_from_account(self, *_args, **_kwargs):
        return None

    def _diag_touch(self, *_args, **_kwargs):
        return None

    def _diag_clear_pending(self, *_args, **_kwargs):
        return None


class _DialogStub:
    def __init__(self, order_result):
        self.order_result = dict(order_result)

    def exec(self):
        return QDialog.DialogCode.Accepted


class TestManualOrderSafety(unittest.TestCase):
    @patch("app.mixins.dialogs_profiles.QMessageBox.warning")
    def test_validate_manual_order_rejects_invalid_code_and_zero_limit(self, warning):
        trader = _Harness()

        self.assertFalse(
            trader._validate_manual_order_request(
                {"code": "ABC123", "type": "매수", "qty": 1, "price_type": "시장가", "price": 0}
            )
        )
        self.assertFalse(
            trader._validate_manual_order_request(
                {"code": "005930", "type": "매수", "qty": 1, "price_type": "지정가", "price": 0}
            )
        )
        self.assertGreaterEqual(warning.call_count, 2)

    def test_manual_live_guard_runs_for_each_order(self):
        trader = _Harness()
        sell_order = {"code": "005930", "type": "매도", "qty": 1, "price_type": "시장가", "price": 0}

        with patch("app.mixins.dialogs_profiles.ManualOrderDialog", side_effect=lambda *_args: _DialogStub(sell_order)):
            trader._open_manual_order()
            trader._open_manual_order()

        self.assertEqual(trader.guard_calls, 2)

    def test_external_manual_buy_reserves_cash_until_order_sync(self):
        trader = _Harness()

        trader._on_manual_order_result(
            _DummyResult(success=True, order_no="EXT1"),
            {"code": "123456", "qty": 3, "price": 1000, "expected_price": 1000},
            "매수",
            "123456",
        )

        self.assertEqual(trader._reserved_cash_by_code.get("123456"), 3000)
        self.assertIn("123456", trader._manual_pending_state)
        self.assertEqual(trader._manual_pending_state["123456"]["reserved_cash"], 3000)

    @patch("app.mixins.dialogs_profiles.QMessageBox.warning")
    def test_market_buy_without_price_hint_is_rejected(self, warning):
        trader = _Harness()

        valid = trader._validate_manual_order_request(
            {"code": "123456", "type": "매수", "qty": 1, "price_type": "시장가", "price": 0}
        )

        self.assertFalse(valid)
        self.assertTrue(warning.called)


if __name__ == "__main__":
    unittest.main()
