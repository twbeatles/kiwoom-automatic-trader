"""Portfolio allocation utilities for multi-strategy simulation."""

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class AllocationInput:
    strategy_id: str
    signal_strength: float
    volatility: float
    max_weight: float = 0.3


class RiskBudgetAllocator:
    def __init__(self, total_risk_budget: float = 1.0):
        self.total_risk_budget = max(0.0, float(total_risk_budget))

    def allocate(self, inputs: Iterable[AllocationInput]) -> Dict[str, float]:
        rows: List[AllocationInput] = list(inputs)
        if not rows or self.total_risk_budget <= 0:
            return {}

        # Inverse-volatility with signal-strength weighting.
        raw: Dict[str, float] = {}
        for item in rows:
            vol = max(item.volatility, 1e-8)
            score = max(0.0, item.signal_strength)
            raw[item.strategy_id] = (score / vol)

        total = sum(raw.values())
        if total <= 0:
            return {item.strategy_id: 0.0 for item in rows}

        weights: Dict[str, float] = {}
        for item in rows:
            base = raw[item.strategy_id] / total
            capped = min(item.max_weight, base * self.total_risk_budget)
            weights[item.strategy_id] = capped

        # Re-normalize under budget.
        used = sum(weights.values())
        if used > self.total_risk_budget and used > 0:
            scale = self.total_risk_budget / used
            for key in list(weights.keys()):
                weights[key] *= scale

        return weights
