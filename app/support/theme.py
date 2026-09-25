"""Centralized theme engine for Kiwoom Pro Algo-Trader (P4 theme/a11y).

Tokenized dark/light QSS with WCAG 2.1 AA support:
- palette tokens per theme (single source of truth)
- text/background pairs verified at >= 4.5:1 (see TEXT_CONTRAST_PAIRS)
- 2px focus rings on all interactive widgets
- font scaling via ``ui_font_scale`` (0.85 ~ 1.5)
- screen-reader names via :func:`apply_accessibility_names`

Qt-free: pure string building + duck-typed host access, so unit tests
run without PyQt6.
"""

from __future__ import annotations

THEME_NAMES = ("dark", "light")

FONT_SCALE_MIN = 0.85
FONT_SCALE_MAX = 1.5
DEFAULT_FONT_SCALE = 1.0

DARK_TOKENS = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "surface_2": "#21262d",
    "input_bg": "#010409",
    "border": "#30363d",
    "text": "#c9d1d9",
    "text_bright": "#e6edf3",
    "text_muted": "#8b949e",  # 6.15:1 on bg (AA pass, verified)
    "text_disabled": "#9aa4b2",  # 6.03:1 on surface_2 (AA pass; was #484f58 @1.84)
    "accent": "#58a6ff",  # 7.49:1 on bg
    "accent_solid": "#1f6feb",
    "accent_hover": "#388bfd",
    "accent_pressed": "#1158c7",
    "success": "#3fb950",  # 7.45:1 on bg
    "danger": "#f85149",  # 5.65:1 on bg
    "danger_solid": "#da3633",
    "danger_hover": "#f85149",
    "danger_pressed": "#b62324",
    "warning": "#d29922",
    "warning_dark": "#9a6700",
    "on_accent": "#ffffff",  # 4.63:1 on accent_solid
    "on_danger": "#ffffff",  # 4.61:1 on danger_solid
    "focus_ring": "#79c0ff",
    "selection_bg": "#1f6feb",
    "selection_fg": "#ffffff",
    "font_family": "'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif",
    "mono_family": "'Consolas', monospace",
}

LIGHT_TOKENS = {
    "bg": "#f8f9fa",
    "surface": "#ffffff",
    "surface_2": "#e9ecef",
    "input_bg": "#ffffff",
    "border": "#ced4da",
    "border_soft": "#dee2e6",
    "text": "#212529",  # 14.63:1 on bg
    "text_bright": "#212529",
    "text_muted": "#495057",  # 8.18:1 on white (also used for tabs)
    "text_disabled": "#495057",  # 6.90:1 on surface_2 (AA pass; was #6c757d @3.95)
    "accent": "#0b5ed7",  # 5.84:1 on white (text usages)
    "accent_solid": "#0d6efd",
    "accent_hover": "#3d8bfd",
    "accent_pressed": "#0b5ed7",
    "success": "#198754",
    "success_dark": "#157347",
    "success_pressed": "#146c43",
    "danger": "#dc3545",
    "danger_dark": "#bb2d3b",
    "warning": "#ffc107",
    "warning_dark": "#ffb300",
    "pending": "#fd7e14",
    "on_accent": "#ffffff",
    "on_danger": "#ffffff",
    "focus_ring": "#0b5ed7",
    "selection_bg": "#0d6efd",
    "selection_fg": "#ffffff",
    "log_bg": "#212529",
    "log_fg": "#20c997",  # 7.25:1 on log_bg
    "font_family": "'Malgun Gothic', 'Segoe UI', sans-serif",
    "mono_family": "'Cascadia Code', 'Consolas', 'D2Coding', monospace",
}

TOKENS = {"dark": DARK_TOKENS, "light": LIGHT_TOKENS}

