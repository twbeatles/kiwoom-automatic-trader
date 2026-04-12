import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin
from app.mixins.trading_session import TradingSessionMixin


class _DummySignal:
    def emit(self):
        return None


class _DummyREST:
    def __init__(self, trader):
        self.trader = trader
        self.cancel_calls = []

    def cancel_order(self, _account, order_no, code, quantity):
        self.cancel_calls.append(
            {
                "order_no": str(order_no),
                "code": str(code),
                "quantity": int(quantity),
                "pending_present": code in self.trader._pending_order_state or code in self.trader._manual_pending_state,
            }
        )

        class _Result:
            success = True
            message = "ok"

        return _Result()

    def get_positions(self, _account):
        return []


class _Harness(TradingSessionMixin, OrderSyncMixin, ExecutionEngineMixin):
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "held": 0,
                "available_qty": 0,
                "status": "buy_submitted",
                "buy_price": 0,
                "invest_amount": 0,
            }
        }
        self.external_positions = {}
        self._pending_order_state = {
            "005930": {
                "side": "buy",
                "reason": "BUY_SPLIT",
                "state": "submitted",
                "order_no": "A1",
                "submitted_qty": 3,
                "filled_qty": 0,
                "remaining_qty": 3,
                "child_orders": [
                    {
                        "order_no": "A1-1",
                        "submitted_qty": 1,
                        "filled_qty": 0,
                        "remaining_qty": 1,
                        "reserved_cash": 1000,
                        "state": "submitted",
                    },
                    {
                        "order_no": "A1-2",
                        "submitted_qty": 2,
                        "filled_qty": 0,
                        "remaining_qty": 2,
                        "reserved_cash": 2000,
                        "state": "submitted",
                    },
                ],
            }
        }
        self._manual_pending_state = {
            "123456": {
                "side": "buy",
                "reason": "manual",
                "state": "submitted",
                "order_no": "M1",
                "submitted_qty": 1,
                "filled_qty": 0,
                "remaining_qty": 1,
                "reserved_cash": 500,
            }
        }
        self._reserved_cash_by_code = {"005930": 3000, "123456": 500}
        self._last_exec_event = {}
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._dirty_codes = set()
        self._diagnostics_dirty_codes = set()
        self._log_cooldown_map = {}
        self._holding_or_pending_count = 0
        self._sync_failed_codes = set()
        self.sig_update_table = _DummySignal()
        self.current_account = "12345678"
        self.logs = []
        self.rest_client = _DummyREST(self)

    def log(self, msg):
        self.logs.append(str(msg))

    def _diag_touch(self, *_args, **_kwargs):
        return None

    def _diag_clear_pending(self, *_args, **_kwargs):
        return None


class TestOrderCleanupShutdown(unittest.TestCase):
    def test_cleanup_cancels_split_children_and_manual_live_orders_before_local_clear(self):
        trader = _Harness()

        result = trader._cleanup_active_orders("unit_test", timeout_sec=0.0)

        self.assertEqual({call["order_no"] for call in trader.rest_client.cancel_calls}, {"A1-1", "A1-2", "M1"})
        self.assertTrue(all(call["pending_present"] for call in trader.rest_client.cancel_calls))
        self.assertEqual(result["unresolved_codes"], ["005930", "123456"])
        self.assertEqual(trader._pending_order_state, {})
        self.assertEqual(trader._manual_pending_state, {})
        self.assertEqual(trader._reserved_cash_by_code, {})


if __name__ == "__main__":
    unittest.main()
