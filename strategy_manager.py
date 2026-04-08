"""
Strategy Manager v4.5
매매 전략 로직 - 확장된 기능 포함
"""

from typing import Any, Dict

from strategies import StrategyPackEngine
from strategies.manager_mixins import (
    StrategyManagerEvaluationMixin,
    StrategyManagerIndicatorMixin,
    StrategyManagerLoggingMixin,
    StrategyManagerMarketIntelMixin,
    StrategyManagerPortfolioRiskMixin,
    StrategyManagerSignalFilterMixin,
)


class StrategyManager(
    StrategyManagerEvaluationMixin,
    StrategyManagerPortfolioRiskMixin,
    StrategyManagerIndicatorMixin,
    StrategyManagerSignalFilterMixin,
    StrategyManagerMarketIntelMixin,
    StrategyManagerLoggingMixin,
):
    """매매 전략 오케스트레이션 레이어."""

    def __init__(self, trader, config=None):
        self.trader = trader
        self.config = config
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.sector_investments: Dict[str, float] = {}
        self.market_investments = {"kospi": 0, "kosdaq": 0}
        self._decision_cache: Dict[str, Dict[str, Any]] = {}
        self.pack_engine = StrategyPackEngine(self)
