"""
Light Theme for Kiwoom Pro Algo-Trader
라이트 테마 스타일시트
"""

LIGHT_STYLESHEET = """
/* ============================================
   Kiwoom Pro Algo-Trader v4.3 Light Theme
   Modern, Clean, Professional
   ============================================ */

/* === 기본 위젯 === */
QMainWindow, QWidget {
    background-color: #f8f9fa;
    color: #212529;
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* === 그룹박스 (클린 카드 스타일) === */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 12px;
    margin-top: 20px;
    padding: 24px 18px 18px 18px;
    font-weight: bold;
    color: #0d6efd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 24px;
    padding: 4px 14px;
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    font-size: 14px;
}

/* === 대시보드 카드 === */
QGroupBox#dashboardCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffffff, stop:1 #f8f9fa);
    border: 1px solid rgba(13, 110, 253, 0.2);
    border-radius: 16px;
    padding: 20px;
}

/* === 버튼 === */
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #198754, stop:1 #157347);
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
        stop:0 #20c997, stop:1 #198754);
}
QPushButton:pressed {
    background-color: #146c43;
}
QPushButton:disabled {
    background-color: #e9ecef;
    color: #6c757d;
}

/* 연결 버튼 (파란색) */
QPushButton#connectBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d6efd, stop:1 #0b5ed7);
    border-radius: 12px;
    padding: 14px 32px;
    font-size: 14px;
}
QPushButton#connectBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3d8bfd, stop:1 #0d6efd);
}

/* 시작 버튼 (빨간색/주황색) */
QPushButton#startBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #dc3545, stop:1 #bb2d3b);
    font-size: 16px;
    padding: 14px 36px;
    border-radius: 14px;
}
QPushButton#startBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f8d7da, stop:0.1 #dc3545, stop:1 #bb2d3b);
}

/* 긴급 청산 버튼 */
QPushButton#emergencyBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffc107, stop:1 #ffb300);
    color: #212529;
    font-weight: bold;
}
QPushButton#emergencyBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffda6a, stop:1 #ffc107);
}

/* === 입력 필드 === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 8px;
    padding: 10px 12px;
    color: #212529;
    selection-background-color: #0d6efd;
    font-size: 13px;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #86b7fe;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #0d6efd;
    padding: 9px 11px;
}
QComboBox::drop-down {
    border: none;
    padding-right: 12px;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #ced4da;
    border-radius: 8px;
    selection-background-color: #0d6efd;
    padding: 4px;
}

/* === 테이블 === */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    gridline-color: #dee2e6;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    color: #212529;
    selection-background-color: rgba(13, 110, 253, 0.15);
    font-size: 13px;
}
QTableWidget::item {
    padding: 10px 8px;
    border-bottom: 1px solid #e9ecef;
}
QTableWidget::item:hover {
    background-color: rgba(13, 110, 253, 0.08);
}
QTableWidget::item:selected {
    background-color: rgba(13, 110, 253, 0.2);
    color: #212529;
}
QHeaderView::section {
    background-color: #e9ecef;
    color: #0d6efd;
    padding: 12px 10px;
    border: none;
    border-bottom: 2px solid #0d6efd;
    font-weight: bold;
    font-size: 12px;
}

/* === 로그 영역 (터미널 스타일) === */
QTextEdit {
    background-color: #212529;
    border: 1px solid #343a40;
    border-radius: 10px;
    color: #20c997;
    font-family: 'Cascadia Code', 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    padding: 12px;
    selection-background-color: rgba(13, 110, 253, 0.3);
}

/* === 라벨 === */
QLabel {
    color: #495057;
    font-size: 13px;
}

/* 상태 라벨 스타일 */
QLabel#statusConnected {
    color: #198754;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(25, 135, 84, 0.1);
    border: 1px solid rgba(25, 135, 84, 0.3);
}
QLabel#statusDisconnected {
    color: #dc3545;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(220, 53, 69, 0.1);
    border: 1px solid rgba(220, 53, 69, 0.3);
}
QLabel#statusPending {
    color: #fd7e14;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(253, 126, 20, 0.1);
    border: 1px solid rgba(253, 126, 20, 0.3);
}

/* === 체크박스 === */
QCheckBox {
    color: #212529;
    spacing: 10px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid #ced4da;
    background-color: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #0d6efd;
    background-color: rgba(13, 110, 253, 0.05);
}
QCheckBox::indicator:checked {
    background-color: #0d6efd;
    border-color: #0d6efd;
}

/* === 상태바 === */
QStatusBar {
    background-color: #e9ecef;
    color: #495057;
    border-top: 1px solid #dee2e6;
    padding: 8px 16px;
    font-size: 12px;
}

/* === 탭 위젯 === */
QTabWidget::pane {
    border: 1px solid #dee2e6;
    border-radius: 10px;
    background-color: #ffffff;
    top: -1px;
    padding: 8px;
}
QTabBar::tab {
    background-color: transparent;
    color: #6c757d;
    padding: 12px 22px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border: 1px solid transparent;
    font-weight: 500;
    font-size: 13px;
}
QTabBar::tab:hover {
    background-color: #f8f9fa;
    color: #212529;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0d6efd;
    border: 1px solid #dee2e6;
    border-bottom: 3px solid #0d6efd;
    font-weight: bold;
}

/* === 메뉴 === */
QMenuBar {
    background-color: #ffffff;
    color: #212529;
    padding: 6px 8px;
    border-bottom: 1px solid #dee2e6;
    font-size: 13px;
}
QMenuBar::item {
    padding: 8px 14px;
    border-radius: 8px;
}
QMenuBar::item:selected {
    background-color: rgba(13, 110, 253, 0.1);
}
QMenu {
    background-color: #ffffff;
    color: #212529;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 8px;
}
QMenu::item {
    padding: 10px 28px 10px 16px;
    border-radius: 6px;
    margin: 2px 4px;
}
QMenu::item:selected {
    background-color: #0d6efd;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #dee2e6;
    margin: 8px 12px;
}

/* === 스크롤바 === */
QScrollBar:vertical {
    background-color: #f8f9fa;
    width: 10px;
    border-radius: 5px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background-color: #ced4da;
    border-radius: 5px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background-color: #adb5bd;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* === 스플리터 === */
QSplitter::handle {
    background-color: #dee2e6;
    height: 6px;
    border-radius: 3px;
    margin: 2px 40px;
}
QSplitter::handle:hover {
    background-color: #0d6efd;
}

/* === 툴팁 === */
QToolTip {
    background-color: #212529;
    color: #f8f9fa;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
}

/* === 프로그레스바 === */
QProgressBar {
    background-color: #e9ecef;
    border-radius: 8px;
    height: 10px;
    text-align: center;
    font-size: 10px;
    color: #212529;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0d6efd, stop:0.5 #20c997, stop:1 #198754);
    border-radius: 8px;
}

/* === 리스트 위젯 === */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 8px;
    color: #212529;
}
QListWidget::item {
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 0;
}
QListWidget::item:hover {
    background-color: rgba(13, 110, 253, 0.08);
}
QListWidget::item:selected {
    background-color: rgba(13, 110, 253, 0.15);
    color: #212529;
}

/* === 다이얼로그 === */
QDialog {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 16px;
}

/* === 메시지 박스 === */
QMessageBox {
    background-color: #ffffff;
}
QMessageBox QLabel {
    color: #212529;
    font-size: 13px;
}
QMessageBox QPushButton {
    min-width: 80px;
    padding: 10px 20px;
}
"""

