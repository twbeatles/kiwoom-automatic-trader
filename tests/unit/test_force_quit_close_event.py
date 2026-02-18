import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox

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


class _Harness(SystemShellMixin):
    def __init__(self):
        self._force_quit_requested = False
        self._shutdown_in_progress = False
        self.chk_minimize_tray = _DummyCheck(True)
        self.is_running = True
        self.telegram = None
        self.sound = None
        self._history_dirty = False
        self.stop_called = 0
        self.close_called = 0

    def close(self):
        self.close_called += 1

    def stop_trading(self):
        self.stop_called += 1
        self.is_running = False

    def _save_trade_history(self):
        pass


class TestForceQuitCloseEvent(unittest.TestCase):
    @patch("app.mixins.system_shell.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    def test_force_quit_bypasses_tray_minimize_path(self, _question):
        trader = _Harness()
        trader._force_quit()

        self.assertTrue(trader._force_quit_requested)
        self.assertEqual(trader.close_called, 1)

        event = _DummyEvent()
        trader.closeEvent(event)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)
        self.assertEqual(trader.stop_called, 1)
        self.assertFalse(trader._force_quit_requested)


if __name__ == "__main__":
    unittest.main()