# (foreground, background) text pairs that must stay >= 4.5:1.
TEXT_CONTRAST_PAIRS = {
    "dark": [
        ("text", "bg"),
        ("text_muted", "bg"),
        ("text_disabled", "surface_2"),
        ("accent", "bg"),
        ("success", "bg"),
        ("danger", "bg"),
        ("on_accent", "accent_solid"),
        ("on_danger", "danger_solid"),
    ],
    "light": [
        ("text", "bg"),
        ("text_muted", "surface"),
        ("text_disabled", "surface_2"),
        ("accent", "surface"),
        ("log_fg", "log_bg"),
    ],
}

# Base font sizes (px) at scale 1.0; scaled by ui_font_scale.
BASE_FONT_SIZES = {
    "base": 14,
    "widget": 13,
    "small": 12,
    "button": 13,
    "button_large": 15,
    "header": 12,
    "title": 15,
    "log": 13,
}

DARK_BASE_FONT_SIZES = dict(BASE_FONT_SIZES)
LIGHT_BASE_FONT_SIZES = {
    "base": 13,
    "widget": 13,
    "small": 12,
    "button": 13,
    "button_large": 16,
    "header": 12,
    "title": 13,
    "log": 12,
}


def clamp_font_scale(value) -> float:
    """Clamp a font-scale value into [FONT_SCALE_MIN, FONT_SCALE_MAX]."""
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return DEFAULT_FONT_SCALE
    return max(FONT_SCALE_MIN, min(FONT_SCALE_MAX, scale))


def scaled_sizes(theme: str, font_scale: float = 1.0) -> dict:
    """Return px font sizes for *theme* scaled by *font_scale*."""
    base = DARK_BASE_FONT_SIZES if theme == "dark" else LIGHT_BASE_FONT_SIZES
    scale = clamp_font_scale(font_scale)
    return {key: max(9, int(round(px * scale))) for key, px in base.items()}


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colors."""
    l1 = _relative_luminance(fg_hex)
    l2 = _relative_luminance(bg_hex)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def check_theme_contrast(theme: str) -> dict:
    """Return {pair: ratio} for the theme's TEXT_CONTRAST_PAIRS."""
    tokens = TOKENS[theme]
    report = {}
    for fg_key, bg_key in TEXT_CONTRAST_PAIRS[theme]:
        report[f"{fg_key} on {bg_key}"] = round(
            contrast_ratio(tokens[fg_key], tokens[bg_key]), 2
        )
    return report


def build_stylesheet(theme: str = "dark", font_scale: float = 1.0) -> str:
    """Build the full QSS for *theme* with font sizes scaled."""
    if theme not in TOKENS:
        theme = "dark"
    t = TOKENS[theme]
    fs = scaled_sizes(theme, font_scale)
    if theme == "dark":
        return _build_dark(t, fs)
    return _build_light(t, fs)


def _focus_block(selectors: str, ring: str) -> str:
    return (
        f"{selectors} {{\n"
        f"    border: 2px solid {ring};\n"
        f"    outline: none;\n"
        f"}}"
    )


