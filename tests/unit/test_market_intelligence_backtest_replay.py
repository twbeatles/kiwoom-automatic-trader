import unittest
from datetime import datetime, timedelta
from pathlib import Path
import json
import shutil
import tempfile

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

    def test_jsonl_loader_supports_structured_payload_and_sector_scope(self):
        bars = self._bars()
        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            event_path = Path(tmpdir) / "market_intelligence_events.jsonl"
            event_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "ts": bars[0].ts.isoformat(),
                                "scope": "market",
                                "symbol": "KR_MARKET",
                                "source": "macro",
                                "event_type": "market_risk_mode",
                                "payload": {"macro_regime": "risk_off", "portfolio_budget_scale": 0.8},
                            }
                        ),
                        json.dumps(
                            {
                                "ts": bars[0].ts.isoformat(),
                                "scope": "sector",
                                "source": "news",
                                "event_type": "sector_block",
                                "payload": {"sector": "반도체", "action_policy": "block_entry"},
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            events = EventDrivenBacktestEngine.load_intelligence_events_jsonl(event_path)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        engine = EventDrivenBacktestEngine(BacktestConfig(timeframe="1d", commission_bps=0, slippage_bps=0))

        def signal_fn(bar, positions):
            if bar.ts >= bars[1].ts and positions[bar.symbol].side == "flat":
                return {bar.symbol: "buy", "__meta__": {"sector": "반도체"}}
            return {bar.symbol: "hold", "__meta__": {"sector": "반도체"}}

        result = engine.run(bars, signal_fn, initial_cash=1000.0, allocation_per_trade=0.5, intelligence_events=events)

        self.assertEqual(result.trades, [])

    def test_jsonl_loader_supports_legacy_raw_ref_payload(self):
        bars = self._bars()
        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            event_path = Path(tmpdir) / "market_intelligence_events.jsonl"
            event_path.write_text(
                json.dumps(
                    {
                        "ts": bars[0].ts.isoformat(),
                        "scope": "market",
                        "symbol": "KR_MARKET",
                        "source": "macro",
                        "event_type": "market_risk_mode",
                        "raw_ref": json.dumps({"macro_regime": "risk_off"}),
                    }
                ),
                encoding="utf-8",
            )
            events = EventDrivenBacktestEngine.load_intelligence_events_jsonl(event_path)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        engine = EventDrivenBacktestEngine(BacktestConfig(timeframe="1d", commission_bps=0, slippage_bps=0))

        def signal_fn(bar, positions):
            if bar.ts == bars[1].ts and positions[bar.symbol].side == "flat":
                return {bar.symbol: "buy"}
            return {bar.symbol: "hold"}

        result = engine.run(bars, signal_fn, initial_cash=1000.0, allocation_per_trade=0.5, intelligence_events=events)

        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0]["qty"], 3.5, places=6)

    def test_positive_news_only_scales_existing_buy_signal(self):
        bars = self._bars()
        engine = EventDrivenBacktestEngine(BacktestConfig(timeframe="1d", commission_bps=0, slippage_bps=0))
        events = [
            BacktestIntelligenceEvent(
                ts=bars[0].ts,
                symbol="AAA",
                source="news",
                event_type="headline",
                score=70.0,
                payload={"action_policy": "allow", "news_score": 70.0, "size_multiplier": 1.2},
            )
        ]

        def buy_signal(bar, positions):
            if bar.ts == bars[1].ts and positions[bar.symbol].side == "flat":
                return {bar.symbol: "buy"}
            return {bar.symbol: "hold"}

        def no_signal(bar, positions):
            return {bar.symbol: "hold"}

        result_with_signal = engine.run(bars, buy_signal, initial_cash=1000.0, allocation_per_trade=0.5, intelligence_events=events)
        result_without_signal = engine.run(bars, no_signal, initial_cash=1000.0, allocation_per_trade=0.5, intelligence_events=events)

        self.assertEqual(len(result_with_signal.trades), 1)
        self.assertAlmostEqual(result_with_signal.trades[0]["qty"], 6.0, places=6)
        self.assertEqual(result_without_signal.trades, [])


if __name__ == "__main__":
    unittest.main()
