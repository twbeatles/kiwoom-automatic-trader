"""Event-driven backtest engine.

Phase-1 target: deterministic daily simulation with minute extensibility.

SOLID 분할 구조의 facade: 상태(`models`), 인텔리전스(`_intel_events`), 정책(`_policy`),
가드(`_guards`), 지표(`_metrics`) 믹스인을 조합한다. 공개 API·import 경로는 그대로 유지된다.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional  # noqa: F401

from ._intel_events import BacktestIntelEventsMixin
from .models import (  # noqa: F401
    BacktestBar, BacktestConfig, BacktestIntelligenceEvent, BacktestResult, PositionState,
)


class EventDrivenBacktestEngine(BacktestIntelEventsMixin):
    """Event-driven backtest orchestrator (facade: behavior unchanged)."""

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
        symbol_intelligence_state: Dict[str, Dict[str, Any]] = {}
        scoped_intelligence_state: Dict[str, Dict[str, Any]] = {"market": {}, "sector": {}, "theme": {}}

        ordered = sorted(bars, key=lambda bar: (bar.ts, bar.symbol))
        ordered_events = sorted(list(intelligence_events or []), key=lambda event: (event.ts, event.scope, event.symbol, event.event_type))
        event_idx = 0
        for bar in ordered:
            if self.config.timeframe.endswith("m") and not self._is_tradable_time(bar.ts):
                continue

            while event_idx < len(ordered_events) and ordered_events[event_idx].ts <= bar.ts:
                self._apply_intelligence_event(symbol_intelligence_state, scoped_intelligence_state, ordered_events[event_idx])
                event_idx += 1

            if bar.symbol not in positions:
                positions[bar.symbol] = PositionState()
            series = price_history.setdefault(bar.symbol, [])
            series.append(float(bar.close))
            if len(series) > 2000:
                del series[:-2000]
            last_prices[bar.symbol] = float(bar.close)

            symbol_state = positions[bar.symbol]
            if symbol_state.side == "long":
                symbol_state.peak_price = max(symbol_state.peak_price, float(bar.high or bar.close or 0.0), float(bar.close or 0.0))

            signals = signal_fn(bar, positions) or {}
            meta = signals.get("__meta__", {}) if isinstance(signals, dict) else {}
            if not isinstance(meta, dict):
                meta = {}
            meta = dict(meta)
            effective_intelligence = self._compose_effective_intelligence(
                symbol=bar.symbol,
                meta=meta,
                symbol_intelligence_state=symbol_intelligence_state,
                scoped_intelligence_state=scoped_intelligence_state,
            )
            meta["market_intel"] = effective_intelligence
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
            action, reduce_fraction = self._apply_position_defense(
                action=action,
                bar=bar,
                symbol_state=symbol_state,
                intelligence=effective_intelligence,
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

            fill_action = "sell" if action == "sell_partial" else action
            fill_price = self._apply_costs(bar.close, fill_action)
            if action in {"buy", "sell", "sell_partial", "short", "cover"} and fill_price > 0 and bar.close > 0:
                slip_bps = abs((fill_price - bar.close) / bar.close) * 10000.0
                recent_slippage_bps.append(slip_bps)

            if action == "buy" and symbol_state.side == "flat":
                risk_cash = max(0.0, cash * allocation_per_trade)
                if self.config.use_regime_sizing:
                    risk_cash *= self._regime_scale(series)
                risk_cash *= self._market_intel_allocation_scale(effective_intelligence)
                qty = (risk_cash / fill_price) if fill_price > 0 else 0.0
                if qty > 0:
                    cost = qty * fill_price
                    cash -= cost
                    symbol_state.side = "long"
                    symbol_state.quantity = qty
                    symbol_state.entry_price = fill_price
                    symbol_state.peak_price = fill_price
                    symbol_state.last_intel_event_id = ""
                    trades.append({"ts": bar.ts.isoformat(), "symbol": bar.symbol, "side": "buy", "price": fill_price, "qty": qty})

            elif action == "sell_partial" and symbol_state.side == "long":
                fraction = max(0.05, min(1.0, float(reduce_fraction if reduce_fraction is not None else self.config.reduce_size_ratio)))
                qty = min(symbol_state.quantity, max(0.0, symbol_state.quantity * fraction))
                if qty > 0:
                    proceeds = qty * fill_price
                    pnl = (fill_price - symbol_state.entry_price) * qty
                    cash += proceeds
                    symbol_state.quantity = max(0.0, symbol_state.quantity - qty)
                    trades.append(
                        {
                            "ts": bar.ts.isoformat(),
                            "symbol": bar.symbol,
                            "side": "sell_reduce",
                            "price": fill_price,
                            "qty": qty,
                            "pnl": pnl,
                        }
                    )
                    if symbol_state.quantity <= 1e-9:
                        symbol_state.side = "flat"
                        symbol_state.quantity = 0.0
                        symbol_state.entry_price = 0.0
                        symbol_state.peak_price = 0.0

            elif action == "sell" and symbol_state.side == "long":
                proceeds = symbol_state.quantity * fill_price
                pnl = (fill_price - symbol_state.entry_price) * symbol_state.quantity
                cash += proceeds
                trades.append(
                    {
                        "ts": bar.ts.isoformat(),
                        "symbol": bar.symbol,
                        "side": "sell",
                        "price": fill_price,
                        "qty": symbol_state.quantity,
                        "pnl": pnl,
                    }
                )
                symbol_state.side = "flat"
                symbol_state.quantity = 0.0
                symbol_state.entry_price = 0.0
                symbol_state.peak_price = 0.0
                symbol_state.last_intel_event_id = ""

            elif action == "short" and symbol_state.side == "flat":
                risk_cash = max(0.0, cash * allocation_per_trade)
                if self.config.use_regime_sizing:
                    risk_cash *= self._regime_scale(series)
                risk_cash *= self._market_intel_allocation_scale(effective_intelligence)
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
                trades.append(
                    {
                        "ts": bar.ts.isoformat(),
                        "symbol": bar.symbol,
                        "side": "cover",
                        "price": fill_price,
                        "qty": symbol_state.quantity,
                        "pnl": pnl,
                    }
                )
                symbol_state.side = "flat"
                symbol_state.quantity = 0.0
                symbol_state.entry_price = 0.0

            equity = cash + self._mark_to_market(positions, last_prices)
            equity_curve.append(equity)

        result = BacktestResult(equity_curve=equity_curve, trades=trades)
        result.metrics = self._calculate_metrics(equity_curve, trades, initial_cash)
        result.metrics["avg_slippage_bps"] = self._avg_abs_bps(recent_slippage_bps)
        return result
