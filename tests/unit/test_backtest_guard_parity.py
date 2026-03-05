import unittest
from datetime import datetime, timedelta

from backtest.engine import BacktestBar, BacktestConfig, EventDrivenBacktestEngine


class TestBacktestGuardParity(unittest.TestCase):
    def _bars(self):
        base = datetime(2025, 1, 1, 9, 0)
        return [
            BacktestBar(symbol="AAA", ts=base + timedelta(days=i), open=100 + i, high=101 + i, low=99 + i, close=100 + i)
            for i in range(5)
        ]

    def test_vi_guard_blocks_entry(self):
        cfg = BacktestConfig(use_vi_guard=True)
        engine = EventDrivenBacktestEngine(cfg)

        def signal_fn(bar, _positions):
            return {bar.symbol: "buy", "__meta__": {"market_state": "vi"}}

        result = engine.run(self._bars(), signal_fn, initial_cash=1_000_000, allocation_per_trade=0.5)

        self.assertEqual(len(result.trades), 0)


if __name__ == "__main__":
    unittest.main()
