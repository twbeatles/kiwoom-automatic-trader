"""ISSUE-001: stale pending reconciliation.

연속 성공-빈 포지션 동기화 + 미체결 조회 결과를 조합해 고착 pending을
해제/격리하는지 검증한다. Worker는 동기 실행 FakeThreadpool로 대체한다.
"""
import unittest

from api.models import OpenOrder
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


class _SyncThreadpool:
    def start(self, worker):
        worker.run()


class _FakeRestClient:
    supports_open_orders = True

    def __init__(self, open_orders):
        self._open_orders = list(open_orders)
        self.open_order_calls = 0

    def get_open_orders(self, account_no):
        self.open_order_calls += 1
        return list(self._open_orders)


class _Harness(OrderSyncMixin):
    def __init__(self, open_orders):
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
        self._pending_empty_sync_count = {}
        self._pending_reconcile_inflight = set()
        self.virtual_deposit = 0
        self.is_running = True
        self.current_account = "00000000"
        self.rest_client = _FakeRestClient(open_orders)
        self.threadpool = _SyncThreadpool()
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


def _submit_buy(trader):
    trader._set_pending_order(
        "005930", "buy", "BUY", expected_price=1000, submitted_qty=5, order_no="O1"
    )
    trader._reserved_cash_by_code["005930"] = 5000
    trader.universe["005930"]["status"] = "buy_submitted"


class TestPendingReconcileStale(unittest.TestCase):
    def test_releases_pending_when_order_absent_from_open_orders(self):
        trader = _Harness(
            [OpenOrder(order_no="O9", code="005930", side="buy", quantity=2)]
        )
        _submit_buy(trader)
        for _ in range(3):
            trader._on_position_sync_result({"005930"}, [])
        self.assertNotIn("005930", trader._pending_order_state)
        self.assertNotIn("005930", trader._reserved_cash_by_code)
        self.assertEqual(trader.virtual_deposit, 5000)
        self.assertEqual(trader.universe["005930"]["status"], "watch")
        self.assertEqual(trader.rest_client.open_order_calls, 1)

    def test_isolates_sync_failed_when_open_orders_empty(self):
        trader = _Harness([])
        _submit_buy(trader)
        for _ in range(3):
            trader._on_position_sync_result({"005930"}, [])
        self.assertNotIn("005930", trader._pending_order_state)
        self.assertIn("005930", trader._sync_failed_codes)
        self.assertEqual(trader.universe["005930"]["status"], "sync_failed")
        # 매수 예약현금은 fail-closed 격리 시에도 환불된다.
        self.assertEqual(trader.virtual_deposit, 5000)

    def test_keeps_waiting_when_order_still_open(self):
        trader = _Harness(
            [OpenOrder(order_no="O1", code="005930", side="buy", quantity=5)]
        )
        _submit_buy(trader)
        for _ in range(5):
            trader._on_position_sync_result({"005930"}, [])
        pending = trader._pending_order_state.get("005930")
        self.assertIsNotNone(pending)
        self.assertEqual((pending or {})["state"], "submitted")
        self.assertNotIn("005930", trader._sync_failed_codes)
        self.assertEqual(trader._reserved_cash_by_code.get("005930"), 5000)

    def test_counter_resets_when_position_matched(self):
        trader = _Harness([])
        _submit_buy(trader)
        trader._on_position_sync_result({"005930"}, [])
        trader._on_position_sync_result({"005930"}, [])
        self.assertEqual(trader._pending_empty_sync_count.get("005930"), 2)
        from api.models import Position

        trader._on_position_sync_result(
            {"005930"},
            [Position(code="005930", quantity=5, buy_price=1000, buy_amount=5000)],
        )
        self.assertNotIn("005930", trader._pending_empty_sync_count)
        self.assertEqual(trader.rest_client.open_order_calls, 0)


if __name__ == "__main__":
    unittest.main()
