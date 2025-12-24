"""
Kiwoom Pro Algo-Trader v3.1
키움증권 OpenAPI+ 기반 자동매매 프로그램

변동성 돌파 전략 + 이동평균 필터 + 트레일링 스톱
MACD, 볼린저밴드, ATR, 스토캐스틱RSI, DMI/ADX 지표 지원
진입 점수 시스템, 다단계 익절, 일괄 매수/매도 기능

v3.1 신규 기능:
- Toast 알림 시스템
- 일괄 매도 기능 (2중 확인)
- 설정 초기화 버튼
- HiDPI 지원
- 로그 폴더 열기 기능 개선

v3.0 기능:
- MACD 골든크로스 필터
- 볼린저 밴드 필터
- ATR 동적 손절
- 스토캐스틱 RSI / DMI-ADX 추세 지표
- 진입 점수 시스템 (가중치 기반)
- 보조지표 필터
- 다단계 익절 기능
- 거래 내역 탭 및 CSV 내보내기
- 프리셋 관리자 (사용자 정의 저장/삭제)
- 시스템 설정 / 도움말 다이얼로그
- 메뉴바 및 시스템 트레이 지원
"""

import sys
import os
import json
import datetime
import time
import logging
import winreg
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QBrush, QFont, QIcon, QPalette, QTextCursor


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
# 다크 테마 스타일시트
# ============================================================================
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #edf2f4;
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
}

QGroupBox {
    border: 1px solid #3d5a80;
    border-radius: 8px;
    margin-top: 12px;
    padding: 15px 10px 10px 10px;
    font-weight: bold;
    font-size: 13px;
    color: #90e0ef;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 15px;
    padding: 0 8px;
}

QPushButton {
    background-color: #3d5a80;
    color: #edf2f4;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #4a6fa5;
}

QPushButton:pressed {
    background-color: #2c4a6e;
}

QPushButton:disabled {
    background-color: #2d2d44;
    color: #666680;
}

QPushButton#loginBtn {
    background-color: #00b4d8;
}

QPushButton#loginBtn:hover {
    background-color: #0096c7;
}

QPushButton#startBtn {
    background-color: #e63946;
    font-size: 15px;
}

QPushButton#startBtn:hover {
    background-color: #d62839;
}

QPushButton#stopBtn {
    background-color: #6c757d;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #16213e;
    border: 1px solid #3d5a80;
    border-radius: 5px;
    padding: 8px;
    color: #edf2f4;
    selection-background-color: #00b4d8;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #00b4d8;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QTableWidget {
    background-color: #16213e;
    alternate-background-color: #1a2744;
    gridline-color: #2d3a5a;
    border: 1px solid #3d5a80;
    border-radius: 8px;
    color: #edf2f4;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2d3a5a;
}

QTableWidget::item:selected {
    background-color: #3d5a80;
}

QHeaderView::section {
    background-color: #0f3460;
    color: #90e0ef;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #00b4d8;
    font-weight: bold;
}

QTextEdit {
    background-color: #0d1b2a;
    border: 1px solid #3d5a80;
    border-radius: 8px;
    color: #90e0ef;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 10px;
}

QLabel {
    color: #b8c5d6;
    font-size: 12px;
}

QLabel#depositLabel {
    color: #00b4d8;
    font-weight: bold;
    font-size: 14px;
}

QLabel#profitLabel {
    color: #f72585;
    font-weight: bold;
    font-size: 14px;
}

QLabel#profitPositive {
    color: #e63946;
    font-weight: bold;
    font-size: 14px;
}

QLabel#profitNegative {
    color: #4361ee;
    font-weight: bold;
    font-size: 14px;
}

QStatusBar {
    background-color: #0f3460;
    color: #90e0ef;
    border-top: 1px solid #3d5a80;
    font-size: 11px;
}

QStatusBar::item {
    border: none;
}

QTabWidget::pane {
    border: 1px solid #3d5a80;
    border-radius: 8px;
    background-color: #1a1a2e;
}

QTabBar::tab {
    background-color: #16213e;
    color: #b8c5d6;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #3d5a80;
    color: #edf2f4;
}

QTabBar::tab:hover:!selected {
    background-color: #2d3a5a;
}

QSplitter::handle {
    background-color: #3d5a80;
}

QScrollBar:vertical {
    background-color: #16213e;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #3d5a80;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4a6fa5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QToolTip {
    background-color: #0f3460;
    color: #edf2f4;
    border: 1px solid #3d5a80;
    border-radius: 4px;
    padding: 5px;
}
"""


# ============================================================================
# Toast 알림 위젯 (v3.1 신규)
# ============================================================================
class ToastWidget(QLabel):
    """비침습적 Toast 알림 위젯"""
    
    COLORS = {
        'success': '#28a745',
        'info': '#17a2b8',
        'warning': '#ffc107',
        'error': '#dc3545'
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fade_out)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(1.0)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.finished.connect(self.hide)
    
    def show_toast(self, message, toast_type='info', duration=3000):
        """Toast 메시지 표시"""
        color = self.COLORS.get(toast_type, self.COLORS['info'])
        
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
        """)
        
        self.setText(message)
        self.adjustSize()
        
        # 부모 창 기준 위치 결정
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.right() - self.width() - 20
            y = parent_geo.bottom() - self.height() - 60
            self.move(x, y)
        
        self.opacity_effect.setOpacity(1.0)
        self.show()
        self.timer.start(duration)
    
    def fade_out(self):
        """페이드 아웃 효과"""
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
        
        self.logger.info("프로그램 초기화 완료 (v3.1)")

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
        self.setWindowTitle("Kiwoom Pro Algo-Trader v3.1 [고급 매매 알고리즘]")
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
        
        # 거래 내역 탭 (v3.0 신규)
        tab_widget.addTab(self.create_history_tab(), "📝 거래 내역")
        
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
        self.statusbar.addPermanentWidget(QLabel("Kiwoom Pro Algo-Trader v3.1"))

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
            "atr_mult": self.spin_atr_mult.value()
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
