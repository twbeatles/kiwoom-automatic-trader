"""UI construction mixin for KiwoomProTrader."""

# pyright: reportWildcardImportFromLibrary=false
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import *

from app.support.backtest_runner import backtest_result_to_dict, metric_rows, run_backtest_from_files
from app.support.ui_text import (
    ASSET_SCOPE_CHOICES,
    BACKTEST_TIMEFRAME_CHOICES,
    DAILY_LOSS_BASIS_CHOICES,
    EXECUTION_MODE_CHOICES,
    EXECUTION_POLICY_CHOICES,
    PORTFOLIO_MODE_CHOICES,
    STRATEGY_CHOICES,
    populate_combo,
)
from app.support.worker import Worker
from app.support.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox
from config import Config
from dark_theme import DARK_STYLESHEET
from app.mixins._typing import TraderMixinBase


class UIBuildLayoutMixin(TraderMixinBase):
    def _init_ui(self):
        self.setWindowTitle("키움 자동매매 도우미 v4.5 | Kiwoom Pro Algo-Trader [REST API]")
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
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(6)
        main_splitter.addWidget(self._create_tabs())
        main_splitter.addWidget(self._create_stock_panel())
        main_splitter.setSizes([350, 500])  # 초기 비율
        layout.addWidget(main_splitter)

        self._create_statusbar()
    def _create_dashboard(self):
        """
        메인 대시보드 생성 - 시장 상태, 계좌 정보, 빠른 실행 버튼 포함
        v4.4 디자인 리팩토링 - 더 깔끔한 레이아웃과 항상 보이는 컨트롤
        """
        group = QGroupBox("📊 자동매매 대시보드")
        group.setObjectName("dashboardCard")

        # 메인 레이아웃 (가로: 상태 패널 | 컨트롤 패널)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- 왼쪽 패널: 계좌 & 상태 정보 ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)

        # 행 1: API 연결 & 계좌 선택
        row1 = QHBoxLayout()
        self.btn_connect = QPushButton("🔌 API 연결")
        self.btn_connect.setObjectName("connectBtn")
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.clicked.connect(self.connect_api)
        self.btn_connect.setMinimumWidth(120)

        lbl_account = QLabel("계좌번호:")
        lbl_account.setStyleSheet("color: #8b949e; font-weight: 600;")
        self.combo_acc = NoScrollComboBox()
        self.combo_acc.setMinimumWidth(180)
        self.combo_acc.currentTextChanged.connect(self._on_account_changed)

        row1.addWidget(self.btn_connect)
        row1.addWidget(lbl_account)
        row1.addWidget(self.combo_acc)
        row1.addStretch()

        # 행 2: 주요 지표 (예수금, 손익, 연결상태)
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        self.lbl_deposit = QLabel("💰 예수금: -")
        self.lbl_deposit.setStyleSheet("""
            color: #e6edf3; font-weight: bold; font-size: 15px;
            padding: 10px 15px; border-radius: 8px;
            background: rgba(56, 139, 253, 0.1); border: 1px solid rgba(56, 139, 253, 0.2);
        """)

        self.lbl_profit = QLabel("📈 당일손익: -")
        self.lbl_profit.setObjectName("profitLabel")
        self.lbl_profit.setStyleSheet("""
            color: #e6edf3; font-weight: bold; font-size: 15px;
            padding: 10px 15px; border-radius: 8px;
            background: rgba(139, 148, 158, 0.1); border: 1px solid rgba(139, 148, 158, 0.2);
        """)

        self.lbl_status = QLabel("● 연결 끊김")
        self.lbl_status.setObjectName("statusDisconnected")

        row2.addWidget(self.lbl_deposit)
        row2.addWidget(self.lbl_profit)
        row2.addWidget(self.lbl_status)
        row2.addStretch()

        left_panel.addLayout(row1)
        left_panel.addLayout(row2)

        # --- 오른쪽 패널: 빠른 실행 (그리드) ---
        right_panel = QGridLayout()
        right_panel.setSpacing(10)

        # 시작/중지 버튼
        self.btn_start = QPushButton("🚀 자동매매 시작")
        self.btn_start.setObjectName("startBtn")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_trading)
        self.btn_start.setEnabled(False)
        self.btn_start.setMinimumHeight(45)

        self.btn_stop = QPushButton("⏹️ 중지")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_trading)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton { background-color: #30363d; border: 1px solid #8b949e; }
            QPushButton:hover { background-color: #3b434b; }
        """)
        self.btn_stop.setMinimumHeight(45)

        # 긴급 청산 버튼
        self.btn_emergency = QPushButton("🚨 긴급 전량청산")
        self.btn_emergency.setObjectName("emergencyBtn")
        self.btn_emergency.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_emergency.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9a6700, stop:1 #d29922);
                color: white; border: none; font-weight: bold;
            }
            QPushButton:hover { background: #d29922; }
            QPushButton:pressed { background: #9a6700; }
        """)
        self.btn_emergency.clicked.connect(self._emergency_liquidate)
        self.btn_emergency.setEnabled(False)

        # 보조 버튼
        btn_preset = QPushButton("📋 프리셋")
        btn_preset.clicked.connect(self._open_presets)

        btn_search = QPushButton("🔍 종목검색")
        btn_search.clicked.connect(self._open_stock_search)

        # 그리드에 위젯 추가
        # 행 0: 시작 | 중지
        right_panel.addWidget(self.btn_start, 0, 0, 1, 2)
        right_panel.addWidget(self.btn_stop, 0, 2, 1, 2)

        # 행 1: 프리셋 | 검색 | 긴급청산
        right_panel.addWidget(btn_preset, 1, 0, 1, 1)
        right_panel.addWidget(btn_search, 1, 1, 1, 1)
        right_panel.addWidget(self.btn_emergency, 1, 2, 1, 2)

        # 메인 레이아웃에 패널 추가
        main_layout.addLayout(left_panel, 65) # 너비 65%
        main_layout.addLayout(right_panel, 35) # 너비 35%

        group.setLayout(main_layout)
        return group
    def _create_tabs(self):
        tabs = QTabWidget()
        self.main_tabs = tabs
        tabs.addTab(self._create_strategy_tab(), "🎯 핵심 설정")
        tabs.addTab(self._create_advanced_tab(), "🛠 상세 설정")
        if hasattr(self, "_create_market_intelligence_settings_tab"):
            tabs.addTab(self._create_market_intelligence_settings_tab(), "🧠 인텔리전스 설정")
        api_tab = self._create_api_tab()
        api_tab.setObjectName("api_tab")
        tabs.addTab(api_tab, "🔐 API/알림")
        tabs.addTab(self._create_chart_tab(), "📈 차트")
        tabs.addTab(self._create_orderbook_tab(), "📋 호가")
        tabs.addTab(self._create_condition_tab(), "🔍 조건 검색")
        tabs.addTab(self._create_ranking_tab(), "🏆 순위")
        tabs.addTab(self._create_stats_tab(), "📊 통계")
        tabs.addTab(self._create_history_tab(), "📝 내역")
        if hasattr(self, "_create_market_intelligence_tab"):
            tabs.addTab(self._create_market_intelligence_tab(), "🧠 인텔리전스 현황")
        if hasattr(self, "_create_market_replay_tab"):
            tabs.addTab(self._create_market_replay_tab(), "📼 인텔리전스 리플레이")
        tabs.addTab(self._create_diagnostics_tab(), "🩺 시스템 진단")
        return tabs
    def _create_stock_panel(self):
        """주식 테이블 + 로그 패널 (내부 스플리터)"""
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)

        # 주식 테이블
        self.table = QTableWidget()
        cols = ["종목명", "현재가", "목표가", "상태", "보유", "매입가", "수익률", "최고수익", "투자금"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        table_vertical_header = self.table.verticalHeader()
        table_horizontal_header = self.table.horizontalHeader()
        if table_vertical_header is not None:
            table_vertical_header.setVisible(False)
        if table_horizontal_header is not None:
            table_horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.table)

        # 로그 영역
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        splitter.addWidget(self.log_text)

        # 초기 비율 설정 (대략 3:1)
        splitter.setSizes([600, 200])

        return splitter
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

        status_bar = self.statusBar()
        if status_bar is None:
            return
        status_bar.addWidget(self.status_time)
        status_bar.addWidget(QLabel("  "))  # 간격
        status_bar.addWidget(self.status_trading)
        status_bar.addPermanentWidget(QLabel("v4.5 | 키움 REST API"))
