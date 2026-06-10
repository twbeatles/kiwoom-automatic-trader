"""Canonical PersistenceSettingsMixin feature package."""

from .schema import PersistenceSchemaMixin
from .trade_history import PersistenceTradeHistoryMixin
from .settings_io import PersistenceSettingsIOMixin


class PersistenceSettingsMixin(PersistenceSchemaMixin, PersistenceTradeHistoryMixin, PersistenceSettingsIOMixin):
    """Composed PersistenceSettingsMixin split by feature responsibility."""

    pass

__all__ = [
    "PersistenceSettingsMixin",
    "PersistenceSchemaMixin",
    "PersistenceTradeHistoryMixin",
    "PersistenceSettingsIOMixin",
]
