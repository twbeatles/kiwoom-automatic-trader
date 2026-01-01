"""
Kiwoom Pro Algo-Trader v4.0
키움증권 OpenAPI+ 기반 전문가용 자동매매 프로그램

변동성 돌파 전략 + 이동평균 필터 + 트레일링 스톱
MACD, 볼린저밴드, ATR, 스토캐스틱RSI, DMI/ADX 지표 지원
진입 점수 시스템, 다단계 익절, 일괄 매수/매도 기능

v4.0 신규 기능:
- 전략 모듈 통합 (변동성 돌파, 골든크로스, 그리드 매매, RSI 역추세)
- 텔레그램 알림 시스템 (매수/매도/손절/일일리포트)
- 예약 스케줄러 (시간대/요일 설정)
- 수익 차트 시각화 (matplotlib)
- 백테스트 기능 (과거 데이터 기반 전략 검증)
- 페이퍼 트레이딩 (모의투자 모드)

v3.1 기능:
- Toast 알림, 일괄 매도, 설정 초기화, HiDPI 지원

v3.0 기능:
- MACD/BB/ATR 필터, DMI-ADX 추세, 다단계 익절, 프리셋 관리자
"""

import sys
import os
import json
import datetime
import time
import logging
import threading
import winreg
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QBrush, QFont, QIcon, QPalette, QTextCursor

# ============================================================================
# Optional Dependencies (v4.0)
# ============================================================================
# 전략 모듈
try:
    from strategies import get_strategy, get_strategy_list, SignalType, BaseStrategy
    STRATEGIES_MODULE_AVAILABLE = True
except ImportError:
    STRATEGIES_MODULE_AVAILABLE = False

# 텔레그램 알림
try:
    import telegram
    from telegram import Bot
    TELEGRAM_MODULE_AVAILABLE = True
except ImportError:
    TELEGRAM_MODULE_AVAILABLE = False

# matplotlib 차트
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ============================================================================
# 설정 클래스
# ============================================================================
class Config:
    """프로그램 설정 상수"""
    # 화면 번호
    SCREEN_DEPOSIT = "1002"
    SCREEN_DAILY = "1001"
    SCREEN_REAL = "2000"
    SCREEN_ORDER = "0101"
    
    # 기본값
    DEFAULT_CODES = "005930,000660,042700,005380"
    DEFAULT_BETTING_RATIO = 10.0
    DEFAULT_K_VALUE = 0.5
    DEFAULT_TS_START = 3.0
    DEFAULT_TS_STOP = 1.5
    DEFAULT_LOSS_CUT = 2.0
    
    # RSI 설정
    DEFAULT_RSI_PERIOD = 14
    DEFAULT_RSI_UPPER = 70
    DEFAULT_RSI_LOWER = 30
    DEFAULT_USE_RSI = True
    
    # MACD 설정 (v3.0 신규)
    DEFAULT_MACD_FAST = 12
    DEFAULT_MACD_SLOW = 26
    DEFAULT_MACD_SIGNAL = 9
    DEFAULT_USE_MACD = True
    
    # 볼린저 밴드 설정 (v3.0 신규)
    DEFAULT_BB_PERIOD = 20
    DEFAULT_BB_STD = 2.0
    DEFAULT_USE_BB = False
    
    # ATR 설정 (v3.0 신규)
    DEFAULT_ATR_PERIOD = 14
    DEFAULT_ATR_MULTIPLIER = 2.0
    DEFAULT_USE_ATR = False
    
    # 스토캐스틱 RSI 설정 (v3.0 신규)
    DEFAULT_STOCH_RSI_PERIOD = 14
    DEFAULT_STOCH_K_PERIOD = 3
    DEFAULT_STOCH_D_PERIOD = 3
    DEFAULT_USE_STOCH_RSI = False
    
    # DMI/ADX 설정 (v3.0 신규)
    DEFAULT_DMI_PERIOD = 14
    DEFAULT_ADX_THRESHOLD = 25
    DEFAULT_USE_DMI = False
    
    # 거래량 설정
    DEFAULT_VOLUME_MULTIPLIER = 1.5
    DEFAULT_VOLUME_PERIOD = 20
    DEFAULT_USE_VOLUME = True
    
    # 리스크 관리
    DEFAULT_MAX_DAILY_LOSS = 3.0
    DEFAULT_MAX_HOLDINGS = 5
    DEFAULT_USE_RISK_MGMT = True
    
    # 진입 점수 시스템 (v3.0 신규)
    ENTRY_SCORE_THRESHOLD = 60
    USE_ENTRY_SCORING = False
    ENTRY_WEIGHTS = {
        'target_break': 20,
        'ma_filter': 15,
        'rsi_optimal': 20,
        'macd_golden': 20,
        'volume_confirm': 15,
        'bb_position': 10,
    }
    
    # 다단계 익절 설정 (v3.0 신규)
    PARTIAL_TAKE_PROFIT = [
        {'rate': 3.0, 'sell_ratio': 30},
        {'rate': 5.0, 'sell_ratio': 30},
        {'rate': 8.0, 'sell_ratio': 20},
    ]
    DEFAULT_USE_PARTIAL_PROFIT = False
    
    # 파일 경로
    SETTINGS_FILE = "kiwoom_settings.json"
    PRESETS_FILE = "kiwoom_presets.json"
    TRADE_HISTORY_FILE = "kiwoom_trade_history.json"
    LOG_DIR = "logs"
    
    # 시간 설정
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 19
    NO_ENTRY_HOUR = 15
    
    # API 재시도 설정 (v3.0 신규)
    API_MAX_RETRIES = 3
    API_RETRY_DELAY = 1
    
    # 메모리 관리 (v3.0 신규)
    MAX_LOG_LINES = 500
    
    # 기본 프리셋 정의 (v3.0 신규)
    DEFAULT_PRESETS = {
        "aggressive": {
            "name": "🔥 공격적",
            "description": "높은 수익을 추구하지만 리스크도 높음",
            "k": 0.6, "ts_start": 2.0, "ts_stop": 1.0, "loss": 3.0,
            "betting": 15.0, "rsi_upper": 75, "max_holdings": 7
        },
        "normal": {
            "name": "⚖️ 표준",
            "description": "균형 잡힌 수익과 리스크 관리",
            "k": 0.5, "ts_start": 3.0, "ts_stop": 1.5, "loss": 2.0,
            "betting": 10.0, "rsi_upper": 70, "max_holdings": 5
        },
        "conservative": {
            "name": "🛡️ 보수적",
            "description": "안정적인 수익, 낮은 리스크",
            "k": 0.4, "ts_start": 4.0, "ts_stop": 2.0, "loss": 1.5,
            "betting": 5.0, "rsi_upper": 65, "max_holdings": 3
        }
    }
    
    # 툴팁 설명 (v3.0 신규)
    TOOLTIPS = {
        "codes": "감시할 종목 코드를 콤마(,)로 구분하여 입력합니다.\n예: 005930,000660,042700",
        "betting": "총 예수금 대비 종목당 투자 비율입니다.\n권장: 5% ~ 20%",
        "k_value": "변동성 돌파 전략의 K 계수\n목표가 = 시가 + (전일 변동폭 × K값)\n권장: 0.3 ~ 0.5",
        "ts_start": "트레일링 스톱 발동 수익률\n권장: 3% ~ 10%",
        "ts_stop": "고점 대비 하락 허용폭\n권장: 1% ~ 3%",
        "loss_cut": "절대 손절 기준\n권장: 2% ~ 5%",
        "rsi": "과매수 판단 기준 RSI\n권장: 65 ~ 75",
        "max_holdings": "동시 보유 가능 최대 종목 수\n권장: 3 ~ 7개"
    }
    
    # 도움말 콘텐츠 (v3.0 신규)
    HELP_CONTENT = {
        "quick_start": """
## 🚀 빠른 시작 가이드

### 1단계: 로그인
키움증권 OpenAPI+ 로그인 창에서 로그인합니다.

### 2단계: 종목 선택
감시할 종목 코드를 콤마로 구분하여 입력합니다.
예: 005930,000660,042700

### 3단계: 전략 선택
- 초보자: **보수적** 프리셋 권장
- 경험자: **표준** 프리셋으로 시작
- 고급: 직접 파라미터 조정

### 4단계: 매매 시작
"🚀 전략 분석 및 매매 시작" 버튼을 클릭합니다.
        """,
        "strategy": """
## 📈 전략 설명

### 변동성 돌파 전략
래리 윌리엄스(Larry Williams)가 개발한 단기 트레이딩 전략입니다.

**핵심 원리:**
- 전일 고가 - 전일 저가 = 변동폭
- 목표가 = 당일 시가 + (변동폭 × K값)
- 현재가가 목표가를 돌파하면 매수

### 트레일링 스톱
- 목표 수익률 도달 시 고점 추적 시작
- 고점 대비 설정 하락폭 발생 시 매도
        """,
        "faq": """
## ❓ 자주 묻는 질문

**Q: 15시 이후에도 매수가 되나요?**
A: 아니요, 15시 이후에는 신규 매수가 중지됩니다.

**Q: 손실이 발생하면 어떻게 되나요?**
A: 설정된 손절률에 따라 자동으로 매도됩니다.

**Q: 프로그램 종료 시 보유 종목은?**
A: 자동 청산되지 않습니다. 수동 청산이 필요합니다.
        """
    }


# ============================================================================
# 다크 테마 스타일시트 (v4.0 Enhanced)
# ============================================================================
DARK_STYLESHEET = """
/* ========== 기본 스타일 ========== */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Malgun Gothic', 'Segoe UI', 'Noto Sans KR', sans-serif;
    font-size: 12px;
}

/* ========== 그룹박스 (Glass Morphism) ========== */
QGroupBox {
    background-color: rgba(22, 27, 34, 0.8);
    border: 1px solid rgba(48, 54, 61, 0.8);
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px 15px 15px 15px;
    font-weight: bold;
    font-size: 13px;
    color: #58a6ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 10px;
    color: #79c0ff;
    background-color: #0d1117;
    border-radius: 4px;
}

/* ========== 버튼 (Gradient + Glow) ========== */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #2d333b, stop:1 #21262d);
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: 600;
    font-size: 13px;
    min-height: 18px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #3d444d, stop:1 #2d333b);
    border-color: #58a6ff;
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #21262d, stop:1 #161b22);
    padding-top: 11px;
    padding-bottom: 9px;
}

QPushButton:disabled {
    background: #21262d;
    color: #484f58;
    border-color: #21262d;
}

/* 로그인 버튼 (Cyan Accent) */
QPushButton#loginBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #238636, stop:1 #2ea043);
    border: none;
    color: white;
}

QPushButton#loginBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #2ea043, stop:1 #3fb950);
}

/* 시작 버튼 (Red Accent) */
QPushButton#startBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #da3633, stop:1 #f85149);
    border: none;
    font-size: 15px;
    font-weight: bold;
    min-width: 200px;
}

QPushButton#startBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #f85149, stop:1 #ff6b6b);
}

QPushButton#startBtn:disabled {
    background: #21262d;
}

/* 중지 버튼 */
QPushButton#stopBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #484f58, stop:1 #30363d);
}

/* ========== 입력 필드 ========== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit, QDateEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 10px 12px;
    color: #e6edf3;
    selection-background-color: #58a6ff;
    min-height: 20px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTimeEdit:focus, QDateEdit:focus {
    border: 2px solid #58a6ff;
    background-color: #161b22;
}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #484f58;
}

QComboBox::drop-down {
    border: none;
    width: 32px;
    background: transparent;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    selection-background-color: #21262d;
    color: #e6edf3;
    padding: 4px;
}

/* ========== 테이블 (Enhanced) ========== */
QTableWidget {
    background-color: #0d1117;
    alternate-background-color: #161b22;
    gridline-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    color: #e6edf3;
    selection-background-color: rgba(88, 166, 255, 0.2);
}

QTableWidget::item {
    padding: 12px 8px;
    border-bottom: 1px solid #21262d;
}

QTableWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.15);
    color: #e6edf3;
}

QTableWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.08);
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #21262d, stop:1 #161b22);
    color: #79c0ff;
    padding: 12px 8px;
    border: none;
    border-bottom: 2px solid #58a6ff;
    font-weight: bold;
    font-size: 12px;
}

/* ========== 텍스트 에디터 (로그) ========== */
QTextEdit {
    background-color: #010409;
    border: 1px solid #30363d;
    border-radius: 10px;
    color: #8b949e;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 12px;
    line-height: 1.5;
}

/* ========== 라벨 ========== */
QLabel {
    color: #8b949e;
    font-size: 12px;
}

QLabel#depositLabel {
    color: #58a6ff;
    font-weight: bold;
    font-size: 14px;
    padding: 5px 10px;
    background-color: rgba(88, 166, 255, 0.1);
    border-radius: 6px;
}

QLabel#profitLabel {
    color: #f0883e;
    font-weight: bold;
    font-size: 14px;
    padding: 5px 10px;
    background-color: rgba(240, 136, 62, 0.1);
    border-radius: 6px;
}

QLabel#profitPositive {
    color: #3fb950;
    font-weight: bold;
    font-size: 14px;
}

QLabel#profitNegative {
    color: #f85149;
    font-weight: bold;
    font-size: 14px;
}

/* ========== 상태바 ========== */
QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #161b22, stop:1 #0d1117);
    color: #8b949e;
    border-top: 1px solid #30363d;
    font-size: 11px;
    min-height: 28px;
}

QStatusBar::item {
    border: none;
}

/* ========== 탭 (Modern) ========== */
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 10px;
    background-color: rgba(22, 27, 34, 0.6);
    top: -1px;
}

QTabBar::tab {
    background: transparent;
    color: #8b949e;
    padding: 12px 24px;
    margin-right: 4px;
    border: none;
    border-bottom: 3px solid transparent;
    font-size: 12px;
    font-weight: 500;
}

QTabBar::tab:selected {
    color: #e6edf3;
    border-bottom: 3px solid #58a6ff;
    background: rgba(88, 166, 255, 0.08);
}

QTabBar::tab:hover:!selected {
    color: #e6edf3;
    background: rgba(88, 166, 255, 0.05);
    border-bottom: 3px solid #30363d;
}

/* ========== 스플리터 ========== */
QSplitter::handle {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 transparent, stop:0.4 #30363d, 
        stop:0.6 #30363d, stop:1 transparent);
    height: 6px;
}

QSplitter::handle:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 transparent, stop:0.4 #58a6ff, 
        stop:0.6 #58a6ff, stop:1 transparent);
}

/* ========== 스크롤바 ========== */
QScrollBar:vertical {
    background-color: transparent;
    width: 12px;
    margin: 4px;
}

QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #484f58;
}

QScrollBar::handle:vertical:pressed {
    background-color: #58a6ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 12px;
    margin: 4px;
}

QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #484f58;
}

/* ========== 툴팁 ========== */
QToolTip {
    background-color: #1c2128;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
}

/* ========== 체크박스 ========== */
QCheckBox {
    color: #e6edf3;
    spacing: 8px;
    font-size: 12px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #30363d;
    border-radius: 4px;
    background-color: #0d1117;
}

QCheckBox::indicator:hover {
    border-color: #58a6ff;
}

QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #238636;
}

QCheckBox::indicator:checked:hover {
    background-color: #2ea043;
    border-color: #2ea043;
}

/* ========== 메뉴 ========== */
QMenuBar {
    background-color: #010409;
    color: #e6edf3;
    border-bottom: 1px solid #21262d;
    padding: 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 8px 16px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #21262d;
}

QMenu {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 32px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #21262d;
}

QMenu::separator {
    height: 1px;
    background-color: #30363d;
    margin: 6px 12px;
}

/* ========== 프로그레스바 ========== */
QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 #238636, stop:1 #3fb950);
    border-radius: 4px;
}

/* ========== 리스트 위젯 ========== */
QListWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 6px;
    color: #e6edf3;
}

QListWidget::item {
    padding: 10px 12px;
    border-radius: 4px;
    margin: 2px 0;
}

QListWidget::item:selected {
    background-color: rgba(88, 166, 255, 0.15);
}

QListWidget::item:hover {
    background-color: rgba(88, 166, 255, 0.08);
}

/* ========== 다이얼로그 ========== */
QDialog {
    background-color: #0d1117;
}

QMessageBox {
    background-color: #161b22;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""


# ============================================================================
# Toast 알림 위젯 (v4.0 Enhanced)
# ============================================================================
class ToastWidget(QLabel):
    """비침습적 Toast 알림 위젯 - 아이콘 + 그림자 효과"""
    
    # GitHub 스타일 색상
    COLORS = {
        'success': '#238636',
        'info': '#58a6ff',
        'warning': '#d29922',
        'error': '#f85149'
    }
    
    ICONS = {
        'success': '✓',
        'info': 'ℹ',
        'warning': '⚠',
        'error': '✕'
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWordWrap(True)
        self.setMinimumWidth(320)
        self.setMaximumWidth(450)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fade_out)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(1.0)
        
        # 부드러운 페이드 애니메이션
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(400)
        self.fade_animation.finished.connect(self.hide)
    
    def show_toast(self, message, toast_type='info', duration=3500):
        """Toast 메시지 표시"""
        color = self.COLORS.get(toast_type, self.COLORS['info'])
        icon = self.ICONS.get(toast_type, 'ℹ')
        
        # 아이콘과 함께 텍스트 표시
        display_text = f"  {icon}   {message}"
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 16px 24px;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
            }}
        """)
        
        self.setText(display_text)
        self.adjustSize()
        
        # 부모 창 기준 우측 하단에 위치
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.right() - self.width() - 24
            y = parent_geo.bottom() - self.height() - 80
            self.move(x, y)
        
        self.opacity_effect.setOpacity(1.0)
        self.show()
        self.raise_()  # 맨 위로
        self.timer.start(duration)
    
    def fade_out(self):
        """부드러운 페이드 아웃 효과"""
        self.timer.stop()
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()


