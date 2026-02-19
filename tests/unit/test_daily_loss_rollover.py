import datetime
import unittest

from app.mixins.persistence_settings import PersistenceSettingsMixin
from app.mixins.trading_session import TradingSessionMixin
from app.mixins.system_shell import SystemShellMixin


class _TradingDayHarness(TradingSessionMixin):
    def __init__(self):
        self._trading_day = datetime.date(2026, 2, 18)
        self.daily_realized_profit = -10000
        self.daily_initial_deposit = 500000
        self.daily_loss_triggered = True
        self.deposit = 1000000
        self.initial_deposit = 0


class _PersistenceHarness(PersistenceSettingsMixin):
    def __init__(self):
        self.trade_history = []
        self._history_dirty = False
        self.trade_count = 0
        self.win_count = 0
        self.total_realized_profit = 0
        self.daily_realized_profit = 0

    def _refresh_history_table(self):
        return None


class _DummyLabel:
    def __init__(self):
        self.text = ""
        self.style = ""
        self.obj_name = ""

    def setText(self, text):
        self.text = str(text)

    def setStyleSheet(self, style):
        self.style = str(style)

    def setObjectName(self, name):
        self.obj_name = str(name)


class _DummyCheck:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


class _DummySpin:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class _SystemShellHarness(SystemShellMixin):
    def __init__(self):
        self.status_time = _DummyLabel()
        self.status_trading = _DummyLabel()
        self._last_status_badge = None
        self.schedule = {"enabled": False}
        self.is_connected = False
        self.is_running = True
        self.time_liquidate_executed = True
        self.chk_use_risk = _DummyCheck(True)
        self.daily_loss_triggered = False
        self.daily_realized_profit = -50000
        self.daily_initial_deposit = 1000000
        self.total_realized_profit = 99999999  # daily 기준 계산인지 확인용
        self.spin_max_loss = _DummySpin(3.0)
        self._history_dirty = False
        self.stopped = 0
        self._trading_day = datetime.date.today()

    def _refresh_account_info_async(self):
        return None

    def _time_liquidate(self):
        return None

    def _save_trade_history(self):
        return None

    def stop_trading(self):
        self.stopped += 1

    def log(self, _msg):
        return None


class TestDailyLossRollover(unittest.TestCase):
    def test_rollover_resets_daily_metrics_on_date_change(self):
        trader = _TradingDayHarness()

        trader._rollover_daily_metrics(now=datetime.datetime(2026, 2, 19, 9, 0, 0), reset_baseline=False)

        self.assertEqual(trader._trading_day, datetime.date(2026, 2, 19))
        self.assertEqual(trader.daily_realized_profit, 0)
        self.assertEqual(trader.daily_initial_deposit, 0)
        self.assertFalse(trader.daily_loss_triggered)

    def test_rollover_sets_daily_baseline_once(self):
        trader = _TradingDayHarness()
        trader.daily_initial_deposit = 0
        trader.daily_realized_profit = 0
        trader._trading_day = datetime.date(2026, 2, 19)

        trader._rollover_daily_metrics(now=datetime.datetime(2026, 2, 19, 9, 1, 0), reset_baseline=True)

        self.assertEqual(trader.daily_initial_deposit, 1000000)

    def test_add_trade_updates_daily_realized_only_for_sell(self):
        trader = _PersistenceHarness()
        trader._add_trade({"type": "매수", "profit": 0})
        trader._add_trade({"type": "매도", "profit": 12345})

        self.assertEqual(trader.daily_realized_profit, 12345)

    def test_on_timer_uses_daily_realized_for_loss_limit(self):
        trader = _SystemShellHarness()

        trader._on_timer()

        self.assertEqual(trader.stopped, 1)
        self.assertTrue(trader.daily_loss_triggered)


if __name__ == "__main__":
    unittest.main()
