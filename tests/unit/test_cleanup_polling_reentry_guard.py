"""B1: cleanup 폴링 중 _on_order_execution 재진입 억제 검증.

_cleanup_polling=True 인 동안 _on_order_execution 이 cancel/reject 이벤트를
받아도 _pending_order_state 를 변경(cancelled/rejected 마킹)하지 않아야 한다.
체결 fill 동기화 로그 자체는 남을 수 있으나 pending mutation 은 보류된다.
"""
import unittest

from app.mixins.order_sync import OrderSyncMixin


class _DummySignal:
    def emit(self):
        return None


class _DummyLogger:
    def __init__(self):
        self.messages = []

    def warning(self, msg):
        self.messages.append(str(msg))

    def error(self, msg):
        self.messages.append(str(msg))

    def info(self, msg):
        self.messages.append(str(msg))


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
                "status": "buy_submitted",
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
        self._pending_order_state = {
            "005930": {
                "side": "buy",
                "reason": "BUY",
                "state": "submitted",
                "order_no": "O123",
                "submitted_qty": 2,
                "filled_qty": 0,
                "remaining_qty": 2,
                "expected_price": 1000,
                "child_orders": [],
                "updated_at": None,
            }
        }
        self._manual_pending_state = {}
        self._last_exec_event = {}
        self._sync_failed_codes = set()
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self._reserved_cash_by_code = {"005930": 2000}
        self._log_cooldown_map = {}
        self.virtual_deposit = 0
        self.strategy = _StrategyStub()
        self.sound = None
        self.telegram = None
        self.logger = _DummyLogger()
        self.sig_update_table = _DummySignal()
        self._cleanup_polling = False

    def log(self, _msg):
        return None

    def _diag_touch(self, _code, **_fields):
        return None

    def _diag_clear_pending(self, _code):
        return None

    def _sync_position_from_account(self, *_args, **_kwargs):
        return None

    def _update_order_health_mode(self, now_dt=None):
        return None

    def _record_order_failure(self, *_args, **_kwargs):
        return None

    def _release_reserved_cash_safe(self, *_args, **_kwargs):
        return 0

    def _release_reserved_cash_amount_safe(self, *_args, **_kwargs):
        return 0


class TestCleanupPollingReentryGuard(unittest.TestCase):
    def _cancel_event(self):
        return {
            "code": "005930",
            "stk_nm": "SAMSUNG",
            "order_type": "1",
            "order_status": "접수",
            "ord_no": "O123",
            "exec_qty": 0,
            "qty": 2,
        }

    def test_pending_mutation_deferred_during_cleanup_polling(self):
        trader = _Harness()
        # 폴링 중 상태 시뮬레이션
        trader._cleanup_polling = True
        original_state = dict(trader._pending_order_state["005930"])

        # cancel/reject 성격의 이벤트(실제로는 취소 완료)를 전달
        cancel_event = self._cancel_event()
        cancel_event["order_status"] = "취소"
        trader._on_order_execution(cancel_event)

        # pending state 가 mutated 되지 않는다(state 키 그대로).
        pending = trader._pending_order_state.get("005930", {})
        self.assertEqual(pending.get("state"), original_state["state"])
        self.assertEqual(pending.get("remaining_qty"), original_state["remaining_qty"])
        # reserved cash 도 보존된다.
        self.assertEqual(trader._reserved_cash_by_code.get("005930"), 2000)
        # 보류 로그가 남는다.
        self.assertTrue(any("pending mutation deferred" in m for m in trader.logger.messages))

    def test_pending_mutation_allowed_when_not_polling(self):
        trader = _Harness()
        trader._cleanup_polling = False

        cancel_event = self._cancel_event()
        cancel_event["order_status"] = "취소"
        trader._on_order_execution(cancel_event)

        # 폴링 중이 아니면 cancel 처리로 pending 이 정리된다.
        # (_clear_pending_order 에 의해 pop 되거나 cancelled 로 마킹)
        pending = trader._pending_order_state.get("005930")
        if pending is not None:
            # 마킹만 된 경우 상태가 cancelled 로 바뀌어야 한다.
            self.assertIn(pending.get("state", ""), {"cancelled", None})


if __name__ == "__main__":
    unittest.main()