# ============================================================================
# 프리셋 관리 다이얼로그 (v3.0 신규)
# ============================================================================
class PresetManagerDialog(QDialog):
    """사용자 정의 프리셋 관리 다이얼로그"""
    
    def __init__(self, parent=None, current_values=None):
        super().__init__(parent)
        self.current_values = current_values or {}
        self.presets = self.load_presets()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("📋 프리셋 관리")
        self.setFixedSize(700, 600)
        self.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 프리셋 목록
        group_list = QGroupBox("저장된 프리셋")
        list_layout = QVBoxLayout()
        
        self.preset_list = QListWidget()
        self.preset_list.itemClicked.connect(self.on_preset_selected)
        self.refresh_preset_list()
        list_layout.addWidget(self.preset_list)
        
        self.detail_label = QLabel("프리셋을 선택하면 상세 정보가 표시됩니다.")
        self.detail_label.setStyleSheet("padding: 10px; background-color: #16213e; border-radius: 5px;")
        self.detail_label.setWordWrap(True)
        list_layout.addWidget(self.detail_label)
        
        group_list.setLayout(list_layout)
        layout.addWidget(group_list)
        
        # 새 프리셋 저장
        group_new = QGroupBox("새 프리셋 저장")
        new_layout = QHBoxLayout()
        new_layout.addWidget(QLabel("이름:"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("프리셋 이름 입력")
        new_layout.addWidget(self.input_name)
        btn_save = QPushButton("💾 현재 설정 저장")
        btn_save.clicked.connect(self.save_current_preset)
        new_layout.addWidget(btn_save)
        group_new.setLayout(new_layout)
        layout.addWidget(group_new)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("🗑️ 선택 삭제")
        btn_delete.clicked.connect(self.delete_preset)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch(1)
        btn_apply = QPushButton("✅ 선택 적용")
        btn_apply.clicked.connect(self.apply_preset)
        btn_layout.addWidget(btn_apply)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def load_presets(self):
        presets = dict(Config.DEFAULT_PRESETS)
        try:
            if os.path.exists(Config.PRESETS_FILE):
                with open(Config.PRESETS_FILE, 'r', encoding='utf-8') as f:
                    user_presets = json.load(f)
                    presets.update(user_presets)
        except Exception:
            pass
        return presets
    
    def save_presets_to_file(self):
        user_presets = {k: v for k, v in self.presets.items() if k not in Config.DEFAULT_PRESETS}
        try:
            with open(Config.PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_presets, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def refresh_preset_list(self):
        self.preset_list.clear()
        for key, preset in self.presets.items():
            name = preset.get('name', key)
            is_default = key in Config.DEFAULT_PRESETS
            prefix = "[기본] " if is_default else "[사용자] "
            item = QListWidgetItem(prefix + name)
            item.setData(Qt.UserRole, key)
            if is_default:
                item.setForeground(QColor("#90e0ef"))
            else:
                item.setForeground(QColor("#f72585"))
            self.preset_list.addItem(item)
    
    def on_preset_selected(self, item):
        key = item.data(Qt.UserRole)
        preset = self.presets.get(key, {})
        desc = preset.get('description', '설명 없음')
        details = f"<b>{preset.get('name', key)}</b><br><br>{desc}<br><br><b>설정값:</b><br>"
        details += f"• K값: {preset.get('k', '-')}<br>"
        details += f"• TS 발동: {preset.get('ts_start', '-')}%<br>"
        details += f"• TS 하락폭: {preset.get('ts_stop', '-')}%<br>"
        details += f"• 손절률: {preset.get('loss', '-')}%"
        self.detail_label.setText(details)
    
    def save_current_preset(self):
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "경고", "프리셋 이름을 입력해주세요.")
            return
        key = "custom_" + name.replace(" ", "_").lower()
        if key in Config.DEFAULT_PRESETS:
            QMessageBox.warning(self, "경고", "기본 프리셋과 같은 이름은 사용할 수 없습니다.")
            return
        self.presets[key] = {"name": "⭐ " + name, "description": f"사용자 정의 ({datetime.datetime.now().strftime('%Y-%m-%d')})", **self.current_values}
        self.save_presets_to_file()
        self.refresh_preset_list()
        self.input_name.clear()
        QMessageBox.information(self, "완료", f"'{name}' 프리셋이 저장되었습니다.")
    
    def delete_preset(self):
        item = self.preset_list.currentItem()
        if not item:
            return
        key = item.data(Qt.UserRole)
        if key in Config.DEFAULT_PRESETS:
            QMessageBox.warning(self, "경고", "기본 프리셋은 삭제할 수 없습니다.")
            return
        reply = QMessageBox.question(self, "확인", f"프리셋을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.presets[key]
            self.save_presets_to_file()
            self.refresh_preset_list()
    
    def apply_preset(self):
        item = self.preset_list.currentItem()
        if not item:
            QMessageBox.warning(self, "경고", "적용할 프리셋을 선택해주세요.")
            return
        key = item.data(Qt.UserRole)
        self.selected_preset = self.presets.get(key)
        self.accept()
    
    def get_selected_preset(self):
        return getattr(self, 'selected_preset', None)


# ============================================================================
# 도움말 다이얼로그 (v3.0 신규)
# ============================================================================
class HelpDialog(QDialog):
    """인앱 도움말 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("📚 도움말")
        self.setFixedSize(800, 700)
        self.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        for key, title in [("quick_start", "🚀 빠른 시작"), ("strategy", "📈 전략 설명"), ("faq", "❓ FAQ")]:
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setHtml(self.markdown_to_html(Config.HELP_CONTENT[key]))
            tabs.addTab(text_edit, title)
        
        layout.addWidget(tabs)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
    
    def markdown_to_html(self, md_text):
        import re
        html = md_text.strip()
        html = html.replace("## ", "<h2>").replace("\n### ", "</h2>\n<h3>")
        html = html.replace("### ", "<h3>")
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        html = html.replace("\n- ", "\n• ")
        html = html.replace("\n\n", "</p><p>").replace("\n", "<br>")
        return f"<div style='font-size:13px;line-height:1.6;'><p>{html}</p></div>"


# ============================================================================
# 시스템 설정 다이얼로그 (v3.0 신규)
# ============================================================================
class SettingsDialog(QDialog):
    """시스템 설정 다이얼로그"""
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("⚙️ 시스템 설정")
        self.setFixedSize(500, 400)
        self.setStyleSheet(DARK_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 시작 설정
        group_startup = QGroupBox("🚀 시작 설정")
        startup_layout = QVBoxLayout()
        self.chk_run_at_startup = QCheckBox("Windows 시작 시 자동 실행")
        self.chk_run_at_startup.setChecked(self.settings.get('run_at_startup', False))
        startup_layout.addWidget(self.chk_run_at_startup)
        self.chk_auto_connect = QCheckBox("시작 시 자동 로그인 시도")
        self.chk_auto_connect.setChecked(self.settings.get('auto_connect', False))
        startup_layout.addWidget(self.chk_auto_connect)
        group_startup.setLayout(startup_layout)
        layout.addWidget(group_startup)
        
        # 알림 설정
        group_notify = QGroupBox("🔔 알림 설정")
        notify_layout = QVBoxLayout()
        self.chk_sound_enabled = QCheckBox("거래 체결 시 소리 재생")
        self.chk_sound_enabled.setChecked(self.settings.get('sound_enabled', False))
        notify_layout.addWidget(self.chk_sound_enabled)
        group_notify.setLayout(notify_layout)
        layout.addWidget(group_notify)
        
        layout.addStretch(1)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(btn_save)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def get_settings(self):
        return {
            'run_at_startup': self.chk_run_at_startup.isChecked(),
            'auto_connect': self.chk_auto_connect.isChecked(),
            'sound_enabled': self.chk_sound_enabled.isChecked()
        }


# ============================================================================
# 메인 트레이더 클래스
# ============================================================================
class KiwoomProTrader(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 내부 변수 초기화
        self.universe = {} 
        self.deposit = 0
        self.initial_deposit = 0  # 당일 시작 예수금 (손실률 계산용)
        self.total_realized_profit = 0  # 누적 실현손익
        self.trade_count = 0  # 거래 횟수
        self.win_count = 0  # 이익 거래 횟수
        self.req_queue = []
        self.is_running = False
        self.is_connected = False
        self.time_cut_executed = False  # 시간 청산 실행 여부
        self.daily_loss_triggered = False  # 일일 손실 한도 도달 여부
        
        # v3.0 신규 변수
        self.trade_history = []  # 거래 히스토리
        self.system_settings = {
            'run_at_startup': False,
            'auto_connect': False,
            'sound_enabled': False
        }
        self.price_history = {}  # 종목별 가격 이력
        
        # 로깅 설정
        self.setup_logging()
        
        # 거래 히스토리 로드
        self.load_trade_history()
        
        # UI 초기화
        self.init_ui()
        
        # 메뉴바 생성
        self.create_menu_bar()
        
        # Kiwoom API 설정
        self.setup_kiwoom_api()
        
        # 타이머 설정
        self.setup_timers()
        
        # 시스템 트레이 설정
        self.init_tray_icon()
        
        # 설정 불러오기
        self.load_settings()
        
        # Toast 알림 위젯 초기화 (v3.1 신규)
        self.toast = ToastWidget(self)
        
        self.logger.info("프로그램 초기화 완료 (v4.0)")

    def setup_logging(self):
        """로깅 시스템 설정"""
        log_dir = Path(Config.LOG_DIR)
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"trader_{datetime.datetime.now().strftime('%Y%m%d')}.log"
        
        self.logger = logging.getLogger('KiwoomTrader')
        self.logger.setLevel(logging.DEBUG)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("Kiwoom Pro Algo-Trader v4.0 [전문가용 자동매매]")
        self.setGeometry(100, 100, 1300, 950)
        self.setMinimumSize(1100, 800)
        self.setStyleSheet(DARK_STYLESHEET)
        
        # 메인 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 상단: 대시보드
        main_layout.addWidget(self.create_dashboard())
        
        # 중간: 탭 위젯 (전략 설정 + 통계)
        main_layout.addWidget(self.create_tab_widget())
        
        # 하단: 스플리터 (테이블 + 로그)
        main_layout.addWidget(self.create_splitter())
        
        # 상태바
        self.create_statusbar()

    def create_dashboard(self):
        """대시보드 생성"""
        group_dash = QGroupBox("📊 Trading Dashboard")
        layout_dash = QHBoxLayout()
        layout_dash.setSpacing(15)
        
        # 접속 버튼
        self.btn_login = QPushButton("🔌 시스템 접속")
        self.btn_login.setObjectName("loginBtn")
        self.btn_login.setMinimumSize(140, 45)
        self.btn_login.clicked.connect(self.login)
        self.btn_login.setToolTip("키움증권 OpenAPI+에 로그인합니다")
        
        # 계좌 선택
        self.combo_acc = QComboBox()
        self.combo_acc.setMinimumWidth(180)
        self.combo_acc.currentIndexChanged.connect(self.get_deposit_info)
        self.combo_acc.setToolTip("거래에 사용할 계좌를 선택합니다")
        
        # 예수금 표시
        self.lbl_deposit = QLabel("💰 주문가능금액: 0 원")
        self.lbl_deposit.setObjectName("depositLabel")
        
        # 실현손익 표시
        self.lbl_total_profit = QLabel("📈 당일 실현손익: 0 원")
        self.lbl_total_profit.setObjectName("profitLabel")
        
        # 연결 상태 표시
        self.lbl_connection = QLabel("● 연결 대기")
        self.lbl_connection.setStyleSheet("color: #ffc107; font-weight: bold;")
        
        layout_dash.addWidget(self.btn_login)
        layout_dash.addWidget(QLabel("계좌:"))
        layout_dash.addWidget(self.combo_acc)
        layout_dash.addSpacing(20)
        layout_dash.addWidget(self.lbl_deposit)
        layout_dash.addSpacing(20)
        layout_dash.addWidget(self.lbl_total_profit)
        layout_dash.addStretch(1)
        
        # 일괄 매도 버튼 (v3.1 신규)
        self.btn_batch_sell = QPushButton("📤 일괄 매도")
        self.btn_batch_sell.setStyleSheet("background-color: #dc3545;")
        self.btn_batch_sell.clicked.connect(self.execute_batch_sell)
        self.btn_batch_sell.setToolTip("보유 중인 모든 종목을 시장가로 매도합니다")
        self.btn_batch_sell.setEnabled(False)
        layout_dash.addWidget(self.btn_batch_sell)
        layout_dash.addSpacing(10)
        
        layout_dash.addWidget(self.lbl_connection)
        
        group_dash.setLayout(layout_dash)
        return group_dash

    def create_tab_widget(self):
        """탭 위젯 생성"""
        tab_widget = QTabWidget()
        
        # 전략 설정 탭
        tab_widget.addTab(self.create_strategy_tab(), "⚙️ 전략 설정")
        
        # 고급 설정 탭
        tab_widget.addTab(self.create_advanced_tab(), "🔬 고급 설정")
        
        # 통계 탭
        tab_widget.addTab(self.create_statistics_tab(), "📊 거래 통계")
        
        # 거래 내역 탭
        tab_widget.addTab(self.create_history_tab(), "📝 거래 내역")
        
        # === v4.0 신규 탭 ===
        # 텔레그램 알림 탭
        tab_widget.addTab(self.create_telegram_tab(), "📱 텔레그램")
        
        # 예약 스케줄러 탭
        tab_widget.addTab(self.create_scheduler_tab(), "⏰ 스케줄러")
        
        # 수익 차트 탭
        tab_widget.addTab(self.create_chart_tab(), "📈 차트")
        
        # 백테스트 탭
        tab_widget.addTab(self.create_backtest_tab(), "🧪 백테스트")
        
        # 페이퍼 트레이딩 탭
        tab_widget.addTab(self.create_paper_trading_tab(), "🎮 모의투자")
        
        return tab_widget

    def create_strategy_tab(self):
        """전략 설정 탭 생성"""
        widget = QWidget()
        layout_set = QGridLayout(widget)
        layout_set.setSpacing(12)
        layout_set.setContentsMargins(15, 15, 15, 15)
        
        # 감시 종목
        layout_set.addWidget(QLabel("📋 감시 종목 (콤마 구분):"), 0, 0)
        self.input_codes = QLineEdit(Config.DEFAULT_CODES)
        self.input_codes.setPlaceholderText("예: 005930,000660,042700")
        self.input_codes.setToolTip("감시할 종목 코드를 콤마(,)로 구분하여 입력합니다")
        layout_set.addWidget(self.input_codes, 0, 1, 1, 5)
        
        # 투자 비중
        layout_set.addWidget(QLabel("💵 종목당 투자비중:"), 1, 0)
        self.spin_betting = QDoubleSpinBox()
        self.spin_betting.setRange(1, 100)
        self.spin_betting.setValue(Config.DEFAULT_BETTING_RATIO)
        self.spin_betting.setSuffix(" %")
        self.spin_betting.setToolTip("각 종목에 투자할 예수금의 비율")
        layout_set.addWidget(self.spin_betting, 1, 1)
        
        # K값
        layout_set.addWidget(QLabel("📐 변동성 K값:"), 1, 2)
        self.spin_k = QDoubleSpinBox()
        self.spin_k.setRange(0.1, 1.0)
        self.spin_k.setSingleStep(0.1)
        self.spin_k.setValue(Config.DEFAULT_K_VALUE)
        self.spin_k.setToolTip("변동성 돌파 전략의 K 계수 (0.5 권장)")
        layout_set.addWidget(self.spin_k, 1, 3)
        
        # 빈 공간
        layout_set.addWidget(QLabel(""), 1, 4)
        layout_set.addWidget(QLabel(""), 1, 5)
        
        # 트레일링 스톱 발동
        layout_set.addWidget(QLabel("🎯 TS 발동 수익률:"), 2, 0)
        self.spin_ts_start = QDoubleSpinBox()
        self.spin_ts_start.setRange(0.5, 20.0)
        self.spin_ts_start.setValue(Config.DEFAULT_TS_START)
        self.spin_ts_start.setSuffix(" %")
        self.spin_ts_start.setToolTip("트레일링 스톱이 활성화되는 최소 수익률")
        layout_set.addWidget(self.spin_ts_start, 2, 1)
        
        # 트레일링 스톱 하락폭
        layout_set.addWidget(QLabel("📉 TS 하락폭:"), 2, 2)
        self.spin_ts_stop = QDoubleSpinBox()
        self.spin_ts_stop.setRange(0.5, 10.0)
        self.spin_ts_stop.setValue(Config.DEFAULT_TS_STOP)
        self.spin_ts_stop.setSuffix(" %")
        self.spin_ts_stop.setToolTip("고점 대비 이만큼 하락하면 매도")
        layout_set.addWidget(self.spin_ts_stop, 2, 3)
        
        # 손절률
        layout_set.addWidget(QLabel("🛑 절대 손절률:"), 2, 4)
        self.spin_loss = QDoubleSpinBox()
        self.spin_loss.setRange(0.5, 10.0)
        self.spin_loss.setValue(Config.DEFAULT_LOSS_CUT)
        self.spin_loss.setSuffix(" %")
        self.spin_loss.setToolTip("이 비율 이상 손실 시 강제 매도")
        layout_set.addWidget(self.spin_loss, 2, 5)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_save = QPushButton("💾 설정 저장")
        self.btn_save.clicked.connect(self.save_settings)
        
        self.btn_reset = QPushButton("🔄 초기화")
        self.btn_reset.clicked.connect(self.reset_to_defaults)
        self.btn_reset.setToolTip("모든 설정을 기본값으로 초기화합니다")
        
        self.btn_start = QPushButton("🚀 전략 분석 및 매매 시작")
        self.btn_start.setObjectName("startBtn")
        self.btn_start.setMinimumSize(250, 50)
        self.btn_start.clicked.connect(self.start_trading)
        self.btn_start.setEnabled(False)
        
        self.btn_stop = QPushButton("⏹️ 매매 중지")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setMinimumSize(120, 50)
        self.btn_stop.clicked.connect(self.stop_trading)
        self.btn_stop.setEnabled(False)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        
        layout_set.addLayout(btn_layout, 3, 0, 1, 6)
        
        return widget

    def create_advanced_tab(self):
        """고급 설정 탭 생성 - RSI, 거래량, 리스크 관리"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === RSI 필터 그룹 ===
        group_rsi = QGroupBox("📈 RSI 필터")
        rsi_layout = QGridLayout()
        
        self.chk_use_rsi = QCheckBox("RSI 필터 사용")
        self.chk_use_rsi.setChecked(Config.DEFAULT_USE_RSI)
        self.chk_use_rsi.setToolTip("RSI 과매수 구간 진입 방지")
        rsi_layout.addWidget(self.chk_use_rsi, 0, 0, 1, 2)
        
        rsi_layout.addWidget(QLabel("RSI 상한선:"), 1, 0)
        self.spin_rsi_upper = QSpinBox()
        self.spin_rsi_upper.setRange(50, 90)
        self.spin_rsi_upper.setValue(Config.DEFAULT_RSI_UPPER)
        self.spin_rsi_upper.setToolTip("이 값 이상이면 진입 금지 (과매수)")
        rsi_layout.addWidget(self.spin_rsi_upper, 1, 1)
        
        rsi_layout.addWidget(QLabel("RSI 기간:"), 1, 2)
        self.spin_rsi_period = QSpinBox()
        self.spin_rsi_period.setRange(5, 30)
        self.spin_rsi_period.setValue(Config.DEFAULT_RSI_PERIOD)
        rsi_layout.addWidget(self.spin_rsi_period, 1, 3)
        
        group_rsi.setLayout(rsi_layout)
        layout.addWidget(group_rsi)
        
        # === MACD 필터 그룹 (v3.0 신규) ===
        group_macd = QGroupBox("📉 MACD 필터")
        macd_layout = QGridLayout()
        
        self.chk_use_macd = QCheckBox("MACD 필터 사용")
        self.chk_use_macd.setChecked(Config.DEFAULT_USE_MACD)
        self.chk_use_macd.setToolTip("MACD > Signal (상승 추세) 일 때만 진입")
        macd_layout.addWidget(self.chk_use_macd, 0, 0, 1, 2)
        group_macd.setLayout(macd_layout)
        layout.addWidget(group_macd)

        # === 볼린저 밴드 필터 (v3.0 신규) ===
        group_bb = QGroupBox("📊 볼린저 밴드")
        bb_layout = QGridLayout()
        self.chk_use_bb = QCheckBox("밴드 하단 돌파 시 진입")
        self.chk_use_bb.setToolTip("현재가가 볼린저 밴드 하단보다 낮을 때 (저점 매수) 진입 허용\n또는 밴드 폭이 좁아졌을 때 등 전략 변형 가능")
        bb_layout.addWidget(self.chk_use_bb, 0, 0, 1, 2)
        
        bb_layout.addWidget(QLabel("승수(k):"), 1, 0)
        self.spin_bb_k = QDoubleSpinBox()
        self.spin_bb_k.setRange(1.0, 4.0)
        self.spin_bb_k.setValue(2.0)
        bb_layout.addWidget(self.spin_bb_k, 1, 1)
        group_bb.setLayout(bb_layout)
        layout.addWidget(group_bb)
        
        # === DMI/ADX 필터 (v3.0 신규) ===
        group_dmi = QGroupBox("📈 DMI/ADX 추세")
        dmi_layout = QGridLayout()
        self.chk_use_dmi = QCheckBox("P-DI > M-DI (상승 추세)")
        dmi_layout.addWidget(self.chk_use_dmi, 0, 0, 1, 2)
        
        dmi_layout.addWidget(QLabel("ADX 기준:"), 1, 0)
        self.spin_adx = QDoubleSpinBox()
        self.spin_adx.setRange(0, 50)
        self.spin_adx.setValue(20)
        self.spin_adx.setToolTip("ADX가 이 값 이상일 때 강한 추세로 판단")
        dmi_layout.addWidget(self.spin_adx, 1, 1)
        group_dmi.setLayout(dmi_layout)
        layout.addWidget(group_dmi)
        
        # === ATR 필터 (v3.0 신규) ===
        group_atr = QGroupBox("📉 ATR 동적 손절")
        atr_layout = QGridLayout()
        self.chk_use_atr = QCheckBox("ATR 기반 손절 사용")
        self.chk_use_atr.setToolTip("고정 손절률 대신 ATR(변동성) 기반으로 손절폭을 설정합니다.\n손절가 = 매수가 - (ATR × 승수)")
        atr_layout.addWidget(self.chk_use_atr, 0, 0, 1, 2)
        
        atr_layout.addWidget(QLabel("ATR 승수:"), 1, 0)
        self.spin_atr_mult = QDoubleSpinBox()
        self.spin_atr_mult.setRange(1.0, 5.0)
        self.spin_atr_mult.setValue(Config.DEFAULT_ATR_MULTIPLIER)
        self.spin_atr_mult.setSingleStep(0.1)
        atr_layout.addWidget(self.spin_atr_mult, 1, 1)
        group_atr.setLayout(atr_layout)
        layout.addWidget(group_atr)
        
        # === 거래량 필터 그룹 ===
        group_vol = QGroupBox("📊 거래량 필터")
        vol_layout = QGridLayout()
        
        self.chk_use_volume = QCheckBox("거래량 필터 사용")
        self.chk_use_volume.setChecked(Config.DEFAULT_USE_VOLUME)
        self.chk_use_volume.setToolTip("5일 평균 거래량 대비 배수 이상일 때만 진입")
        vol_layout.addWidget(self.chk_use_volume, 0, 0, 1, 2)
        
        vol_layout.addWidget(QLabel("거래량 배수:"), 1, 0)
        self.spin_volume_mult = QDoubleSpinBox()
        self.spin_volume_mult.setRange(1.0, 5.0)
        self.spin_volume_mult.setSingleStep(0.1)
        self.spin_volume_mult.setValue(Config.DEFAULT_VOLUME_MULTIPLIER)
        self.spin_volume_mult.setToolTip("5일 평균 거래량의 N배 이상")
        vol_layout.addWidget(self.spin_volume_mult, 1, 1)
        
        group_vol.setLayout(vol_layout)
        layout.addWidget(group_vol)
        
        # === 리스크 관리 그룹 ===
        group_risk = QGroupBox("🛡️ 리스크 관리")
        risk_layout = QGridLayout()
        
        self.chk_use_risk = QCheckBox("리스크 관리 사용")
        self.chk_use_risk.setChecked(Config.DEFAULT_USE_RISK_MGMT)
        risk_layout.addWidget(self.chk_use_risk, 0, 0, 1, 2)
        
        risk_layout.addWidget(QLabel("일일 최대 손실률:"), 1, 0)
        self.spin_max_loss = QDoubleSpinBox()
        self.spin_max_loss.setRange(1.0, 10.0)
        self.spin_max_loss.setValue(Config.DEFAULT_MAX_DAILY_LOSS)
        self.spin_max_loss.setSuffix(" %")
        self.spin_max_loss.setToolTip("이 손실률 도달 시 당일 추가 매매 중단")
        risk_layout.addWidget(self.spin_max_loss, 1, 1)
        
        risk_layout.addWidget(QLabel("최대 보유 종목:"), 1, 2)
        self.spin_max_holdings = QSpinBox()
        self.spin_max_holdings.setRange(1, 20)
        self.spin_max_holdings.setValue(Config.DEFAULT_MAX_HOLDINGS)
        self.spin_max_holdings.setToolTip("동시 보유 가능 최대 종목 수")
        risk_layout.addWidget(self.spin_max_holdings, 1, 3)
        
        group_risk.setLayout(risk_layout)
        layout.addWidget(group_risk)
        
        # === 프리셋 그룹 ===
        group_preset = QGroupBox("📋 전략 프리셋")
        preset_layout = QHBoxLayout()
        
        btn_aggressive = QPushButton("🔥 공격적")
        btn_aggressive.clicked.connect(lambda: self.apply_preset("aggressive"))
        btn_aggressive.setToolTip("K=0.6, TS=2%, 손절=3%")
        
        btn_normal = QPushButton("⚖️ 표준")
        btn_normal.clicked.connect(lambda: self.apply_preset("normal"))
        btn_normal.setToolTip("K=0.5, TS=3%, 손절=2%")
        
        btn_conservative = QPushButton("🛡️ 보수적")
        btn_conservative.clicked.connect(lambda: self.apply_preset("conservative"))
        btn_conservative.setToolTip("K=0.4, TS=4%, 손절=1.5%")
        
        btn_manage = QPushButton("📁 프리셋 관리")
        btn_manage.clicked.connect(self.open_preset_manager)
        btn_manage.setToolTip("사용자 정의 프리셋 저장/불러오기")
        
        preset_layout.addWidget(btn_aggressive)
        preset_layout.addWidget(btn_normal)
        preset_layout.addWidget(btn_conservative)
        preset_layout.addStretch(1)
        preset_layout.addWidget(btn_manage)
        
        group_preset.setLayout(preset_layout)
        layout.addWidget(group_preset)
        
        layout.addStretch(1)
        return widget

    def create_statistics_tab(self):
        """거래 통계 탭 생성"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 통계 라벨들
        stat_style = """
            QLabel {
                background-color: #16213e;
                border: 1px solid #3d5a80;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
            }
        """
        
        # 거래 횟수
        self.stat_trades = QLabel("📊 총 거래 횟수\n0 회")
        self.stat_trades.setStyleSheet(stat_style)
        self.stat_trades.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stat_trades, 0, 0)
        
        # 승률
        self.stat_winrate = QLabel("🎯 승률\n0.0 %")
        self.stat_winrate.setStyleSheet(stat_style)
        self.stat_winrate.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stat_winrate, 0, 1)
        
        # 총 수익
        self.stat_profit = QLabel("💰 총 실현손익\n0 원")
        self.stat_profit.setStyleSheet(stat_style)
        self.stat_profit.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stat_profit, 0, 2)
        
        # 보유 종목 수
        self.stat_holdings = QLabel("📦 보유 종목\n0 개")
        self.stat_holdings.setStyleSheet(stat_style)
        self.stat_holdings.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.stat_holdings, 0, 3)
        
        # 통계 초기화 버튼
        btn_reset = QPushButton("🔄 통계 초기화")
        btn_reset.clicked.connect(self.reset_statistics)
        layout.addWidget(btn_reset, 1, 0, 1, 4)
        
        layout.setRowStretch(2, 1)
        
        return widget

    def create_history_tab(self):
        """거래 내역 탭 생성 (v3.0 신규)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 거래 내역 테이블
        self.history_table = QTableWidget()
        cols = ["시간", "종목", "구분", "가격", "수량", "금액", "손익", "사유"]
        self.history_table.setColumnCount(len(cols))
        self.history_table.setHorizontalHeaderLabels(cols)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.history_table)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        
        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self.refresh_history_table)
        btn_layout.addWidget(btn_refresh)
        
        btn_export = QPushButton("📤 CSV 내보내기")
        btn_export.clicked.connect(self.export_history_csv)
        btn_layout.addWidget(btn_export)
        
        btn_layout.addStretch(1)
        
        btn_clear = QPushButton("🗑️ 오늘 기록 삭제")
        btn_clear.clicked.connect(self.clear_today_history)
        btn_layout.addWidget(btn_clear)
        
        layout.addLayout(btn_layout)
        
        # 초기 로드
        QTimer.singleShot(100, self.refresh_history_table)
        
        return widget
    
    def refresh_history_table(self):
        """거래 내역 테이블 새로고침"""
        self.history_table.setRowCount(0)
        for record in reversed(self.trade_history[-100:]):  # 최근 100건
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            
            # 시간
            timestamp = record.get('timestamp', '')
            if 'T' in timestamp:
                time_str = timestamp.split('T')[1][:8]
                date_str = timestamp.split('T')[0][5:]
                display_time = f"{date_str} {time_str}"
            else:
                display_time = timestamp
            
            items = [
                display_time,
                record.get('name', record.get('code', '')),
                record.get('type', ''),
                f"{record.get('price', 0):,.0f}",
                str(record.get('quantity', 0)),
                f"{record.get('amount', 0):,.0f}",
                f"{record.get('profit', 0):+,.0f}",
                record.get('reason', '')
            ]
            
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignCenter)
                
                # 손익 색상
                if col == 6:
                    profit = record.get('profit', 0)
                    if profit > 0:
                        item.setForeground(QColor("#e63946"))
                    elif profit < 0:
                        item.setForeground(QColor("#4361ee"))
                
                # 구분 색상
                if col == 2:
                    if record.get('type') == '매수':
                        item.setForeground(QColor("#e63946"))
                    else:
                        item.setForeground(QColor("#4361ee"))
                
                self.history_table.setItem(row, col, item)
    
    def export_history_csv(self):
        """거래 내역 CSV 내보내기"""
        if not self.trade_history:
            QMessageBox.information(self, "알림", "내보낼 거래 내역이 없습니다.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "CSV 내보내기", 
            f"trade_history_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(["시간", "종목코드", "종목명", "구분", "가격", "수량", "금액", "손익", "사유"])
                    for record in self.trade_history:
                        writer.writerow([
                            record.get('timestamp', ''),
                            record.get('code', ''),
                            record.get('name', ''),
                            record.get('type', ''),
                            record.get('price', 0),
                            record.get('quantity', 0),
                            record.get('amount', 0),
                            record.get('profit', 0),
                            record.get('reason', '')
                        ])
                self.log(f"📤 거래 내역 CSV 저장 완료: {filename}")
                QMessageBox.information(self, "완료", f"거래 내역이 저장되었습니다.\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"CSV 저장 실패: {e}")
    
    def clear_today_history(self):
        """오늘 거래 기록 삭제"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_count = sum(1 for r in self.trade_history if r.get('timestamp', '').startswith(today))
        
        if today_count == 0:
            QMessageBox.information(self, "알림", "오늘 거래 기록이 없습니다.")
            return
        
        reply = QMessageBox.question(
            self, "확인",
            f"오늘({today}) 거래 기록 {today_count}건을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.trade_history = [r for r in self.trade_history if not r.get('timestamp', '').startswith(today)]
            self.save_trade_history()
            self.refresh_history_table()
            self.log(f"🗑️ 오늘 거래 기록 {today_count}건 삭제됨")

    def create_splitter(self):
        """스플리터 (테이블 + 로그) 생성"""
        splitter = QSplitter(Qt.Vertical)
        
        # 포트폴리오 테이블
        self.table = QTableWidget()
        cols = ["종목명", "현재가", "목표가", "MA(5)", "상태", "보유수량", "매입가", "수익률", "최고수익률", "투자금"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 로그 창
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(180)
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("로그가 여기에 표시됩니다...")
        
        splitter.addWidget(self.table)
        splitter.addWidget(self.log_text)
        splitter.setSizes([500, 180])
        
        return splitter

    def create_statusbar(self):
        """상태바 생성"""
        self.statusbar = self.statusBar()
        
        # 시간 표시
        self.status_time = QLabel()
        self.statusbar.addWidget(self.status_time)
        
        # 구분자
        self.statusbar.addWidget(QLabel(" | "))
        
        # 거래 상태
        self.status_trading = QLabel("● 대기 중")
        self.status_trading.setStyleSheet("color: #ffc107;")
        self.statusbar.addWidget(self.status_trading)
        
        # 구분자
        self.statusbar.addWidget(QLabel(" | "))
        
        # 실시간 수신 상태
        self.status_realtime = QLabel("실시간: 비활성")
        self.statusbar.addWidget(self.status_realtime)
        
        # 오른쪽 영역
        self.statusbar.addPermanentWidget(QLabel("Kiwoom Pro Algo-Trader v4.0"))

    def setup_kiwoom_api(self):
        """키움 API 설정"""
        try:
            self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
            self.kiwoom.OnEventConnect.connect(self.on_login)
            self.kiwoom.OnReceiveTrData.connect(self.on_receive_tr)
            self.kiwoom.OnReceiveRealData.connect(self.on_receive_real)
            self.kiwoom.OnReceiveChejanData.connect(self.on_chejan)
            self.kiwoom.OnReceiveMsg.connect(self.on_msg)
            self.log("키움 API 초기화 완료")
        except Exception as e:
            self.log(f"[ERROR] 키움 API 초기화 실패: {e}")
            self.logger.error(f"키움 API 초기화 실패: {e}")
            QMessageBox.critical(self, "오류", 
                "키움 OpenAPI+를 초기화할 수 없습니다.\n"
                "키움증권 OpenAPI+가 설치되어 있는지 확인해 주세요.")

    def setup_timers(self):
        """타이머 설정"""
        # TR 요청 큐 처리 타이머
        self.timer_req = QTimer(self)
        self.timer_req.timeout.connect(self.process_queue)
        
        # 시간 청산 및 UI 업데이트 타이머
        self.timer_monitor = QTimer(self)
        self.timer_monitor.start(1000)
        self.timer_monitor.timeout.connect(self.on_timer_tick)

    def on_timer_tick(self):
        """1초마다 실행되는 타이머 콜백"""
        now = datetime.datetime.now()
        
        # 상태바 시간 업데이트
        self.status_time.setText(now.strftime("%Y-%m-%d %H:%M:%S"))
        
        # 시간 청산 체크
        self.check_time_cut()

    # ------------------------------------------------------------------
    # 설정 저장/불러오기
    # ------------------------------------------------------------------
    def save_settings(self):
        """설정 저장"""
        settings = {
            "codes": self.input_codes.text(),
            "betting_ratio": self.spin_betting.value(),
            "k_value": self.spin_k.value(),
            "ts_start": self.spin_ts_start.value(),
            "ts_stop": self.spin_ts_stop.value(),
            "loss_cut": self.spin_loss.value(),
            # 고급 설정
            "use_rsi": self.chk_use_rsi.isChecked(),
            "rsi_upper": self.spin_rsi_upper.value(),
            "rsi_period": self.spin_rsi_period.value(),
            "use_volume": self.chk_use_volume.isChecked(),
            "volume_mult": self.spin_volume_mult.value(),
            "use_risk": self.chk_use_risk.isChecked(),
            "max_daily_loss": self.spin_max_loss.value(),
            "max_holdings": self.spin_max_holdings.value(),
            # v3.0 추가 설정
            "use_macd": self.chk_use_macd.isChecked(),
            "use_bb": self.chk_use_bb.isChecked(),
            "bb_k": self.spin_bb_k.value(),
            "use_dmi": self.chk_use_dmi.isChecked(),
            "adx_threshold": self.spin_adx.value(),
            "use_atr": self.chk_use_atr.isChecked(),
            "atr_mult": self.spin_atr_mult.value(),
            # v4.0 텔레그램 설정
            "telegram_token": getattr(self, 'telegram_token', ''),
            "telegram_chat_id": getattr(self, 'telegram_chat_id', ''),
            "telegram_buy": self.chk_telegram_buy.isChecked() if hasattr(self, 'chk_telegram_buy') else True,
            "telegram_sell": self.chk_telegram_sell.isChecked() if hasattr(self, 'chk_telegram_sell') else True,
            "telegram_loss": self.chk_telegram_loss.isChecked() if hasattr(self, 'chk_telegram_loss') else True,
            "telegram_daily": self.chk_telegram_daily.isChecked() if hasattr(self, 'chk_telegram_daily') else False,
            # v4.0 스케줄러 설정
            "scheduler_enabled": self.chk_scheduler_enabled.isChecked() if hasattr(self, 'chk_scheduler_enabled') else False,
            "schedule_start": self.time_schedule_start.time().toString("HH:mm") if hasattr(self, 'time_schedule_start') else "09:00",
            "schedule_end": self.time_schedule_end.time().toString("HH:mm") if hasattr(self, 'time_schedule_end') else "15:20",
            "schedule_days": [self.chk_days[i].isChecked() for i in range(7)] if hasattr(self, 'chk_days') else [True]*5 + [False]*2,
            "pause_on_volatility": self.chk_pause_on_volatility.isChecked() if hasattr(self, 'chk_pause_on_volatility') else False,
            "time_cut_enabled": self.chk_time_cut_enabled.isChecked() if hasattr(self, 'chk_time_cut_enabled') else True,
            # v4.0 페이퍼 트레이딩 설정
            "paper_mode": self.chk_paper_mode.isChecked() if hasattr(self, 'chk_paper_mode') else False,
            "paper_initial_balance": self.spin_paper_balance.value() if hasattr(self, 'spin_paper_balance') else 10000000
        }
        
        try:
            with open(Config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            self.log("✅ 설정이 저장되었습니다")
            self.logger.info("설정 저장 완료")
        except Exception as e:
            self.log(f"[ERROR] 설정 저장 실패: {e}")
            self.logger.error(f"설정 저장 실패: {e}")

    def load_settings(self):
        """설정 불러오기"""
        try:
            if os.path.exists(Config.SETTINGS_FILE):
                with open(Config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                self.input_codes.setText(settings.get("codes", Config.DEFAULT_CODES))
                self.spin_betting.setValue(settings.get("betting_ratio", Config.DEFAULT_BETTING_RATIO))
                self.spin_k.setValue(settings.get("k_value", Config.DEFAULT_K_VALUE))
                self.spin_ts_start.setValue(settings.get("ts_start", Config.DEFAULT_TS_START))
                self.spin_ts_stop.setValue(settings.get("ts_stop", Config.DEFAULT_TS_STOP))
                self.spin_loss.setValue(settings.get("loss_cut", Config.DEFAULT_LOSS_CUT))
                
                # 고급 설정 불러오기
                self.chk_use_rsi.setChecked(settings.get("use_rsi", Config.DEFAULT_USE_RSI))
                self.spin_rsi_upper.setValue(settings.get("rsi_upper", Config.DEFAULT_RSI_UPPER))
                self.spin_rsi_period.setValue(settings.get("rsi_period", Config.DEFAULT_RSI_PERIOD))
                self.chk_use_volume.setChecked(settings.get("use_volume", Config.DEFAULT_USE_VOLUME))
                self.spin_volume_mult.setValue(settings.get("volume_mult", Config.DEFAULT_VOLUME_MULTIPLIER))
                self.chk_use_risk.setChecked(settings.get("use_risk", Config.DEFAULT_USE_RISK_MGMT))
                self.spin_max_loss.setValue(settings.get("max_daily_loss", Config.DEFAULT_MAX_DAILY_LOSS))
                self.spin_max_holdings.setValue(settings.get("max_holdings", Config.DEFAULT_MAX_HOLDINGS))
                
                # v3.0 추가 설정 불러오기
                self.chk_use_macd.setChecked(settings.get("use_macd", False))
                self.chk_use_bb.setChecked(settings.get("use_bb", False))
                self.spin_bb_k.setValue(settings.get("bb_k", 2.0))
                self.chk_use_dmi.setChecked(settings.get("use_dmi", False))
                self.spin_adx.setValue(settings.get("adx_threshold", 20))
                self.chk_use_atr.setChecked(settings.get("use_atr", False))
                self.spin_atr_mult.setValue(settings.get("atr_mult", 2.0))
                
                # v4.0 텔레그램 설정 불러오기
                self.telegram_token = settings.get("telegram_token", "")
                self.telegram_chat_id = settings.get("telegram_chat_id", "")
                if hasattr(self, 'input_telegram_token') and self.telegram_token:
                    self.input_telegram_token.setText(self.telegram_token)
                if hasattr(self, 'input_telegram_chat_id') and self.telegram_chat_id:
                    self.input_telegram_chat_id.setText(self.telegram_chat_id)
                if hasattr(self, 'chk_telegram_buy'):
                    self.chk_telegram_buy.setChecked(settings.get("telegram_buy", True))
                if hasattr(self, 'chk_telegram_sell'):
                    self.chk_telegram_sell.setChecked(settings.get("telegram_sell", True))
                if hasattr(self, 'chk_telegram_loss'):
                    self.chk_telegram_loss.setChecked(settings.get("telegram_loss", True))
                if hasattr(self, 'chk_telegram_daily'):
                    self.chk_telegram_daily.setChecked(settings.get("telegram_daily", False))
                
                # v4.0 스케줄러 설정 불러오기
                if hasattr(self, 'chk_scheduler_enabled'):
                    self.chk_scheduler_enabled.setChecked(settings.get("scheduler_enabled", False))
                if hasattr(self, 'time_schedule_start'):
                    start_time = settings.get("schedule_start", "09:00")
                    self.time_schedule_start.setTime(QTime.fromString(start_time, "HH:mm"))
                if hasattr(self, 'time_schedule_end'):
                    end_time = settings.get("schedule_end", "15:20")
                    self.time_schedule_end.setTime(QTime.fromString(end_time, "HH:mm"))
                if hasattr(self, 'chk_days'):
                    days = settings.get("schedule_days", [True]*5 + [False]*2)
                    for i, checked in enumerate(days):
                        if i in self.chk_days:
                            self.chk_days[i].setChecked(checked)
                if hasattr(self, 'chk_pause_on_volatility'):
                    self.chk_pause_on_volatility.setChecked(settings.get("pause_on_volatility", False))
                if hasattr(self, 'chk_time_cut_enabled'):
                    self.chk_time_cut_enabled.setChecked(settings.get("time_cut_enabled", True))
                
                # v4.0 페이퍼 트레이딩 설정 불러오기
                if hasattr(self, 'chk_paper_mode'):
                    self.chk_paper_mode.setChecked(settings.get("paper_mode", False))
                if hasattr(self, 'spin_paper_balance'):
                    self.spin_paper_balance.setValue(settings.get("paper_initial_balance", 10000000))
                
                self.log("📂 저장된 설정을 불러왔습니다")
                self.logger.info("설정 불러오기 완료")
        except Exception as e:
            self.log(f"[WARN] 설정 불러오기 실패, 기본값 사용: {e}")
            self.logger.warning(f"설정 불러오기 실패: {e}")

    # ------------------------------------------------------------------
    # 로그인 및 계좌 정보
    # ------------------------------------------------------------------
    def login(self):
        """키움 로그인"""
        self.log("🔄 로그인 시도 중...")
        self.lbl_connection.setText("● 연결 중...")
        self.lbl_connection.setStyleSheet("color: #ffc107; font-weight: bold;")
        
        try:
            self.kiwoom.dynamicCall("CommConnect()")
        except Exception as e:
            self.log(f"[ERROR] 로그인 실패: {e}")
            self.logger.error(f"로그인 실패: {e}")
            self.lbl_connection.setText("● 연결 실패")
            self.lbl_connection.setStyleSheet("color: #e63946; font-weight: bold;")

    def on_login(self, err):
        """로그인 결과 처리"""
        try:
            if err == 0:
                self.is_connected = True
                self.log("✅ 시스템 연결 성공")
                self.logger.info("키움 로그인 성공")
                
                accs = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO").split(';')
                self.combo_acc.clear()
                self.combo_acc.addItems([x for x in accs if x])
                
                self.btn_start.setEnabled(True)
                self.btn_batch_sell.setEnabled(True)
                self.lbl_connection.setText("● 연결됨")
                self.lbl_connection.setStyleSheet("color: #00b894; font-weight: bold;")
            else:
                self.is_connected = False
                self.log(f"❌ 시스템 연결 실패 (오류코드: {err})")
                self.logger.error(f"키움 로그인 실패: {err}")
                self.lbl_connection.setText("● 연결 실패")
                self.lbl_connection.setStyleSheet("color: #e63946; font-weight: bold;")
        except Exception as e:
            self.log(f"[ERROR] 로그인 처리 중 오류: {e}")
            self.logger.error(f"로그인 처리 중 오류: {e}")

    def get_deposit_info(self):
        """예수금 조회"""
        acc = self.combo_acc.currentText()
        if not acc:
            return
            
        try:
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "계좌번호", acc)
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2")
            self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", 
                                   "예수금조회", "opw00001", 0, Config.SCREEN_DEPOSIT)
        except Exception as e:
            self.log(f"[ERROR] 예수금 조회 실패: {e}")
            self.logger.error(f"예수금 조회 실패: {e}")

    # ------------------------------------------------------------------
    # 매매 시작/중지
    # ------------------------------------------------------------------
    def start_trading(self):
        """매매 시작"""
        codes_text = self.input_codes.text().replace(" ", "")
        codes = [c for c in codes_text.split(',') if c]
        
        if not codes:
            QMessageBox.warning(self, "경고", "감시할 종목 코드를 입력해 주세요.")
            return
        
        # 종목 코드 검증
        invalid_codes = [c for c in codes if len(c) != 6 or not c.isdigit()]
        if invalid_codes:
            QMessageBox.warning(self, "경고", 
                f"잘못된 종목 코드가 있습니다: {', '.join(invalid_codes)}\n"
                "종목 코드는 6자리 숫자여야 합니다.")
            return
        
        self.universe = {}
        self.table.setRowCount(0)
        self.req_queue = []
        self.is_running = True
        self.time_cut_executed = False
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_trading.setText("● 분석 중")
        self.status_trading.setStyleSheet("color: #00b4d8;")
        
        for i, code in enumerate(codes):
            try:
                name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code)
                if not name:
                    self.log(f"[WARN] 종목 코드 {code}를 찾을 수 없습니다")
                    continue
                
                # 종목 데이터 구조체
                self.universe[code] = {
                    'name': name,
                    'state': '분석중',
                    'row': len(self.universe),
                    'target': 0,
                    'ma5': 0,
                    'current': 0,
                    'qty': 0,
                    'buy_price': 0,
                    'invest_amt': 0,
                    'high_since_buy': 0,
                    'max_profit_rate': 0.0
                }
                
                row = self.universe[code]['row']
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(f"{name}({code})"))
                self.set_table_item(row, 4, "⏳ 분석중", "#ffc107")
                
                self.req_queue.append(code)
                
            except Exception as e:
                self.log(f"[ERROR] 종목 {code} 초기화 실패: {e}")
                self.logger.error(f"종목 {code} 초기화 실패: {e}")
        
        self.log(f"🚀 포트폴리오 분석 시작 (총 {len(self.universe)} 종목)")
        self.logger.info(f"매매 시작: {len(self.universe)} 종목")
        self.timer_req.start(250)

    def stop_trading(self):
        """매매 중지"""
        self.is_running = False
        self.timer_req.stop()
        
        # 실시간 해제
        try:
            self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", 
                                   Config.SCREEN_REAL, "ALL")
        except Exception:
            pass
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_trading.setText("● 중지됨")
        self.status_trading.setStyleSheet("color: #e63946;")
        self.status_realtime.setText("실시간: 비활성")
        
        self.log("⏹️ 매매가 중지되었습니다")
        self.logger.info("매매 중지")

    def process_queue(self):
        """TR 요청 큐 처리"""
        if self.req_queue:
            code = self.req_queue.pop(0)
            now = datetime.datetime.now().strftime("%Y%m%d")
            
            try:
                self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
                self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "기준일자", now)
                self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
                self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", 
                                       f"일봉_{code}", "opt10081", 0, Config.SCREEN_DAILY)
            except Exception as e:
                self.log(f"[ERROR] 일봉 조회 실패 ({code}): {e}")
                self.logger.error(f"일봉 조회 실패 ({code}): {e}")
        else:
            self.timer_req.stop()
            self.register_realtime()

    # ------------------------------------------------------------------
    # TR 데이터 처리
    # ------------------------------------------------------------------
    def on_receive_tr(self, scr, rqname, trcode, record, next):
        """TR 데이터 수신"""
        try:
            if rqname == "예수금조회":
                self._handle_deposit_tr(trcode)
            elif "일봉_" in rqname:
                self._handle_daily_tr(rqname, trcode)
        except Exception as e:
            self.log(f"[ERROR] TR 처리 중 오류: {e}")
            self.logger.error(f"TR 처리 중 오류: {e}")

    def _handle_deposit_tr(self, trcode):
        """예수금 조회 처리"""
        try:
            d2_str = self.kiwoom.dynamicCall(
                "GetCommData(QString, QString, int, QString)", 
                trcode, "", 0, "d+2추정예수금"
            ).strip()
            
            self.deposit = int(d2_str) if d2_str else 0
            self.lbl_deposit.setText(f"💰 주문가능금액: {self.deposit:,.0f} 원")
            self.logger.info(f"예수금 조회 완료: {self.deposit:,}원")
        except Exception as e:
            self.log(f"[ERROR] 예수금 파싱 실패: {e}")
            self.logger.error(f"예수금 파싱 실패: {e}")

    def _handle_daily_tr(self, rqname, trcode):
        """일봉 데이터 처리"""
        code = rqname.split('_')[1]
        
        if code not in self.universe:
            return
        
        try:
            # 가격 데이터 파싱 (당일 시가, 전일 고가/저가)
            today_open = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", 0, "시가").strip() or "0"))
            prev_high = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", 1, "고가").strip() or "0"))
            prev_low = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", 1, "저가").strip() or "0"))
            
            # --- 변동성 돌파 전략 목표가 계산 ---
            volatility = prev_high - prev_low
            k = self.spin_k.value()
            target_price = today_open + (volatility * k)
            
            # --- 과거 데이터 수집 (지표 계산용, 최대 100일) ---
            price_history = []
            high_history = []
            low_history = []
            
            cnt = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            for i in range(min(cnt, 100)):
                # 수정주가 등 고려하여 "현재가" 가져오기
                close = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", i, "현재가").strip() or "0"))
                high = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", i, "고가").strip() or "0"))
                low = abs(int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", i, "저가").strip() or "0"))
                
                price_history.append(close)
                high_history.append(high)
                low_history.append(low)
            
            # 리스트 뒤집기: [오늘, 어제, 그제...] -> [..., 그제, 어제, 오늘]
            # 지표 계산 시 list[-1]이 최신이어야 함
            price_history.reverse()
            high_history.reverse()
            low_history.reverse()
            
            # 정보 저장
            info = self.universe[code]
            info['price_history'] = price_history
            info['high_history'] = high_history
            info['low_history'] = low_history
            
            # --- 이동평균(5일) 계산 : 전일 기준 5일 평균 ---
            # price_history에는 [..., Day-5, Day-4, Day-3, Day-2, Day-1, Day-0(오늘)]
            # 전일 기준 5일 이동평균: slice [-6:-1]
            if len(price_history) >= 6:
                ma5_list = price_history[-6:-1]
                ma5 = sum(ma5_list) / len(ma5_list)
            else:
                ma5 = 0
            
            # 데이터 저장
            info = self.universe[code]
            info['target'] = int(target_price)
            info['ma5'] = int(ma5)
            info['state'] = '감시중'
            
            # UI 업데이트
            row = info['row']
            self.table.setItem(row, 2, QTableWidgetItem(f"{int(target_price):,}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{int(ma5):,}"))
            self.set_table_item(row, 4, "👀 감시중", "#00b894")
            
            self.log(f"[{info['name']}] 목표가:{int(target_price):,}, MA5:{int(ma5):,}")
            self.logger.info(f"{info['name']} 분석 완료: 목표가={target_price}, MA5={ma5}")
            
        except Exception as e:
            self.log(f"[ERROR] 일봉 분석 실패 ({code}): {e}")
            self.logger.error(f"일봉 분석 실패 ({code}): {e}")

    # ------------------------------------------------------------------
    # 실시간 데이터 처리
    # ------------------------------------------------------------------
    def register_realtime(self):
        """실시간 시세 등록"""
        if not self.universe:
            return
        
        codes = ";".join(self.universe.keys())
        
        try:
            self.kiwoom.dynamicCall(
                "SetRealReg(QString, QString, QString, QString)", 
                Config.SCREEN_REAL, codes, "10;12;20", "0"
            )
            
            self.status_trading.setText("● 매매 중")
            self.status_trading.setStyleSheet("color: #00b894;")
            self.status_realtime.setText(f"실시간: {len(self.universe)}종목 감시")
            
            self.log("🔴 실시간 시세 수신 시작 (Trading Active)")
            self.logger.info("실시간 시세 등록 완료")
        except Exception as e:
            self.log(f"[ERROR] 실시간 등록 실패: {e}")
            self.logger.error(f"실시간 등록 실패: {e}")

    def on_receive_real(self, code, real_type, real_data):
        """실시간 데이터 수신"""
        if real_type != "주식체결" or code not in self.universe:
            return
        
        try:
            curr = abs(int(self.kiwoom.dynamicCall(
                "GetCommRealData(QString, int)", code, 10
            )))
            
            info = self.universe[code]
            info['current'] = curr
            
            # 현재가 업데이트
            self.table.setItem(info['row'], 1, QTableWidgetItem(f"{curr:,}"))
            
            # 매수 로직
            if info['state'] == '감시중' and info['qty'] == 0 and self.is_running:
                self._check_buy_condition(code, curr, info)
            
            # 매도 로직
            elif info['state'] == '보유중' and info['qty'] > 0:
                self._check_sell_condition(code, curr, info)
                
        except Exception as e:
            self.logger.error(f"실시간 처리 중 오류 ({code}): {e}")

    def _check_buy_condition(self, code, curr, info):
        """매수 조건 확인 (확장된 필터 포함)"""
        # 1. 목표가 돌파
        if curr < info['target']:
            return
        
        # 2. 추세 필터 (MA5 위)
        if curr < info['ma5']:
            return
        
        # 3. 15시 이전
        if datetime.datetime.now().hour >= Config.NO_ENTRY_HOUR:
            self.log(f"[{info['name']}] 15시 이후 진입 금지")
            return
        
        # 3.5. 스케줄러 체크 (v4.0 신규)
        if not self.is_trading_allowed_by_schedule():
            self.log(f"[{info['name']}] 스케줄러에 의해 매매 제한")
            return
        
        # 4. RSI 필터 (과매수 회피)
        if not self.check_rsi_condition(code):
            return
        
        # 5. 거래량 필터
        if not self.check_volume_condition(code):
            self.log(f"[{info['name']}] 거래량 부족으로 진입 보류")
            return
        
        # 6. MACD 필터 (v3.0 신규)
        if not self.check_macd_condition(code):
            return
            
        # 7. 볼린저 밴드 필터
        if not self.check_bollinger_condition(code):
            return

        # 8. DMI/ADX 필터
        if not self.check_dmi_condition(code):
            return
        
        # 9. 리스크 관리 (일일 손실 한도, 최대 보유 종목)
        if not self.check_risk_limits():
            return
        
        # 매수 실행
        self.execute_buy(code, curr)

    def _check_sell_condition(self, code, curr, info):
        """매도 조건 확인"""
        buy_p = info['buy_price']
        if buy_p == 0:
            return
        
        profit_rate = (curr - buy_p) / buy_p * 100
        
        # 최고가 갱신
        if curr > info['high_since_buy']:
            info['high_since_buy'] = curr
            info['max_profit_rate'] = profit_rate
        
        # UI 업데이트
        row = info['row']
        profit_item = QTableWidgetItem(f"{profit_rate:.2f}%")
        if profit_rate >= 0:
            profit_item.setForeground(QColor("#e63946"))  # 빨강 (수익)
        else:
            profit_item.setForeground(QColor("#4361ee"))  # 파랑 (손실)
        self.table.setItem(row, 7, profit_item)
        self.table.setItem(row, 8, QTableWidgetItem(f"{info['max_profit_rate']:.2f}%"))
        
        # 1. 절대 손절 (ATR 또는 고정 %)
        loss_limit = -self.spin_loss.value()
        
        # ATR 사용 시 동적 손절 계산
        if self.chk_use_atr.isChecked():
            # ATR 계산
            highs = info.get('high_history', [])
            lows = info.get('low_history', [])
            closes = info.get('price_history', [])
            
            if len(highs) > 15:
                atr = self.calculate_atr(highs, lows, closes)
                mult = self.spin_atr_mult.value()
                # ATR 손절가 = 매수가 - (ATR * Multiplier)
                atr_stop_price = buy_p - (atr * mult)
                
                # 현재가가 ATR 손절가 이하면 손절
                if curr <= atr_stop_price:
                    loss_pct = (curr - buy_p) / buy_p * 100
                    self.log(f"🛑 [{info['name']}] ATR 손절 조건 도달 ({loss_pct:.2f}%) → 매도")
                    self.execute_sell(code, "매도_ATR손절")
                    return
        
        # 기본 고정 손절 (ATR 미사용 또는 조건 미충족 시 백업)
        if profit_rate <= loss_limit:
            self.log(f"🛑 [{info['name']}] 손절 조건 도달 ({profit_rate:.2f}%) → 매도")
            self.execute_sell(code, "매도_손절")
            return
        
        # 2. 트레일링 스톱
        ts_start = self.spin_ts_start.value()
        ts_stop = self.spin_ts_stop.value()
        
        if info['max_profit_rate'] >= ts_start:
            drop_from_high = (info['high_since_buy'] - curr) / info['high_since_buy'] * 100
            
            if drop_from_high >= ts_stop:
                self.log(f"🎯 [{info['name']}] 트레일링 스톱 (고점 대비 -{drop_from_high:.2f}%) → 이익 실현")
                self.execute_sell(code, "매도_TS")

    # ------------------------------------------------------------------
    # 주문 실행
    # ------------------------------------------------------------------
    def execute_buy(self, code, curr_price):
        """매수 주문 실행"""
        ratio = self.spin_betting.value() / 100
        bet_cash = self.deposit * ratio
        
        qty = int(bet_cash / curr_price)
        if qty < 1:
            self.log(f"[{self.universe[code]['name']}] 매수금액 부족으로 진입 실패")
            return
        
        acc = self.combo_acc.currentText()
        
        try:
            self.kiwoom.dynamicCall(
                "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                ["신규매수", Config.SCREEN_ORDER, acc, 1, code, qty, 0, "03", ""]
            )
            
            self.universe[code]['state'] = '주문중'
            self.set_table_item(self.universe[code]['row'], 4, "⏳ 주문중", "#ffc107")
            
            self.log(f"📤 [{self.universe[code]['name']}] 매수 주문: {qty}주")
            self.logger.info(f"매수 주문: {self.universe[code]['name']} {qty}주")
            
            # v4.0 텔레그램 알림
            self.send_telegram_notification(
                f"🟢 매수 주문\n종목: {self.universe[code]['name']}\n수량: {qty}주\n가격: {curr_price:,}원",
                'buy'
            )
        except Exception as e:
            self.log(f"[ERROR] 매수 주문 실패: {e}")
            self.logger.error(f"매수 주문 실패 ({code}): {e}")

    def execute_sell(self, code, msg):
        """매도 주문 실행"""
        qty = self.universe[code]['qty']
        if qty == 0:
            return
        
        acc = self.combo_acc.currentText()
        
        try:
            self.kiwoom.dynamicCall(
                "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                [msg, Config.SCREEN_ORDER, acc, 2, code, qty, 0, "03", ""]
            )
            
            self.log(f"📤 [{self.universe[code]['name']}] 매도 주문: {qty}주 ({msg})")
            self.logger.info(f"매도 주문: {self.universe[code]['name']} {qty}주 ({msg})")
            
            # v4.0 텔레그램 알림
            notify_type = 'loss' if '손절' in msg else 'sell'
            self.send_telegram_notification(
                f"🔴 매도 주문\n종목: {self.universe[code]['name']}\n수량: {qty}주\n사유: {msg}",
                notify_type
            )
        except Exception as e:
            self.log(f"[ERROR] 매도 주문 실패: {e}")
            self.logger.error(f"매도 주문 실패 ({code}): {e}")

    def execute_batch_sell(self):
        """모든 보유 종목 일괄 매도 (v3.1 신규)"""
        # 보유 종목 확인
        holdings = [(code, info) for code, info in self.universe.items() if info.get('qty', 0) > 0]
        
        if not holdings:
            self.toast.show_toast("보유 중인 종목이 없습니다.", "warning")
            return
        
        # 1차 확인
        names = ", ".join([info['name'] for _, info in holdings])
        reply1 = QMessageBox.warning(
            self, "⚠️ 일괄 매도 확인 (1/2)",
            f"다음 종목을 모두 시장가로 매도합니다:\n\n{names}\n\n계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply1 != QMessageBox.Yes:
            return
        
        # 2차 확인
        reply2 = QMessageBox.critical(
            self, "🚨 최종 확인 (2/2)",
            "정말로 모든 보유 종목을 매도하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply2 != QMessageBox.Yes:
            return
        
        # 일괄 매도 실행
        sell_count = 0
        for code, info in holdings:
            try:
                self.execute_sell(code, "일괄매도")
                sell_count += 1
            except Exception as e:
                self.log(f"[ERROR] 일괄 매도 중 오류 ({info['name']}): {e}")
        
        self.toast.show_toast(f"✅ {sell_count}개 종목 매도 주문 완료", "success")
        self.log(f"📤 일괄 매도: {sell_count}개 종목 주문 완료")

    def reset_to_defaults(self):
        """설정을 기본값으로 초기화 (v3.1 신규)"""
        reply = QMessageBox.question(
            self, "설정 초기화",
            "모든 설정을 기본값으로 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 기본 설정 적용
        self.input_codes.setText(Config.DEFAULT_CODES)
        self.spin_betting.setValue(Config.DEFAULT_BETTING_RATIO)
        self.spin_k.setValue(Config.DEFAULT_K_VALUE)
        self.spin_ts_start.setValue(Config.DEFAULT_TS_START)
        self.spin_ts_stop.setValue(Config.DEFAULT_TS_STOP)
        self.spin_loss.setValue(Config.DEFAULT_LOSS_CUT)
        
        # 고급 설정
        self.chk_use_rsi.setChecked(Config.DEFAULT_USE_RSI)
        self.spin_rsi_upper.setValue(Config.DEFAULT_RSI_UPPER)
        self.spin_rsi_period.setValue(Config.DEFAULT_RSI_PERIOD)
        self.chk_use_volume.setChecked(Config.DEFAULT_USE_VOLUME)
        self.spin_volume_mult.setValue(Config.DEFAULT_VOLUME_MULTIPLIER)
        self.chk_use_risk.setChecked(Config.DEFAULT_USE_RISK_MGMT)
        self.spin_max_loss.setValue(Config.DEFAULT_MAX_DAILY_LOSS)
        self.spin_max_holdings.setValue(Config.DEFAULT_MAX_HOLDINGS)
        
        # v3.0 설정
        self.chk_use_macd.setChecked(Config.DEFAULT_USE_MACD)
        self.chk_use_bb.setChecked(Config.DEFAULT_USE_BB)
        self.spin_bb_k.setValue(Config.DEFAULT_BB_STD)
        self.chk_use_dmi.setChecked(Config.DEFAULT_USE_DMI)
        self.spin_adx.setValue(Config.DEFAULT_ADX_THRESHOLD)
        self.chk_use_atr.setChecked(Config.DEFAULT_USE_ATR)
        self.spin_atr_mult.setValue(Config.DEFAULT_ATR_MULTIPLIER)
        
        self.toast.show_toast("✅ 설정이 기본값으로 초기화되었습니다.", "success")
        self.log("🔄 설정이 기본값으로 초기화되었습니다")

    # ------------------------------------------------------------------
    # 체결 데이터 처리
    # ------------------------------------------------------------------
    def on_chejan(self, gubun, item_cnt, fid_list):
        """체결 데이터 수신"""
        try:
            if gubun != '0':
                return
            
            code = self.kiwoom.dynamicCall("GetChejanData(int)", 9001) \
                      .replace("A", "").strip()
            status = self.kiwoom.dynamicCall("GetChejanData(int)", 913).strip()
            
            if status != "체결" or code not in self.universe:
                return
            
            name = self.universe[code]['name']
            order_type = self.kiwoom.dynamicCall("GetChejanData(int)", 905).strip()
            price = int(self.kiwoom.dynamicCall("GetChejanData(int)", 910).strip() or "0")
            qty = int(self.kiwoom.dynamicCall("GetChejanData(int)", 911).strip() or "0")
            
            info = self.universe[code]
            row = info['row']
            
            if "매수" in order_type:
                self._handle_buy_execution(code, info, row, price, qty, name)
            elif "매도" in order_type:
                self._handle_sell_execution(code, info, row, price, qty, name)
            
            # 통계 업데이트
            self._update_statistics()
            
            # 예수금 다시 조회
            QTimer.singleShot(1000, self.get_deposit_info)
            
        except Exception as e:
            self.log(f"[ERROR] 체결 처리 중 오류: {e}")
            self.logger.error(f"체결 처리 중 오류: {e}")

    def _handle_buy_execution(self, code, info, row, price, qty, name):
        """매수 체결 처리"""
        info['qty'] += qty
        info['buy_price'] = price
        info['invest_amt'] = price * info['qty']
        info['high_since_buy'] = price
        info['state'] = "보유중"
        
        self.table.setItem(row, 5, QTableWidgetItem(f"{info['qty']:,}"))
        self.table.setItem(row, 6, QTableWidgetItem(f"{price:,}"))
        self.table.setItem(row, 9, QTableWidgetItem(f"{info['invest_amt']:,}"))
        self.set_table_item(row, 4, "💼 보유중", "#00b4d8")
        
        self.log(f"✅ [{name}] 매수 체결: {qty}주 @ {price:,}원")
        self.logger.info(f"매수 체결: {name} {qty}주 @ {price}원")

    def _handle_sell_execution(self, code, info, row, price, qty, name):
        """매도 체결 처리"""
        # 실현손익 계산 (누적)
        profit = (price - info['buy_price']) * qty
        self.total_realized_profit += profit
        
        # 거래 통계
        self.trade_count += 1
        if profit > 0:
            self.win_count += 1
        
        # UI 업데이트
        profit_text = f"📈 당일 실현손익: {self.total_realized_profit:,}원"
        if self.total_realized_profit >= 0:
            self.lbl_total_profit.setObjectName("profitPositive")
        else:
            self.lbl_total_profit.setObjectName("profitNegative")
        self.lbl_total_profit.setText(profit_text)
        self.lbl_total_profit.setStyle(self.lbl_total_profit.style())
        
        info['qty'] = 0
        info['state'] = "매도완료"
        self.set_table_item(row, 4, "✅ 청산완료", "#6c757d")
        
        self.log(f"✅ [{name}] 매도 체결: {qty}주 @ {price:,}원 (손익: {profit:+,}원)")
        self.logger.info(f"매도 체결: {name} {qty}주 @ {price}원, 손익: {profit}원")

    # ------------------------------------------------------------------
    # 유틸리티
    # ------------------------------------------------------------------
    def check_time_cut(self):
        """시간 청산 체크"""
        if not self.is_running or self.time_cut_executed:
            return
        
        now = datetime.datetime.now()
        
        # 15시 19분 이후 강제 청산
        if now.hour == Config.MARKET_CLOSE_HOUR and now.minute >= Config.MARKET_CLOSE_MINUTE:
            self.time_cut_executed = True
            self.log("⏰ 장 마감 임박! 일괄 청산 실행")
            self.logger.info("시간 청산 실행")
            
            for code, info in self.universe.items():
                if info['qty'] > 0:
                    self.execute_sell(code, "시간청산")
            
            self.is_running = False
            self.status_trading.setText("● 시간 청산")
            self.status_trading.setStyleSheet("color: #ffc107;")

    def set_table_item(self, row, col, text, bg_color):
        """테이블 아이템 설정 (배경색 포함)"""
        item = QTableWidgetItem(text)
        item.setBackground(QColor(bg_color))
        item.setForeground(QColor("#1a1a2e"))  # 텍스트 색상
        self.table.setItem(row, col, item)

    def _update_statistics(self):
        """거래 통계 업데이트"""
        self.stat_trades.setText(f"📊 총 거래 횟수\n{self.trade_count} 회")
        
        winrate = (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0
        self.stat_winrate.setText(f"🎯 승률\n{winrate:.1f} %")
        
        profit_color = "#e63946" if self.total_realized_profit >= 0 else "#4361ee"
        self.stat_profit.setText(f"💰 총 실현손익\n{self.total_realized_profit:,} 원")
        self.stat_profit.setStyleSheet(f"""
            QLabel {{
                background-color: #16213e;
                border: 1px solid #3d5a80;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                color: {profit_color};
            }}
        """)
        
        holdings = sum(1 for info in self.universe.values() if info['qty'] > 0)
        self.stat_holdings.setText(f"📦 보유 종목\n{holdings} 개")

    def reset_statistics(self):
        """통계 초기화"""
        reply = QMessageBox.question(
            self, "확인", "거래 통계를 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.total_realized_profit = 0
            self.trade_count = 0
            self.win_count = 0
            self._update_statistics()
            self.lbl_total_profit.setText("📈 당일 실현손익: 0 원")
            self.log("🔄 거래 통계가 초기화되었습니다")

    def on_msg(self, scr, rq, tr, msg):
        """서버 메시지 수신"""
        self.log(f"[Server] {msg}")
        self.logger.info(f"서버 메시지: {msg}")

    # ------------------------------------------------------------------
    # 시스템 트레이 및 종료 처리
    # ------------------------------------------------------------------
    def init_tray_icon(self):
        """시스템 트레이 아이콘 초기화"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        
        tray_menu = QMenu()
        action_restore = QAction("열기", self)
        action_restore.triggered.connect(self.showNormal)
        tray_menu.addAction(action_restore)
        
        tray_menu.addSeparator()
        
        action_quit = QAction("종료", self)
        action_quit.triggered.connect(self.force_quit)
        tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
        self.tray_icon.setToolTip("Kiwoom Pro Algo-Trader v3.1")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()

    def force_quit(self):
        self.allow_close = True
        self.close()

    def closeEvent(self, event):
        """프로그램 종료 시"""
        if getattr(self, 'allow_close', False):
            if self.is_running:
                reply = QMessageBox.question(
                    self, "종료 확인",
                    "매매가 진행 중입니다. 정말 종료하시겠습니까?\n"
                    "보유 중인 종목은 자동으로 청산되지 않습니다.",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    event.ignore()
                    self.allow_close = False
                    return
            
            self.logger.info("프로그램 종료")
            event.accept()
        else:
            # 트레이로 최소화 (설정 확인 없이 기본 동작으로 설정하거나, 설정에 추가)
            # 여기서는 기본적으로 트레이로 가도록 함
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Kiwoom Algo-Trader",
                "프로그램이 시스템 트레이에서 실행 중입니다.",
                QSystemTrayIcon.Information,
                2000
            )

    # ------------------------------------------------------------------
    # 알고리즘 확장 기능
    # ------------------------------------------------------------------
    def apply_preset(self, preset_type):
        """전략 프리셋 적용"""
        presets = {
            "aggressive": {"k": 0.6, "ts_start": 2.0, "ts_stop": 1.0, "loss": 3.0},
            "normal": {"k": 0.5, "ts_start": 3.0, "ts_stop": 1.5, "loss": 2.0},
            "conservative": {"k": 0.4, "ts_start": 4.0, "ts_stop": 2.0, "loss": 1.5}
        }
        
        if preset_type in presets:
            p = presets[preset_type]
            self.spin_k.setValue(p["k"])
            self.spin_ts_start.setValue(p["ts_start"])
            self.spin_ts_stop.setValue(p["ts_stop"])
            self.spin_loss.setValue(p["loss"])
            self.log(f"📋 {preset_type.upper()} 프리셋이 적용되었습니다")
            
    def check_risk_limits(self):
        """리스크 한도 체크"""
        if not self.chk_use_risk.isChecked():
            return True
        
        # 1. 일일 손실 한도 체크
        if self.initial_deposit > 0:
            loss_rate = (self.total_realized_profit / self.initial_deposit) * 100
            max_loss = -self.spin_max_loss.value()
            
            if loss_rate <= max_loss:
                if not self.daily_loss_triggered:
                    self.daily_loss_triggered = True
                    self.log(f"🛑 일일 손실 한도 도달! ({loss_rate:.2f}%) 추가 매매 중단")
                    self.send_notification("손실 한도 도달", f"일일 손실률 {loss_rate:.2f}% 도달. 추가 매매가 중단됩니다.")
                return False
        
        # 2. 최대 보유 종목 수 체크
        current_holdings = sum(1 for info in self.universe.values() if info['qty'] > 0)
        max_holdings = self.spin_max_holdings.value()
        
        if current_holdings >= max_holdings:
            return False
        
        return True
    
    def calculate_rsi(self, code, period=14):
        """RSI 계산 (종목별 저장된 가격 데이터 기반)"""
        if code not in self.universe:
            return 50  # 기본값
        
        info = self.universe[code]
        prices = info.get('price_history', [])
        
        if len(prices) < period + 1:
            return 50  # 데이터 부족
        
        # 가격 변화 계산
        gains = []
        losses = []
        
        for i in range(1, period + 1):
            change = prices[-(i)] - prices[-(i+1)]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def check_rsi_condition(self, code):
        """RSI 조건 확인"""
        if not self.chk_use_rsi.isChecked():
            return True
        
        rsi = self.calculate_rsi(code, self.spin_rsi_period.value())
        upper_limit = self.spin_rsi_upper.value()
        
        if rsi >= upper_limit:
            info = self.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] RSI {rsi:.1f} >= {upper_limit} (과매수) 진입 보류")
            return False
        
        return True
    
    def check_volume_condition(self, code):
        """거래량 조건 확인"""
        if not self.chk_use_volume.isChecked():
            return True
        
        if code not in self.universe:
            return True
        
        info = self.universe[code]
        current_volume = info.get('current_volume', 0)
        avg_volume = info.get('avg_volume_5', 0)
        
        if avg_volume == 0:
            return True
        
        required_mult = self.spin_volume_mult.value()
        actual_mult = current_volume / avg_volume
        
        if actual_mult < required_mult:
            return False
        
        return True
    
    def send_notification(self, title, message):
        """시스템 알림 전송"""
        try:
            if sys.platform == 'win32' and self.system_settings.get('sound_enabled', False):
                from ctypes import windll
                windll.user32.MessageBeep(0x00000040)
            self.log(f"🔔 [{title}] {message}")
            self.logger.info(f"알림: {title} - {message}")
        except Exception as e:
            self.logger.error(f"알림 전송 실패: {e}")

    # ------------------------------------------------------------------
    # 메뉴바 (v3.0 신규)
    # ------------------------------------------------------------------
    def create_menu_bar(self):
        """메뉴바 생성"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일")
        file_menu.addAction("⚙️ 시스템 설정", self.show_settings)
        file_menu.addSeparator()
        file_menu.addAction("❌ 종료", self.close)
        
        # 보기 메뉴
        view_menu = menubar.addMenu("보기")
        view_menu.addAction("📜 로그 폴더 열기", self.open_log_folder)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말")
        help_menu.addAction("📚 사용 가이드", self.show_help)
        help_menu.addAction("ℹ️ 정보", lambda: QMessageBox.about(self, "정보", 
            "Kiwoom Pro Algo-Trader v3.1\n\n키움증권 OpenAPI+ 기반 자동매매 프로그램\n\n변동성 돌파 전략 + 다중 지표 필터"))

    def open_log_folder(self):
        """로그 폴더 열기 (v3.1 신규)"""
        try:
            log_path = Path(Config.LOG_DIR)
            if not log_path.exists():
                log_path.mkdir(parents=True, exist_ok=True)
                self.toast.show_toast("로그 폴더가 생성되었습니다.", "info")
            os.startfile(log_path)
        except Exception as e:
            self.log(f"[ERROR] 로그 폴더 열기 실패: {e}")
            self.toast.show_toast(f"로그 폴더를 열 수 없습니다: {e}", "error")

    def show_settings(self):
        """시스템 설정 다이얼로그"""
        dialog = SettingsDialog(self, self.system_settings)
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if new_settings['run_at_startup'] != self.system_settings.get('run_at_startup', False):
                self.set_startup_registry(new_settings['run_at_startup'])
            self.system_settings.update(new_settings)
            self.save_settings()
            self.log("⚙️ 시스템 설정 저장됨")

    def show_help(self):
        """도움말 다이얼로그"""
        dialog = HelpDialog(self)
        dialog.exec_()

    def set_startup_registry(self, enable):
        """Windows 시작 프로그램 레지스트리 설정"""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "KiwoomProTrader"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
                self.log("✅ Windows 시작 시 자동 실행 설정됨")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    self.log("❌ Windows 시작 시 자동 실행 해제됨")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self.logger.error(f"레지스트리 설정 실패: {e}")

    # ------------------------------------------------------------------
    # 거래 히스토리 관리 (v3.0 신규)
    # ------------------------------------------------------------------
    def load_trade_history(self):
        """거래 히스토리 불러오기"""
        try:
            if os.path.exists(Config.TRADE_HISTORY_FILE):
                with open(Config.TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.trade_history = json.load(f)
        except Exception as e:
            self.trade_history = []
            logging.error(f"거래 히스토리 로드 실패: {e}")

    def save_trade_history(self):
        """거래 히스토리 저장"""
        try:
            with open(Config.TRADE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"거래 히스토리 저장 실패: {e}")

    def add_trade_record(self, code, trade_type, price, quantity, profit=0, reason=""):
        """거래 기록 추가"""
        name = self.universe.get(code, {}).get('name', code)
        record = {
            'timestamp': datetime.datetime.now().isoformat(),
            'code': code,
            'name': name,
            'type': trade_type,
            'price': price,
            'quantity': quantity,
            'amount': price * quantity,
            'profit': profit,
            'reason': reason
        }
        self.trade_history.append(record)
        self.save_trade_history()

    # ------------------------------------------------------------------
    # MACD 계산 (v3.0 신규)
    # ------------------------------------------------------------------
    def calculate_macd(self, prices):
        """MACD 계산 (단순 구현)"""
        if len(prices) < Config.DEFAULT_MACD_SLOW + Config.DEFAULT_MACD_SIGNAL:
            return 0, 0, 0
        
        def ema(data, period):
            multiplier = 2 / (period + 1)
            result = [data[0]]
            for i in range(1, len(data)):
                result.append((data[i] - result[-1]) * multiplier + result[-1])
            return result
        
        ema_fast = ema(prices, Config.DEFAULT_MACD_FAST)
        ema_slow = ema(prices, Config.DEFAULT_MACD_SLOW)
        macd = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal = ema(macd, Config.DEFAULT_MACD_SIGNAL)
        histogram = macd[-1] - signal[-1]
        return macd[-1], signal[-1], histogram

    def check_macd_condition(self, code):
        """MACD 조건 확인"""
        if not hasattr(self, 'chk_use_macd') or not self.chk_use_macd.isChecked():
            return True
        
        prices = self.price_history.get(code, [])
        if len(prices) < 30:
            return True
        
        macd, signal, _ = self.calculate_macd(prices)
        if macd <= signal:
            self.log(f"[{self.universe.get(code, {}).get('name', code)}] MACD {macd:.2f} <= Signal {signal:.2f} 진입 보류")
            return False
        return True

    # ------------------------------------------------------------------
    # 볼린저 밴드 및 DMI 계산 (v3.0 신규)
    # ------------------------------------------------------------------
    def calculate_bollinger(self, prices, k=2.0, period=20):
        """볼린저 밴드 계산"""
        if len(prices) < period:
            return 0, 0, 0
        
        subset = prices[-period:]
        avg = sum(subset) / period
        variance = sum((x - avg) ** 2 for x in subset) / period
        std_dev = variance ** 0.5
        
        upper = avg + (std_dev * k)
        lower = avg - (std_dev * k)
        return upper, avg, lower

    def check_bollinger_condition(self, code):
        """볼린저 밴드 조건 확인"""
        if not hasattr(self, 'chk_use_bb') or not self.chk_use_bb.isChecked():
            return True
        
        prices = self.universe.get(code, {}).get('price_history', [])
        current_price = self.universe.get(code, {}).get('current', 0)
        
        if len(prices) < 20 or current_price == 0:
            return True
            
        k = self.spin_bb_k.value()
        _, _, lower = self.calculate_bollinger(prices, k=k)
        
        # 밴드 하단보다 현재가가 낮으면(돌파) 매수 간주
        if current_price > lower:
            # self.log(f"[{code}] BB 하단 미달")
            return False
            
        return True

    def calculate_atr(self, high_list, low_list, close_list, period=14):
        """ATR(Average True Range) 계산"""
        if len(high_list) < period + 1:
            return 0
            
        tr_list = []
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i-1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
        if len(tr_list) < period:
            return 0
            
        # Simple SMA for ATR
        atr = sum(tr_list[-period:]) / period
        return atr

    def calculate_dmi(self, high_list, low_list, close_list, period=14):
        """DMI(P-DI, M-DI, ADX) 계산"""
        if len(high_list) < period + 1:
            return 0, 0, 0
            
        # 1. TR, DM+ , DM- 계산
        tr_list = []
        p_dm_list = []
        m_dm_list = []
        
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i-1]
            
            # TR = Max(|High-Low|, |High-PrevClose|, |Low-PrevClose|)
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
            # DM
            prev_h = high_list[i-1]
            prev_l = low_list[i-1]
            
            up_move = h - prev_h
            down_move = prev_l - l
            
            if up_move > down_move and up_move > 0:
                p_dm_list.append(up_move)
            else:
                p_dm_list.append(0)
                
            if down_move > up_move and down_move > 0:
                m_dm_list.append(down_move)
            else:
                m_dm_list.append(0)
        
        # 2. Smooth Values (Wilder's Smoothing usually, but here simple SMA or EMA for simplicity)
        # Using simple SMA for period
        if len(tr_list) < period:
            return 0, 0, 0
            
        tr_sum = sum(tr_list[-period:])
        p_dm_sum = sum(p_dm_list[-period:])
        m_dm_sum = sum(m_dm_list[-period:])
        
        if tr_sum == 0:
            return 0, 0, 0
            
        p_di = (p_dm_sum / tr_sum) * 100
        m_di = (m_dm_sum / tr_sum) * 100
        
        dx = abs(p_di - m_di) / (p_di + m_di) * 100 if (p_di + m_di) > 0 else 0
        adx = dx # For strict ADX, need smoothing of DX. Here using simple DX for approximation.
        
        return p_di, m_di, adx

    def check_dmi_condition(self, code):
        """DMI/ADX 조건 확인"""
        if not hasattr(self, 'chk_use_dmi') or not self.chk_use_dmi.isChecked():
            return True
            
        info = self.universe.get(code, {})
        high_list = info.get('high_history', [])
        low_list = info.get('low_history', [])
        close_list = info.get('price_history', [])
        
        if len(high_list) < 20:
            return True
            
        p_di, m_di, adx = self.calculate_dmi(high_list, low_list, close_list)
        
        # 조건 1: P-DI > M-DI (상승 추세)
        if p_di <= m_di:
            # self.log(f"[{code}] P-DI({p_di:.1f}) <= M-DI({m_di:.1f})")
            return False
            
        # 조건 2: ADX 기준
        threshold = self.spin_adx.value()
        if adx < threshold:
            # self.log(f"[{code}] ADX({adx:.1f}) < {threshold}")
            return False
            
        return True

    # ========================================================================
    # v4.0 신규 탭 생성 메서드
    # ========================================================================
    def create_telegram_tab(self):
        """텔레그램 알림 설정 탭 (v4.0 신규)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        if not TELEGRAM_MODULE_AVAILABLE:
            lbl_no_tg = QLabel("📱 텔레그램 기능을 사용하려면 python-telegram-bot 설치가 필요합니다.\n\npip install python-telegram-bot")
            lbl_no_tg.setAlignment(Qt.AlignCenter)
            lbl_no_tg.setStyleSheet("font-size: 14px; color: #ffc107;")
            layout.addWidget(lbl_no_tg)
            layout.addStretch(1)
            return widget
        
        # 텔레그램 봇 설정
        group_bot = QGroupBox("🤖 텔레그램 봇 설정")
        bot_layout = QGridLayout()
        
        bot_layout.addWidget(QLabel("Bot Token:"), 0, 0)
        self.input_telegram_token = QLineEdit()
        self.input_telegram_token.setPlaceholderText("텔레그램 @BotFather에서 발급받은 토큰")
        self.input_telegram_token.setEchoMode(QLineEdit.Password)
        bot_layout.addWidget(self.input_telegram_token, 0, 1)
        
        bot_layout.addWidget(QLabel("Chat ID:"), 1, 0)
        self.input_telegram_chat_id = QLineEdit()
        self.input_telegram_chat_id.setPlaceholderText("알림을 받을 채팅 ID (@userinfobot으로 확인)")
        bot_layout.addWidget(self.input_telegram_chat_id, 1, 1)
        
        group_bot.setLayout(bot_layout)
        layout.addWidget(group_bot)
        
        # 알림 유형 설정
        group_notify = QGroupBox("🔔 알림 설정")
        notify_layout = QVBoxLayout()
        
        self.chk_telegram_buy = QCheckBox("매수 체결 알림")
        self.chk_telegram_buy.setChecked(True)
        notify_layout.addWidget(self.chk_telegram_buy)
        
        self.chk_telegram_sell = QCheckBox("매도 체결 알림")
        self.chk_telegram_sell.setChecked(True)
        notify_layout.addWidget(self.chk_telegram_sell)
        
        self.chk_telegram_loss = QCheckBox("손절 알림")
        self.chk_telegram_loss.setChecked(True)
        notify_layout.addWidget(self.chk_telegram_loss)
        
        self.chk_telegram_daily = QCheckBox("일일 리포트 (장 마감 후)")
        self.chk_telegram_daily.setChecked(False)
        notify_layout.addWidget(self.chk_telegram_daily)
        
        group_notify.setLayout(notify_layout)
        layout.addWidget(group_notify)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        
        btn_save_telegram = QPushButton("💾 설정 저장")
        btn_save_telegram.clicked.connect(self.save_telegram_settings)
        btn_layout.addWidget(btn_save_telegram)
        
        btn_test_telegram = QPushButton("📤 테스트 메시지 발송")
        btn_test_telegram.clicked.connect(self.send_telegram_test)
        btn_layout.addWidget(btn_test_telegram)
        
        btn_layout.addStretch(1)
        
        self.lbl_telegram_status = QLabel("● 미연결")
        self.lbl_telegram_status.setStyleSheet("color: #ffc107;")
        btn_layout.addWidget(self.lbl_telegram_status)
        
        layout.addLayout(btn_layout)
        layout.addStretch(1)
        
        return widget
    
    def create_scheduler_tab(self):
        """예약 스케줄러 탭 (v4.0 신규)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 스케줄러 활성화
        self.chk_scheduler_enabled = QCheckBox("📅 예약 매매 스케줄러 활성화")
        self.chk_scheduler_enabled.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.chk_scheduler_enabled)
        
        # 시간대 설정
        group_time = QGroupBox("⏰ 매매 허용 시간대")
        time_layout = QGridLayout()
        
        time_layout.addWidget(QLabel("시작 시간:"), 0, 0)
        self.time_schedule_start = QTimeEdit()
        self.time_schedule_start.setTime(QTime(9, 0))
        self.time_schedule_start.setDisplayFormat("HH:mm")
        time_layout.addWidget(self.time_schedule_start, 0, 1)
        
        time_layout.addWidget(QLabel("종료 시간:"), 0, 2)
        self.time_schedule_end = QTimeEdit()
        self.time_schedule_end.setTime(QTime(15, 20))
        self.time_schedule_end.setDisplayFormat("HH:mm")
        time_layout.addWidget(self.time_schedule_end, 0, 3)
        
        group_time.setLayout(time_layout)
        layout.addWidget(group_time)
        
        # 요일 설정
        group_days = QGroupBox("📆 매매 허용 요일")
        days_layout = QHBoxLayout()
        
        self.chk_days = {}
        day_names = ["월", "화", "수", "목", "금", "토", "일"]
        for i, day in enumerate(day_names):
            chk = QCheckBox(day)
            chk.setChecked(i < 5)  # 평일만 기본 체크
            self.chk_days[i] = chk
            days_layout.addWidget(chk)
        
        group_days.setLayout(days_layout)
        layout.addWidget(group_days)
        
        # 특별 설정
        group_special = QGroupBox("⚡ 특별 설정")
        special_layout = QVBoxLayout()
        
        self.chk_pause_on_volatility = QCheckBox("급격한 변동성 발생 시 자동 일시정지")
        special_layout.addWidget(self.chk_pause_on_volatility)
        
        self.chk_time_cut_enabled = QCheckBox("장 마감 전 자동 청산 (15:19)")
        self.chk_time_cut_enabled.setChecked(True)
        special_layout.addWidget(self.chk_time_cut_enabled)
        
        group_special.setLayout(special_layout)
        layout.addWidget(group_special)
        
        # 저장 버튼
        btn_save_schedule = QPushButton("💾 스케줄 저장")
        btn_save_schedule.clicked.connect(self.save_scheduler_settings)
        layout.addWidget(btn_save_schedule)
        
        layout.addStretch(1)
        return widget
    
    def create_chart_tab(self):
        """수익 차트 탭 (v4.0 신규)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        if not MATPLOTLIB_AVAILABLE:
            lbl_no_chart = QLabel("📊 차트 기능을 사용하려면 matplotlib 설치가 필요합니다.\n\npip install matplotlib")
            lbl_no_chart.setAlignment(Qt.AlignCenter)
            lbl_no_chart.setStyleSheet("font-size: 14px; color: #ffc107;")
            layout.addWidget(lbl_no_chart)
            layout.addStretch(1)
            return widget
        
        # 차트 유형 선택
        chart_type_layout = QHBoxLayout()
        chart_type_layout.addWidget(QLabel("차트 유형:"))
        
        self.combo_chart_type = QComboBox()
        self.combo_chart_type.addItems(["📈 누적 수익률", "🥧 종목별 손익", "📊 일별 손익"])
        self.combo_chart_type.currentIndexChanged.connect(self.update_chart)
        chart_type_layout.addWidget(self.combo_chart_type)
        
        btn_refresh_chart = QPushButton("🔄 새로고침")
        btn_refresh_chart.clicked.connect(self.update_chart)
        chart_type_layout.addWidget(btn_refresh_chart)
        
        chart_type_layout.addStretch(1)
        layout.addLayout(chart_type_layout)
        
        # 차트 캔버스
        self.chart_figure = Figure(figsize=(10, 6), dpi=100, facecolor='#1a1a2e')
        self.chart_canvas = FigureCanvas(self.chart_figure)
        self.chart_canvas.setStyleSheet("background-color: #1a1a2e;")
        layout.addWidget(self.chart_canvas, 1)
        
        return widget
    
    def create_backtest_tab(self):
        """백테스트 탭 (v4.0 신규)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 설정 영역
        group_settings = QGroupBox("⚙️ 백테스트 설정")
        settings_layout = QGridLayout()
        
        settings_layout.addWidget(QLabel("종목코드:"), 0, 0)
        self.input_bt_code = QLineEdit("005930")
        self.input_bt_code.setToolTip("백테스트할 종목 코드 입력")
        settings_layout.addWidget(self.input_bt_code, 0, 1)
        
        settings_layout.addWidget(QLabel("시작일:"), 0, 2)
        self.date_bt_start = QDateEdit()
        self.date_bt_start.setCalendarPopup(True)
        self.date_bt_start.setDate(QDate.currentDate().addMonths(-3))
        settings_layout.addWidget(self.date_bt_start, 0, 3)
        
        settings_layout.addWidget(QLabel("종료일:"), 0, 4)
        self.date_bt_end = QDateEdit()
        self.date_bt_end.setCalendarPopup(True)
        self.date_bt_end.setDate(QDate.currentDate())
        settings_layout.addWidget(self.date_bt_end, 0, 5)
        
        settings_layout.addWidget(QLabel("초기 자금:"), 1, 0)
        self.spin_bt_balance = QSpinBox()
        self.spin_bt_balance.setRange(1000000, 1000000000)
        self.spin_bt_balance.setValue(10000000)
        self.spin_bt_balance.setSingleStep(1000000)
        self.spin_bt_balance.setSuffix(" 원")
        settings_layout.addWidget(self.spin_bt_balance, 1, 1)
        
        settings_layout.addWidget(QLabel("K값:"), 1, 2)
        self.spin_bt_k = QDoubleSpinBox()
        self.spin_bt_k.setRange(0.1, 1.0)
        self.spin_bt_k.setValue(0.5)
        self.spin_bt_k.setSingleStep(0.1)
        settings_layout.addWidget(self.spin_bt_k, 1, 3)
        
        group_settings.setLayout(settings_layout)
        layout.addWidget(group_settings)
        
        # 실행 버튼
        btn_run_backtest = QPushButton("🚀 백테스트 실행")
        btn_run_backtest.setMinimumHeight(40)
        btn_run_backtest.setStyleSheet("font-size: 14px; font-weight: bold;")
        btn_run_backtest.clicked.connect(self.run_backtest)
        layout.addWidget(btn_run_backtest)
        
        # 결과 영역
        group_result = QGroupBox("📊 백테스트 결과")
        result_layout = QGridLayout()
        
        stat_style = "font-size: 13px; padding: 8px; background-color: #16213e; border-radius: 5px;"
        
        self.lbl_bt_trades = QLabel("총 거래: -")
        self.lbl_bt_trades.setStyleSheet(stat_style)
        result_layout.addWidget(self.lbl_bt_trades, 0, 0)
        
        self.lbl_bt_winrate = QLabel("승률: -")
        self.lbl_bt_winrate.setStyleSheet(stat_style)
        result_layout.addWidget(self.lbl_bt_winrate, 0, 1)
        
        self.lbl_bt_profit = QLabel("총 수익률: -")
        self.lbl_bt_profit.setStyleSheet(stat_style)
        result_layout.addWidget(self.lbl_bt_profit, 0, 2)
        
        self.lbl_bt_mdd = QLabel("MDD: -")
        self.lbl_bt_mdd.setStyleSheet(stat_style)
        result_layout.addWidget(self.lbl_bt_mdd, 1, 0)
        
        self.lbl_bt_avg_profit = QLabel("평균 수익: -")
        self.lbl_bt_avg_profit.setStyleSheet(stat_style)
        result_layout.addWidget(self.lbl_bt_avg_profit, 1, 1)
        
        self.lbl_bt_avg_loss = QLabel("평균 손실: -")
        self.lbl_bt_avg_loss.setStyleSheet(stat_style)
        result_layout.addWidget(self.lbl_bt_avg_loss, 1, 2)
        
        group_result.setLayout(result_layout)
        layout.addWidget(group_result)
        
        # 거래 내역 테이블
        self.bt_table = QTableWidget()
        bt_cols = ["진입시간", "청산시간", "진입가", "청산가", "수익률", "사유"]
        self.bt_table.setColumnCount(len(bt_cols))
        self.bt_table.setHorizontalHeaderLabels(bt_cols)
        self.bt_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bt_table.setMaximumHeight(200)
        layout.addWidget(self.bt_table)
        
        return widget
    
    def create_paper_trading_tab(self):
        """페이퍼 트레이딩 (모의투자) 탭 (v4.0 신규)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 모드 토글
        mode_layout = QHBoxLayout()
        
        self.chk_paper_mode = QCheckBox("🎮 페이퍼 트레이딩 모드 (모의투자)")
        self.chk_paper_mode.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.chk_paper_mode.stateChanged.connect(self.on_paper_mode_changed)
        mode_layout.addWidget(self.chk_paper_mode)
        
        mode_layout.addStretch(1)
        
        self.lbl_paper_status = QLabel("● 실전 모드")
        self.lbl_paper_status.setStyleSheet("color: #e63946; font-weight: bold;")
        mode_layout.addWidget(self.lbl_paper_status)
        
        layout.addLayout(mode_layout)
        
        # 가상 자산
        group_virtual = QGroupBox("💰 가상 자산 현황")
        virtual_layout = QGridLayout()
        
        virtual_layout.addWidget(QLabel("초기 자금 설정:"), 0, 0)
        self.spin_paper_balance = QSpinBox()
        self.spin_paper_balance.setRange(1000000, 1000000000)
        self.spin_paper_balance.setValue(10000000)
        self.spin_paper_balance.setSingleStep(1000000)
        self.spin_paper_balance.setSuffix(" 원")
        virtual_layout.addWidget(self.spin_paper_balance, 0, 1)
        
        btn_reset_paper = QPushButton("🔄 자산 초기화")
        btn_reset_paper.clicked.connect(self.reset_paper_trading)
        virtual_layout.addWidget(btn_reset_paper, 0, 2)
        
        stat_style = "font-size: 14px; padding: 10px; background-color: #16213e; border-radius: 5px;"
        
        self.lbl_paper_balance = QLabel("💵 현재 원화: 10,000,000 원")
        self.lbl_paper_balance.setStyleSheet(stat_style)
        virtual_layout.addWidget(self.lbl_paper_balance, 1, 0)
        
        self.lbl_paper_holdings_value = QLabel("📦 보유 평가: 0 원")
        self.lbl_paper_holdings_value.setStyleSheet(stat_style)
        virtual_layout.addWidget(self.lbl_paper_holdings_value, 1, 1)
        
        self.lbl_paper_total = QLabel("💰 총 평가자산: 10,000,000 원")
        self.lbl_paper_total.setStyleSheet(stat_style)
        virtual_layout.addWidget(self.lbl_paper_total, 1, 2)
        
        self.lbl_paper_profit = QLabel("📈 수익률: 0.00%")
        self.lbl_paper_profit.setStyleSheet(stat_style + "color: #90e0ef;")
        virtual_layout.addWidget(self.lbl_paper_profit, 2, 0, 1, 3)
        
        group_virtual.setLayout(virtual_layout)
        layout.addWidget(group_virtual)
        
        # 가상 보유 내역
        group_holdings = QGroupBox("📋 가상 보유 내역")
        holdings_layout = QVBoxLayout()
        
        self.paper_table = QTableWidget()
        paper_cols = ["종목", "수량", "평균단가", "현재가", "평가금액", "수익률"]
        self.paper_table.setColumnCount(len(paper_cols))
        self.paper_table.setHorizontalHeaderLabels(paper_cols)
        self.paper_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        holdings_layout.addWidget(self.paper_table)
        
        group_holdings.setLayout(holdings_layout)
        layout.addWidget(group_holdings, 1)
        
        # 내부 변수 초기화
        self.paper_balance = 10000000
        self.paper_holdings = {}
        
        return widget

    # ========================================================================
    # v4.0 신규 기능 메서드
    # ========================================================================
    def save_telegram_settings(self):
        """텔레그램 설정 저장"""
        if not TELEGRAM_MODULE_AVAILABLE:
            return
        
        token = self.input_telegram_token.text().strip()
        chat_id = self.input_telegram_chat_id.text().strip()
        
        if token and chat_id:
            self.telegram_token = token
            self.telegram_chat_id = chat_id
            self.lbl_telegram_status.setText("● 연결됨")
            self.lbl_telegram_status.setStyleSheet("color: #00b4d8;")
            self.log("📱 텔레그램 설정이 저장되었습니다")
        else:
            self.lbl_telegram_status.setText("● 미연결")
            self.lbl_telegram_status.setStyleSheet("color: #ffc107;")
        
        self.save_settings()
    
    def send_telegram_test(self):
        """텔레그램 테스트 메시지 발송"""
        if not TELEGRAM_MODULE_AVAILABLE:
            QMessageBox.warning(self, "경고", "텔레그램 모듈이 설치되지 않았습니다.\npip install python-telegram-bot")
            return
        
        token = getattr(self, 'telegram_token', '')
        chat_id = getattr(self, 'telegram_chat_id', '')
        
        if not token or not chat_id:
            QMessageBox.warning(self, "경고", "텔레그램 Bot Token과 Chat ID를 먼저 설정해주세요.")
            return
        
        try:
            bot = Bot(token=token)
            bot.send_message(chat_id=chat_id, text="🤖 Kiwoom Pro Trader v4.0 테스트 메시지입니다!")
            QMessageBox.information(self, "성공", "테스트 메시지가 발송되었습니다!")
            self.log("📱 텔레그램 테스트 메시지 발송 완료")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"텔레그램 발송 실패: {e}")
    
    def send_telegram_notification(self, message, notify_type='info'):
        """텔레그램 알림 발송"""
        if not TELEGRAM_MODULE_AVAILABLE:
            return
        
        token = getattr(self, 'telegram_token', '')
        chat_id = getattr(self, 'telegram_chat_id', '')
        
        if not token or not chat_id:
            return
        
        # 알림 유형 확인
        if notify_type == 'buy' and hasattr(self, 'chk_telegram_buy') and not self.chk_telegram_buy.isChecked():
            return
        if notify_type == 'sell' and hasattr(self, 'chk_telegram_sell') and not self.chk_telegram_sell.isChecked():
            return
        if notify_type == 'loss' and hasattr(self, 'chk_telegram_loss') and not self.chk_telegram_loss.isChecked():
            return
        
        def send():
            try:
                bot = Bot(token=token)
                bot.send_message(chat_id=chat_id, text=message)
            except Exception:
                pass
        
        threading.Thread(target=send, daemon=True).start()
    
    def save_scheduler_settings(self):
        """스케줄러 설정 저장"""
        self.log("⏰ 스케줄러 설정이 저장되었습니다")
        self.save_settings()
    
    def is_trading_allowed_by_schedule(self):
        """스케줄에 따른 매매 허용 여부 확인"""
        if not hasattr(self, 'chk_scheduler_enabled') or not self.chk_scheduler_enabled.isChecked():
            return True
        
        now = datetime.datetime.now()
        weekday = now.weekday()
        current_time = now.time()
        
        # 요일 체크
        if weekday in self.chk_days and not self.chk_days[weekday].isChecked():
            return False
        
        # 시간 체크
        start_time = self.time_schedule_start.time().toPyTime()
        end_time = self.time_schedule_end.time().toPyTime()
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
    
    def update_chart(self):
        """수익 차트 업데이트"""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        self.chart_figure.clear()
        ax = self.chart_figure.add_subplot(111)
        ax.set_facecolor('#16213e')
        
        chart_type = self.combo_chart_type.currentIndex()
        
        if chart_type == 0:  # 누적 수익률
            self._draw_cumulative_chart(ax)
        elif chart_type == 1:  # 종목별 손익
            self._draw_pie_chart(ax)
        else:  # 일별 손익
            self._draw_daily_chart(ax)
        
        self.chart_figure.tight_layout()
        self.chart_canvas.draw()
    
    def _draw_cumulative_chart(self, ax):
        """누적 수익률 차트"""
        if not self.trade_history:
            ax.text(0.5, 0.5, '거래 기록이 없습니다', ha='center', va='center',
                   fontsize=14, color='#90e0ef', transform=ax.transAxes)
            return
        
        profits = [0]
        for trade in self.trade_history:
            if trade.get('type') == '매도':
                profits.append(profits[-1] + trade.get('profit', 0))
        
        ax.plot(range(len(profits)), profits, color='#00b4d8', linewidth=2)
        ax.fill_between(range(len(profits)), profits, alpha=0.3, color='#00b4d8')
        ax.set_xlabel('거래 횟수', color='#b8c5d6')
        ax.set_ylabel('누적 수익 (원)', color='#b8c5d6')
        ax.set_title('누적 수익 추이', color='#90e0ef', fontsize=14)
        ax.tick_params(colors='#b8c5d6')
        ax.grid(True, alpha=0.3, color='#3d5a80')
    
    def _draw_pie_chart(self, ax):
        """종목별 손익 파이 차트"""
        if not self.trade_history:
            ax.text(0.5, 0.5, '거래 기록이 없습니다', ha='center', va='center',
                   fontsize=14, color='#90e0ef', transform=ax.transAxes)
            return
        
        code_profits = {}
        for trade in self.trade_history:
            if trade.get('type') == '매도':
                code = trade.get('name', trade.get('code', 'Unknown'))
                code_profits[code] = code_profits.get(code, 0) + trade.get('profit', 0)
        
        if not code_profits:
            ax.text(0.5, 0.5, '매도 기록이 없습니다', ha='center', va='center',
                   fontsize=14, color='#90e0ef', transform=ax.transAxes)
            return
        
        labels = list(code_profits.keys())
        sizes = [abs(v) for v in code_profits.values()]
        colors = ['#00b4d8' if code_profits[l] >= 0 else '#e63946' for l in labels]
        
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.set_title('종목별 손익 분포', color='#90e0ef', fontsize=14)
    
    def _draw_daily_chart(self, ax):
        """일별 손익 막대 차트"""
        if not self.trade_history:
            ax.text(0.5, 0.5, '거래 기록이 없습니다', ha='center', va='center',
                   fontsize=14, color='#90e0ef', transform=ax.transAxes)
            return
        
        daily_profits = {}
        for trade in self.trade_history:
            if trade.get('type') == '매도':
                date = trade.get('timestamp', '')[:10]
                daily_profits[date] = daily_profits.get(date, 0) + trade.get('profit', 0)
        
        if not daily_profits:
            ax.text(0.5, 0.5, '매도 기록이 없습니다', ha='center', va='center',
                   fontsize=14, color='#90e0ef', transform=ax.transAxes)
            return
        
        dates = list(daily_profits.keys())
        profits = list(daily_profits.values())
        colors = ['#00b4d8' if p >= 0 else '#e63946' for p in profits]
        
        ax.bar(range(len(dates)), profits, color=colors)
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, ha='right')
        ax.set_xlabel('날짜', color='#b8c5d6')
        ax.set_ylabel('손익 (원)', color='#b8c5d6')
        ax.set_title('일별 손익', color='#90e0ef', fontsize=14)
        ax.tick_params(colors='#b8c5d6')
        ax.grid(True, alpha=0.3, color='#3d5a80', axis='y')
    
    def run_backtest(self):
        """백테스트 실행 (간이 버전)"""
        code = self.input_bt_code.text().strip()
        if not code:
            QMessageBox.warning(self, "경고", "종목 코드를 입력해주세요.")
            return
        
        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 키움증권에 로그인해주세요.")
            return
        
        self.log(f"🧪 백테스트 시작: {code}")
        QMessageBox.information(self, "백테스트", 
            "백테스트 기능은 현재 간이 버전입니다.\n\n"
            "전체 백테스트를 위해서는 별도의 backtest_engine.py 모듈이 필요합니다.\n\n"
            "키움 API에서 과거 데이터를 조회하고 변동성 돌파 전략을 시뮬레이션합니다.")
    
    def on_paper_mode_changed(self, state):
        """페이퍼 트레이딩 모드 변경"""
        if state:
            self.lbl_paper_status.setText("● 모의투자 모드")
            self.lbl_paper_status.setStyleSheet("color: #00b4d8; font-weight: bold;")
            self.log("🎮 페이퍼 트레이딩 모드가 활성화되었습니다")
            # 모의투자 초기화
            self.paper_balance = self.spin_paper_balance.value()
            self.paper_holdings = {}
        else:
            self.lbl_paper_status.setText("● 실전 모드")
            self.lbl_paper_status.setStyleSheet("color: #e63946; font-weight: bold;")
            self.log("⚠️ 실전 모드로 전환되었습니다")
    
    def reset_paper_trading(self):
        """페이퍼 트레이딩 초기화"""
        self.paper_balance = self.spin_paper_balance.value()
        self.paper_holdings = {}
        self.paper_table.setRowCount(0)
        
        self.lbl_paper_balance.setText(f"💵 현재 원화: {self.paper_balance:,} 원")
        self.lbl_paper_holdings_value.setText("📦 보유 평가: 0 원")
        self.lbl_paper_total.setText(f"💰 총 평가자산: {self.paper_balance:,} 원")
        self.lbl_paper_profit.setText("📈 수익률: 0.00%")
        
        self.log("🔄 페이퍼 트레이딩이 초기화되었습니다")

    # ------------------------------------------------------------------
    # 프리셋 관리 (v3.0 개선)
    # ------------------------------------------------------------------
    def open_preset_manager(self):
        """프리셋 관리자 열기"""
        current_values = {
            'k': self.spin_k.value(),
            'ts_start': self.spin_ts_start.value(),
            'ts_stop': self.spin_ts_stop.value(),
            'loss': self.spin_loss.value(),
            'betting': self.spin_betting.value(),
            'rsi_upper': self.spin_rsi_upper.value(),
            'max_holdings': self.spin_max_holdings.value()
        }
        dialog = PresetManagerDialog(self, current_values)
        if dialog.exec_() == QDialog.Accepted:
            preset = dialog.get_selected_preset()
            if preset:
                self.apply_preset_values(preset)

    def apply_preset_values(self, preset):
        """프리셋 값 적용"""
        if 'k' in preset:
            self.spin_k.setValue(preset['k'])
        if 'ts_start' in preset:
            self.spin_ts_start.setValue(preset['ts_start'])
        if 'ts_stop' in preset:
            self.spin_ts_stop.setValue(preset['ts_stop'])
        if 'loss' in preset:
            self.spin_loss.setValue(preset['loss'])
        if 'betting' in preset:
            self.spin_betting.setValue(preset['betting'])
        if 'rsi_upper' in preset:
            self.spin_rsi_upper.setValue(preset['rsi_upper'])
        if 'max_holdings' in preset:
            self.spin_max_holdings.setValue(preset['max_holdings'])
        self.log(f"📋 프리셋 '{preset.get('name', '사용자 정의')}' 적용됨")

    # ------------------------------------------------------------------
    # 로그 개선 (v3.0 메모리 관리)
    # ------------------------------------------------------------------
    def log(self, msg):
        """로그 출력 (메모리 제한 적용)"""
        t = datetime.datetime.now().strftime("[%H:%M:%S]")
        self.log_text.append(f"{t} {msg}")
        
        # 메모리 제한: 오래된 로그 삭제
        if self.log_text.document().blockCount() > Config.MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 50)
            cursor.removeSelectedText()
        
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())


# ============================================================================
# 메인 실행
# ============================================================================
if __name__ == "__main__":
    # HiDPI 지원 (v3.1 신규)
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 크로스 플랫폼 스타일
    
    trader = KiwoomProTrader()
    trader.show()
    
    sys.exit(app.exec_())
