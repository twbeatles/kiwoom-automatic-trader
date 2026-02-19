import unittest
from unittest.mock import patch

from api.models import ExecutionData
from app.mixins.execution_engine import ExecutionEngineMixin
from app.mixins.order_sync import OrderSyncMixin


class _DummyLogger:
    def __init__(self):
        self.messages = []

    def warning(self, msg):
        self.messages.append(str(msg))

    def error(self, msg):
        self.messages.append(str(msg))


class _OrderSyncHarness(OrderSyncMixin):
    def __init__(self):
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._pending_order_state = {"005930": {"side": "buy"}}
        self._sync_failed_codes = set()
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self._log_cooldown_map = {}
        self.universe = {
            "005930": {"name": "삼성전자", "status": "buy_submitted", "held": 0},
            "000660": {"name": "SK하이닉스", "status": "watch", "held": 0},
        }
        self.logger = _DummyLogger()
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class _StrategyStub:
    def check_atr_stop_loss(self, _code):
        return False, 0

    def calculate_partial_take_profit(self, _code, _profit):
        return None

    def evaluate_buy_conditions(self, _code, _ts):
        return True, {}, {}


class _ExecutionHarness(ExecutionEngineMixin):
    def __init__(self):
        self.is_running = True
        self.strategy = _StrategyStub()
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "sync_failed",
                "held": 0,
                "target": 70000,
                "buy_price": 0,
                "current": 69000,
                "price_history": [],
                "minute_prices": [],
            }
        }
        self._sync_failed_codes = {"005930"}
        self._pending_order_state = {}
        self._dirty_codes = set()
        self.buy_calls = 0
        self.sell_calls = 0

    def _execute_buy(self, *_args, **_kwargs):
        self.buy_calls += 1

    def _execute_sell(self, *_args, **_kwargs):
        self.sell_calls += 1


class TestSyncFailedFailsafe(unittest.TestCase):
    def test_retry_exceeded_marks_code_as_sync_failed(self):
        trader = _OrderSyncHarness()
        scheduled = []

        with patch("app.mixins.order_sync.QTimer.singleShot", side_effect=lambda ms, _cb: scheduled.append(ms)), patch(
            "app.mixins.order_sync.Config.POSITION_SYNC_MAX_RETRIES", 1
        ), patch("app.mixins.order_sync.Config.POSITION_SYNC_DEBOUNCE_MS", 100), patch(
            "app.mixins.order_sync.Config.POSITION_SYNC_BACKOFF_MAX_MS", 500
        ):
            trader._on_position_sync_error({"005930"}, Exception("e1"))
            trader._position_sync_scheduled = False
            trader._on_position_sync_error({"005930"}, Exception("e2"))

        self.assertEqual(scheduled, [100])
        self.assertEqual(trader.universe["005930"]["status"], "sync_failed")
        self.assertEqual(trader.universe["000660"]["status"], "watch")
        self.assertIn("005930", trader._sync_failed_codes)
        self.assertNotIn("005930", trader._pending_order_state)

    def test_execution_engine_skips_sync_failed_code(self):
        trader = _ExecutionHarness()

        trader._on_execution(
            ExecutionData(
                code="005930",
                name="삼성전자",
                exec_price=71000,
                total_volume=100,
                ask_price=71000,
                bid_price=70900,
            )
        )

        self.assertEqual(trader.buy_calls, 0)
        self.assertEqual(trader.sell_calls, 0)
        self.assertIn("005930", trader._dirty_codes)


if __name__ == "__main__":
    unittest.main()
