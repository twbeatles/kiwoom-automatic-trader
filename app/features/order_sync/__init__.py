"""Canonical OrderSyncMixin feature package."""

from .state_maps import OrderSyncStateMapsMixin
from .pending_state import OrderSyncPendingStateMixin
from .realtime import OrderSyncRealtimeMixin
from .pending_api import OrderSyncPendingApiMixin
from .position_sync import OrderSyncPositionSyncMixin


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