def _build_dark(t: dict, fs: dict) -> str:
    focus_inputs = (
        "QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,\n"
        "QPushButton:focus, QTableWidget:focus, QListWidget:focus, QTextEdit:focus"
    )
    return f"""\
/* Kiwoom Pro Algo-Trader v4.5 Dark Theme (tokenized: app/support/theme.py) */
QMainWindow, QWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    font-family: {t['font_family']};
    font-size: {fs['base']}px;
    selection-background-color: {t['selection_bg']};
    selection-color: {t['selection_fg']};
}}
QGroupBox {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 12px;
    margin-top: 24px;
    padding: 24px 16px 16px 16px;
    font-weight: 600;
    color: {t['accent']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 4px 12px;
    background-color: {t['bg']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    color: {t['accent']};
}}
QGroupBox#dashboardCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t['surface']}, stop:1 {t['bg']});
    border: 1px solid rgba(88, 166, 255, 0.3);
    border-radius: 16px;
}}
QPushButton {{
    background-color: {t['surface_2']};
    border: 1px solid rgba(240, 246, 252, 0.1);
    border-radius: 8px;
    color: {t['text']};
    padding: 10px 20px;
    font-weight: 600;
    font-size: {fs['button']}px;
}}
QPushButton:hover {{
    background-color: {t['border']};
    border-color: {t['text_muted']};
}}
QPushButton:pressed {{
    background-color: {t['surface']};
    border-color: {t['accent']};
}}
QPushButton:disabled {{
    background-color: rgba(33, 38, 45, 0.5);
    color: {t['text_disabled']};
    border: none;
}}
QPushButton#connectBtn {{
    background-color: {t['accent_solid']};
    color: {t['on_accent']};
    border: none;
    font-size: {fs['base']}px;
    padding: 12px 24px;
}}
QPushButton#connectBtn:hover {{ background-color: {t['accent_hover']}; }}
QPushButton#connectBtn:pressed {{ background-color: {t['accent_pressed']}; }}
QPushButton#startBtn {{
    background-color: {t['danger_solid']};
    color: {t['on_danger']};
    font-size: {fs['button_large']}px;
    padding: 12px 30px;
    border-radius: 10px;
}}
QPushButton#startBtn:hover {{ background-color: {t['danger_hover']}; }}
QPushButton#startBtn:pressed {{ background-color: {t['danger_pressed']}; }}
QPushButton#stopBtn {{
    background-color: {t['surface_2']};
    border: 1px solid {t['text_muted']};
}}
QPushButton#stopBtn:hover {{ background-color: {t['border']}; }}
QPushButton#emergencyBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t['warning_dark']}, stop:1 {t['warning']});
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton#emergencyBtn:hover {{ background: {t['warning']}; }}
QPushButton#emergencyBtn:pressed {{ background: {t['warning_dark']}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {t['input_bg']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 8px 12px;
    color: {t['text']};
    font-size: {fs['widget']}px;
}}
{_focus_block(focus_inputs, t['focus_ring'])}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {t['text_muted']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    selection-background-color: {t['selection_bg']};
    padding: 4px;
}}
QTableWidget {{
    background-color: {t['bg']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    gridline-color: {t['surface_2']};
    outline: none;
}}
QTableWidget::item {{
    padding: 12px 8px;
    border-bottom: 1px solid {t['surface_2']};
}}
QTableWidget::item:hover {{ background-color: rgba(88, 166, 255, 0.08); }}
QTableWidget::item:selected {{
    background-color: rgba(88, 166, 255, 0.15);
    color: {t['accent']};
}}
QHeaderView::section {{
    background-color: {t['surface']};
    padding: 12px;
    border: none;
    border-bottom: 2px solid {t['border']};
    color: {t['text_muted']};
    font-weight: 700;
    font-size: {fs['header']}px;
    text-transform: uppercase;
}}
QCheckBox {{
    color: {t['text']};
    spacing: 10px;
    font-size: {fs['widget']}px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid {t['border']};
    background-color: {t['bg']};
}}
QCheckBox::indicator:hover {{
    border-color: {t['accent']};
    background-color: rgba(88, 166, 255, 0.05);
}}
QCheckBox::indicator:checked {{
    background-color: {t['accent_solid']};
    border-color: {t['accent_solid']};
}}
QLabel {{
    color: {t['text']};
    font-size: {fs['widget']}px;
}}
QLabel#depositCard {{
    color: {t['text_bright']};
    font-weight: bold;
    font-size: {fs['title']}px;
    padding: 10px 15px;
    border-radius: 8px;
    background: rgba(56, 139, 253, 0.1);
    border: 1px solid rgba(56, 139, 253, 0.2);
}}
QLabel#profitCard {{
    color: {t['text_bright']};
    font-weight: bold;
    font-size: {fs['title']}px;
    padding: 10px 15px;
    border-radius: 8px;
    background: rgba(139, 148, 158, 0.1);
    border: 1px solid rgba(139, 148, 158, 0.2);
}}
QLabel#statusConnected {{
    color: {t['success']};
    background-color: rgba(63, 185, 80, 0.1);
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid rgba(63, 185, 80, 0.2);
}}
QLabel#statusDisconnected {{
    color: {t['danger']};
    background-color: rgba(248, 81, 73, 0.1);
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid rgba(248, 81, 73, 0.2);
}}
QScrollBar:vertical {{
    border: none;
    background: {t['bg']};
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {t['border']};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {t['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: 8px;
    background: {t['bg']};
    top: -1px;
}}
QTabBar::tab {{
    background: {t['bg']};
    border: 1px solid transparent;
    color: {t['text_muted']};
    padding: 10px 20px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    color: {t['accent']};
    border-bottom: 2px solid {t['accent']};
}}
QTabBar::tab:hover {{
    color: {t['text']};
    background-color: {t['surface']};
}}
QTabBar::tab:focus {{ border: 2px solid {t['focus_ring']}; }}
QSplitter::handle {{
    background-color: {t['border']};
    height: 6px;
    border-radius: 3px;
    margin: 2px 40px;
}}
QSplitter::handle:hover {{ background-color: {t['accent']}; }}
QToolTip {{
    background-color: {t['surface']};
    color: {t['text_bright']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: {fs['small']}px;
}}
QMenuBar {{
    background-color: {t['bg']};
    color: {t['text']};
    padding: 6px 8px;
    border-bottom: 1px solid {t['surface_2']};
    font-size: {fs['widget']}px;
}}
QMenuBar::item {{
    padding: 8px 14px;
    border-radius: 8px;
}}
QMenuBar::item:selected {{ background-color: rgba(88, 166, 255, 0.1); }}
QMenuBar::item:focus {{ border: 2px solid {t['focus_ring']}; }}
QMenu {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 8px;
}}
QMenu::item {{
    padding: 10px 28px 10px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}}
QMenu::item:selected {{
    background-color: {t['accent_solid']};
    color: {t['selection_fg']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {t['surface_2']};
    margin: 8px 12px;
}}
QStatusBar {{
    background-color: {t['bg']};
    color: {t['text_muted']};
    border-top: 1px solid {t['surface_2']};
    padding: 8px 16px;
    font-size: {fs['small']}px;
}}
QProgressBar {{
    background-color: {t['surface_2']};
    border-radius: 8px;
    height: 10px;
    text-align: center;
    font-size: 10px;
    color: {t['text']};
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['accent_solid']}, stop:0.5 {t['accent']}, stop:1 {t['success']});
    border-radius: 8px;
}}
QListWidget {{
    background-color: {t['bg']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 8px;
    color: {t['text']};
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 0;
}}
QListWidget::item:hover {{ background-color: rgba(88, 166, 255, 0.08); }}
QListWidget::item:selected {{
    background-color: rgba(88, 166, 255, 0.15);
    color: {t['text']};
}}
QDialog {{
    background-color: {t['bg']};
    border: 1px solid {t['border']};
    border-radius: 16px;
}}
QMessageBox {{ background-color: {t['surface']}; }}
QMessageBox QLabel {{
    color: {t['text']};
    font-size: {fs['widget']}px;
}}
QMessageBox QPushButton {{
    min-width: 80px;
    padding: 10px 20px;
}}
.profit {{ color: {t['success']}; }}
.loss {{ color: {t['danger']}; }}
QTextEdit {{
    background-color: {t['bg']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    font-family: {t['mono_family']};
    font-size: {fs['log']}px;
    line-height: 1.5;
}}
"""


