"""Backtest entry guards (SRP: tradable-time/shock/regime/liquidity/slippage/order-health)."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional

from ._policy import BacktestPolicyMixin
from .models import BacktestBar


class BacktestGuardsMixin(BacktestPolicyMixin):
    """Backtest entry guards (SRP: tradable-time/shock/regime/liquidity/slippage/order-health)."""

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

    def _trim_fail_events(self, events: Deque[float], now_ts: float):
        window_sec = max(1, int(self.config.order_health_window_sec))
        while events and now_ts - float(events[0]) > window_sec:
            events.popleft()

    def _shock_cooldown_delta(self):
        return timedelta(minutes=max(1, int(self.config.shock_cooldown_min)))

    def _order_health_cooldown_delta(self):
        return timedelta(seconds=max(1, int(self.config.order_health_cooldown_sec)))
