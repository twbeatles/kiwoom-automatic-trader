import unittest
from datetime import datetime, timedelta

from backtest.engine import BacktestBar, BacktestConfig, BacktestIntelligenceEvent, EventDrivenBacktestEngine


class TestMarketIntelligenceBacktestReplay(unittest.TestCase):
    def _bars(self):
        base = datetime(2025, 1, 1, 9, 0)
        return [
            BacktestBar(symbol="AAA", ts=base + timedelta(days=i), open=100, high=101, low=99, close=100, volume=1000)
            for i in range(5)
        ]

    def test_negative_news_sidecar_blocks_entry(self):
        bars = self._bars()
        engine = EventDrivenBacktestEngine(BacktestConfig(timeframe="1d", commission_bps=0, slippage_bps=0))
        events = [
            BacktestIntelligenceEvent(
                ts=bars[0].ts,
                symbol="AAA",
                source="news",
                event_type="headline",
                score=-80.0,
                blocking=True,
            )
        ]

        def signal_fn(bar, positions):
            if bar.ts >= bars[1].ts and positions[bar.symbol].side == "flat":
                return {bar.symbol: "buy"}
            return {bar.symbol: "hold"}

        result = engine.run(bars, signal_fn, initial_cash=1000.0, allocation_per_trade=0.5, intelligence_events=events)

        self.assertEqual(result.trades, [])

    def test_risk_off_sidecar_reduces_allocation(self):
        bars = self._bars()
        cfg = BacktestConfig(timeframe="1d", commission_bps=0, slippage_bps=0)
        engine = EventDrivenBacktestEngine(cfg)
        events = [
            BacktestIntelligenceEvent(
                ts=bars[0].ts,
                symbol="AAA",
                source="macro",
                event_type="macro_regime",
                score=-60.0,
                raw_ref={"macro_regime": "risk_off"},
            )
        ]

        def signal_fn(bar, positions):
            if bar.ts == bars[1].ts and positions[bar.symbol].side == "flat":
                return {bar.symbol: "buy"}
            return {bar.symbol: "hold"}

        result = engine.run(bars, signal_fn, initial_cash=1000.0, allocation_per_trade=0.5, intelligence_events=events)

        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0]["qty"], 3.5, places=6)


if __name__ == "__main__":
    unittest.main()
