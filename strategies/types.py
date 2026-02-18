"""Core strategy data structures for modular strategy packs."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalDirection(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"


@dataclass
class Signal:
    strategy_id: str
    direction: SignalDirection
    strength: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyContext:
    code: str
    now_ts: float
    info: Dict[str, Any]
    config: Any
    portfolio_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    passed: bool
    conditions: Dict[str, bool]
    metrics: Dict[str, float]
    signals: List[Signal] = field(default_factory=list)
    reason: Optional[str] = None
