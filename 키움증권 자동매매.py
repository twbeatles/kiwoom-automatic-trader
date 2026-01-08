"""
Kiwoom Pro Algo-Trader v4.0
키움증권 REST API 기반 자동매매 프로그램

v4.0: REST API 마이그레이션 + v3.0 기능 복원
- 변동성 돌파 전략 + 트레일링 스톱
- RSI, MACD, 볼린저밴드, DMI 필터
- 프리셋 관리, 거래 통계/내역, 텔레그램 알림
- 시스템 트레이, 메뉴바, 도움말
"""

import sys
import os
import json
import csv
import datetime
import logging
import threading
import queue
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QColor, QFont, QTextCursor, QIcon, QAction

from config import Config
from strategy_manager import StrategyManager
from api import KiwoomAuth, KiwoomRESTClient, KiwoomWebSocketClient
from api.models import StockQuote, ExecutionData, OrderType, PriceType

# 신규 모듈 (v4.1)
from notification_manager import NotificationManager, NotificationSettings, NotificationType
from risk_manager import RiskManager, RiskSettings
from themes import get_theme, get_available_themes, DARK_THEME
from stock_screener import StockScreener, ScreenerCondition, ConditionType
from backtest_engine import BacktestEngine, BacktestParams, BacktestResult


# ============================================================================
# 다크 테마 스타일시트
# ============================================================================
DARK_STYLESHEET = """
/* ============================================
   Kiwoom Pro Algo-Trader v4.0 Premium Theme
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

/* === 버튼 (프리미엄 호버/클릭 효과 강화) === */
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
    /* 그림자 효과 */
    margin: 2px;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2ea043, stop:0.5 #27903b, stop:1 #238636);
    border: 1px solid rgba(63, 185, 80, 0.6);
    margin: 1px;
}
QPushButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #166c2e, stop:0.5 #1a7f37, stop:1 #166c2e);
    padding-top: 14px;
    padding-bottom: 10px;
    border: 1px solid rgba(63, 185, 80, 0.3);
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

/* === 테이블 (프리미엄 데이터 그리드 강화) === */
QTableWidget {
    background-color: #0d1117;
    alternate-background-color: rgba(22, 27, 34, 0.7);
    gridline-color: rgba(48, 54, 61, 0.4);
    border: 1px solid #30363d;
    border-radius: 12px;
    color: #e6edf3;
    selection-background-color: rgba(88, 166, 255, 0.25);
    font-size: 13px;
    outline: none;
}
QTableWidget::item {
    padding: 12px 10px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.25);
    border-left: 3px solid transparent;
}
QTableWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.12);
    border-left: 3px solid rgba(88, 166, 255, 0.5);
}
QTableWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.25);
    border-left: 3px solid #58a6ff;
    color: #ffffff;
}
QHeaderView::section {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #21262d, stop:0.5 #1c2128, stop:1 #161b22);
    color: #58a6ff;
    padding: 14px 12px;
    border: none;
    border-bottom: 2px solid #58a6ff;
    border-right: 1px solid rgba(48, 54, 61, 0.3);
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QHeaderView::section:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #30363d, stop:1 #21262d);
    color: #79b8ff;
}
QHeaderView::section:first {
    border-top-left-radius: 10px;
}
QHeaderView::section:last {
    border-top-right-radius: 10px;
    border-right: none;
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

/* 상태 라벨 스타일 (개선된 배지) */
QLabel#statusConnected {
    color: #3fb950;
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(63, 185, 80, 0.2), stop:1 rgba(63, 185, 80, 0.1));
    border: 1px solid rgba(63, 185, 80, 0.4);
    min-width: 80px;
}
QLabel#statusDisconnected {
    color: #f85149;
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(248, 81, 73, 0.2), stop:1 rgba(248, 81, 73, 0.1));
    border: 1px solid rgba(248, 81, 73, 0.4);
    min-width: 80px;
}
QLabel#statusPending {
    color: #d29922;
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(210, 153, 34, 0.2), stop:1 rgba(210, 153, 34, 0.1));
    border: 1px solid rgba(210, 153, 34, 0.4);
    min-width: 80px;
}

/* 수익/손실 라벨 (강화) */
QLabel#profitLabel {
    font-size: 16px;
    font-weight: bold;
    padding: 10px 18px;
    border-radius: 12px;
    letter-spacing: 0.3px;
}
QLabel#profitPositive {
    color: #3fb950;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(63, 185, 80, 0.15), stop:1 rgba(38, 166, 65, 0.1));
    border: 1px solid rgba(63, 185, 80, 0.3);
}
QLabel#profitNegative {
    color: #f85149;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(248, 81, 73, 0.15), stop:1 rgba(218, 54, 51, 0.1));
    border: 1px solid rgba(248, 81, 73, 0.3);
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
    border-radius: 4px;
}
QSplitter::handle:vertical {
    height: 8px;
    min-height: 8px;
    margin: 0px 20px;
}
QSplitter::handle:horizontal {
    width: 8px;
    min-width: 8px;
    margin: 20px 0px;
}
QSplitter::handle:hover {
    background-color: #58a6ff;
}
QSplitter::handle:pressed {
    background-color: #79b8ff;
}

/* === 툴팁 (프리미엄 강화) === */
QToolTip {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #21262d, stop:1 #161b22);
    color: #e6edf3;
    border: 1px solid rgba(88, 166, 255, 0.3);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 12px;
    font-weight: 500;
}

/* === 프로그레스바 (강화된 그라디언트) === */
QProgressBar {
    background-color: #21262d;
    border-radius: 10px;
    height: 12px;
    text-align: center;
    font-size: 10px;
    color: #e6edf3;
    border: 1px solid #30363d;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #238636, stop:0.3 #2ea043, stop:0.7 #3fb950, stop:1 #58a6ff);
    border-radius: 9px;
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



# ============================================================================
# 텔레그램 알림 클래스
# ============================================================================
class TelegramNotifier:
    """비동기 텔레그램 알림 클래스"""
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        if self.enabled:
            self._start_worker()
    
    def _start_worker(self):
        """백그라운드 전송 스레드 시작"""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
    
    def _worker(self):
        """메시지 전송 워커"""
        import requests
        while not self._stop:
            try:
                text = self._queue.get(timeout=1)
                if text is None:
                    break
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                requests.post(url, data={'chat_id': self.chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=5)
            except queue.Empty:
                continue
            except requests.RequestException as e:
                logging.getLogger('Telegram').warning(f"전송 실패: {e}")
            except Exception as e:
                logging.getLogger('Telegram').error(f"오류: {e}")
    
    def send(self, text: str):
        """비동기 메시지 전송 (큐에 추가)"""
        if self.enabled:
            self._queue.put(text)
    
    def stop(self):
        """워커 종료"""
        self._stop = True
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)


# ============================================================================
# 프리셋 관리 다이얼로그
# ============================================================================
class PresetDialog(QDialog):
    def __init__(self, parent=None, current_values=None):
        super().__init__(parent)
        self.current_values = current_values or {}
        self.presets = self._load_presets()
        self.selected_preset = None
        self._init_ui()
    
    def _init_ui(self):
        self.setWindowTitle("📋 프리셋 관리")
        self.setFixedSize(600, 500)
        self.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        # 목록
        self.list_widget = QListWidget()
        self._refresh_list()
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(QLabel("저장된 프리셋:"))
        layout.addWidget(self.list_widget)
        
        # 상세정보
        self.detail_label = QLabel("프리셋을 선택하세요")
        self.detail_label.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        
        # 새 프리셋 저장
        save_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("새 프리셋 이름")
        save_layout.addWidget(self.name_input)
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save_preset)
        save_layout.addWidget(btn_save)
        layout.addLayout(save_layout)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_preset)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_apply = QPushButton("✅ 적용")
        btn_apply.clicked.connect(self._apply_preset)
        btn_layout.addWidget(btn_apply)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def _load_presets(self):
        presets = dict(Config.DEFAULT_PRESETS)
        try:
            if os.path.exists(Config.PRESETS_FILE):
                with open(Config.PRESETS_FILE, 'r', encoding='utf-8') as f:
                    presets.update(json.load(f))
        except (IOError, json.JSONDecodeError, Exception) as e:
            pass
        return presets
    
    def _save_presets(self):
        user = {k: v for k, v in self.presets.items() if k not in Config.DEFAULT_PRESETS}
        try:
            with open(Config.PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(user, f, ensure_ascii=False, indent=2)
        except (IOError, Exception) as e:
            pass
    
    def _refresh_list(self):
        self.list_widget.clear()
        for key, preset in self.presets.items():
            prefix = "[기본] " if key in Config.DEFAULT_PRESETS else "[사용자] "
            item = QListWidgetItem(prefix + preset.get('name', key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list_widget.addItem(item)
    
    def _on_select(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        p = self.presets.get(key, {})
        self.detail_label.setText(f"<b>{p.get('name', key)}</b><br>{p.get('description', '')}<br><br>"
            f"K값: {p.get('k', '-')} | TS발동: {p.get('ts_start', '-')}% | 손절: {p.get('loss', '-')}%")
    
    def _save_preset(self):
        name = self.name_input.text().strip()
        if not name:
            return
        key = f"custom_{name.lower().replace(' ', '_')}"
        self.presets[key] = {"name": f"⭐ {name}", "description": f"사용자 정의 ({datetime.datetime.now():%Y-%m-%d})", **self.current_values}
        self._save_presets()
        self._refresh_list()
        self.name_input.clear()
    
    def _delete_preset(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key in Config.DEFAULT_PRESETS:
            QMessageBox.warning(self, "경고", "기본 프리셋은 삭제할 수 없습니다.")
            return
        del self.presets[key]
        self._save_presets()
        self._refresh_list()
    
    def _apply_preset(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_preset = self.presets.get(item.data(Qt.ItemDataRole.UserRole))
            self.accept()


# ============================================================================
# 도움말 다이얼로그
# ============================================================================
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📚 도움말")
        self.setFixedSize(700, 600)
        self.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        for key, title in [("quick_start", "🚀 빠른 시작"), ("strategy", "📈 전략"), ("faq", "❓ FAQ")]:
            text = QTextEdit()
            text.setReadOnly(True)
            text.setHtml(f"<div style='font-size:13px'>{Config.HELP_CONTENT.get(key, '')}</div>")
            tabs.addTab(text, title)
        
        layout.addWidget(tabs)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.close)
        layout.addWidget(btn)


# ============================================================================
# 메인 트레이더 클래스
# ============================================================================
class KiwoomProTrader(QMainWindow):
    sig_log = pyqtSignal(str)
    sig_execution = pyqtSignal(object)
    sig_update_table = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # 상태 변수
        self.universe: Dict[str, Dict[str, Any]] = {}
        self.deposit = 0
        self.initial_deposit = 0
        self.is_running = False
        self.is_connected = False
        self.daily_loss_triggered = False
        self.time_liquidate_executed = False  # 시간 청산 중복 방지
        self.total_realized_profit = 0
        self.trade_count = 0
        self.win_count = 0
        self._history_dirty = False  # 저장 최적화용 플래그
        
        # API
        self.auth: Optional[KiwoomAuth] = None
        self.rest_client: Optional[KiwoomRESTClient] = None
        self.ws_client: Optional[KiwoomWebSocketClient] = None
        self.current_account = ""
        
        # 데이터
        self.trade_history = []
        self.price_history = {}
        self.telegram: Optional[TelegramNotifier] = None
        self.strategy = StrategyManager(self)
        
        # 신규 매니저 (v4.1)
        self.notification_mgr = NotificationManager()
        self.risk_mgr = RiskManager()
        self.backtest_engine = BacktestEngine()
        self.screener = StockScreener()
        self.current_theme = 'dark'
        
        # 로깅
        self._setup_logging()
        self._load_trade_history()
        
        # 시그널 연결
        self.sig_log.connect(self._append_log)
        self.sig_execution.connect(self._on_execution)
        self.sig_update_table.connect(self._refresh_table)
        
        # UI
        self._init_ui()
        self._create_menu()
        self._create_tray()
        self._setup_timers()
        self._load_settings()
        
        self.logger.info("프로그램 초기화 완료 (v4.0)")
    
    def _setup_logging(self):
        Path(Config.LOG_DIR).mkdir(exist_ok=True)
        self.logger = logging.getLogger('KiwoomTrader')
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(Path(Config.LOG_DIR) / f"trader_{datetime.datetime.now():%Y%m%d}.log", encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)
    
    def _init_ui(self):
        self.setWindowTitle("Kiwoom Pro Algo-Trader v4.0 [REST API]")
        self.setGeometry(100, 100, 1400, 950)
        self.setMinimumSize(1100, 800)
        self.setStyleSheet(DARK_STYLESHEET)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 대시보드 (상단 고정)
        layout.addWidget(self._create_dashboard())
        
        # 메인 스플리터 (탭 + 테이블/로그 영역 크기 조절 가능)
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setHandleWidth(8)  # 핸들 너비 증가
        self.main_splitter.setChildrenCollapsible(False)  # 완전 접힘 방지 (자유 드래그 가능)
        self.main_splitter.setOpaqueResize(True)  # 실시간 리사이즈 미리보기
        self.tabs_widget = self._create_tabs()
        self.main_splitter.addWidget(self.tabs_widget)
        self.main_splitter.addWidget(self._create_stock_panel())
        self.main_splitter.setSizes([350, 500])  # 초기 비율
        layout.addWidget(self.main_splitter)
        
        self._create_statusbar()
    
    def _create_dashboard(self):
        group = QGroupBox("📊 Trading Dashboard")
        group.setObjectName("dashboardCard")  # 글래스모피즘 스타일 적용
        layout = QHBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # 연결 버튼
        self.btn_connect = QPushButton("🔌 API 연결")
        self.btn_connect.setObjectName("connectBtn")
        self.btn_connect.clicked.connect(self.connect_api)
        self.btn_connect.setMinimumWidth(140)
        
        # 계좌 선택
        account_layout = QHBoxLayout()
        account_layout.setSpacing(8)
        lbl_account = QLabel("계좌:")
        lbl_account.setStyleSheet("color: #8b949e; font-weight: 500;")
        self.combo_acc = QComboBox()
        self.combo_acc.setMinimumWidth(160)
        self.combo_acc.currentTextChanged.connect(self._on_account_changed)
        account_layout.addWidget(lbl_account)
        account_layout.addWidget(self.combo_acc)
        
        # 예수금 라벨 (강조 스타일)
        self.lbl_deposit = QLabel("💰 예수금: - 원")
        self.lbl_deposit.setStyleSheet("""
            color: #e6edf3;
            font-weight: bold;
            font-size: 14px;
            padding: 8px 16px;
            background: rgba(88, 166, 255, 0.1);
            border-radius: 10px;
            border: 1px solid rgba(88, 166, 255, 0.2);
        """)
        
        # 손익 라벨 (동적 스타일 - 기본 중립)
        self.lbl_profit = QLabel("📈 손익: - 원")
        self.lbl_profit.setObjectName("profitLabel")
        self.lbl_profit.setStyleSheet("""
            color: #e6edf3;
            font-weight: bold;
            font-size: 14px;
            padding: 8px 16px;
            background: rgba(139, 148, 158, 0.1);
            border-radius: 10px;
            border: 1px solid rgba(139, 148, 158, 0.2);
        """)
        
        # 상태 인디케이터 (펄스 효과 스타일)
        self.lbl_status = QLabel("● 연결 대기")
        self.lbl_status.setObjectName("statusPending")
        self.lbl_status.setStyleSheet("""
            color: #d29922;
            font-weight: bold;
            font-size: 13px;
            padding: 8px 16px;
            background: rgba(210, 153, 34, 0.15);
            border-radius: 14px;
            border: 1px solid rgba(210, 153, 34, 0.3);
        """)
        # 메뉴 접기 버튼
        self.btn_collapse = QPushButton("📂 메뉴 접기")
        self.btn_collapse.setCheckable(True)
        self.btn_collapse.setMaximumWidth(110)
        self.btn_collapse.clicked.connect(self._toggle_menu)
        self.btn_collapse.setStyleSheet("""
            QPushButton {
                background: rgba(48, 54, 61, 0.8);
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 6px 12px;
                color: #e6edf3;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(88, 166, 255, 0.2);
                border-color: #58a6ff;
            }
            QPushButton:checked {
                background: rgba(88, 166, 255, 0.3);
                border-color: #58a6ff;
            }
        """)
        
        layout.addWidget(self.btn_connect)
        layout.addLayout(account_layout)
        layout.addSpacing(24)
        layout.addWidget(self.lbl_deposit)
        layout.addWidget(self.lbl_profit)
        layout.addStretch()
        layout.addWidget(self.btn_collapse)
        layout.addWidget(self.lbl_status)
        group.setLayout(layout)
        return group
    
    def _create_tabs(self):
        tabs = QTabWidget()
        tabs.addTab(self._create_strategy_tab(), "⚙️ 전략 설정")
        tabs.addTab(self._create_advanced_tab(), "🔬 고급 설정")
        tabs.addTab(self._create_chart_tab(), "📈 차트")
        tabs.addTab(self._create_orderbook_tab(), "📋 호가창")
        tabs.addTab(self._create_condition_tab(), "🔍 조건검색")
        tabs.addTab(self._create_ranking_tab(), "🏆 순위")
        tabs.addTab(self._create_screener_tab(), "🔎 스크리너")  # v4.1
        tabs.addTab(self._create_backtest_tab(), "📊 백테스트")  # v4.1
        tabs.addTab(self._create_stats_tab(), "📊 통계")
        tabs.addTab(self._create_history_tab(), "📝 내역")
        tabs.addTab(self._create_api_tab(), "🔑 API")
        return tabs
    
    def _toggle_menu(self, checked):
        """메뉴(탭 영역) 접기/펼치기 토글"""
        if checked:
            self.tabs_widget.hide()
            self.btn_collapse.setText("📁 메뉴 펼치기")
        else:
            self.tabs_widget.show()
            self.btn_collapse.setText("📂 메뉴 접기")
    
    def _create_strategy_tab(self):
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(10)
        
        # 즐겨찾기 콤보박스
        self.combo_favorites = QComboBox()
        self.combo_favorites.addItem("📌 즐겨찾기 선택...")
        self._load_favorites()
        self.combo_favorites.currentIndexChanged.connect(self._on_favorite_selected)
        layout.addWidget(self.combo_favorites, 0, 1)
        
        # 종목 입력 (드래그앤드롭 지원)
        self.input_codes = QLineEdit(Config.DEFAULT_CODES)
        self.input_codes.setAcceptDrops(True)
        self.input_codes.setPlaceholderText("종목코드를 쉼표로 구분하여 입력 (드래그앤드롭 가능)")
        self.input_codes.dragEnterEvent = self._drag_enter_codes
        self.input_codes.dropEvent = self._drop_codes
        layout.addWidget(self.input_codes, 0, 2, 1, 3)
        
        # 즐겨찾기 저장 버튼
        btn_save_fav = QPushButton("⭐")
        btn_save_fav.setMaximumWidth(35)
        btn_save_fav.setToolTip("현재 종목 즐겨찾기에 저장")
        btn_save_fav.clicked.connect(self._save_favorite)
        layout.addWidget(btn_save_fav, 0, 5)
        
        layout.addWidget(QLabel("💵 투자비중:"), 1, 0)
        self.spin_betting = QDoubleSpinBox()
        self.spin_betting.setRange(1, 100)
        self.spin_betting.setValue(Config.DEFAULT_BETTING_RATIO)
        self.spin_betting.setSuffix(" %")
        layout.addWidget(self.spin_betting, 1, 1)
        
        layout.addWidget(QLabel("📐 K값:"), 1, 2)
        self.spin_k = QDoubleSpinBox()
        self.spin_k.setRange(0.1, 1.0)
        self.spin_k.setSingleStep(0.1)
        self.spin_k.setValue(Config.DEFAULT_K_VALUE)
        layout.addWidget(self.spin_k, 1, 3)
        
        layout.addWidget(QLabel("🎯 TS 발동:"), 2, 0)
        self.spin_ts_start = QDoubleSpinBox()
        self.spin_ts_start.setRange(0.5, 20)
        self.spin_ts_start.setValue(Config.DEFAULT_TS_START)
        self.spin_ts_start.setSuffix(" %")
        layout.addWidget(self.spin_ts_start, 2, 1)
        
        layout.addWidget(QLabel("📉 TS 하락:"), 2, 2)
        self.spin_ts_stop = QDoubleSpinBox()
        self.spin_ts_stop.setRange(0.5, 10)
        self.spin_ts_stop.setValue(Config.DEFAULT_TS_STOP)
        self.spin_ts_stop.setSuffix(" %")
        layout.addWidget(self.spin_ts_stop, 2, 3)
        
        layout.addWidget(QLabel("🛑 손절률:"), 2, 4)
        self.spin_loss = QDoubleSpinBox()
        self.spin_loss.setRange(0.5, 10)
        self.spin_loss.setValue(Config.DEFAULT_LOSS_CUT)
        self.spin_loss.setSuffix(" %")
        layout.addWidget(self.spin_loss, 2, 5)
        
        # 버튼
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 매매 시작")
        self.btn_start.setObjectName("startBtn")
        self.btn_start.clicked.connect(self.start_trading)
        self.btn_start.setEnabled(False)
        
        self.btn_stop = QPushButton("⏹️ 매매 중지")
        self.btn_stop.clicked.connect(self.stop_trading)
        self.btn_stop.setEnabled(False)
        
        btn_preset = QPushButton("📋 프리셋")
        btn_preset.clicked.connect(self._open_presets)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(btn_preset)
        btn_layout.addStretch()
        layout.addLayout(btn_layout, 3, 0, 1, 6)
        
        return widget
    
    def _create_advanced_tab(self):
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(10)
        
        # RSI
        self.chk_use_rsi = QCheckBox("RSI 필터")
        self.chk_use_rsi.setChecked(Config.DEFAULT_USE_RSI)
        layout.addWidget(self.chk_use_rsi, 0, 0)
        layout.addWidget(QLabel("과매수:"), 0, 1)
        self.spin_rsi_upper = QSpinBox()
        self.spin_rsi_upper.setRange(50, 90)
        self.spin_rsi_upper.setValue(Config.DEFAULT_RSI_UPPER)
        layout.addWidget(self.spin_rsi_upper, 0, 2)
        layout.addWidget(QLabel("기간:"), 0, 3)
        self.spin_rsi_period = QSpinBox()
        self.spin_rsi_period.setRange(5, 30)
        self.spin_rsi_period.setValue(Config.DEFAULT_RSI_PERIOD)
        layout.addWidget(self.spin_rsi_period, 0, 4)
        
        # MACD
        self.chk_use_macd = QCheckBox("MACD 필터")
        self.chk_use_macd.setChecked(Config.DEFAULT_USE_MACD)
        layout.addWidget(self.chk_use_macd, 1, 0)
        
        # 볼린저
        self.chk_use_bb = QCheckBox("볼린저밴드")
        self.chk_use_bb.setChecked(Config.DEFAULT_USE_BB)
        layout.addWidget(self.chk_use_bb, 2, 0)
        layout.addWidget(QLabel("배수:"), 2, 1)
        self.spin_bb_k = QDoubleSpinBox()
        self.spin_bb_k.setRange(1.0, 3.0)
        self.spin_bb_k.setValue(Config.DEFAULT_BB_STD)
        layout.addWidget(self.spin_bb_k, 2, 2)
        
        # DMI
        self.chk_use_dmi = QCheckBox("DMI/ADX 필터")
        self.chk_use_dmi.setChecked(Config.DEFAULT_USE_DMI)
        layout.addWidget(self.chk_use_dmi, 3, 0)
        layout.addWidget(QLabel("ADX 기준:"), 3, 1)
        self.spin_adx = QSpinBox()
        self.spin_adx.setRange(10, 50)
        self.spin_adx.setValue(Config.DEFAULT_ADX_THRESHOLD)
        layout.addWidget(self.spin_adx, 3, 2)
        
        # 거래량
        self.chk_use_volume = QCheckBox("거래량 필터")
        self.chk_use_volume.setChecked(Config.DEFAULT_USE_VOLUME)
        layout.addWidget(self.chk_use_volume, 4, 0)
        layout.addWidget(QLabel("배수:"), 4, 1)
        self.spin_volume_mult = QDoubleSpinBox()
        self.spin_volume_mult.setRange(1.0, 5.0)
        self.spin_volume_mult.setValue(Config.DEFAULT_VOLUME_MULTIPLIER)
        layout.addWidget(self.spin_volume_mult, 4, 2)
        
        # 리스크 관리
        self.chk_use_risk = QCheckBox("일일 손실 한도")
        self.chk_use_risk.setChecked(Config.DEFAULT_USE_RISK_MGMT)
        layout.addWidget(self.chk_use_risk, 5, 0)
        layout.addWidget(QLabel("한도:"), 5, 1)
        self.spin_max_loss = QDoubleSpinBox()
        self.spin_max_loss.setRange(1, 20)
        self.spin_max_loss.setValue(Config.DEFAULT_MAX_DAILY_LOSS)
        self.spin_max_loss.setSuffix(" %")
        layout.addWidget(self.spin_max_loss, 5, 2)
        layout.addWidget(QLabel("최대보유:"), 5, 3)
        self.spin_max_holdings = QSpinBox()
        self.spin_max_holdings.setRange(1, 20)
        self.spin_max_holdings.setValue(Config.DEFAULT_MAX_HOLDINGS)
        layout.addWidget(self.spin_max_holdings, 5, 4)
        
        # === 신규 전략 옵션 ===
        layout.addWidget(QLabel(""), 6, 0)  # 구분선
        
        # 이동평균 크로스오버
        self.chk_use_ma = QCheckBox("MA 크로스오버")
        layout.addWidget(self.chk_use_ma, 7, 0)
        layout.addWidget(QLabel("단기:"), 7, 1)
        self.spin_ma_short = QSpinBox()
        self.spin_ma_short.setRange(3, 20)
        self.spin_ma_short.setValue(5)
        layout.addWidget(self.spin_ma_short, 7, 2)
        layout.addWidget(QLabel("장기:"), 7, 3)
        self.spin_ma_long = QSpinBox()
        self.spin_ma_long.setRange(10, 60)
        self.spin_ma_long.setValue(20)
        layout.addWidget(self.spin_ma_long, 7, 4)
        
        # 시간대별 전략
        self.chk_use_time_strategy = QCheckBox("시간대별 전략")
        self.chk_use_time_strategy.setToolTip("09:00-09:30 공격적, 09:30-14:30 기본, 14:30- 보수적")
        layout.addWidget(self.chk_use_time_strategy, 8, 0, 1, 2)
        
        # ATR 포지션 사이징
        self.chk_use_atr_sizing = QCheckBox("ATR 사이징")
        layout.addWidget(self.chk_use_atr_sizing, 8, 2)
        layout.addWidget(QLabel("위험%:"), 8, 3)
        self.spin_risk_percent = QDoubleSpinBox()
        self.spin_risk_percent.setRange(0.5, 5.0)
        self.spin_risk_percent.setValue(1.0)
        self.spin_risk_percent.setSuffix(" %")
        layout.addWidget(self.spin_risk_percent, 8, 4)
        
        # 분할 매수/매도
        self.chk_use_split = QCheckBox("분할 주문")
        layout.addWidget(self.chk_use_split, 9, 0)
        layout.addWidget(QLabel("횟수:"), 9, 1)
        self.spin_split_count = QSpinBox()
        self.spin_split_count.setRange(2, 5)
        self.spin_split_count.setValue(3)
        layout.addWidget(self.spin_split_count, 9, 2)
        layout.addWidget(QLabel("간격%:"), 9, 3)
        self.spin_split_percent = QDoubleSpinBox()
        self.spin_split_percent.setRange(0.1, 2.0)
        self.spin_split_percent.setValue(0.5)
        self.spin_split_percent.setSuffix(" %")
        layout.addWidget(self.spin_split_percent, 9, 4)
        
        layout.setRowStretch(10, 1)
        return widget
    
    def _create_chart_tab(self):
        """📈 차트 시각화 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 종목 선택
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("종목코드:"))
        self.chart_code_input = QLineEdit("005930")
        self.chart_code_input.setMaximumWidth(100)
        ctrl_layout.addWidget(self.chart_code_input)
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["일봉", "주봉", "1분봉", "5분봉", "15분봉", "30분봉", "60분봉"])
        ctrl_layout.addWidget(self.chart_type_combo)
        
        btn_load = QPushButton("🔄 차트 조회")
        btn_load.clicked.connect(self._load_chart)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # 차트 영역 (테이블로 대체 - pyqtgraph 없을 시)
        self.chart_table = QTableWidget()
        self.chart_table.setColumnCount(6)
        self.chart_table.setHorizontalHeaderLabels(["날짜", "시가", "고가", "저가", "종가", "거래량"])
        self.chart_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.chart_table)
        
        # 차트 정보
        self.chart_info = QLabel("차트를 조회하세요")
        self.chart_info.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        layout.addWidget(self.chart_info)
        
        return widget
    
    def _create_orderbook_tab(self):
        """📋 호가창 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 종목 선택
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("종목코드:"))
        self.hoga_code_input = QLineEdit("005930")
        self.hoga_code_input.setMaximumWidth(100)
        ctrl_layout.addWidget(self.hoga_code_input)
        
        btn_load = QPushButton("🔄 호가 조회")
        btn_load.clicked.connect(self._load_orderbook)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # 호가 테이블 그룹
        hoga_group = QGroupBox("10단 호가")
        hoga_layout = QHBoxLayout()
        hoga_layout.setSpacing(10)
        
        # 매도 호가 테이블
        self.ask_table = QTableWidget(10, 2)
        self.ask_table.setHorizontalHeaderLabels(["매도호가", "잔량"])
        self.ask_table.verticalHeader().setVisible(False)  # 행 번호 숨김
        self.ask_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ask_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ask_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ask_table.setFixedHeight(320)
        for i in range(10):
            self.ask_table.setRowHeight(i, 28)
        hoga_layout.addWidget(self.ask_table)
        
        # 매수 호가 테이블
        self.bid_table = QTableWidget(10, 2)
        self.bid_table.setHorizontalHeaderLabels(["매수호가", "잔량"])
        self.bid_table.verticalHeader().setVisible(False)  # 행 번호 숨김
        self.bid_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bid_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bid_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.bid_table.setFixedHeight(320)
        for i in range(10):
            self.bid_table.setRowHeight(i, 28)
        hoga_layout.addWidget(self.bid_table)
        
        hoga_group.setLayout(hoga_layout)
        layout.addWidget(hoga_group)
        
        # 총 잔량 표시
        self.hoga_info = QLabel("총 매도잔량: - | 총 매수잔량: -")
        self.hoga_info.setStyleSheet("font-weight: bold; padding: 10px; font-size: 14px;")
        layout.addWidget(self.hoga_info)
        
        layout.addStretch()
        return widget
    
    def _create_condition_tab(self):
        """🔍 조건검색 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 조건식 선택
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("조건식:"))
        self.condition_combo = QComboBox()
        self.condition_combo.setMinimumWidth(200)
        ctrl_layout.addWidget(self.condition_combo)
        
        btn_refresh = QPushButton("🔄 목록 갱신")
        btn_refresh.clicked.connect(self._load_conditions)
        ctrl_layout.addWidget(btn_refresh)
        
        btn_search = QPushButton("🔍 검색 실행")
        btn_search.clicked.connect(self._execute_condition)
        ctrl_layout.addWidget(btn_search)
        
        btn_apply = QPushButton("📌 종목 적용")
        btn_apply.clicked.connect(self._apply_condition_result)
        ctrl_layout.addWidget(btn_apply)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # 검색 결과
        self.condition_table = QTableWidget()
        self.condition_table.setColumnCount(5)
        self.condition_table.setHorizontalHeaderLabels(["종목코드", "종목명", "현재가", "등락률", "거래량"])
        self.condition_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.condition_table)
        
        self.condition_info = QLabel("조건검색 결과가 여기에 표시됩니다")
        layout.addWidget(self.condition_info)
        
        return widget
    
    def _create_ranking_tab(self):
        """🏆 순위 정보 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 순위 유형 선택
        ctrl_layout = QHBoxLayout()
        self.ranking_type = QComboBox()
        self.ranking_type.addItems(["거래량 상위", "상승률 상위", "하락률 상위"])
        ctrl_layout.addWidget(self.ranking_type)
        
        self.ranking_market = QComboBox()
        self.ranking_market.addItems(["전체", "코스피", "코스닥"])
        ctrl_layout.addWidget(self.ranking_market)
        
        btn_load = QPushButton("🔄 순위 조회")
        btn_load.clicked.connect(self._load_ranking)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # 순위 테이블
        self.ranking_table = QTableWidget()
        self.ranking_table.setColumnCount(6)
        self.ranking_table.setHorizontalHeaderLabels(["순위", "종목코드", "종목명", "현재가", "등락률", "거래량"])
        self.ranking_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ranking_table)
        
        return widget
    
    def _create_screener_tab(self):
        """🔎 종목 스크리너 탭 (v4.1)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 조건 선택
        cond_group = QGroupBox("스크리닝 조건")
        cond_layout = QGridLayout()
        
        self.chk_scr_golden = QCheckBox("골든크로스 (MA5>MA20)")
        self.chk_scr_rsi = QCheckBox("RSI 과매도 (<30)")
        self.chk_scr_volume = QCheckBox("거래량 급등 (2배)")
        self.chk_scr_breakout = QCheckBox("변동성 돌파")
        self.chk_scr_bb = QCheckBox("볼린저 하단 터치")
        
        cond_layout.addWidget(self.chk_scr_golden, 0, 0)
        cond_layout.addWidget(self.chk_scr_rsi, 0, 1)
        cond_layout.addWidget(self.chk_scr_volume, 0, 2)
        cond_layout.addWidget(self.chk_scr_breakout, 1, 0)
        cond_layout.addWidget(self.chk_scr_bb, 1, 1)
        
        cond_group.setLayout(cond_layout)
        layout.addWidget(cond_group)
        
        # 종목 입력
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("스캔 종목:"))
        self.screener_codes = QLineEdit()
        self.screener_codes.setPlaceholderText("종목코드 (쉼표 구분) 또는 비워두면 관심종목 사용")
        input_layout.addWidget(self.screener_codes)
        
        self.chk_scr_all = QCheckBox("모든 조건 충족")
        input_layout.addWidget(self.chk_scr_all)
        
        btn_scan = QPushButton("🔍 스캔 실행")
        btn_scan.clicked.connect(self._run_screener)
        input_layout.addWidget(btn_scan)
        
        layout.addLayout(input_layout)
        
        # 결과 테이블
        self.screener_table = QTableWidget()
        self.screener_table.setColumnCount(6)
        self.screener_table.setHorizontalHeaderLabels(["종목코드", "종목명", "현재가", "등락률", "거래량", "매칭조건"])
        self.screener_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.screener_table)
        
        # 적용 버튼
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("📌 감시 종목에 적용")
        btn_apply.clicked.connect(self._apply_screener_result)
        btn_layout.addWidget(btn_apply)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _run_screener(self):
        """스크리너 실행"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        # 조건 수집
        conditions = []
        if self.chk_scr_golden.isChecked():
            conditions.append(ScreenerCondition(ConditionType.MA_GOLDEN_CROSS, {'short': 5, 'long': 20}))
        if self.chk_scr_rsi.isChecked():
            conditions.append(ScreenerCondition(ConditionType.RSI_OVERSOLD, {'threshold': 30}))
        if self.chk_scr_volume.isChecked():
            conditions.append(ScreenerCondition(ConditionType.VOLUME_SURGE, {'multiplier': 2.0}))
        if self.chk_scr_breakout.isChecked():
            conditions.append(ScreenerCondition(ConditionType.VOLATILITY_BREAKOUT, {'k': 0.5}))
        if self.chk_scr_bb.isChecked():
            conditions.append(ScreenerCondition(ConditionType.BB_LOWER_TOUCH))
        
        if not conditions:
            self.log("⚠️ 스크리닝 조건을 선택하세요")
            return
        
        # 종목 리스트
        codes_text = self.screener_codes.text().strip()
        if codes_text:
            codes = [c.strip() for c in codes_text.split(",") if c.strip()]
        else:
            codes = list(self.universe.keys()) or ["005930", "000660", "035720"]
        
        self.log(f"🔍 스크리너 실행: {len(codes)}개 종목, {len(conditions)}개 조건")
        
        # 스크리너 설정 및 실행
        self.screener.set_clients(self.rest_client)
        results = self.screener.scan(codes, conditions, require_all=self.chk_scr_all.isChecked())
        
        # 결과 표시
        self.screener_table.setRowCount(len(results))
        for i, r in enumerate(results):
            items = [r.code, r.name, f"{r.current_price:,}", f"{r.change_rate:+.2f}%",
                    f"{r.volume:,}", ", ".join(r.matched_conditions)]
            for j, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignCenter)
                self.screener_table.setItem(i, j, item)
        
        self.log(f"🔎 스크리너 결과: {len(results)}개 종목 매칭")
    
    def _apply_screener_result(self):
        """스크리너 결과를 감시 종목에 적용"""
        codes = []
        for i in range(self.screener_table.rowCount()):
            item = self.screener_table.item(i, 0)
            if item:
                codes.append(item.text())
        
        if codes:
            self.input_codes.setText(",".join(codes[:10]))
            self.log(f"📌 스크리너 결과 {len(codes[:10])}개 종목 적용")
    
    def _create_backtest_tab(self):
        """📊 백테스트 탭 (v4.1)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 파라미터 설정
        param_group = QGroupBox("백테스트 설정")
        param_layout = QGridLayout()
        
        param_layout.addWidget(QLabel("종목코드:"), 0, 0)
        self.bt_code = QLineEdit("005930")
        self.bt_code.setMaximumWidth(100)
        param_layout.addWidget(self.bt_code, 0, 1)
        
        param_layout.addWidget(QLabel("초기자본:"), 0, 2)
        self.bt_capital = QSpinBox()
        self.bt_capital.setRange(1000000, 100000000)
        self.bt_capital.setValue(10000000)
        self.bt_capital.setSingleStep(1000000)
        self.bt_capital.setSuffix(" 원")
        param_layout.addWidget(self.bt_capital, 0, 3)
        
        param_layout.addWidget(QLabel("K값:"), 1, 0)
        self.bt_k = QDoubleSpinBox()
        self.bt_k.setRange(0.1, 1.0)
        self.bt_k.setValue(0.5)
        self.bt_k.setSingleStep(0.1)
        param_layout.addWidget(self.bt_k, 1, 1)
        
        param_layout.addWidget(QLabel("TS 발동%:"), 1, 2)
        self.bt_ts_start = QDoubleSpinBox()
        self.bt_ts_start.setRange(1.0, 10.0)
        self.bt_ts_start.setValue(3.0)
        param_layout.addWidget(self.bt_ts_start, 1, 3)
        
        param_layout.addWidget(QLabel("TS 하락%:"), 2, 0)
        self.bt_ts_stop = QDoubleSpinBox()
        self.bt_ts_stop.setRange(0.5, 5.0)
        self.bt_ts_stop.setValue(1.5)
        param_layout.addWidget(self.bt_ts_stop, 2, 1)
        
        param_layout.addWidget(QLabel("손절%:"), 2, 2)
        self.bt_loss = QDoubleSpinBox()
        self.bt_loss.setRange(0.5, 10.0)
        self.bt_loss.setValue(2.0)
        param_layout.addWidget(self.bt_loss, 2, 3)
        
        self.bt_use_rsi = QCheckBox("RSI 필터")
        self.bt_use_rsi.setChecked(True)
        self.bt_use_volume = QCheckBox("거래량 필터")
        self.bt_use_volume.setChecked(True)
        param_layout.addWidget(self.bt_use_rsi, 3, 0)
        param_layout.addWidget(self.bt_use_volume, 3, 1)
        
        btn_run = QPushButton("▶️ 백테스트 실행")
        btn_run.clicked.connect(self._run_backtest)
        param_layout.addWidget(btn_run, 3, 2, 1, 2)
        
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        
        # 결과 표시
        result_group = QGroupBox("백테스트 결과")
        result_layout = QGridLayout()
        
        self.bt_labels = {}
        labels_info = [
            ("total_return", "총 수익률"), ("total_profit", "총 손익"),
            ("total_trades", "거래 횟수"), ("win_rate", "승률"),
            ("max_drawdown", "최대 낙폭(MDD)"), ("sharpe", "샤프 비율"),
            ("profit_factor", "손익비"), ("avg_profit", "평균 수익"),
        ]
        for i, (key, label) in enumerate(labels_info):
            result_layout.addWidget(QLabel(f"{label}:"), i // 4, (i % 4) * 2)
            lbl = QLabel("-")
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.bt_labels[key] = lbl
            result_layout.addWidget(lbl, i // 4, (i % 4) * 2 + 1)
        
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)
        
        # 거래 내역
        self.bt_trades_table = QTableWidget()
        self.bt_trades_table.setColumnCount(7)
        self.bt_trades_table.setHorizontalHeaderLabels(["매수일", "매수가", "매도일", "매도가", "수량", "손익", "사유"])
        self.bt_trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.bt_trades_table)
        
        # 보고서 출력
        self.bt_report = QTextEdit()
        self.bt_report.setReadOnly(True)
        self.bt_report.setMaximumHeight(150)
        layout.addWidget(self.bt_report)
        
        return widget
    
    def _run_backtest(self):
        """백테스트 실행"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        code = self.bt_code.text().strip()
        if not code:
            self.log("⚠️ 종목코드를 입력하세요")
            return
        
        params = BacktestParams(
            initial_capital=self.bt_capital.value(),
            k_value=self.bt_k.value(),
            ts_start=self.bt_ts_start.value(),
            ts_stop=self.bt_ts_stop.value(),
            loss_cut=self.bt_loss.value(),
            use_rsi=self.bt_use_rsi.isChecked(),
            use_volume=self.bt_use_volume.isChecked(),
        )
        
        self.log(f"📊 백테스트 시작: {code}")
        
        # 백테스트 실행
        self.backtest_engine.set_client(self.rest_client)
        result = self.backtest_engine.run(code, params)
        
        if not result:
            self.log("❌ 백테스트 실패 (데이터 부족)")
            return
        
        # 결과 표시
        self.bt_labels["total_return"].setText(f"{result.total_return:+.2f}%")
        self.bt_labels["total_profit"].setText(f"{result.total_profit:+,}원")
        self.bt_labels["total_trades"].setText(f"{result.total_trades}회")
        self.bt_labels["win_rate"].setText(f"{result.win_rate:.1f}%")
        self.bt_labels["max_drawdown"].setText(f"{result.max_drawdown:.2f}%")
        self.bt_labels["sharpe"].setText(f"{result.sharpe_ratio:.2f}")
        self.bt_labels["profit_factor"].setText(f"{result.profit_factor:.2f}")
        self.bt_labels["avg_profit"].setText(f"{result.avg_profit:+,.0f}원")
        
        # 수익률에 따른 색상
        color = "#3fb950" if result.total_return > 0 else "#f85149"
        self.bt_labels["total_return"].setStyleSheet(f"font-weight: bold; font-size: 14px; color: {color};")
        self.bt_labels["total_profit"].setStyleSheet(f"font-weight: bold; font-size: 14px; color: {color};")
        
        # 거래 내역
        self.bt_trades_table.setRowCount(len(result.trades))
        for i, t in enumerate(result.trades):
            profit_color = "#3fb950" if t.profit > 0 else "#f85149"
            items = [t.entry_date, f"{t.entry_price:,}", t.exit_date, f"{t.exit_price:,}",
                    str(t.quantity), f"{t.profit:+,}", t.reason]
            for j, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignCenter)
                if j == 5:  # 손익 컬럼
                    item.setForeground(QColor(profit_color))
                self.bt_trades_table.setItem(i, j, item)
        
        # 보고서
        report = self.backtest_engine.generate_report(result)
        self.bt_report.setText(report)
        
        self.log(f"✅ 백테스트 완료: {code} - 수익률 {result.total_return:+.2f}%")
    
    # === 새로운 탭 이벤트 핸들러 ===
    def _load_chart(self):
        """차트 데이터 조회"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        code = self.chart_code_input.text().strip()
        chart_type = self.chart_type_combo.currentText()
        
        try:
            if "일봉" in chart_type:
                data = self.rest_client.get_daily_chart(code, 60)
            elif "주봉" in chart_type:
                data = self.rest_client.get_weekly_chart(code, 52)
            else:
                interval = int(chart_type.replace("분봉", ""))
                data = self.rest_client.get_minute_chart(code, interval, 60)
            
            self.chart_table.setRowCount(len(data))
            for i, candle in enumerate(data):
                items = [candle.date, f"{candle.open_price:,}", f"{candle.high_price:,}",
                        f"{candle.low_price:,}", f"{candle.close_price:,}", f"{candle.volume:,}"]
                for j, text in enumerate(items):
                    self.chart_table.setItem(i, j, QTableWidgetItem(str(text)))
            
            self.chart_info.setText(f"📊 {code} {chart_type} - {len(data)}개 조회")
            self.log(f"📈 차트 조회: {code} ({chart_type})")
        except Exception as e:
            self.log(f"❌ 차트 조회 실패: {e}")
    
    def _load_orderbook(self):
        """호가 데이터 조회"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        code = self.hoga_code_input.text().strip()
        
        try:
            ob = self.rest_client.get_order_book(code)
            if ob:
                for i in range(10):
                    # 매도 호가 (역순)
                    idx = 9 - i
                    self.ask_table.setItem(i, 0, QTableWidgetItem(f"{ob.ask_prices[idx]:,}"))
                    self.ask_table.setItem(i, 1, QTableWidgetItem(f"{ob.ask_volumes[idx]:,}"))
                    # 매수 호가
                    self.bid_table.setItem(i, 0, QTableWidgetItem(f"{ob.bid_prices[i]:,}"))
                    self.bid_table.setItem(i, 1, QTableWidgetItem(f"{ob.bid_volumes[i]:,}"))
                
                self.hoga_info.setText(f"총 매도잔량: {ob.total_ask_volume:,} | 총 매수잔량: {ob.total_bid_volume:,}")
                self.log(f"📋 호가 조회: {code}")
        except Exception as e:
            self.log(f"❌ 호가 조회 실패: {e}")
    
    def _load_conditions(self):
        """조건식 목록 조회"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        try:
            conditions = self.rest_client.get_condition_list()
            self.condition_combo.clear()
            for cond in conditions:
                self.condition_combo.addItem(f"{cond['index']}: {cond['name']}", cond)
            self.log(f"🔍 조건식 {len(conditions)}개 로드")
        except Exception as e:
            self.log(f"❌ 조건식 조회 실패: {e}")
    
    def _execute_condition(self):
        """조건검색 실행"""
        if not self.rest_client:
            return
        
        cond_data = self.condition_combo.currentData()
        if not cond_data:
            return
        
        try:
            results = self.rest_client.search_by_condition(cond_data['index'], cond_data['name'])
            self.condition_table.setRowCount(len(results))
            for i, stock in enumerate(results):
                items = [stock['code'], stock['name'], f"{stock['current_price']:,}",
                        f"{stock['change_rate']:.2f}%", f"{stock['volume']:,}"]
                for j, text in enumerate(items):
                    self.condition_table.setItem(i, j, QTableWidgetItem(str(text)))
            
            self.condition_info.setText(f"🔍 {len(results)}개 종목 검색됨")
            self.log(f"🔍 조건검색 완료: {len(results)}개")
        except Exception as e:
            self.log(f"❌ 조건검색 실패: {e}")
    
    def _apply_condition_result(self):
        """조건검색 결과를 감시 종목에 적용"""
        codes = []
        for i in range(self.condition_table.rowCount()):
            item = self.condition_table.item(i, 0)
            if item:
                codes.append(item.text())
        
        if codes:
            self.input_codes.setText(",".join(codes[:10]))  # 최대 10개
            self.log(f"📌 {len(codes[:10])}개 종목 적용")
    
    def _load_ranking(self):
        """순위 정보 조회"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        ranking_type = self.ranking_type.currentText()
        market_idx = self.ranking_market.currentIndex()
        market = str(market_idx)
        
        try:
            if "거래량" in ranking_type:
                data = self.rest_client.get_volume_ranking(market, 30)
            elif "상승" in ranking_type:
                data = self.rest_client.get_fluctuation_ranking(market, "1", 30)
            else:
                data = self.rest_client.get_fluctuation_ranking(market, "2", 30)
            
            self.ranking_table.setRowCount(len(data))
            for i, item in enumerate(data):
                items = [str(item['rank']), item['code'], item['name'],
                        f"{item['current_price']:,}", f"{item['change_rate']:.2f}%", f"{item['volume']:,}"]
                for j, text in enumerate(items):
                    self.ranking_table.setItem(i, j, QTableWidgetItem(str(text)))
            
            self.log(f"🏆 {ranking_type} 조회 완료")
        except Exception as e:
            self.log(f"❌ 순위 조회 실패: {e}")
    
    def _create_stats_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.stats_labels = {}
        stats_group = QGroupBox("📊 오늘의 성과")
        grid = QGridLayout()
        
        for i, (key, label) in enumerate([
            ("trades", "총 거래 횟수"), ("wins", "이익 거래"), ("winrate", "승률"),
            ("profit", "실현 손익"), ("max_profit", "최대 수익"), ("max_loss", "최대 손실")
        ]):
            grid.addWidget(QLabel(f"{label}:"), i // 3, (i % 3) * 2)
            lbl = QLabel("-")
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.stats_labels[key] = lbl
            grid.addWidget(lbl, i // 3, (i % 3) * 2 + 1)
        
        stats_group.setLayout(grid)
        layout.addWidget(stats_group)
        
        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self._update_stats)
        layout.addWidget(btn_refresh)
        layout.addStretch()
        return widget
    
    def _create_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.history_table = QTableWidget()
        cols = ["시간", "종목", "구분", "가격", "수량", "금액", "손익", "사유"]
        self.history_table.setColumnCount(len(cols))
        self.history_table.setHorizontalHeaderLabels(cols)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history_table)
        
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("📤 CSV 내보내기")
        btn_export.clicked.connect(self._export_csv)
        btn_layout.addWidget(btn_export)
        btn_clear = QPushButton("🗑️ 오늘 기록 삭제")
        btn_clear.clicked.connect(self._clear_today_history)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self._refresh_history_table()
        return widget
    
    def _create_api_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # API 인증
        group1 = QGroupBox("🔐 REST API 인증")
        form1 = QFormLayout()
        self.input_app_key = QLineEdit()
        self.input_app_key.setEchoMode(QLineEdit.EchoMode.Password)
        form1.addRow("App Key:", self.input_app_key)
        self.input_secret = QLineEdit()
        self.input_secret.setEchoMode(QLineEdit.EchoMode.Password)
        form1.addRow("Secret Key:", self.input_secret)
        self.chk_mock = QCheckBox("모의투자")
        form1.addRow("", self.chk_mock)
        group1.setLayout(form1)
        layout.addWidget(group1)
        
        # 텔레그램
        group2 = QGroupBox("📱 텔레그램 알림")
        form2 = QFormLayout()
        self.input_tg_token = QLineEdit()
        self.input_tg_token.setPlaceholderText("Bot Token")
        form2.addRow("봇 토큰:", self.input_tg_token)
        self.input_tg_chat = QLineEdit()
        self.input_tg_chat.setPlaceholderText("Chat ID")
        form2.addRow("챗 ID:", self.input_tg_chat)
        self.chk_use_telegram = QCheckBox("텔레그램 알림 사용")
        form2.addRow("", self.chk_use_telegram)
        group2.setLayout(form2)
        layout.addWidget(group2)
        
        btn_save = QPushButton("💾 설정 저장")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)
        layout.addStretch()
        return widget
    
    def _create_stock_panel(self):
        """주식 테이블 + 로그 패널 (내부 스플리터)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 주식 테이블
        self.table = QTableWidget()
        cols = ["종목명", "현재가", "목표가", "상태", "보유", "매입가", "수익률", "최고수익", "투자금"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        layout.addWidget(self.table, 3)  # 비율 3
        
        # 로그 영역
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        layout.addWidget(self.log_text, 1)  # 비율 1
        
        return panel
    
    def _create_statusbar(self):
        # 시간 표시
        self.status_time = QLabel()
        self.status_time.setStyleSheet("color: #8b949e; font-family: monospace; font-size: 13px;")
        
        # 매매 상태 배지
        self.status_trading = QLabel("⏸️ 대기 중")
        self.status_trading.setObjectName("tradingOff")
        self.status_trading.setStyleSheet("""
            color: #8b949e;
            font-weight: bold;
            padding: 4px 12px;
            background: rgba(48, 54, 61, 0.5);
            border-radius: 10px;
        """)
        
        self.statusBar().addWidget(self.status_time)
        self.statusBar().addWidget(QLabel("  "))  # 간격
        self.statusBar().addWidget(self.status_trading)
        self.statusBar().addPermanentWidget(QLabel("v4.0 REST API"))
    
    def _create_menu(self):
        menubar = self.menuBar()
        
        # 파일
        file_menu = menubar.addMenu("파일")
        file_menu.addAction("💾 설정 저장", self._save_settings)
        file_menu.addAction("📂 설정 불러오기", self._load_settings)
        file_menu.addSeparator()
        file_menu.addAction("📤 거래내역 내보내기", self._export_csv)
        file_menu.addSeparator()
        file_menu.addAction("종료", self.close)
        
        # 도구
        tools_menu = menubar.addMenu("도구")
        tools_menu.addAction("📋 프리셋 관리", self._open_presets)
        tools_menu.addAction("🔄 계좌 새로고침", lambda: self._on_account_changed(self.current_account))
        tools_menu.addSeparator()
        tools_menu.addAction("🛡️ 리스크 상태 보기", self._show_risk_status)
        tools_menu.addAction("🔔 알림 테스트", self._test_notification)
        
        # 보기 (v4.1)
        view_menu = menubar.addMenu("보기")
        view_menu.addAction("🌙 다크 테마", lambda: self._set_theme('dark'))
        view_menu.addAction("☀️ 라이트 테마", lambda: self._set_theme('light'))
        view_menu.addSeparator()
        view_menu.addAction("🔲 미니 모드", self._toggle_mini_mode)
        
        # 도움말
        help_menu = menubar.addMenu("도움말")
        help_menu.addAction("📚 사용 가이드", lambda: HelpDialog(self).exec())
        help_menu.addAction("ℹ️ 버전 정보", lambda: QMessageBox.information(self, "정보", "Kiwoom Pro Algo-Trader v4.1\nREST API + 신규 기능"))
    
    def _set_theme(self, theme_name: str):
        """테마 변경 (v4.1)"""
        self.current_theme = theme_name
        self.setStyleSheet(get_theme(theme_name))
        self.log(f"🎨 테마 변경: {theme_name.upper()}")
    
    def _toggle_mini_mode(self):
        """미니 모드 토글 (v4.1)"""
        if self.isMaximized() or self.width() > 600:
            # 미니 모드로 전환
            self.setGeometry(self.x(), self.y(), 400, 200)
            self.tabs_widget.hide()
            self.log("🔲 미니 모드 ON")
        else:
            # 일반 모드로 복원
            self.setGeometry(100, 100, 1400, 950)
            self.tabs_widget.show()
            self.log("🔳 미니 모드 OFF")
    
    def _show_risk_status(self):
        """리스크 상태 표시 (v4.1)"""
        status = self.risk_mgr.get_status()
        msg = f"""
🛡️ 리스크 상태

📉 드로다운: {status['current_drawdown']:.2f}% (오늘 최대: {status['max_drawdown_today']:.2f}%)
📊 연속 손실: {status['consecutive_losses']}회 / 연속 이익: {status['consecutive_wins']}회
📈 오늘 거래: {status['today_trades']}회 (승: {status['today_wins']} / 패: {status['today_losses']})
💰 오늘 손익: {status['today_profit']:+,}원

🚦 매매 허용: {'✅ 예' if status['trading_allowed'] else '❌ 아니오'}
{f"   사유: {status['trading_blocked_reason']}" if not status['trading_allowed'] else ""}

🚫 블랙리스트: {status['blacklist_count']}개 종목
{', '.join(status['blacklist'][:5]) if status['blacklist'] else '(없음)'}
        """
        QMessageBox.information(self, "리스크 상태", msg.strip())
    
    def _test_notification(self):
        """알림 테스트 (v4.1)"""
        self.notification_mgr.notify(NotificationType.ALERT, {
            "title": "테스트 알림",
            "message": "알림 시스템이 정상 작동합니다!"
        })
        self.log("🔔 알림 테스트 발송")
    
    
    def _create_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Kiwoom Trader v4.0")
        
        tray_menu = QMenu()
        tray_menu.addAction("열기", self.showNormal)
        tray_menu.addAction("종료", self.close)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray_icon.show()
    
    def _setup_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(1000)
    
    def _on_timer(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        self.status_time.setText(time_str)
        
        if self.is_running:
            self.status_trading.setText("🚀 매매 중")
            self.status_trading.setObjectName("tradingActive")
            self.status_trading.setStyleSheet("""
                color: #3fb950;
                font-weight: bold;
                padding: 4px 12px;
                background: rgba(63, 185, 80, 0.15);
                border-radius: 10px;
                border: 1px solid rgba(63, 185, 80, 0.3);
            """)
        else:
            self.status_trading.setText("⏸️ 대기 중")
            self.status_trading.setObjectName("tradingOff")
            self.status_trading.setStyleSheet("""
                color: #8b949e;
                font-weight: bold;
                padding: 4px 12px;
                background: rgba(48, 54, 61, 0.5);
                border-radius: 10px;
            """)
        
        if not self.is_running:
            return
        
        # 시간 청산 체크 (15:19) - 중복 방지
        if not self.time_liquidate_executed:
            if now.hour == Config.MARKET_CLOSE_HOUR and now.minute >= Config.MARKET_CLOSE_MINUTE:
                self.time_liquidate_executed = True
                self._time_liquidate()
        
        # 일일 손실 한도 체크
        if self.chk_use_risk.isChecked() and not self.daily_loss_triggered and self.initial_deposit > 0:
            loss_rate = (self.total_realized_profit / self.initial_deposit) * 100
            if loss_rate <= -self.spin_max_loss.value():
                self.daily_loss_triggered = True
                self.log(f"⚠️ 일일 손실 한도 도달 ({loss_rate:.2f}%) - 매매 중지")
                self.stop_trading()
        
        # 지연된 거래 내역 저장
        if self._history_dirty:
            self._save_trade_history()
            self._history_dirty = False
    
    def _time_liquidate(self):
        """장 마감 전 청산"""
        for code, info in self.universe.items():
            if info.get('held', 0) > 0:
                self.log(f"⏰ 시간 청산: {info.get('name', code)}")
                # 실제 매도 로직은 추후 구현
    
    # === API ===
    def connect_api(self):
        app_key = self.input_app_key.text().strip()
        secret_key = self.input_secret.text().strip()
        
        if not app_key or not secret_key:
            QMessageBox.warning(self, "경고", "App Key와 Secret Key를 입력해주세요.")
            return
        
        self.log("🔄 API 연결 시도...")
        self.lbl_status.setText("● 연결 중...")
        self.lbl_status.setStyleSheet("color: #ffc107;")
        
        try:
            self.auth = KiwoomAuth(app_key, secret_key, self.chk_mock.isChecked())
            result = self.auth.test_connection()
            
            if result["success"]:
                self.rest_client = KiwoomRESTClient(self.auth)
                self.ws_client = KiwoomWebSocketClient(self.auth)
                
                accounts = self.rest_client.get_account_list()
                self.combo_acc.clear()
                self.combo_acc.addItems(accounts if accounts else ["테스트계좌"])
                
                self.is_connected = True
                self.lbl_status.setText("● 연결됨")
                self.lbl_status.setObjectName("statusConnected")
                self.lbl_status.setStyleSheet("""
                    color: #3fb950;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 16px;
                    background: rgba(63, 185, 80, 0.15);
                    border-radius: 14px;
                    border: 1px solid rgba(63, 185, 80, 0.3);
                """)
                self.btn_start.setEnabled(True)
                self.log(f"✅ API 연결 성공")
                
                # 텔레그램 초기화
                if self.chk_use_telegram.isChecked():
                    self.telegram = TelegramNotifier(self.input_tg_token.text(), self.input_tg_chat.text())
                    self.telegram.send("🚀 Kiwoom Trader 연결됨")
            else:
                self.lbl_status.setText("● 연결 실패")
                self.lbl_status.setObjectName("statusDisconnected")
                self.lbl_status.setStyleSheet("""
                    color: #f85149;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 16px;
                    background: rgba(248, 81, 73, 0.15);
                    border-radius: 14px;
                    border: 1px solid rgba(248, 81, 73, 0.3);
                """)
                self.log(f"❌ 연결 실패: {result['message']}")
        except Exception as e:
            self.lbl_status.setText("● 오류")
            self.lbl_status.setObjectName("statusDisconnected")
            self.lbl_status.setStyleSheet("""
                color: #f85149;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                background: rgba(248, 81, 73, 0.15);
                border-radius: 14px;
                border: 1px solid rgba(248, 81, 73, 0.3);
            """)
            self.log(f"❌ 오류: {e}")
    
    def _on_account_changed(self, account):
        self.current_account = account
        if self.rest_client and account:
            info = self.rest_client.get_account_info(account)
            if info is None:
                self.logger.warning(f"계좌 정보 조회 실패: {account}")
                return
            
            self.deposit = getattr(info, 'available_amount', 0) or 0
            self.initial_deposit = self.initial_deposit or self.deposit
            self.lbl_deposit.setText(f"💰 예수금: {self.deposit:,} 원")
            
            profit = getattr(info, 'total_profit', 0) or 0
            self.lbl_profit.setText(f"📈 손익: {profit:+,} 원")
            
            # 손익에 따른 동적 스타일
            if profit > 0:
                self.lbl_profit.setStyleSheet("""
                    color: #3fb950;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                    background: rgba(63, 185, 80, 0.15);
                    border-radius: 10px;
                    border: 1px solid rgba(63, 185, 80, 0.2);
                """)
            elif profit < 0:
                self.lbl_profit.setStyleSheet("""
                    color: #f85149;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                    background: rgba(248, 81, 73, 0.15);
                    border-radius: 10px;
                    border: 1px solid rgba(248, 81, 73, 0.2);
                """)
            else:
                self.lbl_profit.setStyleSheet("""
                    color: #e6edf3;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 16px;
                    background: rgba(139, 148, 158, 0.1);
                    border-radius: 10px;
                    border: 1px solid rgba(139, 148, 158, 0.2);
                """)
    
    # === 매매 ===
    def start_trading(self):
        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 API에 연결하세요.")
            return
        
        codes = [c.strip() for c in self.input_codes.text().split(",") if c.strip()]
        if not codes:
            QMessageBox.warning(self, "경고", "감시 종목을 입력하세요.")
            return
        
        try:
            self.is_running = True
            self.daily_loss_triggered = False
            self.time_liquidate_executed = False
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            
            if self.ws_client:
                self.ws_client.connect()
                self.ws_client.subscribe_execution(codes, self._on_realtime)
            
            self._init_universe(codes)
            self.log(f"🚀 매매 시작 - {len(codes)}개 종목")
            
            if self.telegram:
                self.telegram.send(f"🚀 매매 시작\n종목: {', '.join(codes)}")
        except Exception as e:
            self.is_running = False
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.log(f"❌ 매매 시작 실패: {e}")
            QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{e}")
    
    def stop_trading(self):
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        try:
            if self.ws_client:
                self.ws_client.unsubscribe_all()
                self.ws_client.disconnect()
        except Exception as e:
            self.log(f"⚠️ WebSocket 종료 중 오류: {e}")
        
        self.log("⏹️ 매매 중지")
        if self.telegram:
            self.telegram.send("⏹️ 매매 중지됨")
    
    def _init_universe(self, codes):
        self.table.setRowCount(len(codes))
        failed_codes = []
        
        for i, code in enumerate(codes):
            try:
                if self.rest_client:
                    quote = self.rest_client.get_stock_quote(code)
                    if quote:
                        self.universe[code] = {
                            "name": quote.name, "current": quote.current_price,
                            "open": quote.open_price, "high": quote.high_price,
                            "low": quote.low_price, "prev_close": quote.prev_close,
                            "target": 0, "held": 0, "buy_price": 0,
                            "max_profit_rate": 0, "status": "감시"
                        }
                        self._update_row(i, code)
                    else:
                        failed_codes.append(code)
                        self.log(f"⚠️ {code} 시세 조회 실패")
            except Exception as e:
                failed_codes.append(code)
                self.log(f"⚠️ {code} 초기화 오류: {e}")
        
        if failed_codes:
            self.log(f"⚠️ {len(failed_codes)}개 종목 초기화 실패: {', '.join(failed_codes)}")
    
    def _update_row(self, row, code):
        info = self.universe.get(code, {})
        profit_rate = 0
        if info.get('held', 0) > 0 and info.get('buy_price', 0) > 0:
            profit_rate = (info['current'] - info['buy_price']) / info['buy_price'] * 100
        
        data = [
            info.get("name", code), f"{info.get('current', 0):,}",
            f"{info.get('target', 0):,}", info.get("status", ""),
            str(info.get("held", 0)), f"{info.get('buy_price', 0):,}",
            f"{profit_rate:.2f}%", f"{info.get('max_profit_rate', 0):.2f}%",
            f"{info.get('invest_amount', 0):,}"
        ]
        self.table.setUpdatesEnabled(False)
        try:
            for col, text in enumerate(data):
                existing = self.table.item(row, col)
                text_str = str(text)
                if existing and existing.text() == text_str:
                    continue  # 변경 없으면 스킵
                item = QTableWidgetItem(text_str)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 6 and profit_rate != 0:
                    item.setForeground(QColor("#e63946" if profit_rate > 0 else "#4361ee"))
                self.table.setItem(row, col, item)
        finally:
            self.table.setUpdatesEnabled(True)
    
    def _refresh_table(self):
        for i, code in enumerate(self.universe.keys()):
            self._update_row(i, code)
    
    def _on_realtime(self, data: ExecutionData):
        self.sig_execution.emit(data)
    
    def _on_execution(self, data: ExecutionData):
        if data.code in self.universe:
            self.universe[data.code]["current"] = data.exec_price
            
            # 가격 히스토리 관리 (메모리 최적화)
            if 'price_history' not in self.universe[data.code]:
                self.universe[data.code]['price_history'] = []
            
            history = self.universe[data.code]['price_history']
            history.append(data.exec_price)
            
            # 최대 개수 제한 (Config.MAX_PRICE_HISTORY = 100)
            max_history = getattr(Config, 'MAX_PRICE_HISTORY', 100)
            if len(history) > max_history:
                self.universe[data.code]['price_history'] = history[-max_history:]
            
            self.sig_update_table.emit()
    
    def _show_table_context_menu(self, pos):
        """테이블 우클릭 컨텍스트 메뉴 (v4.1)"""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        
        # 선택된 종목 코드 가져오기
        codes = list(self.universe.keys())
        if row >= len(codes):
            return
        code = codes[row]
        info = self.universe.get(code, {})
        name = info.get('name', code)
        
        menu = QMenu(self)
        
        # 수동 매수
        buy_action = menu.addAction(f"🛒 수동 매수: {name}")
        buy_action.triggered.connect(lambda: self._manual_buy(code, name))
        
        # 수동 매도 (보유 시)
        if info.get('held', 0) > 0:
            sell_action = menu.addAction(f"💰 수동 매도: {name}")
            sell_action.triggered.connect(lambda: self._manual_sell(code, name))
        
        menu.addSeparator()
        
        # 블랙리스트 추가/제거
        if self.risk_mgr.is_blacklisted(code):
            bl_action = menu.addAction(f"✅ 블랙리스트 해제: {name}")
            bl_action.triggered.connect(lambda: self._toggle_blacklist(code, False))
        else:
            bl_action = menu.addAction(f"🚫 블랙리스트 추가: {name}")
            bl_action.triggered.connect(lambda: self._toggle_blacklist(code, True))
        
        # 감시 제외
        remove_action = menu.addAction(f"❌ 감시 제외: {name}")
        remove_action.triggered.connect(lambda: self._remove_from_watch(code))
        
        menu.exec(self.table.viewport().mapToGlobal(pos))
    
    def _manual_buy(self, code: str, name: str):
        """수동 매수 (v4.1)"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        # 간단한 수량 입력
        quantity, ok = QInputDialog.getInt(self, "수동 매수", f"{name} ({code})\n매수 수량:", 1, 1, 10000)
        if not ok:
            return
        
        try:
            # 현재가 조회
            quote = self.rest_client.get_stock_quote(code)
            if not quote:
                self.log(f"❌ {name} 시세 조회 실패")
                return
            
            price = quote.current_price
            
            # 확인
            if QMessageBox.question(
                self, "매수 확인",
                f"{name} ({code})\n{price:,}원 × {quantity}주 = {price * quantity:,}원\n\n매수하시겠습니까?"
            ) != QMessageBox.StandardButton.Yes:
                return
            
            # 시장가 매수
            result = self.rest_client.buy_market(self.current_account, code, quantity)
            if result:
                self.log(f"🛒 수동 매수: {name} {quantity}주 @ {price:,}원")
                self.notification_mgr.notify_buy(code, name, price, quantity)
            else:
                self.log(f"❌ 매수 실패: {name}")
                
        except Exception as e:
            self.log(f"❌ 수동 매수 오류: {e}")
    
    def _manual_sell(self, code: str, name: str):
        """수동 매도 (v4.1)"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        info = self.universe.get(code, {})
        held = info.get('held', 0)
        
        if held <= 0:
            self.log(f"⚠️ {name} 보유 수량 없음")
            return
        
        # 수량 입력
        quantity, ok = QInputDialog.getInt(self, "수동 매도", f"{name} ({code})\n보유: {held}주\n매도 수량:", held, 1, held)
        if not ok:
            return
        
        try:
            quote = self.rest_client.get_stock_quote(code)
            price = quote.current_price if quote else info.get('current', 0)
            buy_price = info.get('buy_price', price)
            profit = (price - buy_price) * quantity
            
            if QMessageBox.question(
                self, "매도 확인",
                f"{name} ({code})\n{price:,}원 × {quantity}주\n예상 손익: {profit:+,}원\n\n매도하시겠습니까?"
            ) != QMessageBox.StandardButton.Yes:
                return
            
            result = self.rest_client.sell_market(self.current_account, code, quantity)
            if result:
                self.log(f"💰 수동 매도: {name} {quantity}주 @ {price:,}원 (손익: {profit:+,}원)")
                self.notification_mgr.notify_sell(code, name, price, quantity, profit)
                self.risk_mgr.record_trade(profit, code)
            else:
                self.log(f"❌ 매도 실패: {name}")
                
        except Exception as e:
            self.log(f"❌ 수동 매도 오류: {e}")
    
    def _toggle_blacklist(self, code: str, add: bool):
        """블랙리스트 토글 (v4.1)"""
        info = self.universe.get(code, {})
        name = info.get('name', code)
        
        if add:
            self.risk_mgr.add_to_blacklist(code)
            self.log(f"🚫 블랙리스트 추가: {name}")
        else:
            self.risk_mgr.remove_from_blacklist(code)
            self.log(f"✅ 블랙리스트 해제: {name}")
    
    def _remove_from_watch(self, code: str):
        """감시 목록에서 제외 (v4.1)"""
        if code in self.universe:
            name = self.universe[code].get('name', code)
            del self.universe[code]
            
            # 테이블 갱신
            codes = self.input_codes.text().split(',')
            codes = [c.strip() for c in codes if c.strip() != code]
            self.input_codes.setText(','.join(codes))
            
            self._init_universe(codes)
            self.log(f"❌ 감시 제외: {name}")
    
    # === 기록 ===
    def _add_trade(self, record: dict):
        """거래 기록 추가 (지연 저장)"""
        record["timestamp"] = datetime.datetime.now().isoformat()
        self.trade_history.append(record)
        self._history_dirty = True  # 타이머에서 저장
        self._refresh_history_table()
        
        if record.get("type") == "매수":
            self.trade_count += 1
        if record.get("profit", 0) > 0:
            self.win_count += 1
        self.total_realized_profit += record.get("profit", 0)
    
    def _refresh_history_table(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_history = [r for r in self.trade_history if r.get('timestamp', '').startswith(today)]
        
        self.history_table.setRowCount(len(today_history))
        for row, r in enumerate(reversed(today_history)):
            time_str = r.get('timestamp', '').split('T')[-1][:8] if 'T' in r.get('timestamp', '') else r.get('timestamp', '')
            items = [time_str, r.get('name', r.get('code', '')), r.get('type', ''),
                     f"{r.get('price', 0):,}", str(r.get('quantity', 0)),
                     f"{r.get('amount', 0):,}", f"{r.get('profit', 0):+,}", r.get('reason', '')]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 6:
                    item.setForeground(QColor("#e63946" if r.get('profit', 0) > 0 else "#4361ee"))
                self.history_table.setItem(row, col, item)
    
    def _export_csv(self):
        if not self.trade_history:
            QMessageBox.information(self, "알림", "내보낼 내역이 없습니다.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"trades_{datetime.datetime.now():%Y%m%d}.csv", "CSV (*.csv)")
        if filename:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["시간", "코드", "종목", "구분", "가격", "수량", "금액", "손익", "사유"])
                for r in self.trade_history:
                    writer.writerow([r.get('timestamp'), r.get('code'), r.get('name'), r.get('type'),
                                   r.get('price'), r.get('quantity'), r.get('amount'), r.get('profit'), r.get('reason')])
            self.log(f"📤 CSV 저장: {filename}")
    
    def _clear_today_history(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        count = sum(1 for r in self.trade_history if r.get('timestamp', '').startswith(today))
        if count == 0:
            return
        if QMessageBox.question(self, "확인", f"오늘 기록 {count}건 삭제?") == QMessageBox.StandardButton.Yes:
            self.trade_history = [r for r in self.trade_history if not r.get('timestamp', '').startswith(today)]
            self._save_trade_history()
            self._refresh_history_table()
    
    def _update_stats(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_trades = [r for r in self.trade_history if r.get('timestamp', '').startswith(today)]
        sells = [r for r in today_trades if r.get('type') == '매도']
        
        wins = sum(1 for r in sells if r.get('profit', 0) > 0)
        total_profit = sum(r.get('profit', 0) for r in sells)
        profits = [r.get('profit', 0) for r in sells]
        
        self.stats_labels["trades"].setText(str(len(today_trades)))
        self.stats_labels["wins"].setText(f"{wins}/{len(sells)}")
        self.stats_labels["winrate"].setText(f"{wins/len(sells)*100:.1f}%" if sells else "-")
        self.stats_labels["profit"].setText(f"{total_profit:+,} 원")
        self.stats_labels["max_profit"].setText(f"{max(profits):+,}" if profits else "-")
        self.stats_labels["max_loss"].setText(f"{min(profits):+,}" if profits else "-")
    
    def _load_trade_history(self):
        """거래 내역 로드"""
        try:
            if os.path.exists(Config.TRADE_HISTORY_FILE):
                with open(Config.TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.trade_history = json.load(f)
        except json.JSONDecodeError as e:
            self.logger.warning(f"거래 내역 파싱 실패: {e}")
            self.trade_history = []
        except OSError as e:
            self.logger.warning(f"거래 내역 로드 실패: {e}")
    
    def _save_trade_history(self):
        """거래 내역 저장"""
        try:
            with open(Config.TRADE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.error(f"거래 내역 저장 실패: {e}")
    
    # === 설정 ===
    def _save_settings(self):
        settings = {
            "app_key": self.input_app_key.text(), "secret_key": self.input_secret.text(),
            "is_mock": self.chk_mock.isChecked(), "codes": self.input_codes.text(),
            "betting": self.spin_betting.value(), "k_value": self.spin_k.value(),
            "ts_start": self.spin_ts_start.value(), "ts_stop": self.spin_ts_stop.value(),
            "loss_cut": self.spin_loss.value(),
            "use_rsi": self.chk_use_rsi.isChecked(), "rsi_upper": self.spin_rsi_upper.value(),
            "rsi_period": self.spin_rsi_period.value(),
            "use_macd": self.chk_use_macd.isChecked(),
            "use_bb": self.chk_use_bb.isChecked(), "bb_k": self.spin_bb_k.value(),
            "use_dmi": self.chk_use_dmi.isChecked(), "adx": self.spin_adx.value(),
            "use_volume": self.chk_use_volume.isChecked(), "volume_mult": self.spin_volume_mult.value(),
            "use_risk": self.chk_use_risk.isChecked(), "max_loss": self.spin_max_loss.value(),
            "max_holdings": self.spin_max_holdings.value(),
            "tg_token": self.input_tg_token.text(), "tg_chat": self.input_tg_chat.text(),
            "use_telegram": self.chk_use_telegram.isChecked()
        }
        try:
            with open(Config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            self.log("✅ 설정 저장 완료")
        except Exception as e:
            self.log(f"❌ 저장 실패: {e}")
    
    def _load_settings(self):
        try:
            if os.path.exists(Config.SETTINGS_FILE):
                with open(Config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    s = json.load(f)
                self.input_app_key.setText(s.get("app_key", ""))
                self.input_secret.setText(s.get("secret_key", ""))
                self.chk_mock.setChecked(s.get("is_mock", False))
                self.input_codes.setText(s.get("codes", Config.DEFAULT_CODES))
                self.spin_betting.setValue(s.get("betting", Config.DEFAULT_BETTING_RATIO))
                self.spin_k.setValue(s.get("k_value", Config.DEFAULT_K_VALUE))
                self.spin_ts_start.setValue(s.get("ts_start", Config.DEFAULT_TS_START))
                self.spin_ts_stop.setValue(s.get("ts_stop", Config.DEFAULT_TS_STOP))
                self.spin_loss.setValue(s.get("loss_cut", Config.DEFAULT_LOSS_CUT))
                self.chk_use_rsi.setChecked(s.get("use_rsi", True))
                self.spin_rsi_upper.setValue(s.get("rsi_upper", 70))
                self.spin_rsi_period.setValue(s.get("rsi_period", 14))
                self.chk_use_macd.setChecked(s.get("use_macd", True))
                self.chk_use_bb.setChecked(s.get("use_bb", False))
                self.spin_bb_k.setValue(s.get("bb_k", 2.0))
                self.chk_use_dmi.setChecked(s.get("use_dmi", False))
                self.spin_adx.setValue(s.get("adx", 25))
                self.chk_use_volume.setChecked(s.get("use_volume", True))
                self.spin_volume_mult.setValue(s.get("volume_mult", 1.5))
                self.chk_use_risk.setChecked(s.get("use_risk", True))
                self.spin_max_loss.setValue(s.get("max_loss", 3.0))
                self.spin_max_holdings.setValue(s.get("max_holdings", 5))
                self.input_tg_token.setText(s.get("tg_token", ""))
                self.input_tg_chat.setText(s.get("tg_chat", ""))
                self.chk_use_telegram.setChecked(s.get("use_telegram", False))
                self.log("📂 설정 불러옴")
        except (IOError, json.JSONDecodeError, KeyError, Exception) as e:
            self.logger.warning(f"설정 로드 오류: {e}")
    
    def _open_presets(self):
        current = {"k": self.spin_k.value(), "ts_start": self.spin_ts_start.value(),
                   "ts_stop": self.spin_ts_stop.value(), "loss": self.spin_loss.value(),
                   "betting": self.spin_betting.value()}
        dialog = PresetDialog(self, current)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_preset:
            p = dialog.selected_preset
            self.spin_k.setValue(p.get("k", 0.5))
            self.spin_ts_start.setValue(p.get("ts_start", 3.0))
            self.spin_ts_stop.setValue(p.get("ts_stop", 1.5))
            self.spin_loss.setValue(p.get("loss", 2.0))
            self.spin_betting.setValue(p.get("betting", 10.0))
            self.log(f"📋 프리셋 적용: {p.get('name', 'Unknown')}")
    
    # === 즐겨찾기 관리 ===
    def _load_favorites(self):
        """즐겨찾기 그룹 로드"""
        try:
            fav_file = Path(Config.DATA_DIR) / "favorites.json"
            if fav_file.exists():
                with open(fav_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
                for name in self.favorites.keys():
                    self.combo_favorites.addItem(f"⭐ {name}")
            else:
                self.favorites = {}
        except Exception:
            self.favorites = {}
    
    def _on_favorite_selected(self, index):
        """즐겨찾기 선택 시"""
        if index <= 0:
            return
        name = self.combo_favorites.currentText().replace("⭐ ", "")
        if name in self.favorites:
            codes = self.favorites[name]
            self.input_codes.setText(",".join(codes))
            self.log(f"⭐ 즐겨찾기 적용: {name} ({len(codes)}개)")
    
    def _save_favorite(self):
        """현재 종목을 즐겨찾기에 저장"""
        codes = [c.strip() for c in self.input_codes.text().split(",") if c.strip()]
        if not codes:
            QMessageBox.warning(self, "경고", "저장할 종목이 없습니다.")
            return
        
        name, ok = QInputDialog.getText(self, "즐겨찾기 저장", "그룹 이름:")
        if ok and name:
            self.favorites[name] = codes
            # 콤보박스에 추가 (중복 확인)
            existing = [self.combo_favorites.itemText(i) for i in range(self.combo_favorites.count())]
            if f"⭐ {name}" not in existing:
                self.combo_favorites.addItem(f"⭐ {name}")
            
            # 파일 저장
            try:
                fav_file = Path(Config.DATA_DIR) / "favorites.json"
                fav_file.parent.mkdir(parents=True, exist_ok=True)
                with open(fav_file, 'w', encoding='utf-8') as f:
                    json.dump(self.favorites, f, ensure_ascii=False, indent=2)
                self.log(f"⭐ 즐겨찾기 저장: {name} ({len(codes)}개)")
            except Exception as e:
                self.log(f"❌ 즐겨찾기 저장 실패: {e}")
    
    # === 드래그앤드롭 ===
    def _drag_enter_codes(self, event):
        """드래그 진입 이벤트"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def _drop_codes(self, event):
        """드롭 이벤트 - 텍스트에서 종목코드 추출"""
        text = event.mimeData().text()
        # 숫자 6자리 패턴 추출 (종목코드)
        import re
        codes = re.findall(r'\b\d{6}\b', text)
        if codes:
            current = self.input_codes.text()
            if current:
                new_codes = current + "," + ",".join(codes)
            else:
                new_codes = ",".join(codes)
            self.input_codes.setText(new_codes)
            self.log(f"📥 드롭으로 종목 추가: {','.join(codes)}")
        event.acceptProposedAction()
    
    # === 로그 ===
    def log(self, msg):
        self.sig_log.emit(msg)
        self.logger.info(msg)
    
    def _append_log(self, msg):
        timestamp = f"[{datetime.datetime.now():%H:%M:%S}]"
        
        # 로그 레벨별 색상 및 배지
        if "❌" in msg or "실패" in msg or "오류" in msg:
            color = "#f85149"  # Red (Error)
            badge_style = "color: #f85149; font-weight: bold;"
            level_mark = "ERR"
        elif "⚠️" in msg or "경고" in msg:
            color = "#d29922"  # Orange (Warning)
            badge_style = "color: #d29922; font-weight: bold;"
            level_mark = "WRN"
        elif "✅" in msg or "성공" in msg or "완료" in msg or "🚀" in msg:
            color = "#3fb950"  # Green (Success)
            badge_style = "color: #3fb950; font-weight: bold;"
            level_mark = "SUC"
        elif "⭐" in msg or "프리셋" in msg:
            color = "#58a6ff"  # Blue (Info/Notice)
            badge_style = "color: #58a6ff; font-weight: bold;"
            level_mark = "INF"
        else:
            color = "#e6edf3"  # Default
            badge_style = "color: #8b949e;"
            level_mark = "INF"
        
        # HTML 포맷팅 (타임스탬프 | 레벨 | 메시지)
        html = f"""
        <div style="margin-bottom: 2px;">
            <span style="color: #8b949e; font-family: monospace;">{timestamp}</span>
            <span style="{badge_style} margin-left: 4px; margin-right: 4px;">[{level_mark}]</span>
            <span style="color: {color};">{msg}</span>
        </div>
        """
        
        self.log_text.append(html)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        
        # 로그 제한 (줄 수 대신 블록 수로 관리)
        if self.log_text.document().blockCount() > Config.MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(50):  # 한 번에 50줄 삭제
                cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
    
    def closeEvent(self, event):
        if self.is_running:
            reply = QMessageBox.question(self, "종료 확인", 
                                       "현재 매매가 진행 중입니다.\n강제로 종료하시겠습니까?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        self.stop_trading()
        
        # === 리소스 정리 (순서 중요) ===
        
        # 1. 타이머 정지
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
        
        # 2. WebSocket 연결 종료
        if self.ws_client:
            try:
                self.ws_client.disconnect()
            except Exception as e:
                self.logger.warning(f"WebSocket 종료 오류: {e}")
        
        # 3. REST 세션 종료
        if self.rest_client:
            try:
                self.rest_client.close()
            except Exception as e:
                self.logger.warning(f"REST 클라이언트 종료 오류: {e}")
        
        # 4. 텔레그램 정리
        if self.telegram:
            try:
                self.telegram.stop()
            except Exception:
                pass
        
        # 5. 리스크 매니저 상태 저장
        if hasattr(self, 'risk_mgr') and self.risk_mgr:
            try:
                self.risk_mgr.save_state()
            except Exception:
                pass
        
        # 6. 트레이 아이콘 숨김
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
            
        # 7. 미저장 데이터 저장
        if self._history_dirty:
            self._save_trade_history()
        
        # 8. 로깅 핸들러 정리
        for handler in self.logger.handlers[:]:
            try:
                handler.close()
                self.logger.removeHandler(handler)
            except Exception:
                pass
        
        self.logger.info("프로그램 정상 종료")
        event.accept()


def main():
    # HiDPI 지원 설정 (QApplication 생성 전에 설정해야 함)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 전역 예외 핸들러
    def exception_handler(exc_type, exc_value, exc_tb):
        import traceback
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger('Main').critical(f"치명적 오류:\n{error_msg}")
        QMessageBox.critical(None, "오류 발생", 
            f"프로그램 오류가 발생했습니다.\n\n{exc_type.__name__}: {exc_value}\n\n자세한 내용은 로그를 확인하세요.")
    
    sys.excepthook = exception_handler
    
    try:
        window = KiwoomProTrader()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "시작 오류", f"프로그램 시작 실패:\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

