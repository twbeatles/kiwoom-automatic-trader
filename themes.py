"""
Theme Manager for Kiwoom Pro Algo-Trader
다크/라이트 테마 스타일시트 관리
"""

# ============================================================================
# 다크 테마 (기본)
# ============================================================================
DARK_THEME = """
/* ============================================
   Kiwoom Pro Algo-Trader Dark Theme
   ============================================ */

/* === 기본 위젯 === */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* === 그룹박스 === */
QGroupBox {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(22, 27, 34, 0.95), stop:1 rgba(13, 17, 23, 0.98));
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 16px;
    margin-top: 20px;
    padding: 24px 18px 18px 18px;
    font-weight: bold;
    color: #58a6ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 24px;
    padding: 4px 14px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #161b22, stop:1 #0d1117);
    border: 1px solid #30363d;
    border-radius: 8px;
    font-size: 14px;
}

/* === 대시보드 카드 === */
QGroupBox#dashboardCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(22, 27, 34, 0.9), stop:0.5 rgba(18, 22, 28, 0.95), stop:1 rgba(13, 17, 23, 0.98));
    border: 1px solid rgba(88, 166, 255, 0.2);
    border-radius: 20px;
    padding: 20px;
}

/* === 버튼 === */
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #238636, stop:0.5 #1f7a31, stop:1 #1a7f37);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 12px 28px;
    font-weight: bold;
    font-size: 13px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2ea043, stop:0.5 #27903b, stop:1 #238636);
    border: 1px solid rgba(46, 160, 67, 0.5);
}
QPushButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a7f37, stop:1 #166c2e);
}
QPushButton:disabled {
    background-color: #21262d;
    color: #484f58;
    border: 1px solid #30363d;
}

QPushButton#connectBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #58a6ff, stop:0.5 #4393e6, stop:1 #1f6feb);
    border-radius: 12px;
    padding: 14px 32px;
    font-size: 14px;
}
QPushButton#connectBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #79b8ff, stop:0.5 #58a6ff, stop:1 #388bfd);
    border: 1px solid rgba(121, 184, 255, 0.4);
}

QPushButton#startBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f85149, stop:0.3 #e5443c, stop:1 #da3633);
    font-size: 16px;
    padding: 14px 36px;
    border-radius: 14px;
}
QPushButton#startBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ff6b6b, stop:0.5 #f85149, stop:1 #e5443c);
}
QPushButton#startBtn:disabled {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #30363d, stop:1 #21262d);
    color: #484f58;
}

/* === 입력 필드 === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: rgba(22, 27, 34, 0.95);
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px 14px;
    color: #e6edf3;
    selection-background-color: #58a6ff;
    font-size: 13px;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #484f58;
    background-color: rgba(22, 27, 34, 1);
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #58a6ff;
    background-color: rgba(22, 27, 34, 1);
    padding: 11px 13px;
}

/* === 테이블 === */
QTableWidget {
    background-color: #0d1117;
    alternate-background-color: rgba(22, 27, 34, 0.6);
    gridline-color: rgba(33, 38, 45, 0.5);
    border: 1px solid #30363d;
    border-radius: 12px;
    color: #e6edf3;
    selection-background-color: rgba(88, 166, 255, 0.25);
    font-size: 13px;
}
QTableWidget::item {
    padding: 10px 8px;
    border-bottom: 1px solid rgba(33, 38, 45, 0.3);
}
QTableWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.15);
}
QTableWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.3);
    color: #ffffff;
}
QHeaderView::section {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #21262d, stop:0.5 #1c2128, stop:1 #161b22);
    color: #58a6ff;
    padding: 14px 12px;
    border: none;
    border-bottom: 2px solid #58a6ff;
    font-weight: bold;
    font-size: 12px;
}

/* === 로그 영역 === */
QTextEdit {
    background-color: #010409;
    border: 1px solid #21262d;
    border-radius: 12px;
    color: #7ee787;
    font-family: 'Cascadia Code', 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    padding: 14px;
}

/* === 라벨 === */
QLabel {
    color: #8b949e;
    font-size: 13px;
}

/* === 체크박스 === */
QCheckBox {
    color: #e6edf3;
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
QCheckBox::indicator:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #238636, stop:1 #2ea043);
    border-color: #238636;
}

/* === 탭 위젯 === */
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 12px;
    background-color: #0d1117;
    top: -1px;
    padding: 8px;
}
QTabBar::tab {
    background-color: transparent;
    color: #8b949e;
    padding: 14px 24px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border: 1px solid transparent;
    font-weight: 500;
    font-size: 13px;
}
QTabBar::tab:hover {
    background-color: rgba(33, 38, 45, 0.8);
    color: #e6edf3;
}
QTabBar::tab:selected {
    background-color: #0d1117;
    color: #58a6ff;
    border: 1px solid #30363d;
    border-bottom: 3px solid #58a6ff;
    font-weight: bold;
}

/* === 메뉴바 === */
QMenuBar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c2128, stop:1 #161b22);
    color: #e6edf3;
    padding: 6px 8px;
    border-bottom: 1px solid #30363d;
}
QMenuBar::item {
    padding: 8px 14px;
    border-radius: 8px;
}
QMenuBar::item:selected {
    background-color: rgba(88, 166, 255, 0.2);
}
QMenu {
    background-color: #161b22;
    color: #e6edf3;
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
    background-color: #58a6ff;
    color: #ffffff;
}

/* === 스크롤바 === */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: rgba(48, 54, 61, 0.8);
    border-radius: 5px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background-color: rgba(88, 166, 255, 0.5);
}

/* === 스플리터 === */
QSplitter::handle {
    background-color: #21262d;
    border-radius: 4px;
}
QSplitter::handle:vertical {
    height: 8px;
    min-height: 8px;
    margin: 0px 20px;
}
QSplitter::handle:hover {
    background-color: #58a6ff;
}

/* === 상태바 === */
QStatusBar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #161b22, stop:1 #0d1117);
    color: #8b949e;
    border-top: 1px solid #30363d;
    padding: 8px 16px;
}

/* === 프로그레스바 === */
QProgressBar {
    background-color: #21262d;
    border-radius: 8px;
    height: 10px;
    text-align: center;
    color: #e6edf3;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #238636, stop:0.5 #3fb950, stop:1 #58a6ff);
    border-radius: 8px;
}

/* === 툴팁 === */
QToolTip {
    background-color: #1c2128;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 14px;
}
"""


