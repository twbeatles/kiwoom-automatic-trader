import unittest
from unittest.mock import patch

from app.mixins.order_sync import OrderSyncMixin


class _DummyLogger:
    def __init__(self):
        self.messages = []

    def warning(self, msg):
        self.messages.append(str(msg))


class _Harness(OrderSyncMixin):
    def __init__(self):
        self._position_sync_pending = set()
        self._position_sync_batch = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self.logger = _DummyLogger()


class TestPositionSyncBackoff(unittest.TestCase):
    def test_position_sync_backoff_stops_after_max_retries(self):
        trader = _Harness()
        scheduled = []

        with patch("app.mixins.order_sync.QTimer.singleShot", side_effect=lambda ms, _cb: scheduled.append(ms)), patch(
            "app.mixins.order_sync.Config.POSITION_SYNC_MAX_RETRIES", 2
        ), patch("app.mixins.order_sync.Config.POSITION_SYNC_DEBOUNCE_MS", 100), patch(
            "app.mixins.order_sync.Config.POSITION_SYNC_BACKOFF_MAX_MS", 250
        ):
            trader._on_position_sync_error({"005930"}, Exception("e1"))
            self.assertEqual(scheduled, [100])

            trader._position_sync_scheduled = False
            trader._on_position_sync_error({"005930"}, Exception("e2"))
            self.assertEqual(scheduled, [100, 200])

            trader._position_sync_scheduled = False
            trader._on_position_sync_error({"005930"}, Exception("e3"))
            self.assertEqual(scheduled, [100, 200])
            self.assertEqual(trader._position_sync_batch, set())
            self.assertEqual(trader._position_sync_retry_count, 0)


if __name__ == "__main__":
    unittest.main()
