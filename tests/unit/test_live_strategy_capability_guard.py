import unittest
from unittest.mock import patch

from app.mixins.trading_session import TradingSessionMixin
from config import TradingConfig


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


class _DummyCheck:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return bool(self._checked)


class _Harness(TradingSessionMixin):
    def __init__(self):
        self.is_running = False
        self.is_connected = True
        self.input_codes = _DummyLineEdit("005930")
        self.btn_start = _DummyButton()
        self.btn_stop = _DummyButton()
        self.btn_emergency = _DummyButton()
        self.chk_mock = _DummyCheck(False)  # live mode
        self.ws_client = None
        self.telegram = None
        self.schedule_started = False
        self.daily_loss_triggered = False
        self.time_liquidate_executed = False
        self._position_sync_pending = set()
        self._pending_order_state = {}
        self._last_exec_event = {}
        self._sync_failed_codes = set()
        self.config = TradingConfig()
        self.config.strategy_pack["primary_strategy"] = "pairs_trading_cointegration"  # sim-only
        self.init_calls = 0
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))

    def _confirm_live_trading_guard(self):
        return True

    def _init_universe(self, _codes):
        self.init_calls += 1
        return ["005930"]

    def _sync_positions_snapshot(self, _codes):
        return True, ""


class TestLiveStrategyCapabilityGuard(unittest.TestCase):
    @patch("app.mixins.trading_session.QMessageBox.warning")
    def test_live_start_blocked_for_sim_only_strategy(self, warn):
        trader = _Harness()

        trader.start_trading()

        self.assertFalse(trader.is_running)
        self.assertEqual(trader.init_calls, 0)
        self.assertTrue(warn.called)
        self.assertTrue(any("전략가드" in msg for msg in trader.logs))


if __name__ == "__main__":
    unittest.main()
