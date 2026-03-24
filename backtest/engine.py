"""Event-driven backtest engine.

Phase-1 target: deterministic daily simulation with minute extensibility.
"""

import json
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, time
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional


@dataclass
class BacktestBar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class BacktestIntelligenceEvent:
    ts: datetime
    scope: str = "symbol"
    symbol: str = ""
    source: str = ""
    event_type: str = ""
    score: float = 0.0
    tags: List[str] = field(default_factory=list)
    summary: str = ""
    blocking: bool = False
    raw_ref: Any = ""


@dataclass
class PositionState:
    side: str = "flat"  # flat/long/short
    quantity: float = 0.0
    entry_price: float = 0.0


@dataclass
class BacktestConfig:
    timeframe: str = "1d"
    commission_bps: float = 5.0
    slippage_bps: float = 3.0
    tradable_start: time = time(9, 0)
    tradable_end: time = time(15, 20)
    use_shock_guard: bool = True
    shock_1m_pct: float = 1.5
    shock_5m_pct: float = 2.8
    shock_cooldown_min: int = 10
    use_vi_guard: bool = True
    vi_cooldown_min: int = 7
    use_regime_sizing: bool = True
    regime_elevated_atr_pct: float = 2.5
    regime_extreme_atr_pct: float = 4.0
    regime_size_scale_elevated: float = 0.7
    regime_size_scale_extreme: float = 0.4
    use_liquidity_stress_guard: bool = True
    stress_spread_pct: float = 1.0
    stress_min_value_ratio: float = 0.35
    min_avg_value: float = 1_000_000_000.0
    use_slippage_guard: bool = True
    max_slippage_bps: float = 15.0
    slippage_window_trades: int = 20
    use_order_health_guard: bool = True
    order_health_fail_count: int = 5
    order_health_window_sec: int = 60
    order_health_cooldown_sec: int = 180
    news_block_threshold: float = -60.0
    macro_block_threshold: float = -40.0
    theme_heat_threshold: float = 60.0


