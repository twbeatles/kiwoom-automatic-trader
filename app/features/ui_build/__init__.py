"""Canonical UIBuildMixin feature package."""

from .backtest import UIBuildBacktestMixin
from .layout import UIBuildLayoutMixin
from .settings_tabs import UIBuildSettingsTabsMixin
from .market_tabs import UIBuildMarketTabsMixin
from .data_tabs import UIBuildDataTabsMixin


class UIBuildMixin(UIBuildBacktestMixin, UIBuildLayoutMixin, UIBuildSettingsTabsMixin, UIBuildMarketTabsMixin, UIBuildDataTabsMixin):
    """Composed UIBuildMixin split by feature responsibility."""

    pass

__all__ = [
    "UIBuildMixin",
    "UIBuildBacktestMixin",
    "UIBuildLayoutMixin",
    "UIBuildSettingsTabsMixin",
    "UIBuildMarketTabsMixin",
    "UIBuildDataTabsMixin",
]
