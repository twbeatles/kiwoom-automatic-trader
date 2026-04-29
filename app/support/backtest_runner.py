"""Helpers that connect UI inputs to the event-driven backtest engine."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from backtest.engine import BacktestBar, BacktestConfig, BacktestResult, EventDrivenBacktestEngine, PositionState


def _first_value(row: Dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for key in keys:
        if key in row:
            return row[key]
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return ""


def _parse_dt(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    raise ValueError(f"invalid timestamp: {text}")


def _to_float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    return float(text)


def load_backtest_bars_csv(path: str | Path) -> List[BacktestBar]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))

    bars: List[BacktestBar] = []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = str(_first_value(row, "symbol", "code", "종목코드")).strip()
            if not symbol:
                continue
            ts = _parse_dt(_first_value(row, "ts", "timestamp", "datetime", "date", "일자"))
            close = _to_float(_first_value(row, "close", "종가"))
            open_price = _to_float(_first_value(row, "open", "시가"), close)
            high = _to_float(_first_value(row, "high", "고가"), max(open_price, close))
            low = _to_float(_first_value(row, "low", "저가"), min(open_price, close))
            volume = _to_float(_first_value(row, "volume", "거래량"), 0.0)
            if close <= 0:
                continue
            bars.append(
                BacktestBar(
                    symbol=symbol,
                    ts=ts,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
    return sorted(bars, key=lambda bar: (bar.ts, bar.symbol))


def moving_average_signal_fn(lookback: int = 5) -> Callable[[BacktestBar, Dict[str, PositionState]], Dict[str, str]]:
    history: Dict[str, List[float]] = {}
    window = max(2, int(lookback))

    def signal_fn(bar: BacktestBar, positions: Dict[str, PositionState]) -> Dict[str, str]:
        series = history.setdefault(bar.symbol, [])
        action = "hold"
        if len(series) >= window:
            average = sum(series[-window:]) / window
            state = positions[bar.symbol]
            if state.side == "flat" and bar.close > average:
                action = "buy"
            elif state.side == "long" and bar.close < average:
                action = "sell"
        series.append(float(bar.close))
        return {bar.symbol: action}

    return signal_fn


def build_backtest_config(values: Dict[str, Any] | None = None) -> BacktestConfig:
    values = dict(values or {})
    return BacktestConfig(
        timeframe=str(values.get("timeframe", "1d") or "1d"),
        commission_bps=float(values.get("commission_bps", 5.0) or 5.0),
        slippage_bps=float(values.get("slippage_bps", 3.0) or 3.0),
    )


def run_backtest_from_files(
    bars_path: str | Path,
    intelligence_path: str | Path | None = None,
    config_values: Dict[str, Any] | None = None,
    *,
    initial_cash: float = 100_000_000.0,
    allocation_per_trade: float = 0.1,
) -> BacktestResult:
    bars = load_backtest_bars_csv(bars_path)
    if not bars:
        raise ValueError("backtest CSV has no valid bars")
    events = []
    if intelligence_path:
        event_path = Path(intelligence_path)
        if event_path.exists():
            events = EventDrivenBacktestEngine.load_intelligence_events_jsonl(event_path)
    engine = EventDrivenBacktestEngine(build_backtest_config(config_values))
    return engine.run(
        bars,
        moving_average_signal_fn(),
        initial_cash=initial_cash,
        allocation_per_trade=allocation_per_trade,
        intelligence_events=events,
    )


def backtest_result_to_dict(result: BacktestResult) -> Dict[str, Any]:
    return {
        "metrics": dict(result.metrics or {}),
        "trades": [dict(row) for row in result.trades],
        "equity_curve": list(result.equity_curve),
    }


def metric_rows(result: BacktestResult) -> List[tuple[str, str]]:
    return [(str(key), f"{float(value):.4f}") for key, value in sorted((result.metrics or {}).items())]