# ============================================================================
# 라이트 테마
# ============================================================================
LIGHT_THEME = """
/* ============================================
   Kiwoom Pro Algo-Trader Light Theme
   ============================================ */

/* === 기본 위젯 === */
QMainWindow, QWidget {
    background-color: #f6f8fa;
    color: #24292f;
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* === 그룹박스 === */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 16px;
    margin-top: 20px;
    padding: 24px 18px 18px 18px;
    font-weight: bold;
    color: #0969da;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 24px;
    padding: 4px 14px;
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    font-size: 14px;
}

/* === 대시보드 카드 === */
QGroupBox#dashboardCard {
    background: #ffffff;
    border: 1px solid rgba(9, 105, 218, 0.2);
    border-radius: 20px;
    padding: 20px;
}

/* === 버튼 === */
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2da44e, stop:1 #238636);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 12px 28px;
    font-weight: bold;
    font-size: 13px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3fb950, stop:1 #2da44e);
}
QPushButton:disabled {
    background-color: #eaeef2;
    color: #8c959f;
    border: 1px solid #d0d7de;
}

QPushButton#connectBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0969da, stop:1 #0550ae);
    border-radius: 12px;
    padding: 14px 32px;
    font-size: 14px;
}
QPushButton#connectBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #218bff, stop:1 #0969da);
}

QPushButton#startBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #cf222e, stop:1 #a40e26);
    font-size: 16px;
    padding: 14px 36px;
    border-radius: 14px;
}
QPushButton#startBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fa4549, stop:1 #cf222e);
}

/* === 입력 필드 === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 10px;
    padding: 12px 14px;
    color: #24292f;
    selection-background-color: #0969da;
    font-size: 13px;
}
QLineEdit:hover, QComboBox:hover {
    border: 1px solid #8c959f;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #0969da;
    padding: 11px 13px;
}

/* === 테이블 === */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f6f8fa;
    gridline-color: #d0d7de;
    border: 1px solid #d0d7de;
    border-radius: 12px;
    color: #24292f;
    selection-background-color: rgba(9, 105, 218, 0.15);
    font-size: 13px;
}
QTableWidget::item {
    padding: 10px 8px;
    border-bottom: 1px solid #eaeef2;
}
QTableWidget::item:hover {
    background-color: rgba(9, 105, 218, 0.1);
}
QTableWidget::item:selected {
    background-color: rgba(9, 105, 218, 0.2);
    color: #24292f;
}
QHeaderView::section {
    background-color: #f6f8fa;
    color: #0969da;
    padding: 14px 12px;
    border: none;
    border-bottom: 2px solid #0969da;
    font-weight: bold;
    font-size: 12px;
}

/* === 로그 영역 === */
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 12px;
    color: #1a7f37;
    font-family: 'Cascadia Code', 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    padding: 14px;
}

/* === 라벨 === */
QLabel {
    color: #57606a;
    font-size: 13px;
}

/* === 체크박스 === */
QCheckBox {
    color: #24292f;
    spacing: 10px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid #d0d7de;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #2da44e;
    border-color: #2da44e;
}

/* === 탭 위젯 === */
QTabWidget::pane {
    border: 1px solid #d0d7de;
    border-radius: 12px;
    background-color: #ffffff;
    top: -1px;
    padding: 8px;
}
QTabBar::tab {
    background-color: transparent;
    color: #57606a;
    padding: 14px 24px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 500;
    font-size: 13px;
}
QTabBar::tab:hover {
    background-color: #f6f8fa;
    color: #24292f;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0969da;
    border: 1px solid #d0d7de;
    border-bottom: 3px solid #0969da;
    font-weight: bold;
}

/* === 메뉴바 === */
QMenuBar {
    background-color: #f6f8fa;
    color: #24292f;
    padding: 6px 8px;
    border-bottom: 1px solid #d0d7de;
}
QMenuBar::item {
    padding: 8px 14px;
    border-radius: 8px;
}
QMenuBar::item:selected {
    background-color: rgba(9, 105, 218, 0.1);
}
QMenu {
    background-color: #ffffff;
    color: #24292f;
    border: 1px solid #d0d7de;
    border-radius: 10px;
    padding: 8px;
}
QMenu::item {
    padding: 10px 28px 10px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}
QMenu::item:selected {
    background-color: #0969da;
    color: #ffffff;
}

/* === 스크롤바 === */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: rgba(140, 149, 159, 0.5);
    border-radius: 5px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background-color: rgba(9, 105, 218, 0.5);
}

/* === 스플리터 === */
QSplitter::handle {
    background-color: #d0d7de;
    border-radius: 4px;
}
QSplitter::handle:vertical {
    height: 8px;
    min-height: 8px;
    margin: 0px 20px;
}
QSplitter::handle:hover {
    background-color: #0969da;
}

/* === 상태바 === */
QStatusBar {
    background-color: #f6f8fa;
    color: #57606a;
    border-top: 1px solid #d0d7de;
    padding: 8px 16px;
}

/* === 프로그레스바 === */
QProgressBar {
    background-color: #eaeef2;
    border-radius: 8px;
    height: 10px;
    text-align: center;
    color: #24292f;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2da44e, stop:0.5 #3fb950, stop:1 #0969da);
    border-radius: 8px;
}

/* === 툴팁 === */
QToolTip {
    background-color: #ffffff;
    color: #24292f;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 10px 14px;
}
"""


def get_theme(name: str) -> str:
    """
    테마 스타일시트 반환
    
    Args:
        name: 'dark' 또는 'light'
    
    Returns:
        CSS 스타일시트 문자열
    """
    return DARK_THEME if name.lower() == 'dark' else LIGHT_THEME


def get_available_themes() -> list:
    """사용 가능한 테마 목록"""
    return ['dark', 'light']
