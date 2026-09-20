"""Backtest policy math (SRP: policy ranks/allocation/costs/position defense)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

from ._metrics import BacktestMetricsMixin
from .models import BacktestBar, BacktestIntelligenceEvent, PositionState


class BacktestPolicyMixin(BacktestMetricsMixin):
    """Backtest policy math (SRP: policy ranks/allocation/costs/position defense)."""

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
