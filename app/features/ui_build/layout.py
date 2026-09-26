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
from app.support.components.helpers import mark_secondary
from app.support.components.infobar import InfoBarHost
from app.support.design_tokens import FORM_ROW_GAP, GROUP_GAP, SPACE_SM, SPACE_XS
from app.support.theme import apply_accessibility_names, apply_theme
from app.support.ui_scale import recommended_density
from app.mixins._typing import TraderMixinBase


class UIBuildLayoutMixin(TraderMixinBase):
    def _init_ui(self):
        self.setWindowTitle("키움 자동매매 도우미 v4.5 | Kiwoom Pro Algo-Trader [REST API]")
        self._apply_hidpi_defaults()
        self._apply_display_aware_geometry()
        apply_theme(self)
        apply_accessibility_names(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(SPACE_XS)
        layout.setContentsMargins(SPACE_SM, SPACE_SM, SPACE_SM, SPACE_SM)

        # 대시보드 (상단 고정)
        layout.addWidget(self._create_dashboard())

        # 비차단 알림(InfoBar) 호스트: 성공/경고/오류는 모달 대신 여기로 (§15)
        self.infobar = InfoBarHost()
        self.infobar.setMaximumHeight(120)
        layout.addWidget(self.infobar)

        # 메인 스플리터 (탭 + 테이블/로그 영역 크기 조절 가능)
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(6)
        main_splitter.addWidget(self._create_tabs())
        main_splitter.addWidget(self._create_stock_panel())
        main_splitter.setSizes([350, 500])  # 초기 비율
        layout.addWidget(main_splitter)

        self._create_statusbar()
    def _screen_scale_hints(self):
        """Return (device_pixel_ratio, logical_dpi) of the current screen."""
        try:
            screen = self.screen()
        except Exception:
            return None, None
        if screen is None:
            return None, None
        ratio = None
        try:
            ratio = float(screen.devicePixelRatio())
        except Exception:
            ratio = None
        dpi = None
        try:
            dpi = float(screen.logicalDotsPerInchX())
        except Exception:
            try:
                dpi = float(screen.logicalDotsPerInch())
            except Exception:
                dpi = None
        return ratio, dpi

    def _apply_hidpi_defaults(self):
        """Pick first-run density on high-ratio displays.

        Font scale is intentionally NOT lifted: theme fonts are emitted
        in pt so the OS scale already applies, and an app multiplier on
        top renders HiDPI text too large. Saved settings (applied later
        by _load_settings) always win; this only sets the starting
        density so HiDPI first runs stay usable.
        """
        ratio, dpi = self._screen_scale_hints()
        if str(getattr(self, "ui_density", "compact")) == "compact":
            if recommended_density(ratio, dpi) == "comfortable":
                self.ui_density = "comfortable"

    def _apply_display_aware_geometry(self):
        """Size the window from the available screen, not fixed pixels."""
        base_w, base_h, min_w, min_h = 1400, 950, 1100, 800
        try:
            screen = self.screen()
            avail = screen.availableGeometry() if screen is not None else None
        except Exception:
            avail = None
        if avail is None:
            self.setGeometry(100, 100, base_w, base_h)
            self.setMinimumSize(min_w, min_h)
            return
        try:
            avail_w = int(avail.width())
            avail_h = int(avail.height())
        except Exception:
            self.setGeometry(100, 100, base_w, base_h)
            self.setMinimumSize(min_w, min_h)
            return
        width = max(900, min(base_w, int(avail_w * 0.92)))
        height = max(650, min(base_h, int(avail_h * 0.90)))
        self.resize(width, height)
        self.setMinimumSize(min(min_w, width), min(min_h, height))

    def _create_dashboard(self):
        """
        메인 대시보드 생성 - 시장 상태, 계좌 정보, 빠른 실행 버튼 포함
        v4.4 디자인 리팩토링 - 더 깔끔한 레이아웃과 항상 보이는 컨트롤
        """
        group = QGroupBox("자동매매 대시보드")
        group.setObjectName("dashboardCard")

        # 메인 레이아웃 (가로: 상태 패널 | 컨트롤 패널)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(GROUP_GAP)
        main_layout.setContentsMargins(GROUP_GAP, GROUP_GAP, GROUP_GAP, GROUP_GAP)

        # --- 왼쪽 패널: 계좌 & 상태 정보 ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(GROUP_GAP)

        # 행 1: API 연결 & 계좌 선택
        row1 = QHBoxLayout()
        self.btn_connect = QPushButton("API 연결")
        self.btn_connect.setObjectName("connectBtn")
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.clicked.connect(self.connect_api)
        self.btn_connect.setMinimumWidth(120)

        lbl_account = QLabel("계좌번호:")
        mark_secondary(lbl_account)
        self.combo_acc = NoScrollComboBox()
        self.combo_acc.setMinimumWidth(180)
        self.combo_acc.currentTextChanged.connect(self._on_account_changed)

        row1.addWidget(self.btn_connect)
        row1.addWidget(lbl_account)
        row1.addWidget(self.combo_acc)
        row1.addStretch()

        # 행 2: 주요 지표 (예수금, 손익, 연결상태)
        row2 = QHBoxLayout()
        row2.setSpacing(FORM_ROW_GAP)

        self.lbl_deposit = QLabel("예수금: -")
        self.lbl_deposit.setObjectName("depositCard")

        self.lbl_profit = QLabel("당일손익: -")
        self.lbl_profit.setObjectName("profitLabel")

        self.lbl_status = QLabel("● 연결 끊김")
        self.lbl_status.setObjectName("statusDisconnected")

        row2.addWidget(self.lbl_deposit)
        row2.addWidget(self.lbl_profit)
        row2.addWidget(self.lbl_status)
        row2.addStretch()

        left_panel.addLayout(row1)
        left_panel.addLayout(row2)

        # --- 오른쪽 패널: 빠른 실행 (그리드, Primary는 시작 하나만) ---
        right_panel = QGridLayout()
        right_panel.setSpacing(SPACE_XS)

        # 시작/중지 버튼
        self.btn_start = QPushButton("자동매매 시작")
        self.btn_start.setObjectName("startBtn")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_trading)
        self.btn_start.setEnabled(False)
        self.btn_start.setMinimumHeight(45)

        self.btn_stop = QPushButton("중지")
        self.btn_stop.setProperty("secondary_button", True)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_trading)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(45)

        # 긴급 청산 버튼
        self.btn_emergency = QPushButton("긴급 전량청산")
        self.btn_emergency.setObjectName("emergencyBtn")
        self.btn_emergency.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_emergency.clicked.connect(self._emergency_liquidate)
        self.btn_emergency.setEnabled(False)

        # 보조 버튼
        btn_preset = QPushButton("프리셋")
        btn_preset.clicked.connect(self._open_presets)

        btn_search = QPushButton("종목검색")
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
        """5-워크스페이스 탭 + 우측 주문 티켓 도크 (빌더는 workspaces 믹스인)."""
        tabs = self._create_workspace_tabs()
        self._create_order_dock()
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
        mark_secondary(self.status_time)

        # 매매 상태 배지
        self.status_trading = QLabel("대기 중")
        self.status_trading.setObjectName("tradingOff")
        self.status_trading.setProperty("badge", "off")

        status_bar = self.statusBar()
        if status_bar is None:
            return
        status_bar.addWidget(self.status_time)
        status_bar.addWidget(self.status_trading)
        status_bar.addPermanentWidget(QLabel("v4.5 | 키움 REST API"))

    def notify_bar(self, level, title, body="", duration_ms=6000):
        """Non-modal InfoBar notice with log fallback (rules §15)."""
        host = getattr(self, "infobar", None)
        show = getattr(host, "show_message", None)
        if callable(show):
            try:
                return show(level, title, body, duration_ms)
            except Exception:
                pass
        log = getattr(self, "log", None)
        if callable(log):
            log(f"[{level}] {title} {body}".strip())
        return None