def _build_light(t: dict, fs: dict) -> str:
    focus_inputs = (
        "QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,\n"
        "QPushButton:focus, QTableWidget:focus, QListWidget:focus, QTextEdit:focus"
    )
    return f"""\
/* Kiwoom Pro Algo-Trader v4.5 Light Theme (tokenized: app/support/theme.py) */
QMainWindow, QWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    font-family: {t['font_family']};
    font-size: {fs['base']}px;
}}
QGroupBox {{
    background-color: {t['surface']};
    border: 1px solid {t['border_soft']};
    border-radius: 12px;
    margin-top: 20px;
    padding: 24px 18px 18px 18px;
    font-weight: bold;
    color: {t['accent']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 24px;
    padding: 4px 14px;
    background: {t['bg']};
    border: 1px solid {t['border_soft']};
    border-radius: 8px;
    font-size: {fs['base']}px;
}}
QGroupBox#dashboardCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {t['surface']}, stop:1 {t['bg']});
    border: 1px solid rgba(13, 110, 253, 0.2);
    border-radius: 16px;
    padding: 20px;
}}
QPushButton {{
    background-color: {t['success']};
    color: {t['on_accent']};
    border: none;
    border-radius: 10px;
    padding: 12px 28px;
    font-weight: bold;
    font-size: {fs['button']}px;
    min-height: 20px;
}}
QPushButton:hover {{ background-color: {t['success_dark']}; }}
QPushButton:pressed {{ background-color: {t['success_pressed']}; }}
QPushButton:disabled {{
    background-color: {t['surface_2']};
    color: {t['text_disabled']};
}}
QPushButton#connectBtn {{
    background-color: {t['accent_solid']};
    border-radius: 12px;
    padding: 14px 32px;
    font-size: {fs['base']}px;
}}
QPushButton#connectBtn:hover {{ background-color: {t['accent_hover']}; }}
QPushButton#startBtn {{
    background-color: {t['danger']};
    font-size: {fs['button_large']}px;
    padding: 14px 36px;
    border-radius: 14px;
}}
QPushButton#startBtn:hover {{ background-color: {t['danger_dark']}; }}
QPushButton#emergencyBtn {{
    background-color: {t['warning']};
    color: {t['text']};
    font-weight: bold;
}}
QPushButton#emergencyBtn:hover {{ background-color: {t['warning_dark']}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {t['input_bg']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 10px 12px;
    color: {t['text']};
    selection-background-color: {t['selection_bg']};
    font-size: {fs['widget']}px;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid {t['accent_hover']};
}}
{_focus_block(focus_inputs, t['focus_ring'])}
QComboBox::drop-down {{
    border: none;
    padding-right: 12px;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    selection-background-color: {t['selection_bg']};
    padding: 4px;
}}
QTableWidget {{
    background-color: {t['surface']};
    alternate-background-color: {t['bg']};
    gridline-color: {t['border_soft']};
    border: 1px solid {t['border_soft']};
    border-radius: 10px;
    color: {t['text']};
    selection-background-color: rgba(13, 110, 253, 0.15);
    font-size: {fs['widget']}px;
}}
QTableWidget::item {{
    padding: 10px 8px;
    border-bottom: 1px solid {t['surface_2']};
}}
QTableWidget::item:hover {{ background-color: rgba(13, 110, 253, 0.08); }}
QTableWidget::item:selected {{
    background-color: rgba(13, 110, 253, 0.2);
    color: {t['text']};
}}
QHeaderView::section {{
    background-color: {t['surface_2']};
    color: {t['accent']};
    padding: 12px 10px;
    border: none;
    border-bottom: 2px solid {t['accent_solid']};
    font-weight: bold;
    font-size: {fs['header']}px;
}}
QTextEdit {{
    background-color: {t['log_bg']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    color: {t['log_fg']};
    font-family: {t['mono_family']};
    font-size: {fs['log']}px;
    padding: 12px;
    selection-background-color: rgba(13, 110, 253, 0.3);
}}
QLabel {{
    color: {t['text_muted']};
    font-size: {fs['widget']}px;
}}
QLabel#statusConnected {{
    color: {t['success']};
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(25, 135, 84, 0.1);
    border: 1px solid rgba(25, 135, 84, 0.3);
}}
QLabel#statusDisconnected {{
    color: {t['danger']};
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(220, 53, 69, 0.1);
    border: 1px solid rgba(220, 53, 69, 0.3);
}}
QLabel#statusPending {{
    color: {t['pending']};
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(253, 126, 20, 0.1);
    border: 1px solid rgba(253, 126, 20, 0.3);
}}
QCheckBox {{
    color: {t['text']};
    spacing: 10px;
    font-size: {fs['widget']}px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid {t['border']};
    background-color: {t['surface']};
}}
QCheckBox::indicator:hover {{
    border-color: {t['accent_solid']};
    background-color: rgba(13, 110, 253, 0.05);
}}
QCheckBox::indicator:checked {{
    background-color: {t['accent_solid']};
    border-color: {t['accent_solid']};
}}
QStatusBar {{
    background-color: {t['surface_2']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border_soft']};
    padding: 8px 16px;
    font-size: {fs['small']}px;
}}
QTabWidget::pane {{
    border: 1px solid {t['border_soft']};
    border-radius: 10px;
    background-color: {t['surface']};
    top: -1px;
    padding: 8px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {t['text_muted']};
    padding: 12px 22px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border: 1px solid transparent;
    font-weight: 500;
    font-size: {fs['widget']}px;
}}
QTabBar::tab:hover {{
    background-color: {t['bg']};
    color: {t['text']};
}}
QTabBar::tab:selected {{
    background-color: {t['surface']};
    color: {t['accent']};
    border: 1px solid {t['border_soft']};
    border-bottom: 3px solid {t['accent_solid']};
    font-weight: bold;
}}
QTabBar::tab:focus {{ border: 2px solid {t['focus_ring']}; }}
QMenuBar {{
    background-color: {t['surface']};
    color: {t['text']};
    padding: 6px 8px;
    border-bottom: 1px solid {t['border_soft']};
    font-size: {fs['widget']}px;
}}
QMenuBar::item {{
    padding: 8px 14px;
    border-radius: 8px;
}}
QMenuBar::item:selected {{ background-color: rgba(13, 110, 253, 0.1); }}
QMenuBar::item:focus {{ border: 2px solid {t['focus_ring']}; }}
QMenu {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border_soft']};
    border-radius: 10px;
    padding: 8px;
}}
QMenu::item {{
    padding: 10px 28px 10px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}}
QMenu::item:selected {{
    background-color: {t['accent_solid']};
    color: {t['on_accent']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {t['border_soft']};
    margin: 8px 12px;
}}
QScrollBar:vertical {{
    background-color: {t['bg']};
    width: 10px;
    border-radius: 5px;
    margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background-color: {t['border']};
    border-radius: 5px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {t['text_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QSplitter::handle {{
    background-color: {t['border_soft']};
    height: 6px;
    border-radius: 3px;
    margin: 2px 40px;
}}
QSplitter::handle:hover {{ background-color: {t['accent_solid']}; }}
QToolTip {{
    background-color: {t['log_bg']};
    color: {t['bg']};
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: {fs['small']}px;
}}
QProgressBar {{
    background-color: {t['surface_2']};
    border-radius: 8px;
    height: 10px;
    text-align: center;
    font-size: 10px;
    color: {t['text']};
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['accent_solid']}, stop:0.5 {t['log_fg']}, stop:1 {t['success']});
    border-radius: 8px;
}}
QListWidget {{
    background-color: {t['surface']};
    border: 1px solid {t['border_soft']};
    border-radius: 10px;
    padding: 8px;
    color: {t['text']};
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 0;
}}
QListWidget::item:hover {{ background-color: rgba(13, 110, 253, 0.08); }}
QListWidget::item:selected {{
    background-color: rgba(13, 110, 253, 0.15);
    color: {t['text']};
}}
QDialog {{
    background-color: {t['bg']};
    border: 1px solid {t['border_soft']};
    border-radius: 16px;
}}
QMessageBox {{ background-color: {t['surface']}; }}
QMessageBox QLabel {{
    color: {t['text']};
    font-size: {fs['widget']}px;
}}
QMessageBox QPushButton {{
    min-width: 80px;
    padding: 10px 20px;
}}
"""


