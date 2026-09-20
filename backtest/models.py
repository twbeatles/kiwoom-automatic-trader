"""Backtest state shapes (SRP: data only, no behavior)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Dict, List


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
