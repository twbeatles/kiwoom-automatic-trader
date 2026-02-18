"""Base strategy protocol."""

from abc import ABC, abstractmethod

from .types import StrategyContext, StrategyResult


class BaseStrategy(ABC):
    strategy_id = "base"

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyResult:
        raise NotImplementedError
