import datetime
import unittest

from app.mixins.system_shell import SystemShellMixin


class _DummyLabel:
    def __init__(self):
        self.text = ""
        self.object_name = ""
        self.style = ""

    def setText(self, value):
        self.text = str(value)

    def setObjectName(self, value):
        self.object_name = str(value)

    def setStyleSheet(self, value):
        self.style = str(value)


class _Harness(SystemShellMixin):
    def __init__(self):
        now = datetime.datetime.now()
        self.status_time = _DummyLabel()
        self.status_trading = _DummyLabel()
        self._last_status_badge = None
        self.is_running = False
        self.is_connected = True
        self.schedule_started = False
        self._trading_start_inflight = False
        self.schedule = {
            "enabled": True,
            "start": (now - datetime.timedelta(minutes=1)).strftime("%H:%M"),
            "end": (now + datetime.timedelta(minutes=1)).strftime("%H:%M"),
            "liquidate": True,
        }
        self.start_calls = 0
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))

    def start_trading(self, from_schedule: bool = False):
        self.start_calls += 1
        self.logs.append(f"start:{from_schedule}")
        return False


class TestScheduleRetryOnFailedStart(unittest.TestCase):
    def test_schedule_retries_when_start_fails(self):
        trader = _Harness()

        trader._on_timer()
        trader._on_timer()

        self.assertEqual(trader.start_calls, 2)
        self.assertFalse(trader.schedule_started)


if __name__ == "__main__":
    unittest.main()
