import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin
from config import TradingConfig


class _DummySignal:
    def emit(self):
        return None


class _DummyThreadPool:
    def start(self, worker):
        worker.run()


class _SplitStrategyStub:
    def get_split_orders(self, _quantity, _current_price, _order_type):
        return [(3, 1000), (3, 990), (4, 980)]


class _SplitREST:
    def __init__(self):
        self.calls = []

    def buy_limit(self, _account, code, quantity, price):
        self.calls.append((code, quantity, price))
        if price == 990:
            return type("Result", (), {"success": False, "order_no": "", "message": "reject"})()
        return type("Result", (), {"success": True, "order_no": f"O{price}", "message": ""})()


class _Harness(ExecutionEngineMixin, OrderSyncMixin):
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "watch",
                "held": 0,
                "current": 1000,
                "cooldown_until": None,
            }
        }
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._reserved_cash_by_code = {}
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._last_exec_event = {}
        self._sync_failed_codes = set()
        self._log_cooldown_map = {}
        self.rest_client = _SplitREST()
        self.current_account = "12345678"
        self.deposit = 20000
        self.virtual_deposit = self.deposit
        self.threadpool = _DummyThreadPool()
        self.sig_update_table = _DummySignal()
        self.config = TradingConfig()
        self.config.use_split = True
        self.config.execution_policy = "limit"
        self.strategy = _SplitStrategyStub()
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))

    def _sync_position_from_account(self, *_args, **_kwargs):
        return None

    def _diag_touch(self, *_args, **_kwargs):
        return None

    def _diag_clear_pending(self, *_args, **_kwargs):
        return None


class TestSplitBuyExecution(unittest.TestCase):
    def test_split_buy_submits_children_and_refunds_rejected_slice(self):
        trader = _Harness()

        trader._execute_buy("005930", quantity=10, price=1000)

        self.assertEqual(trader.rest_client.calls, [("005930", 3, 1000), ("005930", 3, 990), ("005930", 4, 980)])
        self.assertIn("005930", trader._pending_order_state)
        pending = trader._pending_order_state["005930"]
        self.assertEqual(pending["submitted_qty"], 7)
        self.assertEqual(len(pending["child_orders"]), 2)
        self.assertEqual(trader._reserved_cash_by_code.get("005930"), 6920)
        self.assertEqual(trader.universe["005930"]["status"], "buy_submitted")
        self.assertEqual(trader._holding_or_pending_count, 1)


if __name__ == "__main__":
    unittest.main()
