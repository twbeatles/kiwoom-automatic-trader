"""Canonical OrderSyncMixin feature package."""

from .pending_api import OrderSyncPendingApiMixin
from .pending_state import OrderSyncPendingStateMixin
from .position_sync import OrderSyncPositionSyncMixin
from .realtime import OrderSyncRealtimeMixin
from .state_maps import OrderSyncStateMapsMixin


class OrderSyncMixin(OrderSyncStateMapsMixin, OrderSyncPendingStateMixin, OrderSyncRealtimeMixin, OrderSyncPendingApiMixin, OrderSyncPositionSyncMixin):
    """Composed OrderSyncMixin split by feature responsibility."""

    ACTIVE_PENDING_STATES = {"submitted", "partial"}
    TERMINAL_PENDING_STATES = {"filled", "cancelled", "rejected", "sync_failed"}

__all__ = [
    "OrderSyncMixin",
    "OrderSyncStateMapsMixin",
    "OrderSyncPendingStateMixin",
    "OrderSyncRealtimeMixin",
    "OrderSyncPendingApiMixin",
    "OrderSyncPositionSyncMixin",
]
