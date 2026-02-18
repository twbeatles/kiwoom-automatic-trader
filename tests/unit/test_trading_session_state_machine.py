import unittest
from unittest.mock import patch

from app.mixins.trading_session import TradingSessionMixin


class _DummyLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class _DummyButton:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = bool(value)


class _Harness(TradingSessionMixin):
    def __init__(self, codes_text, init_result, connected=True):
        self.is_running = False
        self.is_connected = connected
        self.input_codes = _DummyLineEdit(codes_text)
        self.btn_start = _DummyButton()
        self.btn_stop = _DummyButton()
        self.btn_emergency = _DummyButton()
        self.daily_loss_triggered = False
        self.time_liquidate_executed = False
        self.schedule_started = True
        self._position_sync_pending = set()
        self._pending_order_state = {}
        self._last_exec_event = {}
        self.ws_client = None
        self.telegram = None
        self.logs = []
        self.init_called_with = None
        self._init_result = init_result

    def log(self, msg):
        self.logs.append(msg)

    def _confirm_live_trading_guard(self):
        return True

    def _init_universe(self, codes):
        self.init_called_with = list(codes)
        return list(self._init_result)


class TestTradingSessionStateMachine(unittest.TestCase):
    @patch("app.mixins.trading_session.QMessageBox.critical")
    @patch("app.mixins.trading_session.QMessageBox.warning")
    def test_start_trading_normalizes_codes(self, _warning, _critical):
        trader = _Harness("005930, 005930, abc, 12345, 000660", ["005930", "000660"])

        trader.start_trading()

        self.assertEqual(trader.init_called_with, ["005930", "000660"])
        self.assertTrue(trader.is_running)
        self.assertFalse(trader.btn_start.enabled)
        self.assertTrue(trader.btn_stop.enabled)
        self.assertTrue(trader.btn_emergency.enabled)

    @patch("app.mixins.trading_session.QMessageBox.critical")
    @patch("app.mixins.trading_session.QMessageBox.warning")
    def test_start_trading_rolls_back_on_empty_init(self, _warning, _critical):
        trader = _Harness("005930", [])

        trader.start_trading()

        self.assertFalse(trader.is_running)
        self.assertTrue(trader.btn_start.enabled)
        self.assertFalse(trader.btn_stop.enabled)
        self.assertFalse(trader.btn_emergency.enabled)
        self.assertFalse(trader.schedule_started)


if __name__ == "__main__":
    unittest.main()
