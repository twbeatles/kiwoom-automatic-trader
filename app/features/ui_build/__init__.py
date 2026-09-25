"""Canonical UIBuildMixin feature package."""

from .workspaces import UIBuildWorkspacesMixin, WORKSPACE_LABELS
from .backtest import UIBuildBacktestMixin
from .layout import UIBuildLayoutMixin
from .settings_tabs import UIBuildSettingsTabsMixin
from .market_tabs import UIBuildMarketTabsMixin
from .data_tabs import UIBuildDataTabsMixin


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