# Legacy single-scale stylesheets (import compat; scale 1.0).
DARK_STYLESHEET = build_stylesheet("dark", 1.0)
LIGHT_STYLESHEET = build_stylesheet("light", 1.0)


# (widget attr, accessible name, accessible description)
ACCESSIBLE_CONTROLS: tuple = (
    ("btn_connect", "API 연결 버튼", "키움 REST API에 연결하거나 해제합니다"),
    ("btn_start", "자동매매 시작 버튼", "선택된 설정으로 자동매매를 시작합니다"),
    ("btn_stop", "자동매매 중지 버튼", "실행 중인 자동매매를 중지합니다"),
    ("btn_emergency", "긴급 청산 버튼", "보유 종목 전체를 즉시 시장가 청산합니다"),
    ("combo_acc", "계좌 선택", "매매에 사용할 계좌번호를 선택합니다"),
    ("input_codes", "종목코드 입력", "매매 대상 종목코드를 쉼표로 구분해 입력합니다"),
    ("btn_search", "종목 검색 버튼", "종목 검색 대화상자를 엽니다"),
    ("btn_manual_order", "수동 주문 버튼", "수동 주문 대화상자를 엽니다"),
    ("combo_strategy_pack", "전략팩 선택", "자동매매에 사용할 전략을 선택합니다"),
    ("btn_backtest", "백테스트 실행 버튼", "선택한 구간으로 백테스트를 실행합니다"),
)


