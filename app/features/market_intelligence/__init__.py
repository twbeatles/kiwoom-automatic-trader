"""Canonical MarketIntelligenceMixin feature package."""

from .audit import MarketIntelAuditMixin
from .runtime import MarketIntelRuntimeMixin
from .scoring_policy import MarketIntelScoringPolicyMixin
from .settings_ui import MarketIntelSettingsUIMixin
from .state import MarketIntelStateMixin
from .views import MarketIntelViewsMixin


class MarketIntelligenceMixin(
    MarketIntelStateMixin,
    MarketIntelSettingsUIMixin,
    MarketIntelScoringPolicyMixin,
    MarketIntelAuditMixin,
    MarketIntelRuntimeMixin,
    MarketIntelViewsMixin,
):
    """Composed MarketIntelligenceMixin split by feature responsibility."""

    pass


__all__ = [
    "MarketIntelligenceMixin",
    "MarketIntelStateMixin",
    "MarketIntelSettingsUIMixin",
    "MarketIntelScoringPolicyMixin",
    "MarketIntelAuditMixin",
    "MarketIntelRuntimeMixin",
    "MarketIntelViewsMixin",
]
