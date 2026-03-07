import unittest
from unittest.mock import patch

from app.mixins.persistence_settings import PersistenceSettingsMixin


class _DummyLogger:
    def error(self, _msg):
        return None


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self, value=None):
        for cb in list(self._callbacks):
            cb(value)


class _Signals:
    def __init__(self):
        self.result = _Signal()
        self.error = _Signal()


class _FakeWorker:
    def __init__(self, fn, *args):
        self.fn = fn
        self.args = args
        self.signals = _Signals()

    def run_success(self):
        result = self.fn(*self.args)
        self.signals.result.emit(result)


class _ThreadPool:
    def __init__(self):
        self.queue = []

    def start(self, worker):
        self.queue.append(worker)

    def run_next_success(self):
        worker = self.queue.pop(0)
        worker.run_success()


class _Harness(PersistenceSettingsMixin):
    def __init__(self, sync_flush=False):
        self.trade_history = []
        self._history_dirty = False
        self._history_save_inflight = False
        self._history_save_pending_snapshot = None
        self.threadpool = _ThreadPool()
        self.logger = _DummyLogger()
        self.config = type("Cfg", (), {"sync_history_flush_on_exit": bool(sync_flush)})()
        self.saved_payloads = []
        self.synced_payload = None

    def _save_trade_history_worker(self, history):
        self.saved_payloads.append(list(history))
        return None

    def _save_trade_history_sync(self, history_snapshot=None):
        payload = list(self.trade_history) if history_snapshot is None else list(history_snapshot)
        self.synced_payload = payload
        self._history_dirty = False
        self._history_save_pending_snapshot = None
        self._history_save_inflight = False


class TestTradeHistorySingleWriter(unittest.TestCase):
    @patch("app.mixins.persistence_settings.Worker", _FakeWorker)
    def test_single_writer_keeps_latest_snapshot_order(self):
        trader = _Harness(sync_flush=False)
        trader.trade_history = [{"seq": 1}]
        trader._history_dirty = True
        trader._save_trade_history()

        trader.trade_history = [{"seq": 2}]
        trader._history_dirty = True
        trader._save_trade_history()

        self.assertEqual(len(trader.threadpool.queue), 1)
        trader.threadpool.run_next_success()
        self.assertEqual(len(trader.threadpool.queue), 1)
        trader.threadpool.run_next_success()

        self.assertEqual(trader.saved_payloads, [[{"seq": 1}], [{"seq": 2}]])
        self.assertFalse(trader._history_dirty)
        self.assertFalse(trader._history_save_inflight)
        self.assertIsNone(trader._history_save_pending_snapshot)

    @patch("app.mixins.persistence_settings.Worker", _FakeWorker)
    def test_exit_flush_persists_latest_snapshot_even_with_async_policy(self):
        trader = _Harness(sync_flush=False)
        trader.trade_history = [{"seq": 9}]
        trader._history_dirty = True
        trader._save_trade_history()

        trader.trade_history = [{"seq": 10}]
        trader._history_dirty = True
        trader._save_trade_history()

        trader._flush_trade_history_on_exit()

        self.assertEqual(trader.synced_payload, [{"seq": 10}])
        self.assertFalse(trader._history_dirty)


if __name__ == "__main__":
    unittest.main()
