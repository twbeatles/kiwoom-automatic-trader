"""Non-modal InfoBar host (srtgo ktrain §27.4 borrow, PyQt6-only).

QFluentWidgets is intentionally NOT added (project binding is PyQt6 and
the package shares one import namespace per binding — conflict risk per
rules §1.1). This host gives the same UX split: non-blocking success /
warning / error banners inline; modal QMessageBox stays reserved for
destructive / must-choose cases (§15).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LEVEL_PROPERTY = {
    "success": "success",
    "info": "info",
    "warning": "warning",
    "error": "error",
}


class InfoBarHost(QWidget):
    """Vertical stack of auto-dismissing notice banners."""

    def __init__(self, parent: QWidget | None = None, max_bars: int = 3):
        super().__init__(parent)
        self._max_bars = max(1, int(max_bars))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._layout = layout

    def show_message(
        self,
        level: str,
        title: str,
        body: str = "",
        duration_ms: int = 6000,
    ) -> QFrame:
        """Add a banner; oldest is dropped past max_bars."""
        bar = QFrame(self)
        bar.setProperty("infobar", LEVEL_PROPERTY.get(level, "info"))
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 8, 8)
        row.setSpacing(8)
        text = QLabel(f"<b>{title}</b> {body}".strip())
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(text, 1)
        close_btn = QPushButton("닫기")
        close_btn.setProperty("secondary_button", True)
        close_btn.clicked.connect(bar.deleteLater)
        row.addWidget(close_btn)
        self._layout.addWidget(bar)
        while self._layout.count() > self._max_bars:
            taken = self._layout.takeAt(0)
            oldest = taken.widget() if taken is not None else None
            if oldest is not None:
                oldest.deleteLater()
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, bar.deleteLater)
        return bar
