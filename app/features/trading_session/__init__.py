"""Canonical TradingSessionMixin feature package."""

from .positions import TradingSessionPositionsMixin
from .cleanup import TradingSessionCleanupMixin
from .risk_state import TradingSessionRiskStateMixin
from .external_flow import TradingSessionExternalFlowMixin
from .lifecycle import TradingSessionLifecycleMixin
from .table import TradingSessionTableMixin

from .positions import BackgroundUniversePayload


class TradingSessionMixin(TradingSessionPositionsMixin, TradingSessionCleanupMixin, TradingSessionRiskStateMixin, TradingSessionExternalFlowMixin, TradingSessionLifecycleMixin, TradingSessionTableMixin):
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
