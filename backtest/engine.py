"""Event-driven backtest engine.

Phase-1 target: deterministic daily simulation with minute extensibility.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
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
    event_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    raw_ref: Any = ""


@dataclass
class PositionState:
    side: str = "flat"
    quantity: float = 0.0
    entry_price: float = 0.0
    peak_price: float = 0.0
    last_intel_event_id: str = ""


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
    reduce_size_ratio: float = 0.5
    tighten_exit_base_trail_pct: float = 2.0


@dataclass
class BacktestResult:
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class EventDrivenBacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @classmethod
    def load_intelligence_events_jsonl(cls, path: str | Path) -> List[BacktestIntelligenceEvent]:
        records: List[BacktestIntelligenceEvent] = []
        file_path = Path(path)
        if not file_path.exists():
            return records
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = str(line or "").strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                ts = cls._parse_timestamp(record.get("ts"))
                if ts is None:
                    continue
                payload = record.get("payload", {})
                if not isinstance(payload, dict):
                    payload = {}
                raw_ref = record.get("raw_ref", "")
                if not payload and isinstance(raw_ref, str) and raw_ref:
                    try:
                        parsed = json.loads(raw_ref)
                        if isinstance(parsed, dict):
                            payload = parsed
                    except Exception:
                        payload = {}
                records.append(
                    BacktestIntelligenceEvent(
                        ts=ts,
                        scope=str(record.get("scope", "symbol") or "symbol"),
                        symbol=str(record.get("symbol", "") or ""),
                        source=str(record.get("source", "") or ""),
                        event_type=str(record.get("event_type", "") or ""),
                        score=float(record.get("score", 0.0) or 0.0),
                        tags=list(record.get("tags", []) or []),
                        summary=str(record.get("summary", "") or ""),
                        blocking=bool(record.get("blocking", False)),
                        event_id=str(record.get("event_id", "") or ""),
                        payload=payload,
                        raw_ref=raw_ref,
                    )
                )
        return sorted(records, key=lambda event: (event.ts, event.scope, event.symbol, event.event_type, event.event_id))

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

    @staticmethod
    def _policy_rank(policy: str) -> int:
        return {
            "allow": 0,
            "watch_only": 1,
            "block_entry": 2,
            "reduce_size": 3,
            "tighten_exit": 4,
            "force_exit": 5,
        }.get(str(policy or "allow"), 0)

    @staticmethod
    def _exit_policy_rank(policy: str) -> int:
        return {
            "none": 0,
            "reduce_size": 3,
            "tighten_exit": 4,
            "force_exit": 5,
        }.get(str(policy or "none"), 0)

    @staticmethod
    def _exit_policy_from_rank(rank: int) -> str:
        return {
            0: "none",
            3: "reduce_size",
            4: "tighten_exit",
            5: "force_exit",
        }.get(int(rank), "none")

    @staticmethod
    def _payload_from_event(event: BacktestIntelligenceEvent) -> Dict[str, Any]:
        if isinstance(event.payload, dict) and event.payload:
            return dict(event.payload)
        if isinstance(event.raw_ref, dict):
            return dict(event.raw_ref)
        if isinstance(event.raw_ref, str) and event.raw_ref:
            try:
                parsed = json.loads(event.raw_ref)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    def _merge_scope_state(self, state: Dict[str, Any], event: BacktestIntelligenceEvent, payload: Dict[str, Any]):
        state["intel_status"] = "fresh"
        state["status"] = "fresh"
        state["last_event_ts"] = event.ts
        state["source"] = str(event.source or state.get("source", ""))
        state["event_type"] = str(event.event_type or payload.get("event_type", state.get("event_type", "")) or "")
        state["event_severity"] = str(
            payload.get("event_severity", "critical" if event.blocking else ("high" if float(event.score or 0.0) <= -60 else "low"))
            or "low"
        )
        if payload:
            state.update(payload)
        if event.event_id or payload.get("event_id"):
            state["last_event_id"] = str(event.event_id or payload.get("event_id") or "")

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

        if event.blocking:
            state["blocking"] = True
        if "action_policy" in payload:
            current = str(state.get("action_policy", "allow") or "allow")
            incoming = str(payload.get("action_policy", "allow") or "allow")
            state["action_policy"] = incoming if self._policy_rank(incoming) >= self._policy_rank(current) else current
        elif event.blocking and self._policy_rank(str(state.get("action_policy", "allow") or "allow")) < self._policy_rank("block_entry"):
            state["action_policy"] = "block_entry"

        if "exit_policy" in payload:
            current_exit = str(state.get("exit_policy", "none") or "none")
            incoming_exit = str(payload.get("exit_policy", "none") or "none")
            if self._exit_policy_rank(incoming_exit) >= self._exit_policy_rank(current_exit):
                state["exit_policy"] = incoming_exit
        elif str(state.get("action_policy", "allow") or "allow") in {"reduce_size", "tighten_exit", "force_exit"}:
            state["exit_policy"] = str(state.get("action_policy", "allow") or "allow")

        if "portfolio_budget_scale" in payload:
            current_scale = float(state.get("portfolio_budget_scale", 1.0) or 1.0)
            incoming_scale = max(0.1, float(payload.get("portfolio_budget_scale", 1.0) or 1.0))
            state["portfolio_budget_scale"] = min(current_scale, incoming_scale)

    def _apply_intelligence_event(
        self,
        symbol_intelligence_state: Dict[str, Dict[str, Any]],
        scoped_intelligence_state: Dict[str, Dict[str, Any]],
        event: BacktestIntelligenceEvent,
    ):
        payload = self._payload_from_event(event)
        scope = str(event.scope or payload.get("scope", "symbol") or "symbol").lower()
        if scope == "market":
            state = scoped_intelligence_state.setdefault("market", {})
        elif scope == "sector":
            sector = str(payload.get("sector", "") or payload.get("scope_key", "") or event.symbol or "")
            if not sector:
                return
            state = scoped_intelligence_state.setdefault("sector", {}).setdefault(sector, {})
        elif scope == "theme":
            theme = str(payload.get("theme", "") or payload.get("scope_key", "") or event.symbol or "")
            if not theme:
                return
            state = scoped_intelligence_state.setdefault("theme", {}).setdefault(theme, {})
        else:
            symbol = str(event.symbol or payload.get("symbol", "") or "")
            if not symbol:
                return
            state = symbol_intelligence_state.setdefault(symbol, {})
        self._merge_scope_state(state, event, payload)

    def _compose_effective_intelligence(
        self,
        *,
        symbol: str,
        meta: Dict[str, Any],
        symbol_intelligence_state: Dict[str, Dict[str, Any]],
        scoped_intelligence_state: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        layers: List[Dict[str, Any]] = []
        market_state = scoped_intelligence_state.get("market", {})
        if isinstance(market_state, dict) and market_state:
            layers.append(market_state)

        sector = str(meta.get("sector", "") or meta.get("industry", "") or "").strip()
        if sector:
            sector_state = scoped_intelligence_state.get("sector", {}).get(sector, {})
            if isinstance(sector_state, dict) and sector_state:
                layers.append(sector_state)

        themes_raw = meta.get("theme_keywords", meta.get("themes", []))
        theme_names: List[str] = []
        if isinstance(themes_raw, str) and themes_raw.strip():
            theme_names = [themes_raw.strip()]
        elif isinstance(themes_raw, list):
            theme_names = [str(theme or "").strip() for theme in themes_raw if str(theme or "").strip()]
        for theme in theme_names:
            theme_state = scoped_intelligence_state.get("theme", {}).get(theme, {})
            if isinstance(theme_state, dict) and theme_state:
                layers.append(theme_state)

        symbol_state = symbol_intelligence_state.get(symbol, {})
        if isinstance(symbol_state, dict) and symbol_state:
            layers.append(symbol_state)

        combined: Dict[str, Any] = {
            "intel_status": "idle",
            "status": "idle",
            "news_score": 0.0,
            "dart_risk_level": "normal",
            "macro_regime": "neutral",
            "theme_score": 0.0,
            "headline_velocity": 0,
            "action_policy": "allow",
            "exit_policy": "none",
            "size_multiplier": 1.0,
            "portfolio_budget_scale": 1.0,
            "blocking": False,
            "last_event_id": "",
            "event_type": "",
            "event_severity": "low",
        }
        action_rank = 0
        exit_rank = 0
        latest_ts: Optional[datetime] = None
        source_health: List[str] = []
        cumulative_news_score = 0.0
        combined_size_multiplier = 1.0
        combined_budget_scale = 1.0
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            status = str(layer.get("status", layer.get("intel_status", "idle")) or "idle")
            if status in {"error", "partial", "stale"}:
                combined["status"] = status
                combined["intel_status"] = status
            elif combined["status"] == "idle" and status:
                combined["status"] = status
                combined["intel_status"] = status

            cumulative_news_score += float(layer.get("news_score", 0.0) or 0.0)
            combined["theme_score"] = max(combined["theme_score"], float(layer.get("theme_score", 0.0) or 0.0))
            combined["headline_velocity"] = max(combined["headline_velocity"], int(layer.get("headline_velocity", 0) or 0))
            if str(layer.get("dart_risk_level", "normal") or "normal") == "high":
                combined["dart_risk_level"] = "high"
            macro_regime = str(layer.get("macro_regime", "neutral") or "neutral")
            if macro_regime == "risk_off":
                combined["macro_regime"] = "risk_off"
            elif macro_regime == "risk_on" and combined["macro_regime"] != "risk_off":
                combined["macro_regime"] = "risk_on"

            layer_policy = str(layer.get("action_policy", "allow") or "allow")
            if self._policy_rank(layer_policy) >= action_rank:
                action_rank = self._policy_rank(layer_policy)
                combined["action_policy"] = layer_policy

            layer_exit = str(layer.get("exit_policy", "none") or "none")
            if self._exit_policy_rank(layer_exit) >= exit_rank:
                exit_rank = self._exit_policy_rank(layer_exit)
                combined["exit_policy"] = self._exit_policy_from_rank(exit_rank)

            size_multiplier = float(layer.get("size_multiplier", 1.0) or 1.0)
            if size_multiplier > 0:
                combined_size_multiplier *= size_multiplier
            budget_scale = float(layer.get("portfolio_budget_scale", 1.0) or 1.0)
            if budget_scale > 0:
                combined_budget_scale = min(combined_budget_scale, budget_scale)

            if bool(layer.get("blocking", False)):
                combined["blocking"] = True
            source_health_text = str(layer.get("source_health", "") or "").strip()
            if source_health_text:
                source_health.append(source_health_text)
            layer_ts = layer.get("last_event_ts")
            if isinstance(layer_ts, datetime) and (latest_ts is None or layer_ts >= latest_ts):
                latest_ts = layer_ts
                combined["last_event_id"] = str(layer.get("last_event_id", "") or combined.get("last_event_id", ""))
                combined["event_type"] = str(layer.get("event_type", "") or combined.get("event_type", ""))
                combined["event_severity"] = str(layer.get("event_severity", "low") or combined.get("event_severity", "low"))

        combined["news_score"] = max(-100.0, min(100.0, cumulative_news_score))
        combined["size_multiplier"] = max(0.1, min(2.0, combined_size_multiplier))
        combined["portfolio_budget_scale"] = max(0.1, min(1.0, combined_budget_scale))
        combined["source_health"] = " | ".join(dict.fromkeys(source_health))
        return combined

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
        current = ts.time()
        return self.config.tradable_start <= current <= self.config.tradable_end

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
        action_policy = str(intelligence.get("action_policy", "") or "")
        news_score = float(intelligence.get("news_score", 0.0) or 0.0)
        dart_risk = str(intelligence.get("dart_risk_level", "normal") or "normal")
        macro_regime = str(intelligence.get("macro_regime", "neutral") or "neutral")
        theme_score = float(intelligence.get("theme_score", 0.0) or 0.0)
        intel_status = str(intelligence.get("status", intelligence.get("intel_status", "idle")) or "idle")

        if action_policy in {"block_entry", "force_exit"}:
            return "hold"
        if dart_risk == "high":
            return "hold"
        if bool(intelligence.get("blocking", False)) and action_policy not in {"reduce_size", "tighten_exit", "watch_only"}:
            return "hold"
        if action_policy not in {"reduce_size", "tighten_exit", "watch_only"} and news_score <= float(self.config.news_block_threshold):
            return "hold"
        if macro_regime == "risk_off" and news_score <= float(self.config.macro_block_threshold) and action_policy not in {"reduce_size", "tighten_exit"}:
            return "hold"
        if intel_status not in {"idle", "disabled", "fresh", "ok_with_data", "ok_empty"}:
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

    def _apply_position_defense(
        self,
        *,
        action: str,
        bar: BacktestBar,
        symbol_state: PositionState,
        intelligence: Dict[str, Any],
    ) -> tuple[str, Optional[float]]:
        if symbol_state.side != "long":
            return action, None
        if action == "sell":
            return action, None

        exit_policy = str(intelligence.get("exit_policy", "none") or "none")
        event_id = str(
            intelligence.get("last_event_id", "")
            or intelligence.get("event_id", "")
            or f"{exit_policy}:{intelligence.get('event_type', '')}:{intelligence.get('event_severity', '')}"
        )
        if exit_policy == "force_exit":
            return "sell", 1.0
        if exit_policy == "reduce_size" and symbol_state.last_intel_event_id != event_id:
            symbol_state.last_intel_event_id = event_id
            ratio = float(intelligence.get("reduce_ratio", self.config.reduce_size_ratio) or self.config.reduce_size_ratio)
            return "sell_partial", ratio
        if exit_policy == "tighten_exit":
            symbol_state.peak_price = max(symbol_state.peak_price, float(bar.high or bar.close or 0.0), float(bar.close or 0.0))
            tighten_scale = float(
                intelligence.get("tighten_exit_scale", intelligence.get("tighten_ts_stop_scale", 0.5)) or 0.5
            )
            trail_pct = max(0.25, float(self.config.tighten_exit_base_trail_pct) * max(0.1, min(1.0, tighten_scale)))
            if symbol_state.peak_price > 0 and float(bar.close or 0.0) <= symbol_state.peak_price * (1.0 - trail_pct / 100.0):
                return "sell", 1.0
        return action, None

    def _market_intel_allocation_scale(self, intelligence: Dict[str, Any]) -> float:
        scale = 1.0
        if str(intelligence.get("action_policy", "allow") or "allow") == "reduce_size":
            scale *= float(intelligence.get("reduce_ratio", self.config.reduce_size_ratio) or self.config.reduce_size_ratio)
        if str(intelligence.get("macro_regime", "neutral") or "neutral") == "risk_off":
            scale *= 0.7
        size_multiplier = float(intelligence.get("size_multiplier", 1.0) or 1.0)
        budget_scale = float(intelligence.get("portfolio_budget_scale", 1.0) or 1.0)
        if size_multiplier > 0:
            scale *= size_multiplier
        if budget_scale > 0:
            scale *= budget_scale
        return max(0.1, min(2.0, scale))

    @staticmethod
    def _avg_abs_bps(values: Deque[float], window: int = 0) -> float:
        if not values:
            return 0.0
        arr = list(values)
        if window > 0:
            arr = arr[-max(1, window) :]
        if not arr:
            return 0.0
        return sum(abs(float(value)) for value in arr) / len(arr)

    def _trim_fail_events(self, events: Deque[float], now_ts: float):
        window_sec = max(1, int(self.config.order_health_window_sec))
        while events and now_ts - float(events[0]) > window_sec:
            events.popleft()

    def _shock_cooldown_delta(self):
        return timedelta(minutes=max(1, int(self.config.shock_cooldown_min)))

    def _order_health_cooldown_delta(self):
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
        for value in equity_curve:
            peak = max(peak, value)
            if peak > 0:
                dd = (peak - value) / peak * 100.0
                max_dd = max(max_dd, dd)
        ret = (equity_curve[-1] - initial_cash) / initial_cash * 100.0 if initial_cash > 0 else 0.0
        return {
            "return_pct": ret,
            "max_drawdown_pct": max_dd,
            "trades": float(len(trades)),
        }
