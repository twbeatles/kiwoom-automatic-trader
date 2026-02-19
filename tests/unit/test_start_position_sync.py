import unittest
from unittest.mock import patch

from api.models import Position
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


class _DummySignal:
    def __init__(self):
        self.emitted = 0

    def emit(self):
        self.emitted += 1


class _DummyStrategy:
    def __init__(self):
        self.reset_called = 0
        self.market_updates = []
        self.sector_updates = []

    def reset_tracking(self):
        self.reset_called += 1

    def update_market_investment(self, code, amount, is_buy=True):
        self.market_updates.append((code, int(amount), bool(is_buy)))

    def update_sector_investment(self, code, amount, is_buy=True):
        self.sector_updates.append((code, int(amount), bool(is_buy)))


class _DummyREST:
    def __init__(self, positions):
        self._positions = positions

    def get_positions(self, _account):
        return self._positions


class _SnapshotHarness(TradingSessionMixin):
    def __init__(self, positions):
        self.rest_client = _DummyREST(positions)
        self.current_account = "12345678"
        self.strategy = _DummyStrategy()
        self.universe = {
            "005930": {"name": "삼성전자", "status": "watch", "held": 0, "buy_price": 0, "invest_amount": 0},
            "000660": {"name": "SK하이닉스", "status": "watch", "held": 0, "buy_price": 0, "invest_amount": 0},
        }
        self._dirty_codes = set()
        self._sync_failed_codes = set()
        self._holding_or_pending_count = 0
        self.sig_update_table = _DummySignal()
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class _StartHarness(TradingSessionMixin):
    def __init__(self, snapshot_ok):
        self.is_running = False
        self.is_connected = True
        self.input_codes = _DummyLineEdit("005930")
        self.btn_start = _DummyButton()
        self.btn_stop = _DummyButton()
        self.btn_emergency = _DummyButton()
        self.ws_client = None
        self.telegram = None
        self.logs = []
        self.schedule_started = True
        self.daily_loss_triggered = False
        self.time_liquidate_executed = False
        self._position_sync_pending = set()
        self._pending_order_state = {}
        self._last_exec_event = {}
        self._sync_failed_codes = set()
        self._snapshot_ok = snapshot_ok

    def log(self, msg):
        self.logs.append(str(msg))

    def _confirm_live_trading_guard(self):
        return True

    def _init_universe(self, _codes):
        return ["005930"]

    def _sync_positions_snapshot(self, _codes):
        return self._snapshot_ok


class TestStartPositionSync(unittest.TestCase):
    def test_sync_positions_snapshot_applies_existing_holding(self):
        positions = [Position(code="005930", quantity=3, buy_price=70000, buy_amount=210000)]
        trader = _SnapshotHarness(positions)

        ok, reason = trader._sync_positions_snapshot(["005930", "000660"])

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        self.assertEqual(trader.universe["005930"]["status"], "holding")
        self.assertEqual(trader.universe["005930"]["held"], 3)
        self.assertEqual(trader.universe["000660"]["status"], "watch")
        self.assertEqual(trader._holding_or_pending_count, 1)
        self.assertEqual(trader.strategy.reset_called, 1)

    def test_sync_positions_snapshot_returns_failure_when_positions_none(self):
        trader = _SnapshotHarness(None)

        ok, reason = trader._sync_positions_snapshot(["005930"])

        self.assertFalse(ok)
        self.assertIn("조회 실패", reason)

    @patch("app.mixins.trading_session.QMessageBox.critical")
    @patch("app.mixins.trading_session.QMessageBox.warning")
    def test_start_trading_stops_when_snapshot_sync_fails(self, _warning, _critical):
        trader = _StartHarness((False, "sync failed"))

        trader.start_trading()

        self.assertFalse(trader.is_running)
        self.assertTrue(trader.btn_start.enabled)
        self.assertFalse(trader.btn_stop.enabled)
        self.assertFalse(trader.btn_emergency.enabled)
        self.assertTrue(any("매매 시작 실패" in msg for msg in trader.logs))


if __name__ == "__main__":
    unittest.main()
