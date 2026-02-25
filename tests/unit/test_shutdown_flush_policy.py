import unittest

from app.mixins.system_shell import SystemShellMixin


class _DummyCheck:
    def __init__(self, checked=False):
        self._checked = bool(checked)

    def isChecked(self):
        return self._checked


class _DummyEvent:
    def __init__(self):
        self.accepted = False
        self.ignored = False

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class _Harness(SystemShellMixin):
    def __init__(self, sync_flush: bool):
        self._force_quit_requested = True
        self._shutdown_in_progress = False
        self.chk_minimize_tray = _DummyCheck(False)
        self.is_running = False
        self.telegram = None
        self.sound = None
        self._history_dirty = True
        self.config = type("Cfg", (), {"sync_history_flush_on_exit": bool(sync_flush)})()
        self.sync_save_count = 0
        self.async_save_count = 0

    def stop_trading(self):
        return None

    def _save_trade_history(self):
        self.async_save_count += 1

    def _save_trade_history_sync(self):
        self.sync_save_count += 1


class TestShutdownFlushPolicy(unittest.TestCase):
    def test_close_event_uses_sync_flush_when_enabled(self):
        trader = _Harness(sync_flush=True)
        event = _DummyEvent()

        trader.closeEvent(event)

        self.assertTrue(event.accepted)
        self.assertEqual(trader.sync_save_count, 1)
        self.assertEqual(trader.async_save_count, 0)

    def test_close_event_uses_async_flush_when_disabled(self):
        trader = _Harness(sync_flush=False)
        event = _DummyEvent()

        trader.closeEvent(event)

        self.assertTrue(event.accepted)
        self.assertEqual(trader.sync_save_count, 0)
        self.assertEqual(trader.async_save_count, 1)


if __name__ == "__main__":
    unittest.main()
