"""HiDPI/display-scale helpers for Kiwoom Pro Algo-Trader.

Qt-free pure logic (unit-testable without PyQt6):

- :func:`recommended_font_scale` maps a screen's devicePixelRatio /
  logical DPI to a ``ui_font_scale`` value in [0.85, 1.5].
- :func:`recommended_density` picks ``compact`` vs ``comfortable`` menu
  density for the same inputs.
- :func:`configure_high_dpi_scaling` enables Qt's fractional-scale
  rounding policy (``PassThrough``) so 125%/150%/175% OS scales are
  honoured instead of being rounded away. Safe to call when PyQt6 is
  missing (reports ``"unavailable"``).

Thresholds follow common Windows display-scale buckets:

- ratio >= 2.0 or DPI >= 192  -> 200% class
- ratio >= 1.5 or DPI >= 144  -> 150% class
- ratio >= 1.25 or DPI >= 120 -> 125% class
- otherwise                  -> 100% class
"""

from __future__ import annotations

from typing import Any

UI_SCALE_STEPS: tuple = (0.85, 1.0, 1.15, 1.3, 1.5)

DENSITY_NAMES = ("compact", "comfortable")
DEFAULT_DENSITY = "compact"


def clamp_density(value: object) -> str:
    """Normalize a density name; unknown values fall back to compact."""
    text = str(value or "").strip().lower()
    if text in DENSITY_NAMES:
        return text
    return DEFAULT_DENSITY


def _scale_class(
    device_pixel_ratio: Any = None,
    logical_dpi: Any = None,
) -> str:
    """Classify the display into 100/125/150/200% buckets."""
    try:
        ratio = float(device_pixel_ratio) if device_pixel_ratio is not None else 0.0
    except (TypeError, ValueError):
        ratio = 0.0
    try:
        dpi = float(logical_dpi) if logical_dpi is not None else 0.0
    except (TypeError, ValueError):
        dpi = 0.0
    if ratio >= 2.0 or dpi >= 192:
        return "200"
    if ratio >= 1.5 or dpi >= 144:
        return "150"
    if ratio >= 1.25 or dpi >= 120:
        return "125"
    return "100"


def recommended_font_scale(
    device_pixel_ratio: Any = None,
    logical_dpi: Any = None,
) -> float:
    """Return the first-run ``ui_font_scale`` for a display.

    Always 1.0: theme fonts are emitted in ``pt`` so the OS text scale
    already keeps physical text size constant across 100/125/150/200%.
    Raising the app multiplier on top of that double-scales text
    (HiDPI text rendered too large), so no bucket steps up anymore.
    Users who want larger text use 보기 > UI 크기 / Ctrl+= explicitly.
    """
    return 1.0


def recommended_density(
    device_pixel_ratio: Any = None,
    logical_dpi: Any = None,
) -> str:
    """Return ``comfortable`` on 150%+ displays, else ``compact``."""
    bucket = _scale_class(device_pixel_ratio, logical_dpi)
    return "comfortable" if bucket in ("150", "200") else "compact"


def next_scale_step(current: Any, direction: int = 1) -> float:
    """Step *current* to the neighbouring value in UI_SCALE_STEPS."""
    try:
        value = float(current)
    except (TypeError, ValueError):
        value = 1.0
    steps = sorted(UI_SCALE_STEPS)
    if direction >= 0:
        for step in steps:
            if step > value + 1e-9:
                return step
        return steps[-1]
    for step in reversed(steps):
        if step < value - 1e-9:
            return step
    return steps[0]


def configure_high_dpi_scaling() -> str:
    """Enable fractional OS-scale handling in Qt; return status string.

    Must be called *before* ``QApplication`` is constructed. Returns one
    of ``"passthrough"``, ``"legacy"`` (policy enum missing on old Qt),
    or ``"unavailable"`` (Qt not importable). Never raises.
    """
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return "unavailable"
    try:
        policy = Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    except Exception:
        return "legacy"
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(policy)
    except Exception:
        return "legacy"
    return "passthrough"
