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

    def test_multi_symbol_mtm_uses_latest_price_cache(self):
        cfg = BacktestConfig(timeframe="1d", commission_bps=0, slippage_bps=0)
        engine = EventDrivenBacktestEngine(cfg)
        base = datetime(2025, 1, 1, 9, 0)
        bars = [
            BacktestBar(symbol="AAA", ts=base, open=100, high=101, low=99, close=100, volume=1000),
            BacktestBar(symbol="BBB", ts=base, open=50, high=51, low=49, close=50, volume=1000),
            BacktestBar(symbol="BBB", ts=base + timedelta(days=1), open=70, high=71, low=69, close=70, volume=1000),
            BacktestBar(symbol="AAA", ts=base + timedelta(days=2), open=100, high=101, low=99, close=100, volume=1000),
        ]

        def signal_fn(bar, positions):
            if bar.ts == base and positions[bar.symbol].side == "flat":
                return {bar.symbol: "buy"}
            return {bar.symbol: "hold"}

        result = engine.run(bars, signal_fn, initial_cash=1000, allocation_per_trade=0.5)
        self.assertAlmostEqual(result.equity_curve[-1], 1100.0, places=6)


if __name__ == "__main__":
    unittest.main()
