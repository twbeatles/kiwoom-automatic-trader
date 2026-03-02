"""Dark theme stylesheet for Kiwoom Pro Algo-Trader."""

DARK_STYLESHEET = """
/* ============================================
   Kiwoom Pro Algo-Trader v4.5 Premium Theme
   Ultra-Modern UI/UX Edition
   ============================================ */

/* === 기본 위젯 설정 === */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
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
}
QPushButton#startBtn:pressed {
    background-color: #b62324;
}

/* Stop Button */
QPushButton#stopBtn {
    background-color: #30363d;
    border: 1px solid #8b949e;
}
QPushButton#stopBtn:hover {
    background-color: #3b434b;
}

/* Emergency Button */
QPushButton#emergencyBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9a6700, stop:1 #d29922);
    color: white;
    border: none;
    font-weight: bold;
}
QPushButton#emergencyBtn:hover {
    background: #d29922;
}
QPushButton#emergencyBtn:pressed {
    background: #9a6700;
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
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    selection-background-color: #1f6feb;
    padding: 4px;
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
QTableWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.08);
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

/* === CheckBox === */
QCheckBox {
    color: #c9d1d9;
    spacing: 10px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid #30363d;
    background-color: #0d1117;
}
QCheckBox::indicator:hover {
    border-color: #58a6ff;
    background-color: rgba(88, 166, 255, 0.05);
}
QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border-color: #1f6feb;
}

/* === Labels === */
QLabel {
    color: #c9d1d9;
    font-size: 13px;
}

/* === Dashboard Info Cards === */
QLabel#depositCard {
    color: #e6edf3;
    font-weight: bold;
    font-size: 15px;
    padding: 10px 15px;
    border-radius: 8px;
    background: rgba(56, 139, 253, 0.1);
    border: 1px solid rgba(56, 139, 253, 0.2);
}
QLabel#profitCard {
    color: #e6edf3;
    font-weight: bold;
    font-size: 15px;
    padding: 10px 15px;
    border-radius: 8px;
    background: rgba(139, 148, 158, 0.1);
    border: 1px solid rgba(139, 148, 158, 0.2);
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

/* === Splitter === */
QSplitter::handle {
    background-color: #30363d;
    height: 6px;
    border-radius: 3px;
    margin: 2px 40px;
}
QSplitter::handle:hover {
    background-color: #58a6ff;
}

/* === ToolTip === */
QToolTip {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
}

/* === Menu === */
QMenuBar {
    background-color: #0d1117;
    color: #c9d1d9;
    padding: 6px 8px;
    border-bottom: 1px solid #21262d;
    font-size: 13px;
}
QMenuBar::item {
    padding: 8px 14px;
    border-radius: 8px;
}
QMenuBar::item:selected {
    background-color: rgba(88, 166, 255, 0.1);
}
QMenu {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 8px;
}
QMenu::item {
    padding: 10px 28px 10px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}
QMenu::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #21262d;
    margin: 8px 12px;
}

/* === StatusBar === */
QStatusBar {
    background-color: #0d1117;
    color: #8b949e;
    border-top: 1px solid #21262d;
    padding: 8px 16px;
    font-size: 12px;
}

/* === ProgressBar === */
QProgressBar {
    background-color: #21262d;
    border-radius: 8px;
    height: 10px;
    text-align: center;
    font-size: 10px;
    color: #c9d1d9;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1f6feb, stop:0.5 #58a6ff, stop:1 #3fb950);
    border-radius: 8px;
}

/* === ListWidget === */
QListWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 8px;
    color: #c9d1d9;
}
QListWidget::item {
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 0;
}
QListWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.08);
}
QListWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.15);
    color: #c9d1d9;
}

/* === Dialog === */
QDialog {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 16px;
}

/* === MessageBox === */
QMessageBox {
    background-color: #161b22;
}
QMessageBox QLabel {
    color: #c9d1d9;
    font-size: 13px;
}
QMessageBox QPushButton {
    min-width: 80px;
    padding: 10px 20px;
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


