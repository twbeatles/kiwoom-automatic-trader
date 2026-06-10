"""Canonical MarketIntelligenceMixin feature package."""

from .state import MarketIntelStateMixin
from .settings_ui import MarketIntelSettingsUIMixin
from .scoring_policy import MarketIntelScoringPolicyMixin
from .audit import MarketIntelAuditMixin
from .runtime import MarketIntelRuntimeMixin
from .views import MarketIntelViewsMixin


class MarketIntelligenceMixin(MarketIntelStateMixin, MarketIntelSettingsUIMixin, MarketIntelScoringPolicyMixin, MarketIntelAuditMixin, MarketIntelRuntimeMixin, MarketIntelViewsMixin):
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