@dataclass
class BacktestResult:
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class EventDrivenBacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        bars: Iterable[BacktestBar],
        signal_fn: Callable[[BacktestBar, Dict[str, PositionState]], Dict[str, str]],
        initial_cash: float = 100000000.0,
        allocation_per_trade: float = 0.1,
        intelligence_events: Optional[Iterable[BacktestIntelligenceEvent]] = None,
    ) -> BacktestResult:
        cash = float(initial_cash)
        positions: Dict[str, PositionState] = {}
        equity_curve: List[float] = []
        trades: List[Dict[str, Any]] = []
        price_history: Dict[str, List[float]] = {}
        last_prices: Dict[str, float] = {}
        recent_slippage_bps: Deque[float] = deque(maxlen=500)
        order_fail_events: Deque[float] = deque(maxlen=500)
        global_risk_until: Optional[datetime] = None
        order_health_until: Optional[datetime] = None
        intelligence_state: Dict[str, Dict[str, Any]] = {}

        ordered = sorted(bars, key=lambda b: (b.ts, b.symbol))
        ordered_events = sorted(list(intelligence_events or []), key=lambda e: (e.ts, e.symbol, e.event_type))
        event_idx = 0
        for bar in ordered:
            if self.config.timeframe.endswith("m") and not self._is_tradable_time(bar.ts):
                continue

            while event_idx < len(ordered_events) and ordered_events[event_idx].ts <= bar.ts:
                self._apply_intelligence_event(intelligence_state, ordered_events[event_idx])
                event_idx += 1

            if bar.symbol not in positions:
                positions[bar.symbol] = PositionState()
            series = price_history.setdefault(bar.symbol, [])
            series.append(float(bar.close))
            if len(series) > 2000:
                del series[:-2000]
            last_prices[bar.symbol] = float(bar.close)

            symbol_state = positions[bar.symbol]
            signals = signal_fn(bar, positions) or {}
            meta = signals.get("__meta__", {}) if isinstance(signals, dict) else {}
            if not isinstance(meta, dict):
                meta = {}
            meta = dict(meta)
            meta["market_intel"] = dict(intelligence_state.get(bar.symbol, {}))
            action = (signals.get(bar.symbol) or "hold").lower()
            action = self._apply_entry_guards(
                action=action,
                bar=bar,
                series=series,
                recent_slippage_bps=recent_slippage_bps,
                order_fail_events=order_fail_events,
                meta=meta,
                global_risk_until=global_risk_until,
                order_health_until=order_health_until,
            )

            if self.config.use_shock_guard:
                if self._is_shock_triggered(series):
                    global_risk_until = bar.ts + self._shock_cooldown_delta()
                elif global_risk_until and bar.ts >= global_risk_until:
                    global_risk_until = None
            if self.config.use_order_health_guard:
                if bool(meta.get("order_failed", False)):
                    order_fail_events.append(bar.ts.timestamp())
                self._trim_fail_events(order_fail_events, bar.ts.timestamp())
                if len(order_fail_events) >= int(self.config.order_health_fail_count):
                    order_health_until = bar.ts + self._order_health_cooldown_delta()
                elif order_health_until and bar.ts >= order_health_until:
                    order_health_until = None

            fill_price = self._apply_costs(bar.close, action)
            if action in {"buy", "sell", "short", "cover"} and fill_price > 0 and bar.close > 0:
                slip_bps = abs((fill_price - bar.close) / bar.close) * 10000.0
                recent_slippage_bps.append(slip_bps)

            if action == "buy" and symbol_state.side == "flat":
                risk_cash = max(0.0, cash * allocation_per_trade)
                if self.config.use_regime_sizing:
                    risk_cash *= self._regime_scale(series)
                risk_cash *= self._market_intel_allocation_scale(intelligence_state.get(bar.symbol, {}))
                qty = (risk_cash / fill_price) if fill_price > 0 else 0.0
                if qty > 0:
                    cost = qty * fill_price
                    cash -= cost
                    symbol_state.side = "long"
                    symbol_state.quantity = qty
                    symbol_state.entry_price = fill_price
                    trades.append({"ts": bar.ts.isoformat(), "symbol": bar.symbol, "side": "buy", "price": fill_price, "qty": qty})

            elif action == "sell" and symbol_state.side == "long":
                proceeds = symbol_state.quantity * fill_price
                pnl = (fill_price - symbol_state.entry_price) * symbol_state.quantity
                cash += proceeds
                trades.append({
                    "ts": bar.ts.isoformat(),
                    "symbol": bar.symbol,
                    "side": "sell",
                    "price": fill_price,
                    "qty": symbol_state.quantity,
                    "pnl": pnl,
                })
                symbol_state.side = "flat"
                symbol_state.quantity = 0.0
                symbol_state.entry_price = 0.0

            elif action == "short" and symbol_state.side == "flat":
                risk_cash = max(0.0, cash * allocation_per_trade)
                if self.config.use_regime_sizing:
                    risk_cash *= self._regime_scale(series)
                risk_cash *= self._market_intel_allocation_scale(intelligence_state.get(bar.symbol, {}))
                qty = (risk_cash / fill_price) if fill_price > 0 else 0.0
                if qty > 0:
                    cash += qty * fill_price
                    symbol_state.side = "short"
                    symbol_state.quantity = qty
                    symbol_state.entry_price = fill_price
                    trades.append({"ts": bar.ts.isoformat(), "symbol": bar.symbol, "side": "short", "price": fill_price, "qty": qty})

            elif action == "cover" and symbol_state.side == "short":
                cost = symbol_state.quantity * fill_price
                pnl = (symbol_state.entry_price - fill_price) * symbol_state.quantity
                cash -= cost
                trades.append({
                    "ts": bar.ts.isoformat(),
                    "symbol": bar.symbol,
                    "side": "cover",
                    "price": fill_price,
                    "qty": symbol_state.quantity,
                    "pnl": pnl,
                })
                symbol_state.side = "flat"
                symbol_state.quantity = 0.0
                symbol_state.entry_price = 0.0

            equity = cash + self._mark_to_market(positions, last_prices)
            equity_curve.append(equity)

        result = BacktestResult(equity_curve=equity_curve, trades=trades)
        result.metrics = self._calculate_metrics(equity_curve, trades, initial_cash)
        result.metrics["avg_slippage_bps"] = self._avg_abs_bps(recent_slippage_bps)
        return result

    def _apply_costs(self, raw_price: float, action: str) -> float:
        if raw_price <= 0:
            return 0.0
        fee = self.config.commission_bps / 10000.0
        slip = self.config.slippage_bps / 10000.0
        if action in {"buy", "cover"}:
            return raw_price * (1.0 + fee + slip)
        if action in {"sell", "short"}:
            return raw_price * (1.0 - fee - slip)
        return raw_price

    def _is_tradable_time(self, ts: datetime) -> bool:
        t = ts.time()
        return self.config.tradable_start <= t <= self.config.tradable_end

    def _is_shock_triggered(self, series: List[float]) -> bool:
        if len(series) < 2:
            return False
        ret_1 = self._series_return(series, 1)
        ret_5 = self._series_return(series, 5)
        return abs(ret_1) >= float(self.config.shock_1m_pct) or abs(ret_5) >= float(self.config.shock_5m_pct)

    @staticmethod
    def _series_return(series: List[float], lookback: int) -> float:
        if len(series) <= lookback:
            return 0.0
        base = float(series[-(lookback + 1)] or 0)
        latest = float(series[-1] or 0)
        if base <= 0 or latest <= 0:
            return 0.0
        return (latest / base - 1.0) * 100.0

    def _regime_scale(self, series: List[float]) -> float:
        if len(series) < 15:
            return 1.0
        current = float(series[-1] or 0)
        if current <= 0:
            return 1.0
        # Lightweight ATR proxy from close-to-close moves for backtest parity.
        diffs = [abs(series[i] - series[i - 1]) for i in range(max(1, len(series) - 14), len(series))]
        atr = sum(diffs) / len(diffs) if diffs else 0.0
        atr_pct = (atr / current) * 100.0 if current > 0 else 0.0
        if atr_pct >= float(self.config.regime_extreme_atr_pct):
            return float(self.config.regime_size_scale_extreme)
        if atr_pct >= float(self.config.regime_elevated_atr_pct):
            return float(self.config.regime_size_scale_elevated)
        return 1.0

    def _apply_entry_guards(
        self,
        action: str,
        bar: BacktestBar,
        series: List[float],
        recent_slippage_bps: Deque[float],
        order_fail_events: Deque[float],
        meta: Dict[str, Any],
        global_risk_until: Optional[datetime],
        order_health_until: Optional[datetime],
    ) -> str:
        if action not in {"buy", "short"}:
            return action

        intelligence = meta.get("market_intel", {}) if isinstance(meta.get("market_intel", {}), dict) else {}
        news_score = float(intelligence.get("news_score", 0.0) or 0.0)
        dart_risk = str(intelligence.get("dart_risk_level", "normal") or "normal")
        macro_regime = str(intelligence.get("macro_regime", "neutral") or "neutral")
        theme_score = float(intelligence.get("theme_score", 0.0) or 0.0)
        intel_status = str(intelligence.get("intel_status", "idle") or "idle")

        if news_score <= float(self.config.news_block_threshold):
            return "hold"
        if dart_risk == "high" or bool(intelligence.get("blocking", False)):
            return "hold"
        if macro_regime == "risk_off" and news_score <= float(self.config.macro_block_threshold):
            return "hold"
        if intel_status not in {"idle", "disabled", "fresh"}:
            return "hold"
        if intelligence.get("require_theme_heat", False) and theme_score < float(self.config.theme_heat_threshold):
            return "hold"

        if self.config.use_shock_guard and global_risk_until and bar.ts < global_risk_until:
            return "hold"

        if self.config.use_vi_guard:
            market_state = str(meta.get("market_state", "normal") or "normal")
            if market_state in {"vi", "halt", "reopen_cooldown"}:
                return "hold"

        if self.config.use_liquidity_stress_guard:
            spread_pct = float(meta.get("spread_pct", 0.0) or 0.0)
            avg_value_20 = float(meta.get("avg_value_20", 0.0) or 0.0)
            stressed = spread_pct > float(self.config.stress_spread_pct) or (
                avg_value_20 > 0 and avg_value_20 < float(self.config.min_avg_value) * float(self.config.stress_min_value_ratio)
            )
            if stressed:
                return "hold"

        if self.config.use_slippage_guard and self._avg_abs_bps(recent_slippage_bps, int(self.config.slippage_window_trades)) > float(
            self.config.max_slippage_bps
        ):
            return "hold"

        if self.config.use_order_health_guard and order_health_until and bar.ts < order_health_until:
            return "hold"

        return action

    @staticmethod
    def _market_intel_allocation_scale(intelligence: Dict[str, Any]) -> float:
        if str(intelligence.get("macro_regime", "neutral") or "neutral") == "risk_off":
            return 0.7
        return 1.0

    def _apply_intelligence_event(
        self,
        intelligence_state: Dict[str, Dict[str, Any]],
        event: BacktestIntelligenceEvent,
    ):
        symbol = str(event.symbol or "")
        if not symbol:
            return
        state = intelligence_state.setdefault(symbol, {})
        state["intel_status"] = "fresh"
        state["last_event_ts"] = event.ts
        state["blocking"] = bool(event.blocking)
        payload: Dict[str, Any] = {}
        if isinstance(event.raw_ref, dict):
            payload = dict(event.raw_ref)
        elif isinstance(event.raw_ref, str) and event.raw_ref:
            try:
                parsed = json.loads(event.raw_ref)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        if payload:
            state.update(payload)
        if event.source == "news":
            state["news_score"] = float(payload.get("news_score", event.score))
            if event.event_type == "headline_velocity":
                state["headline_velocity"] = int(payload.get("headline_velocity", max(1, int(abs(event.score) or len(event.tags)))))
        elif event.source == "dart":
            state["dart_risk_level"] = "high" if event.blocking or float(event.score or 0.0) <= -60 else str(payload.get("dart_risk_level", "normal"))
        elif event.source == "macro":
            if "macro_regime" in payload:
                state["macro_regime"] = str(payload.get("macro_regime", "neutral"))
            elif event.blocking or float(event.score or 0.0) < 0:
                state["macro_regime"] = "risk_off"
            elif float(event.score or 0.0) > 0:
                state["macro_regime"] = "risk_on"
            else:
                state["macro_regime"] = "neutral"
        elif event.source == "theme":
            state["theme_score"] = float(payload.get("theme_score", event.score))

    @staticmethod
    def _avg_abs_bps(values: Deque[float], window: int = 0) -> float:
        if not values:
            return 0.0
        arr = list(values)
        if window > 0:
            arr = arr[-max(1, window) :]
        if not arr:
            return 0.0
        return sum(abs(float(v)) for v in arr) / len(arr)

    def _trim_fail_events(self, events: Deque[float], now_ts: float):
        window_sec = max(1, int(self.config.order_health_window_sec))
        while events and now_ts - float(events[0]) > window_sec:
            events.popleft()

    def _shock_cooldown_delta(self):
        from datetime import timedelta

        return timedelta(minutes=max(1, int(self.config.shock_cooldown_min)))

    def _order_health_cooldown_delta(self):
        from datetime import timedelta

        return timedelta(seconds=max(1, int(self.config.order_health_cooldown_sec)))

    @staticmethod
    def _mark_to_market(positions: Dict[str, PositionState], last_prices: Dict[str, float]) -> float:
        value = 0.0
        for symbol, state in positions.items():
            px = float(last_prices.get(symbol, state.entry_price) or 0)
            if state.side == "long":
                value += state.quantity * px
            elif state.side == "short":
                value -= state.quantity * px
        return value

    @staticmethod
    def _calculate_metrics(equity_curve: List[float], trades: List[Dict[str, Any]], initial_cash: float) -> Dict[str, float]:
        if not equity_curve:
            return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "trades": 0.0}
        peak = equity_curve[0]
        max_dd = 0.0
        for v in equity_curve:
            peak = max(peak, v)
            if peak > 0:
                dd = (peak - v) / peak * 100.0
                max_dd = max(max_dd, dd)
        ret = (equity_curve[-1] - initial_cash) / initial_cash * 100.0 if initial_cash > 0 else 0.0
        return {
            "return_pct": ret,
            "max_drawdown_pct": max_dd,
            "trades": float(len(trades)),
        }
