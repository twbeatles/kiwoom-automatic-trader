import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.mixins.execution_engine import ExecutionEngineMixin
from config import TradingConfig


class _DummySignal:
    def emit(self):
        return None


class _DummyThreadPool:
    def __init__(self):
        self.started = 0

    def start(self, _worker):
        self.started += 1


class _REST:
    def __init__(self):
        self.calls = []

    def buy_market(self, *args):
        self.calls.append(("buy_market", args))

    def sell_market(self, *args):
        self.calls.append(("sell_market", args))


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.config = TradingConfig()
        self.universe = {
            "005930": {
                "name": "Samsung",
                "status": "watch",
                "held": 3,
                "current": 1000,
                "buy_price": 900,
                "cooldown_until": None,
            }
        }
        self._pending_order_state = {}
        self._reserved_cash_by_code = {}
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self.rest_client = _REST()
        self.current_account = "ACC"
        self.deposit = 100000
        self.virtual_deposit = self.deposit
        self.threadpool = _DummyThreadPool()
        self.sig_update_table = _DummySignal()
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class TestSignalOnlyExecution(unittest.TestCase):
    def test_signal_only_buy_never_calls_broker_or_reserves_cash(self):
        trader = _Harness()
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.mixins.execution_engine.Config.ORDER_LIFECYCLE_EVENTS_FILE",
            str(Path(tmpdir) / "orders.jsonl"),
        ):
            trader._execute_buy("005930", quantity=2, price=1000)

            self.assertEqual(trader.rest_client.calls, [])
            self.assertEqual(trader.threadpool.started, 0)
            self.assertEqual(trader._reserved_cash_by_code, {})
            self.assertEqual(trader.virtual_deposit, trader.deposit)
            self.assertTrue(any("[signal-only] BUY skipped" in msg for msg in trader.logs))

    def test_signal_only_sell_never_calls_broker(self):
        trader = _Harness()
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "app.mixins.execution_engine.Config.ORDER_LIFECYCLE_EVENTS_FILE",
            str(Path(tmpdir) / "orders.jsonl"),
        ):
            trader._execute_sell("005930", quantity=1, price=1000, reason="TEST")

            self.assertEqual(trader.rest_client.calls, [])
            self.assertEqual(trader.threadpool.started, 0)
            self.assertEqual(trader.universe["005930"]["status"], "watch")
            self.assertTrue(any("[signal-only] SELL skipped" in msg for msg in trader.logs))


if __name__ == "__main__":
    unittest.main()
