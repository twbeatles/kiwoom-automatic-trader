"""Canonical PersistenceSettingsMixin feature package."""

from .schema import PersistenceSchemaMixin
from .settings_io import PersistenceSettingsIOMixin
from .trade_history import PersistenceTradeHistoryMixin


class PersistenceSettingsMixin(PersistenceSchemaMixin, PersistenceTradeHistoryMixin, PersistenceSettingsIOMixin):
    """Composed PersistenceSettingsMixin split by feature responsibility."""

    pass

__all__ = [
    "PersistenceSettingsMixin",
    "PersistenceSchemaMixin",
    "PersistenceTradeHistoryMixin",
    "PersistenceSettingsIOMixin",
]
