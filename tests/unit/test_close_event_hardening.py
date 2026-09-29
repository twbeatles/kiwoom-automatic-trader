"""Phase-2: closeEvent hardening — 정리 중 예외가 나도 accept+quit 보장."""
import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from app.mixins.system_shell import SystemShellMixin


class _DummyCheck:
    def __init__(self, checked=False):
        self._checked = checked

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


class _DummyLogger:
    def __init__(self):
        self.errors = []

    def error(self, msg):
        self.errors.append(str(msg))

    def warning(self, _msg):
        return None

    def info(self, _msg):
        return None


class _Harness(SystemShellMixin):
    def __init__(self, fail_stop=False):
        self._force_quit_requested = True
        self._shutdown_in_progress = False
        self.chk_minimize_tray = _DummyCheck(False)
        self.is_running = False
        self.telegram = None
        self.sound = None
        self._history_dirty = False
        self.logger = _DummyLogger()
        self._fail_stop = fail_stop

    def stop_trading(self):
        if self._fail_stop:
            raise RuntimeError("cleanup boom")


class TestCloseEventHardening(unittest.TestCase):
    def test_exception_in_stop_still_accepts_and_quits(self):
        trader = _Harness(fail_stop=True)
        fake_timer = MagicMock()
        trader.timer = fake_timer
        trader._theme_watcher_timer = fake_timer
        event = _DummyEvent()
        with patch.object(_Harness, "_quit_application") as quit_mock:
            trader.closeEvent(cast(Any, event))
        self.assertTrue(event.accepted)
        quit_mock.assert_called_once_with()
        self.assertTrue(any("종료 정리 중 오류" in m for m in trader.logger.errors))
        self.assertFalse(trader._force_quit_requested)


if __name__ == "__main__":
    unittest.main()
