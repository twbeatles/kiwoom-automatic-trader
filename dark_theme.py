"""Dark theme stylesheet for Kiwoom Pro Algo-Trader."""

DARK_STYLESHEET = """
/* ============================================
   Kiwoom Pro Algo-Trader v4.4 Premium Theme
   Ultra-Modern UI/UX Edition
   ============================================ */

/* === CSS 변수 (개념적 적용) === */
/* Main Bg: #121212 (Material Dark) */
/* Surface: #1E1E1E */
/* Primary: #BB86FC (Soft Violet) -> Modified to #58A6FF for financial trust */
/* Success: #00C853 (Vibrant Green) */
/* Error: #FF5252 (Vibrant Red) */

/* === 기본 위젯 설청 === */
QMainWindow, QWidget {
    background-color: #0d1117; /* GitHub Dark Dimmed Base */
    color: #c9d1d9; /* GitHub Dark Text */
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 14px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

/* === 그룹박스 (컨테이너) === */
QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    margin-top: 24px;
    padding: 24px 16px 16px 16px;
    font-weight: 600;
    color: #58a6ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 4px 12px;
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #58a6ff;
}

/* === Dashboard Card Special === */
QGroupBox#dashboardCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #161b22, stop:1 #0d1117);
    border: 1px solid rgba(88, 166, 255, 0.3);
    border-radius: 16px;
}

/* === QPushButton (Modern & Flat) === */
QPushButton {
    background-color: #21262d;
    border: 1px solid rgba(240, 246, 252, 0.1);
    border-radius: 8px;
    color: #c9d1d9;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
}
QPushButton:pressed {
    background-color: #161b22;
    border-color: #58a6ff;
}
QPushButton:disabled {
    background-color: rgba(33, 38, 45, 0.5);
    color: #484f58;
    border: none;
}

/* Primary Button (Blue) */
QPushButton#connectBtn {
    background-color: #1f6feb;
    color: #ffffff;
    border: none;
    font-size: 14px;
    padding: 12px 24px;
}
QPushButton#connectBtn:hover {
    background-color: #388bfd;
}
QPushButton#connectBtn:pressed {
    background-color: #1158c7;
}

/* Danger/Action Button (Red) */
QPushButton#startBtn {
    background-color: #da3633;
    color: white;
    font-size: 15px;
    padding: 12px 30px;
    border-radius: 10px;
}
QPushButton#startBtn:hover {
    background-color: #f85149;
    box-shadow: 0 0 10px rgba(248, 81, 73, 0.4);
}
QPushButton#startBtn:pressed {
    background-color: #b62324;
}

/* === Input Fields === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #010409;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    color: #c9d1d9;
    font-size: 13px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #58a6ff;
    background-color: #0d1117;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #8b949e;
    margin-right: 8px;
}

/* === Table Widget (Data Grid) === */
QTableWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    gridline-color: #21262d;
    outline: none;
}
QTableWidget::item {
    padding: 12px 8px;
    border-bottom: 1px solid #21262d;
}
QTableWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.15);
    color: #58a6ff;
}
QHeaderView::section {
    background-color: #161b22;
    padding: 12px;
    border: none;
    border-bottom: 2px solid #30363d;
    color: #8b949e;
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
}

/* === ScrollBar (Minimalist) === */
QScrollBar:vertical {
    border: none;
    background: #0d1117;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #30363d;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #58a6ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* === Tab Widget === */
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 8px;
    background: #0d1117;
    top: -1px;
}
QTabBar::tab {
    background: #0d1117;
    border: 1px solid transparent;
    color: #8b949e;
    padding: 10px 20px;
    font-weight: 600;
}
QTabBar::tab:selected {
    color: #58a6ff;
    border-bottom: 2px solid #58a6ff;
}
QTabBar::tab:hover {
    color: #c9d1d9;
    background-color: #161b22;
}

/* === Status Labels === */
QLabel#statusConnected {
    color: #3fb950;
    background-color: rgba(63, 185, 80, 0.1);
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid rgba(63, 185, 80, 0.2);
}
QLabel#statusDisconnected {
    color: #f85149;
    background-color: rgba(248, 81, 73, 0.1);
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid rgba(248, 81, 73, 0.2);
}

/* === Profit/Loss Colors === */
.profit { color: #3fb950; }
.loss { color: #f85149; }

/* === Log Area === */
QTextEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    font-family: 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.5;
}
"""


