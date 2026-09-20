"""Backtest metrics (SRP: mark-to-market + result statistics)."""

from __future__ import annotations

from typing import Any, Dict, List

from ._base import BacktestEngineBase
from .models import PositionState


class BacktestMetricsMixin(BacktestEngineBase):
    """Backtest metrics (SRP: mark-to-market + result statistics)."""

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
