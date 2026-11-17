"""Canonical TradingSessionMixin feature package."""

from .cleanup import TradingSessionCleanupMixin
from .external_flow import TradingSessionExternalFlowMixin
from .lifecycle import TradingSessionLifecycleMixin
from .positions import BackgroundUniversePayload, TradingSessionPositionsMixin
from .risk_state import TradingSessionRiskStateMixin
from .table import TradingSessionTableMixin


class TradingSessionMixin(
    TradingSessionPositionsMixin,
    TradingSessionCleanupMixin,
    TradingSessionRiskStateMixin,
    TradingSessionExternalFlowMixin,
    TradingSessionLifecycleMixin,
    TradingSessionTableMixin,
):
    """Composed TradingSessionMixin split by feature responsibility."""

    pass


__all__ = [
    "TradingSessionMixin",
    "TradingSessionPositionsMixin",
    "TradingSessionCleanupMixin",
    "TradingSessionRiskStateMixin",
    "TradingSessionExternalFlowMixin",
    "TradingSessionLifecycleMixin",
    "TradingSessionTableMixin",
    "BackgroundUniversePayload",
]
