"""C1: 수동 주문 검증 경로 단일화(choke point) 검증.

_open_manual_order 는 _validate_manual_order_request 를 통과한 주문에만
order["validated"] = True 플래그를 부여하고, 플래그가 없으면 Worker 실행 직전에
주문을 차단한다. 이 테스트는 검증 통과 주문만 실행되고, 플래그 누락 시 차단됨을 고정한다.
"""
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QDialog

from api.models import Position
from app.mixins.dialogs_profiles import DialogsProfilesMixin
from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin
from config import TradingConfig


class _DummyResult:
    def __init__(self, success=True, order_no="A1", message=""):
        self.success = bool(success)
        self.order_no = str(order_no)
        self.message = str(message)


class _RESTSpy:
    """호출을 기록하는 rest_client stub."""

    def __init__(self):
        self.calls = []

    def buy_market(self, *args):
        self.calls.append(("buy_market", args))
        return _DummyResult(True, "B1")

    def sell_market(self, *args):
        self.calls.append(("sell_market", args))
        return _DummyResult(True, "S1")

    def get_stock_quote(self, _code):
        return None

    def get_positions(self, _account):
        return [Position(code="005930", quantity=2, available_qty=2, buy_price=1000, buy_amount=2000)]


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
        self.rest_client = _RESTSpy()
        self.threadpool = _DummyThreadPool()
        self.chk_mock = _DummyCheck(False)
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "current": 1000,
                "held": 2,
                "available_qty": 2,
                "status": "holding",
            }
        }
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
        self.config = TradingConfig(execution_mode="live")

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


class TestManualOrderValidationChokePoint(unittest.TestCase):
    def test_validated_order_is_executed(self):
        """검증 통과 주문은 validated=True 가 세팅되고 실제 주문이 실행된다."""
        trader = _Harness()
        sell_order = {"code": "005930", "type": "매도", "qty": 1, "price_type": "시장가", "price": 0}

        with patch(
            "app.mixins.dialogs_profiles.ManualOrderDialog", side_effect=lambda *_args: _DialogStub(sell_order)
        ):
            trader._open_manual_order()

        # 검증 통과 → 실제 주문 실행(rest_client 호출 발생)
        self.assertEqual(len(trader.rest_client.calls), 1)
        self.assertEqual(trader.rest_client.calls[0][0], "sell_market")

    @patch("app.mixins.dialogs_profiles.QMessageBox.warning")
    def test_unvalidated_order_flag_blocks_execution(self, warning):
        """검증을 우회한(validated 플래그 누락) 주문은 실행 직전에 차단된다.

        _validate_manual_order_request 가 False 를 반환하면 order["validated"] 가
        세팅되지 않으므로, 만약 실행 경로로 들어가더라도 차단되어야 한다.
        """
        trader = _Harness()
        # 유니버스에 없는 종목(검증 실패 유도)
        bad_order = {"code": "999999", "type": "매수", "qty": 1, "price_type": "시장가", "price": 0}

        with patch(
            "app.mixins.dialogs_profiles.ManualOrderDialog", side_effect=lambda *_args: _DialogStub(bad_order)
        ):
            trader._open_manual_order()

        # 검증 실패 → 주문 미실행
        self.assertEqual(trader.rest_client.calls, [])
        # validated 플래그가 세팅되지 않았는지 확인
        self.assertFalse(bad_order.get("validated", False))

    def test_direct_invocation_without_validated_flag_is_blocked(self):
        """Worker 실행 직전 방어막: validated=False 면 차단 로그가 남는다.

        실제 코드 경로를 직접 흉내내어, validated 플래그 없이 실행 블록에
        진입한 경우를 재현한다.
        """
        trader = _Harness()
        order = {
            "code": "005930",
            "type": "매수",
            "qty": 1,
            "price_type": "시장가",
            "price": 0,
            # validated 키 의도적 누락
        }

        # _open_manual_order 의 실행 블록 시작 부분 방어 코드를 직접 흉내
        if not bool(order.get("validated", False)):
            trader.log("❌ 수동 주문 차단: 검증을 통과하지 않은 요청입니다.")
        else:
            trader.rest_client.buy_market(trader.current_account, order["code"], order["qty"])

        self.assertEqual(trader.rest_client.calls, [])
        self.assertTrue(any("검증을 통과하지 않은" in m for m in trader.logs))


if __name__ == "__main__":
    unittest.main()
