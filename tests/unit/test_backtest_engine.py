import unittest
from datetime import datetime, timedelta

from backtest.engine import BacktestBar, BacktestConfig, EventDrivenBacktestEngine


class TestBacktestEngine(unittest.TestCase):
    def _bars(self):
        base = datetime(2025, 1, 1, 9, 0)
        bars = []
        for i in range(30):
            px = 100 + i
            bars.append(BacktestBar(symbol="AAA", ts=base + timedelta(days=i), open=px, high=px + 1, low=px - 1, close=px, volume=1000))
        return bars

    def test_deterministic_result(self):
        engine = EventDrivenBacktestEngine(BacktestConfig(timeframe="1d", commission_bps=1, slippage_bps=1))

        def signal_fn(bar, positions):
            state = positions[bar.symbol]
            if state.side == "flat" and bar.close > 105:
                return {bar.symbol: "buy"}
            if state.side == "long" and bar.close > 120:
                return {bar.symbol: "sell"}
            return {bar.symbol: "hold"}

        r1 = engine.run(self._bars(), signal_fn, initial_cash=1_000_000, allocation_per_trade=0.5)
        r2 = engine.run(self._bars(), signal_fn, initial_cash=1_000_000, allocation_per_trade=0.5)

        self.assertEqual(r1.equity_curve, r2.equity_curve)
        self.assertEqual(r1.trades, r2.trades)
        self.assertEqual(r1.metrics, r2.metrics)


if __name__ == "__main__":
    unittest.main()