def current_settings(host) -> tuple:
    """Return (theme, font_scale) from a duck-typed host."""
    theme = getattr(host, "current_theme", "dark")
    if theme not in TOKENS:
        theme = "dark"
    try:
        from config import Config as _Config  # local import: avoid cycle

        default = getattr(_Config, "DEFAULT_UI_FONT_SCALE", DEFAULT_FONT_SCALE)
    except Exception:
        default = DEFAULT_FONT_SCALE
    scale = clamp_font_scale(getattr(host, "ui_font_scale", default))
    return theme, scale


def apply_theme(host, theme=None, font_scale=None) -> str:
    """Apply a tokenized stylesheet to *host*; return the theme name."""
    if theme is None:
        theme, _ = current_settings(host)
    if theme not in TOKENS:
        theme = "dark"
    if font_scale is None:
        _, font_scale = current_settings(host)
    scale = clamp_font_scale(font_scale)
    host.current_theme = theme
    host.ui_font_scale = scale
    setter = getattr(host, "setStyleSheet", None)
    if callable(setter):
        setter(build_stylesheet(theme, scale))
    return theme


def set_ui_font_scale(host, scale) -> float:
    """Set font scale on *host* and re-apply the current theme."""
    clamped = clamp_font_scale(scale)
    theme = getattr(host, "current_theme", "dark")
    apply_theme(host, theme, clamped)
    return clamped


def apply_accessibility_names(host) -> int:
    """Set screen-reader names on key controls; return count applied."""
    applied = 0
    for attr, name, desc in ACCESSIBLE_CONTROLS:
        widget = getattr(host, attr, None)
        if widget is None:
            continue
        set_name = getattr(widget, "setAccessibleName", None)
        if callable(set_name):
            try:
                set_name(name)
            except Exception:
                continue
        set_desc = getattr(widget, "setAccessibleDescription", None)
        if callable(set_desc):
            try:
                set_desc(desc)
            except Exception:
                pass
        applied += 1
    return applied

