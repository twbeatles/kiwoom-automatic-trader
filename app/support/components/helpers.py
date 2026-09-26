"""Small shared UI helpers: secondary text, validation, status badges.

Colors come from the central theme via dynamic properties (no per-page
hex, DESKTOP_UI_DESIGN_RULES §§7/9). PyQt6 is a hard project dependency,
so this module imports it directly like app/support/widgets.py.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


def _repolish(widget: QWidget) -> None:
    try:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
    except Exception:
        pass


def mark_secondary(widget: QWidget) -> QWidget:
    """Mark *widget* as secondary text via dynamic property (theme QSS)."""
    try:
        widget.setProperty("secondary", True)
    except Exception:
        pass
    return widget


def mark_invalid(widget: QWidget, invalid: bool = True) -> QWidget:
    """Toggle the ``invalid`` dynamic property for form validation."""
    try:
        widget.setProperty("invalid", bool(invalid))
    except Exception:
        pass
    _repolish(widget)
    return widget


def set_connection_badge(widget: QWidget, mode: str) -> QWidget:
    """Status badge for API connection: connected/connecting/disconnected."""
    try:
        widget.setProperty("badge", str(mode))
    except Exception:
        pass
    _repolish(widget)
    return widget


def set_profit_sign(widget: QWidget, sign: int) -> QWidget:
    """Profit badge: sign > 0 up, < 0 down, else flat."""
    state = "up" if sign > 0 else ("down" if sign < 0 else "flat")
    try:
        widget.setProperty("profit_state", state)
    except Exception:
        pass
    _repolish(widget)
    return widget


def set_trading_badge(widget: QWidget, running: bool) -> QWidget:
    """Footer trading badge: running vs idle."""
    try:
        widget.setProperty("badge", "active" if running else "off")
    except Exception:
        pass
    _repolish(widget)
    return widget


def make_empty_state(title: str, hint: str = "") -> QWidget:
    """Title + secondary hint widget (table empty state, §14)."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setProperty("section", True)
    layout.addWidget(title_label)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        mark_secondary(hint_label)
        layout.addWidget(hint_label)
    layout.addStretch()
    return box


def make_section_header(title: str, subtitle: str = "") -> QWidget:
    """Title + secondary subtitle pair (§6: title + secondary text)."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setProperty("section", True)
    layout.addWidget(title_label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        mark_secondary(sub)
        layout.addWidget(sub)
    return box
