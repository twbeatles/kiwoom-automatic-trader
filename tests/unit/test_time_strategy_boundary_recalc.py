import datetime
import unittest

from app.mixins.trading_session import TradingSessionMixin
from config import TradingConfig


class _DummySignal:
    def __init__(self):
        self.count = 0

    def emit(self):
        self.count += 1


class _StrategyStub:
    def __init__(self):
        self.calls = []

    def calculate_target_price(self, code):
        self.calls.append(code)
        return 100000 + len(self.calls)


class _Harness(TradingSessionMixin):
    def __init__(self):
        self.is_running = True
        self.config = TradingConfig(use_time_strategy=True)
        self.strategy = _StrategyStub()
        self.universe = {
            "005930": {"target": 0},
            "000660": {"target": 0},
        }
        self._dirty_codes = set()
        self._last_time_strategy_phase = "aggressive"
        self.sig_update_table = _DummySignal()
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class TestTimeStrategyBoundaryRecalc(unittest.TestCase):
    def test_recalculates_once_per_phase_boundary(self):
        trader = _Harness()

        trader._maybe_recalculate_time_strategy_targets(datetime.datetime(2026, 2, 25, 9, 30, 0))
        self.assertEqual(len(trader.strategy.calls), 2)
        self.assertEqual(trader._last_time_strategy_phase, "normal")

        trader._maybe_recalculate_time_strategy_targets(datetime.datetime(2026, 2, 25, 9, 30, 1))
        self.assertEqual(len(trader.strategy.calls), 2)

        trader._maybe_recalculate_time_strategy_targets(datetime.datetime(2026, 2, 25, 14, 30, 0))
        self.assertEqual(len(trader.strategy.calls), 4)
        self.assertEqual(trader._last_time_strategy_phase, "conservative")


if __name__ == "__main__":
    unittest.main()
