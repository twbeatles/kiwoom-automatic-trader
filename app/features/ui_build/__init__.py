"""Canonical UIBuildMixin feature package."""

from .backtest import UIBuildBacktestMixin
from .data_tabs import UIBuildDataTabsMixin
from .layout import UIBuildLayoutMixin
from .market_tabs import UIBuildMarketTabsMixin
from .settings_tabs import UIBuildSettingsTabsMixin
from .workspaces import WORKSPACE_LABELS, UIBuildWorkspacesMixin


class UIBuildMixin(UIBuildWorkspacesMixin, UIBuildBacktestMixin, UIBuildLayoutMixin, UIBuildSettingsTabsMixin, UIBuildMarketTabsMixin, UIBuildDataTabsMixin):
    """Composed UIBuildMixin split by feature responsibility."""

    pass

__all__ = [
    "UIBuildMixin",
    "UIBuildWorkspacesMixin",
    "WORKSPACE_LABELS",
    "UIBuildBacktestMixin",
    "UIBuildLayoutMixin",
    "UIBuildSettingsTabsMixin",
    "UIBuildMarketTabsMixin",
    "UIBuildDataTabsMixin",
]
