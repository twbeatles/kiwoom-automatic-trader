"""Dark theme stylesheet for Kiwoom Pro Algo-Trader."""

DARK_STYLESHEET = """
/* ============================================
   Kiwoom Pro Algo-Trader v4.3 Premium Theme
   Enhanced UI/UX Edition
   ============================================ */

/* === CSS 변수 (개념적) === */
/* 배경: #0d1117, #161b22, #21262d */
/* 수익: #26a641, #3fb950 (그라디언트) */
/* 손실: #f85149, #da3633 (그라디언트) */
/* 강조: #58a6ff, #79b8ff */
/* 경고: #d29922, #e3b341 */

/* === 기본 위젯 === */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* === 그룹박스 (글래스모피즘 카드 스타일) === */
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

/* === 대시보드 카드 (특별 스타일) === */
QGroupBox#dashboardCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(22, 27, 34, 0.9), stop:0.5 rgba(18, 22, 28, 0.95), stop:1 rgba(13, 17, 23, 0.98));
    border: 1px solid rgba(88, 166, 255, 0.2);
    border-radius: 20px;
    padding: 20px;
}

/* === 버튼 (프리미엄 호버 효과) === */
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
    padding-top: 13px;
    padding-bottom: 11px;
}
QPushButton:disabled {
    background-color: #21262d;
    color: #484f58;
    border: 1px solid #30363d;
}

/* 연결 버튼 (파란색 - 프리미엄) */
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

/* 시작 버튼 (빨간색/주황색 - 임팩트) */
QPushButton#startBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f85149, stop:0.3 #e5443c, stop:1 #da3633);
    font-size: 16px;
    padding: 14px 36px;
    border-radius: 14px;
    letter-spacing: 1px;
}
QPushButton#startBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ff6b6b, stop:0.5 #f85149, stop:1 #e5443c);
    border: 1px solid rgba(255, 107, 107, 0.4);
}
QPushButton#startBtn:disabled {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #30363d, stop:1 #21262d);
    color: #484f58;
}

/* === 입력 필드 (글로우 포커스 효과) === */
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
QComboBox::drop-down {
    border: none;
    padding-right: 12px;
    width: 20px;
}
QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    selection-background-color: #58a6ff;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 8px 12px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: rgba(88, 166, 255, 0.2);
}

/* === 테이블 (프리미엄 데이터 그리드) === */
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
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QHeaderView::section:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #30363d, stop:1 #21262d);
}

/* === 로그 영역 (터미널 스타일) === */
QTextEdit {
    background-color: #010409;
    border: 1px solid #21262d;
    border-radius: 12px;
    color: #7ee787;
    font-family: 'Cascadia Code', 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    padding: 14px;
    line-height: 1.6;
    selection-background-color: rgba(88, 166, 255, 0.3);
}
QTextEdit:focus {
    border: 1px solid #30363d;
}

/* === 라벨 === */
QLabel {
    color: #8b949e;
    font-size: 13px;
}
QLabel[important="true"] {
    color: #e6edf3;
    font-weight: bold;
}

/* 상태 라벨 스타일 */
QLabel#statusConnected {
    color: #3fb950;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(63, 185, 80, 0.15);
    border: 1px solid rgba(63, 185, 80, 0.3);
}
QLabel#statusDisconnected {
    color: #f85149;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(248, 81, 73, 0.15);
    border: 1px solid rgba(248, 81, 73, 0.3);
}
QLabel#statusPending {
    color: #d29922;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(210, 153, 34, 0.15);
    border: 1px solid rgba(210, 153, 34, 0.3);
}

/* 수익/손실 라벨 */
QLabel#profitLabel {
    font-size: 15px;
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 10px;
}

/* === 체크박스 (커스텀 토글) === */
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
QCheckBox::indicator:hover {
    border-color: #58a6ff;
    background-color: rgba(88, 166, 255, 0.1);
}
QCheckBox::indicator:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #238636, stop:1 #2ea043);
    border-color: #238636;
}
QCheckBox::indicator:checked:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2ea043, stop:1 #3fb950);
}

/* === 상태바 (프리미엄) === */
QStatusBar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #161b22, stop:1 #0d1117);
    color: #8b949e;
    border-top: 1px solid #30363d;
    padding: 8px 16px;
    font-size: 12px;
}
QStatusBar::item {
    border: none;
}
QStatusBar QLabel {
    padding: 4px 8px;
}

/* === 탭 위젯 (프리미엄 네비게이션) === */
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
    border-bottom: none;
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

/* === 메뉴 (프리미엄) === */
QMenuBar {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c2128, stop:1 #161b22);
    color: #e6edf3;
    padding: 6px 8px;
    border-bottom: 1px solid #30363d;
    font-size: 13px;
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
QMenu::separator {
    height: 1px;
    background-color: #30363d;
    margin: 8px 12px;
}
QMenu::icon {
    padding-left: 8px;
}

/* === 스크롤바 (슬림 모던) === */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border-radius: 5px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background-color: rgba(48, 54, 61, 0.8);
    border-radius: 5px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background-color: rgba(88, 166, 255, 0.5);
}
QScrollBar::handle:vertical:pressed {
    background-color: #58a6ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
    border-radius: 5px;
    margin: 2px 4px;
}
QScrollBar::handle:horizontal {
    background-color: rgba(48, 54, 61, 0.8);
    border-radius: 5px;
    min-width: 40px;
}
QScrollBar::handle:horizontal:hover {
    background-color: rgba(88, 166, 255, 0.5);
}

/* === 스플리터 (인터랙티브) === */
QSplitter::handle {
    background-color: #21262d;
    height: 6px;
    border-radius: 3px;
    margin: 2px 40px;
}
QSplitter::handle:hover {
    background-color: #58a6ff;
}
QSplitter::handle:pressed {
    background-color: #79b8ff;
}

/* === 툴팁 (프리미엄) === */
QToolTip {
    background-color: #1c2128;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
}

/* === 프로그레스바 (애니메이션) === */
QProgressBar {
    background-color: #21262d;
    border-radius: 8px;
    height: 10px;
    text-align: center;
    font-size: 10px;
    color: #e6edf3;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #238636, stop:0.5 #3fb950, stop:1 #58a6ff);
    border-radius: 8px;
}

/* === 리스트 위젯 === */
QListWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 8px;
    color: #e6edf3;
}
QListWidget::item {
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 0;
}
QListWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.15);
}
QListWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.3);
    color: #ffffff;
}

/* === 다이얼로그 오버레이 === */
QDialog {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 16px;
}

/* === 메시지 박스 === */
QMessageBox {
    background-color: #161b22;
}
QMessageBox QLabel {
    color: #e6edf3;
    font-size: 13px;
}
QMessageBox QPushButton {
    min-width: 80px;
    padding: 10px 20px;
}

/* === 폼 레이아웃 라벨 === */
QFormLayout QLabel {
    color: #8b949e;
    font-weight: 500;
}
"""


