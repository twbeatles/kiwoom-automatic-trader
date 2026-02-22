import datetime
import unittest

from app.mixins.execution_engine import ExecutionEngineMixin


class _DummySignal:
    def emit(self):
        return None


class _DummyThreadPool:
    def __init__(self):
        self.started = 0

    def start(self, _worker):
        self.started += 1


class _DummyResult:
    def __init__(self, success, message=""):
        self.success = success
        self.message = message


class _DummyREST:
    def buy_market(self, *_args):
        return _DummyResult(True, "")


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "watch",
                "held": 0,
                "current": 10000,
                "cooldown_until": None,
            }
        }
        self._pending_order_state = {}
        self._reserved_cash_by_code = {}
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self.rest_client = _DummyREST()
        self.current_account = "12345678"
        self.deposit = 50000
        self.virtual_deposit = self.deposit
        self.threadpool = _DummyThreadPool()
        self.sig_update_table = _DummySignal()
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))

    def _clear_pending_order(self, code):
        self._pending_order_state.pop(code, None)

    def _set_pending_order(self, *_args, **_kwargs):
        return None

    def _sync_position_from_account(self, *_args, **_kwargs):
        return None


class TestBuyRejectCooldown(unittest.TestCase):
    def test_execute_buy_insufficient_cash_sets_cooldown(self):
        trader = _Harness()

        trader._execute_buy("005930", quantity=10, price=10000)

        info = trader.universe["005930"]
        self.assertEqual(trader.threadpool.started, 0)
        self.assertEqual(info["status"], "cooldown")
        self.assertIsNotNone(info.get("cooldown_until"))
        self.assertTrue(any("required=" in msg for msg in trader.logs))
        self.assertEqual(trader._reserved_cash_by_code, {})
        self.assertEqual(trader.virtual_deposit, trader.deposit)

    def test_buy_reject_sets_retry_cooldown(self):
        trader = _Harness()
        trader._execute_buy("005930", quantity=1, price=10000)
        self.assertEqual(trader._reserved_cash_by_code.get("005930"), 10000)
        self.assertEqual(trader.virtual_deposit, 40000)

        trader._on_buy_result(_DummyResult(False, "rejected"), "005930", "삼성전자", 1, 10000)

        info = trader.universe["005930"]
        self.assertEqual(info["status"], "cooldown")
        self.assertGreater(info["cooldown_until"], datetime.datetime.now())
        self.assertNotIn("005930", trader._reserved_cash_by_code)
        self.assertEqual(trader.virtual_deposit, trader.deposit)


if __name__ == "__main__":
    unittest.main()

