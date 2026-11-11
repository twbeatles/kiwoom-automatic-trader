"""Canonical ExecutionEngineMixin feature package."""

from .buy_flow import ExecutionBuyFlowMixin
from .cash_reservation import ExecutionCashReservationMixin
from .guards import ExecutionGuardsMixin
from .mode_lifecycle import ExecutionModeLifecycleMixin
from .sell_flow import ExecutionSellFlowMixin


class ExecutionEngineMixin(ExecutionModeLifecycleMixin, ExecutionCashReservationMixin, ExecutionGuardsMixin, ExecutionBuyFlowMixin, ExecutionSellFlowMixin):
    """Composed ExecutionEngineMixin split by feature responsibility."""

    pass

__all__ = [
    "ExecutionEngineMixin",
    "ExecutionModeLifecycleMixin",
    "ExecutionCashReservationMixin",
    "ExecutionGuardsMixin",
    "ExecutionBuyFlowMixin",
    "ExecutionSellFlowMixin",
]
