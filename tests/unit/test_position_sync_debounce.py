import unittest
from unittest.mock import patch

from app.mixins.order_sync import OrderSyncMixin


class _DummyREST:
    def get_positions(self, _account):
        return []


class _DummyThreadPool:
    def __init__(self):
        self.started = 0

    def start(self, _worker):
        self.started += 1


class _DummySignal:
    def emit(self):
        return None


class _DummyLogger:
    def warning(self, _msg):
        return None


class _Harness(OrderSyncMixin):
    def __init__(self):
        self.universe = {"005930": {"held": 0}, "000660": {"held": 0}}
        self.rest_client = _DummyREST()
        self.current_account = "12345678"
        self._position_sync_batch = set()
        self._position_sync_pending = set()
        self._position_sync_scheduled = False
        self.threadpool = _DummyThreadPool()
        self._pending_order_state = {}
        self._last_exec_event = {}
        self._dirty_codes = set()
        self.logger = _DummyLogger()
        self.strategy = type("S", (), {
            "update_market_investment": lambda *a, **k: None,
            "update_sector_investment": lambda *a, **k: None,
            "update_consecutive_results": lambda *a, **k: None,
        })()
        self.sound = None
        self.telegram = None
        self.sig_update_table = _DummySignal()

    def _add_trade(self, _record):
        return None


class TestPositionSyncDebounce(unittest.TestCase):
    def test_sync_batches_multiple_codes_into_single_worker(self):
        trader = _Harness()
        callbacks = []

        with patch("app.mixins.order_sync.QTimer.singleShot", side_effect=lambda _ms, cb: callbacks.append(cb)):
            trader._sync_position_from_account("005930")
            trader._sync_position_from_account("000660")

            self.assertEqual(trader.threadpool.started, 0)
            self.assertEqual(len(callbacks), 1)

            callbacks[0]()

        self.assertEqual(trader.threadpool.started, 1)
        self.assertIn("__batch__", trader._position_sync_pending)


if __name__ == "__main__":
    unittest.main()
