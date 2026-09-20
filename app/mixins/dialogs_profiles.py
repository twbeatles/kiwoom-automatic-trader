"""Dialogs/profiles mixin for KiwoomProTrader.

SOLID 분할 구조의 composite: 수동주문(`app.features.dialogs.manual_orders`),
즐겨찾기(`favorites`), 프리셋/프로필/예약(`preset_profiles`),
설정 스냅샷(`settings_snapshot`) 믹스인을 조합한다.
공개 API·import 경로·patch seam(`QMessageBox`, `ManualOrderDialog` 등)은 그대로 유지된다.
"""

from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox  # noqa: F401 (seam compat)
from app.support.ui_text import combo_value, set_combo_value  # noqa: F401 (seam compat)
from app.support.worker import Worker  # noqa: F401 (seam compat)
from config import Config  # noqa: F401 (seam compat)
from dark_theme import DARK_STYLESHEET  # noqa: F401 (seam compat)
from light_theme import LIGHT_STYLESHEET  # noqa: F401 (seam compat)
from ui_dialogs import (  # noqa: F401 (seam compat)
    ManualOrderDialog,
    PresetDialog,
    ProfileManagerDialog,
    ScheduleDialog,
    StockSearchDialog,
)
from app.features.dialogs.favorites import FavoritesMixin  # noqa: F401
from app.features.dialogs.manual_orders import ManualOrdersMixin  # noqa: F401
from app.features.dialogs.preset_profiles import PresetProfilesMixin  # noqa: F401
from app.features.dialogs.settings_snapshot import SettingsSnapshotMixin  # noqa: F401


class DialogsProfilesMixin(
    ManualOrdersMixin, FavoritesMixin, PresetProfilesMixin, SettingsSnapshotMixin
):
    """Composite facade (behavior unchanged)."""
