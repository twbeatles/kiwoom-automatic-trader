"""UI construction mixin for KiwoomProTrader."""

# pyright: reportWildcardImportFromLibrary=false
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import *

from app.support.ui_text import (
    ASSET_SCOPE_CHOICES,
    BACKTEST_TIMEFRAME_CHOICES,
    DAILY_LOSS_BASIS_CHOICES,
    EXECUTION_POLICY_CHOICES,
    PORTFOLIO_MODE_CHOICES,
    STRATEGY_CHOICES,
    populate_combo,
)
from app.support.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox
from config import Config
from dark_theme import DARK_STYLESHEET
from ._typing import TraderMixinBase

class UIBuildMixin(TraderMixinBase):
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
        tabs.addTab(self._create_api_tab(), "🔐 API/알림")
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

    def _create_strategy_tab(self):
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setSpacing(14)

        guide_group = QGroupBox("🧭 처음 설정 순서")
        guide_layout = QVBoxLayout(guide_group)
        guide_label = QLabel(
            "\n".join(
                [
                    "1. 종목을 입력하거나 즐겨찾기에서 불러옵니다.",
                    "2. 한 종목 투자 비중을 먼저 작게 잡습니다.",
                    "3. 목표가 민감도(K)로 진입 민감도를 조절합니다.",
                    "4. 이익 보호 시작과 추적 손절 폭을 정합니다.",
                    "5. 최대 손절률을 확인한 뒤 자동매매를 시작합니다.",
                ]
            )
        )
        guide_label.setWordWrap(True)
        guide_label.setStyleSheet("color: #c9d1d9; line-height: 1.5;")
        guide_layout.addWidget(guide_label)
        outer.addWidget(guide_group)

        basic_group = QGroupBox("🎯 기본 매매 수치")
        layout = QGridLayout(basic_group)
        layout.setSpacing(10)

        layout.addWidget(QLabel("📌 즐겨찾기:"), 0, 0)
        self.combo_favorites = NoScrollComboBox()
        self.combo_favorites.addItem("즐겨찾기 선택")
        self._load_favorites()
        self.combo_favorites.currentIndexChanged.connect(self._on_favorite_selected)
        layout.addWidget(self.combo_favorites, 0, 1)

        layout.addWidget(QLabel("🧾 종목 입력:"), 0, 2)
        self.input_codes = QLineEdit(Config.DEFAULT_CODES)
        self.input_codes.setAcceptDrops(True)
        self.input_codes.setPlaceholderText("예: 005930,000660 처럼 쉼표로 구분해 입력")
        self.input_codes.dragEnterEvent = self._drag_enter_codes
        self.input_codes.dropEvent = self._drop_codes
        layout.addWidget(self.input_codes, 0, 3, 1, 3)

        btn_save_fav = QPushButton("⭐ 저장")
        btn_save_fav.setToolTip("현재 입력한 종목을 즐겨찾기로 저장합니다.")
        btn_save_fav.clicked.connect(self._save_favorite)
        layout.addWidget(btn_save_fav, 0, 6)

        layout.addWidget(QLabel("💵 한 종목 투자 비중:"), 1, 0)
        self.spin_betting = NoScrollDoubleSpinBox()
        self.spin_betting.setRange(1, 100)
        self.spin_betting.setValue(Config.DEFAULT_BETTING_RATIO)
        self.spin_betting.setSuffix(" %")
        self.spin_betting.setToolTip("한 종목에 전체 자금의 몇 %를 배분할지 정합니다.")
        layout.addWidget(self.spin_betting, 1, 1)

        layout.addWidget(QLabel("📐 목표가 민감도(K):"), 1, 2)
        self.spin_k = NoScrollDoubleSpinBox()
        self.spin_k.setRange(0.1, 1.0)
        self.spin_k.setSingleStep(0.1)
        self.spin_k.setValue(Config.DEFAULT_K_VALUE)
        self.spin_k.setToolTip("값이 클수록 목표가가 멀어져 진입이 더 신중해집니다.")
        layout.addWidget(self.spin_k, 1, 3)

        layout.addWidget(QLabel("🎯 이익 보호 시작:"), 1, 4)
        self.spin_ts_start = NoScrollDoubleSpinBox()
        self.spin_ts_start.setRange(0.5, 20)
        self.spin_ts_start.setValue(Config.DEFAULT_TS_START)
        self.spin_ts_start.setSuffix(" %")
        self.spin_ts_start.setToolTip("수익률이 이 기준을 넘으면 추적 손절이 시작됩니다.")
        layout.addWidget(self.spin_ts_start, 1, 5)

        layout.addWidget(QLabel("📉 추적 손절 폭:"), 2, 0)
        self.spin_ts_stop = NoScrollDoubleSpinBox()
        self.spin_ts_stop.setRange(0.5, 10)
        self.spin_ts_stop.setValue(Config.DEFAULT_TS_STOP)
        self.spin_ts_stop.setSuffix(" %")
        self.spin_ts_stop.setToolTip("최고 수익률에서 이만큼 밀리면 매도합니다.")
        layout.addWidget(self.spin_ts_stop, 2, 1)

        layout.addWidget(QLabel("🛑 최대 손절률:"), 2, 2)
        self.spin_loss = NoScrollDoubleSpinBox()
        self.spin_loss.setRange(0.5, 10)
        self.spin_loss.setValue(Config.DEFAULT_LOSS_CUT)
        self.spin_loss.setSuffix(" %")
        self.spin_loss.setToolTip("매수 후 손실이 이 기준을 넘으면 손절합니다.")
        layout.addWidget(self.spin_loss, 2, 3)

        note_label = QLabel("초보자 권장: 투자 비중은 낮게 시작하고, 기본값에서 하나씩만 조절하세요.")
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: #8b949e;")
        layout.addWidget(note_label, 3, 0, 1, 7)

        outer.addWidget(basic_group)
        outer.addStretch()
        return widget

    def _create_advanced_tab(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)

        intro = QLabel(
            "세부 옵션은 기능별로 나눠 두었습니다. 초보자는 먼저 [진입 판단], [리스크 관리], [주문/청산]만 확인해도 충분합니다."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b949e;")
        main_layout.addWidget(intro)

        detail_tabs = QTabWidget()
        main_layout.addWidget(detail_tabs)

        def _make_page(title: str, description: str):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(8)

            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #8b949e;")
            page_layout.addWidget(desc)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            page_layout.addWidget(scroll)

            container = QWidget()
            scroll.setWidget(container)
            body = QVBoxLayout(container)
            body.setSpacing(16)
            body.setContentsMargins(0, 0, 0, 0)
            detail_tabs.addTab(page, title)
            return body

        entry_layout = _make_page(
            "진입 판단",
            "목표가 돌파, 보조지표, 재진입 조건처럼 '들어갈지 말지'를 판단하는 항목입니다.",
        )
        risk_layout = _make_page(
            "리스크 관리",
            "손실 한도, 종목 수, 변동성 기반 사이징처럼 계좌 위험을 줄이는 항목입니다.",
        )
        order_layout = _make_page(
            "주문/청산",
            "분할 주문, 재진입 대기, 시간 청산, 유동성 조건 등 체결과 청산 방식을 다룹니다.",
        )
        pack_layout = _make_page(
            "전략팩/백테스트",
            "전략 묶음, 포트폴리오 운용 방식, 백테스트 기본값을 고르는 항목입니다.",
        )
        guard_layout = _make_page(
            "시장 급변동 보호",
            "시장 쇼크, VI, 슬리피지 급등, 주문 실패 급증 시 신규 진입을 자동으로 제한합니다.",
        )
        system_layout = _make_page(
            "시스템",
            "자동 실행, 트레이 최소화, 사운드, 종료 시 저장 같은 앱 동작 방식을 설정합니다.",
        )

        # ── 📊 기술지표 필터 ──
        grp_ind = QGroupBox("📊 보조지표 필터")
        g1 = QGridLayout()
        g1.setSpacing(10)

        self.chk_use_rsi = QCheckBox("RSI 과열 필터")
        self.chk_use_rsi.setChecked(Config.DEFAULT_USE_RSI)
        g1.addWidget(self.chk_use_rsi, 0, 0)
        g1.addWidget(QLabel("과열 기준:"), 0, 1)
        self.spin_rsi_upper = NoScrollSpinBox()
        self.spin_rsi_upper.setRange(50, 90)
        self.spin_rsi_upper.setValue(Config.DEFAULT_RSI_UPPER)
        g1.addWidget(self.spin_rsi_upper, 0, 2)
        g1.addWidget(QLabel("계산 기간:"), 0, 3)
        self.spin_rsi_period = NoScrollSpinBox()
        self.spin_rsi_period.setRange(5, 30)
        self.spin_rsi_period.setValue(Config.DEFAULT_RSI_PERIOD)
        g1.addWidget(self.spin_rsi_period, 0, 4)

        self.chk_use_macd = QCheckBox("MACD 추세 확인")
        self.chk_use_macd.setChecked(Config.DEFAULT_USE_MACD)
        g1.addWidget(self.chk_use_macd, 1, 0)

        self.chk_use_bb = QCheckBox("볼린저밴드 확인")
        self.chk_use_bb.setChecked(Config.DEFAULT_USE_BB)
        g1.addWidget(self.chk_use_bb, 2, 0)
        g1.addWidget(QLabel("표준편차 배수:"), 2, 1)
        self.spin_bb_k = NoScrollDoubleSpinBox()
        self.spin_bb_k.setRange(1.0, 3.0)
        self.spin_bb_k.setValue(Config.DEFAULT_BB_STD)
        g1.addWidget(self.spin_bb_k, 2, 2)

        self.chk_use_dmi = QCheckBox("DMI/ADX 추세 강도")
        self.chk_use_dmi.setChecked(Config.DEFAULT_USE_DMI)
        g1.addWidget(self.chk_use_dmi, 3, 0)
        g1.addWidget(QLabel("ADX 최소값:"), 3, 1)
        self.spin_adx = NoScrollSpinBox()
        self.spin_adx.setRange(10, 50)
        self.spin_adx.setValue(Config.DEFAULT_ADX_THRESHOLD)
        g1.addWidget(self.spin_adx, 3, 2)

        self.chk_use_volume = QCheckBox("거래량 증가 확인")
        self.chk_use_volume.setChecked(Config.DEFAULT_USE_VOLUME)
        g1.addWidget(self.chk_use_volume, 4, 0)
        g1.addWidget(QLabel("평균 대비 배수:"), 4, 1)
        self.spin_volume_mult = NoScrollDoubleSpinBox()
        self.spin_volume_mult.setRange(1.0, 5.0)
        self.spin_volume_mult.setValue(Config.DEFAULT_VOLUME_MULTIPLIER)
        g1.addWidget(self.spin_volume_mult, 4, 2)

        grp_ind.setLayout(g1)
        entry_layout.addWidget(grp_ind)

        # ── 🛡️ 리스크 관리 ──
        grp_risk = QGroupBox("🛡️ 계좌 리스크 관리")
        g2 = QGridLayout()
        g2.setSpacing(10)

        self.chk_use_risk = QCheckBox("일일 손실 한도 사용")
        self.chk_use_risk.setChecked(Config.DEFAULT_USE_RISK_MGMT)
        g2.addWidget(self.chk_use_risk, 0, 0)
        g2.addWidget(QLabel("한도:"), 0, 1)
        self.spin_max_loss = NoScrollDoubleSpinBox()
        self.spin_max_loss.setRange(1, 20)
        self.spin_max_loss.setValue(Config.DEFAULT_MAX_DAILY_LOSS)
        self.spin_max_loss.setSuffix(" %")
        g2.addWidget(self.spin_max_loss, 0, 2)
        g2.addWidget(QLabel("동시 보유 수:"), 0, 3)
        self.spin_max_holdings = NoScrollSpinBox()
        self.spin_max_holdings.setRange(1, 20)
        self.spin_max_holdings.setValue(Config.DEFAULT_MAX_HOLDINGS)
        g2.addWidget(self.spin_max_holdings, 0, 4)
        self.combo_daily_loss_basis = NoScrollComboBox()
        populate_combo(
            self.combo_daily_loss_basis,
            DAILY_LOSS_BASIS_CHOICES,
            str(getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")),
        )
        self.combo_daily_loss_basis.setToolTip("일일 손실 한도를 총자산 기준으로 볼지, 주문가능금액 기준으로 볼지 고릅니다.")
        g2.addWidget(self.combo_daily_loss_basis, 0, 5)
        
        # ATR 손절
        self.chk_use_atr_stop = QCheckBox("ATR 변동성 손절")
        self.chk_use_atr_stop.setToolTip("변동성 기반 동적 손절선")
        g2.addWidget(self.chk_use_atr_stop, 1, 0)
        g2.addWidget(QLabel("ATR 배수:"), 1, 1)
        self.spin_atr_mult = NoScrollDoubleSpinBox()
        self.spin_atr_mult.setRange(1.0, 5.0)
        self.spin_atr_mult.setValue(2.0)
        g2.addWidget(self.spin_atr_mult, 1, 2)

        # 시장 분산
        self.chk_use_market_limit = QCheckBox("시장 분산 제한")
        self.chk_use_market_limit.setToolTip("코스피/코스닥 비중 제한")
        g2.addWidget(self.chk_use_market_limit, 2, 0)
        g2.addWidget(QLabel("한 시장 최대:"), 2, 1)
        self.spin_market_limit = NoScrollSpinBox()
        self.spin_market_limit.setRange(50, 100)
        self.spin_market_limit.setValue(70)
        self.spin_market_limit.setSuffix(" %")
        g2.addWidget(self.spin_market_limit, 2, 2)

        # 섹터 제한
        self.chk_use_sector_limit = QCheckBox("업종 집중 제한")
        self.chk_use_sector_limit.setToolTip("동일 업종 투자 비중 제한")
        g2.addWidget(self.chk_use_sector_limit, 2, 3)
        g2.addWidget(QLabel("한 업종 최대:"), 2, 4)
        self.spin_sector_limit = NoScrollSpinBox()
        self.spin_sector_limit.setRange(10, 50)
        self.spin_sector_limit.setValue(30)
        self.spin_sector_limit.setSuffix(" %")
        g2.addWidget(self.spin_sector_limit, 2, 5)

        # 동적 포지션 사이징
        self.chk_use_dynamic_sizing = QCheckBox("연속 손실 시 비중 축소")
        self.chk_use_dynamic_sizing.setToolTip("연속 손실 시 투자금 자동 축소 (Anti-Martingale)")
        g2.addWidget(self.chk_use_dynamic_sizing, 3, 0, 1, 2)

        # ATR 포지션 사이징
        self.chk_use_atr_sizing = QCheckBox("ATR 기반 주문 크기")
        g2.addWidget(self.chk_use_atr_sizing, 3, 2)
        g2.addWidget(QLabel("허용 위험:"), 3, 3)
        self.spin_risk_percent = NoScrollDoubleSpinBox()
        self.spin_risk_percent.setRange(0.5, 5.0)
        self.spin_risk_percent.setValue(1.0)
        self.spin_risk_percent.setSuffix(" %")
        g2.addWidget(self.spin_risk_percent, 3, 4)

        grp_risk.setLayout(g2)
        risk_layout.addWidget(grp_risk)

        # ── 📈 진입 전략 ──
        grp_entry = QGroupBox("📈 추가 진입 판단")
        g3 = QGridLayout()
        g3.setSpacing(10)

        self.chk_use_ma = QCheckBox("이동평균 정배열")
        g3.addWidget(self.chk_use_ma, 0, 0)
        g3.addWidget(QLabel("단기선:"), 0, 1)
        self.spin_ma_short = NoScrollSpinBox()
        self.spin_ma_short.setRange(3, 20)
        self.spin_ma_short.setValue(Config.DEFAULT_MA_SHORT)
        g3.addWidget(self.spin_ma_short, 0, 2)
        g3.addWidget(QLabel("장기선:"), 0, 3)
        self.spin_ma_long = NoScrollSpinBox()
        self.spin_ma_long.setRange(10, 60)
        self.spin_ma_long.setValue(Config.DEFAULT_MA_LONG)
        g3.addWidget(self.spin_ma_long, 0, 4)

        self.chk_use_stoch_rsi = QCheckBox("스토캐스틱 RSI")
        self.chk_use_stoch_rsi.setToolTip("RSI보다 민감한 과매수/과매도 감지")
        g3.addWidget(self.chk_use_stoch_rsi, 1, 0)
        g3.addWidget(QLabel("과열 기준:"), 1, 1)
        self.spin_stoch_upper = NoScrollSpinBox()
        self.spin_stoch_upper.setRange(60, 95)
        self.spin_stoch_upper.setValue(80)
        g3.addWidget(self.spin_stoch_upper, 1, 2)
        g3.addWidget(QLabel("과매도 기준:"), 1, 3)
        self.spin_stoch_lower = NoScrollSpinBox()
        self.spin_stoch_lower.setRange(5, 40)
        self.spin_stoch_lower.setValue(20)
        g3.addWidget(self.spin_stoch_lower, 1, 4)

        self.chk_use_mtf = QCheckBox("다중 시간대 추세 일치")
        self.chk_use_mtf.setToolTip("일봉+분봉 추세 일치 시에만 진입")
        g3.addWidget(self.chk_use_mtf, 2, 0, 1, 2)

        self.chk_use_gap = QCheckBox("시가 갭 분석")
        self.chk_use_gap.setToolTip("갭 상승/하락에 따라 K값 자동 조정")
        g3.addWidget(self.chk_use_gap, 2, 2, 1, 2)

        self.chk_use_time_strategy = QCheckBox("시간대별 전략 사용")
        self.chk_use_time_strategy.setToolTip("09:00-09:30 공격적, 09:30-14:30 기본, 14:30- 보수적")
        g3.addWidget(self.chk_use_time_strategy, 3, 0, 1, 2)

        self.chk_use_breakout_confirm = QCheckBox("돌파 확인 후 진입")
        self.chk_use_breakout_confirm.setToolTip("목표가 돌파 후 N틱 유지 시 진입")
        self.chk_use_breakout_confirm.setChecked(Config.DEFAULT_USE_BREAKOUT_CONFIRM)
        g3.addWidget(self.chk_use_breakout_confirm, 3, 2)
        g3.addWidget(QLabel("확인 틱 수:"), 3, 3)
        self.spin_breakout_ticks = NoScrollSpinBox()
        self.spin_breakout_ticks.setRange(1, 10)
        self.spin_breakout_ticks.setValue(Config.DEFAULT_BREAKOUT_TICKS)
        g3.addWidget(self.spin_breakout_ticks, 3, 4)

        self.chk_use_entry_score = QCheckBox("종합 점수 기준 사용")
        self.chk_use_entry_score.setToolTip("여러 지표 점수가 기준 이상일 때만 진입")
        self.chk_use_entry_score.setChecked(Config.USE_ENTRY_SCORING)
        g3.addWidget(self.chk_use_entry_score, 4, 0)
        self.spin_entry_score_threshold = NoScrollSpinBox()
        self.spin_entry_score_threshold.setRange(40, 100)
        self.spin_entry_score_threshold.setValue(Config.ENTRY_SCORE_THRESHOLD)
        g3.addWidget(self.spin_entry_score_threshold, 4, 1)

        self.chk_use_partial_profit = QCheckBox("부분 익절 사용")
        self.chk_use_partial_profit.setToolTip("3%→30%, 5%→30%, 8%→20% 분할 청산")
        g3.addWidget(self.chk_use_partial_profit, 4, 2, 1, 2)

        grp_entry.setLayout(g3)
        entry_layout.addWidget(grp_entry)

        # ── ⚙️ 주문 실행 ──
        grp_order = QGroupBox("⚙️ 주문/청산 상세")
        g4 = QGridLayout()
        g4.setSpacing(10)

        self.chk_use_split = QCheckBox("분할 매수")
        self.chk_use_split.setToolTip("지정가 우선 주문 방식에서만 동작하며, 분할 가격으로 즉시 다건 제출됩니다.")
        g4.addWidget(self.chk_use_split, 0, 0)
        g4.addWidget(QLabel("나눌 횟수:"), 0, 1)
        self.spin_split_count = NoScrollSpinBox()
        self.spin_split_count.setRange(2, 5)
        self.spin_split_count.setValue(Config.DEFAULT_SPLIT_COUNT)
        g4.addWidget(self.spin_split_count, 0, 2)
        g4.addWidget(QLabel("매수 간격:"), 0, 3)
        self.spin_split_percent = NoScrollDoubleSpinBox()
        self.spin_split_percent.setRange(0.1, 2.0)
        self.spin_split_percent.setValue(Config.DEFAULT_SPLIT_PERCENT)
        self.spin_split_percent.setSuffix(" %")
        g4.addWidget(self.spin_split_percent, 0, 4)

        self.chk_use_cooldown = QCheckBox("재진입 대기 시간")
        self.chk_use_cooldown.setToolTip("매도 후 일정 시간 재진입 제한")
        self.chk_use_cooldown.setChecked(Config.DEFAULT_USE_COOLDOWN)
        g4.addWidget(self.chk_use_cooldown, 1, 0)
        g4.addWidget(QLabel("대기 시간:"), 1, 1)
        self.spin_cooldown_min = NoScrollSpinBox()
        self.spin_cooldown_min.setRange(1, 120)
        self.spin_cooldown_min.setSuffix(" 분")
        self.spin_cooldown_min.setValue(Config.DEFAULT_COOLDOWN_MINUTES)
        g4.addWidget(self.spin_cooldown_min, 1, 2)

        self.chk_use_time_stop = QCheckBox("보유 시간 초과 청산")
        self.chk_use_time_stop.setToolTip("보유 시간이 기준을 넘으면 자동 청산")
        self.chk_use_time_stop.setChecked(Config.DEFAULT_USE_TIME_STOP)
        g4.addWidget(self.chk_use_time_stop, 1, 3)
        g4.addWidget(QLabel("최대 보유:"), 1, 4)
        self.spin_time_stop_min = NoScrollSpinBox()
        self.spin_time_stop_min.setRange(5, 480)
        self.spin_time_stop_min.setSuffix(" 분")
        self.spin_time_stop_min.setValue(Config.DEFAULT_MAX_HOLD_MINUTES)
        g4.addWidget(self.spin_time_stop_min, 1, 5)

        self.chk_use_liquidity = QCheckBox("유동성 필터")
        self.chk_use_liquidity.setToolTip("20일 평균 거래대금 기준")
        self.chk_use_liquidity.setChecked(Config.DEFAULT_USE_LIQUIDITY)
        g4.addWidget(self.chk_use_liquidity, 2, 0)
        g4.addWidget(QLabel("최소 거래대금:"), 2, 1)
        self.spin_min_value = NoScrollDoubleSpinBox()
        self.spin_min_value.setRange(1, 500)
        self.spin_min_value.setValue(Config.DEFAULT_MIN_AVG_VALUE / 100_000_000)
        self.spin_min_value.setSuffix(" 억")
        g4.addWidget(self.spin_min_value, 2, 2)

        self.chk_use_spread = QCheckBox("호가 스프레드 제한")
        self.chk_use_spread.setToolTip("호가 스프레드가 좁을 때만 진입")
        self.chk_use_spread.setChecked(Config.DEFAULT_USE_SPREAD)
        g4.addWidget(self.chk_use_spread, 2, 3)
        g4.addWidget(QLabel("최대 허용 폭:"), 2, 4)
        self.spin_spread_max = NoScrollDoubleSpinBox()
        self.spin_spread_max.setRange(0.05, 2.0)
        self.spin_spread_max.setValue(Config.DEFAULT_MAX_SPREAD_PCT)
        self.spin_spread_max.setSuffix(" %")
        g4.addWidget(self.spin_spread_max, 2, 5)

        grp_order.setLayout(g4)
        order_layout.addWidget(grp_order)

        # ── 🚀 v5.0 Strategy Pack ──
        grp_v5 = QGroupBox("🚀 전략 묶음/백테스트")
        g5 = QGridLayout()
        g5.setSpacing(10)

        g5.addWidget(QLabel("전략 묶음:"), 0, 0)
        self.combo_strategy_pack = NoScrollComboBox()
        populate_combo(
            self.combo_strategy_pack,
            STRATEGY_CHOICES,
            Config.DEFAULT_STRATEGY_PACK.get("primary_strategy", "volatility_breakout"),
        )
        g5.addWidget(self.combo_strategy_pack, 0, 1, 1, 2)

        g5.addWidget(QLabel("포트폴리오 방식:"), 0, 3)
        self.combo_portfolio_mode = NoScrollComboBox()
        populate_combo(self.combo_portfolio_mode, PORTFOLIO_MODE_CHOICES, Config.DEFAULT_PORTFOLIO_MODE)
        g5.addWidget(self.combo_portfolio_mode, 0, 4)

        self.chk_short_enabled = QCheckBox("공매도 허용 (모의/백테스트 전용)")
        self.chk_short_enabled.setToolTip("SHORT 전략은 현재 자동매매에서 지원하지 않으며, 백테스트/연구용 표기입니다.")
        self.chk_short_enabled.setChecked(Config.DEFAULT_SHORT_ENABLED)
        g5.addWidget(self.chk_short_enabled, 1, 0, 1, 2)

        g5.addWidget(QLabel("운용 자산 범위:"), 1, 2)
        self.combo_asset_scope = NoScrollComboBox()
        populate_combo(self.combo_asset_scope, ASSET_SCOPE_CHOICES, Config.DEFAULT_ASSET_SCOPE)
        g5.addWidget(self.combo_asset_scope, 1, 3, 1, 2)

        g5.addWidget(QLabel("주문 방식:"), 2, 0)
        self.combo_execution_policy = NoScrollComboBox()
        populate_combo(
            self.combo_execution_policy,
            EXECUTION_POLICY_CHOICES,
            getattr(Config, "DEFAULT_EXECUTION_POLICY", "market"),
        )
        g5.addWidget(self.combo_execution_policy, 2, 1)

        g5.addWidget(QLabel("백테스트 시간 단위:"), 2, 2)
        self.combo_backtest_timeframe = NoScrollComboBox()
        populate_combo(
            self.combo_backtest_timeframe,
            BACKTEST_TIMEFRAME_CHOICES,
            Config.DEFAULT_BACKTEST_CONFIG.get("timeframe", "1d"),
        )
        g5.addWidget(self.combo_backtest_timeframe, 2, 3)

        g5.addWidget(QLabel("조회 기간(일):"), 2, 4)
        self.spin_backtest_lookback = NoScrollSpinBox()
        self.spin_backtest_lookback.setRange(60, 5000)
        self.spin_backtest_lookback.setValue(int(Config.DEFAULT_BACKTEST_CONFIG.get("lookback_days", 365)))
        g5.addWidget(self.spin_backtest_lookback, 2, 5)

        g5.addWidget(QLabel("수수료(bp):"), 3, 0)
        self.spin_backtest_commission = NoScrollDoubleSpinBox()
        self.spin_backtest_commission.setRange(0.0, 50.0)
        self.spin_backtest_commission.setValue(float(Config.DEFAULT_BACKTEST_CONFIG.get("commission_bps", 5.0)))
        g5.addWidget(self.spin_backtest_commission, 3, 1)

        g5.addWidget(QLabel("슬리피지(bp):"), 3, 2)
        self.spin_backtest_slippage = NoScrollDoubleSpinBox()
        self.spin_backtest_slippage.setRange(0.0, 50.0)
        self.spin_backtest_slippage.setValue(float(Config.DEFAULT_BACKTEST_CONFIG.get("slippage_bps", 3.0)))
        g5.addWidget(self.spin_backtest_slippage, 3, 3)

        self.chk_feature_modular_pack = QCheckBox("모듈형 전략 엔진 사용")
        self.chk_feature_modular_pack.setChecked(bool(Config.FEATURE_FLAGS.get("use_modular_strategy_pack", True)))
        g5.addWidget(self.chk_feature_modular_pack, 4, 0, 1, 2)
        self.chk_feature_backtest = QCheckBox("백테스트 기능 사용")
        self.chk_feature_backtest.setToolTip("현재는 연구용 설정으로 저장만 되며, UI에서 직접 실행되지는 않습니다.")
        self.chk_feature_backtest.setChecked(bool(Config.FEATURE_FLAGS.get("enable_backtest", True)))
        g5.addWidget(self.chk_feature_backtest, 4, 2)
        self.chk_feature_external_data = QCheckBox("외부 데이터 사용")
        self.chk_feature_external_data.setChecked(bool(Config.FEATURE_FLAGS.get("enable_external_data", True)))
        g5.addWidget(self.chk_feature_external_data, 4, 3, 1, 2)

        lbl_pack_note = QLabel(
            "포트폴리오 방식/백테스트 시간 단위/조회 기간/수수료/슬리피지는 현재 연구용 설정입니다. "
            "설정 저장은 지원하지만 자동매매 런타임에는 직접 연결되지 않습니다."
        )
        lbl_pack_note.setWordWrap(True)
        lbl_pack_note.setStyleSheet("color: #8b949e; font-size: 11px;")
        g5.addWidget(lbl_pack_note, 5, 0, 1, 6)

        grp_v5.setLayout(g5)
        pack_layout.addWidget(grp_v5)

        # ── 🚨 v4 급변동/서킷 가드 ──
        grp_guard = QGroupBox("🚨 시장 급변동 보호")
        g7 = QGridLayout()
        g7.setSpacing(10)

        self.chk_use_shock_guard = QCheckBox("시장 쇼크 보호")
        self.chk_use_shock_guard.setChecked(bool(getattr(Config, "DEFAULT_USE_SHOCK_GUARD", True)))
        g7.addWidget(self.chk_use_shock_guard, 0, 0)
        g7.addWidget(QLabel("1분 변동률:"), 0, 1)
        self.spin_shock_1m = NoScrollDoubleSpinBox()
        self.spin_shock_1m.setRange(0.5, 10.0)
        self.spin_shock_1m.setSingleStep(0.1)
        self.spin_shock_1m.setValue(float(getattr(Config, "DEFAULT_SHOCK_1M_PCT", 1.5)))
        self.spin_shock_1m.setSuffix(" %")
        g7.addWidget(self.spin_shock_1m, 0, 2)
        g7.addWidget(QLabel("5분 변동률:"), 0, 3)
        self.spin_shock_5m = NoScrollDoubleSpinBox()
        self.spin_shock_5m.setRange(1.0, 15.0)
        self.spin_shock_5m.setSingleStep(0.1)
        self.spin_shock_5m.setValue(float(getattr(Config, "DEFAULT_SHOCK_5M_PCT", 2.8)))
        self.spin_shock_5m.setSuffix(" %")
        g7.addWidget(self.spin_shock_5m, 0, 4)
        g7.addWidget(QLabel("보호 유지 시간:"), 0, 5)
        self.spin_shock_cooldown = NoScrollSpinBox()
        self.spin_shock_cooldown.setRange(1, 120)
        self.spin_shock_cooldown.setSuffix(" 분")
        self.spin_shock_cooldown.setValue(int(getattr(Config, "DEFAULT_SHOCK_COOLDOWN_MIN", 10)))
        g7.addWidget(self.spin_shock_cooldown, 0, 6)

        self.chk_use_vi_guard = QCheckBox("VI/거래정지 보호")
        self.chk_use_vi_guard.setChecked(bool(getattr(Config, "DEFAULT_USE_VI_GUARD", True)))
        g7.addWidget(self.chk_use_vi_guard, 1, 0)
        g7.addWidget(QLabel("보호 유지 시간:"), 1, 1)
        self.spin_vi_cooldown = NoScrollSpinBox()
        self.spin_vi_cooldown.setRange(1, 120)
        self.spin_vi_cooldown.setSuffix(" 분")
        self.spin_vi_cooldown.setValue(int(getattr(Config, "DEFAULT_VI_COOLDOWN_MIN", 7)))
        g7.addWidget(self.spin_vi_cooldown, 1, 2)

        self.chk_use_regime_sizing = QCheckBox("시장 상태별 비중 축소")
        self.chk_use_regime_sizing.setChecked(bool(getattr(Config, "DEFAULT_USE_REGIME_SIZING", True)))
        g7.addWidget(self.chk_use_regime_sizing, 1, 3, 1, 2)

        self.chk_use_slippage_guard = QCheckBox("슬리피지 보호")
        self.chk_use_slippage_guard.setChecked(bool(getattr(Config, "DEFAULT_USE_SLIPPAGE_GUARD", True)))
        g7.addWidget(self.chk_use_slippage_guard, 2, 0)
        g7.addWidget(QLabel("최대 허용(bp):"), 2, 1)
        self.spin_max_slippage_bps = NoScrollDoubleSpinBox()
        self.spin_max_slippage_bps.setRange(1.0, 100.0)
        self.spin_max_slippage_bps.setSingleStep(1.0)
        self.spin_max_slippage_bps.setValue(float(getattr(Config, "DEFAULT_MAX_SLIPPAGE_BPS", 15.0)))
        g7.addWidget(self.spin_max_slippage_bps, 2, 2)

        self.chk_use_order_health_guard = QCheckBox("주문 실패 급증 보호")
        self.chk_use_order_health_guard.setChecked(bool(getattr(Config, "DEFAULT_USE_ORDER_HEALTH_GUARD", True)))
        g7.addWidget(self.chk_use_order_health_guard, 2, 3, 1, 2)

        self.chk_use_liquidity_stress_guard = QCheckBox("유동성 스트레스 보호")
        self.chk_use_liquidity_stress_guard.setChecked(
            bool(getattr(Config, "DEFAULT_USE_LIQUIDITY_STRESS_GUARD", True))
        )
        g7.addWidget(self.chk_use_liquidity_stress_guard, 3, 0, 1, 2)

        guard_notice = QLabel("주의: 이 영역은 시장 급변 시 신규 진입을 자동으로 제한합니다. 실거래에서는 기본적으로 켜 두는 편이 안전합니다.")
        guard_notice.setWordWrap(True)
        guard_notice.setStyleSheet("color: #d29922;")
        g7.addWidget(guard_notice, 4, 0, 1, 7)

        grp_guard.setLayout(g7)
        guard_layout.addWidget(grp_guard)

        # ── 🔧 시스템 설정 ──
        grp_sys = QGroupBox("🔧 시스템 설정")
        g6 = QGridLayout()
        g6.setSpacing(10)

        self.chk_auto_start = QCheckBox("윈도우 시작 시 자동 실행")
        self.chk_auto_start.setToolTip("윈도우 부팅 시 프로그램이 자동으로 시작됩니다.")
        self.chk_auto_start.toggled.connect(self._set_auto_start)
        g6.addWidget(self.chk_auto_start, 0, 0, 1, 2)

        self.chk_minimize_tray = QCheckBox("종료 시 트레이로 최소화")
        self.chk_minimize_tray.setToolTip("창을 닫아도 프로그램이 종료되지 않고 트레이 아이콘으로 숨겨집니다.")
        self.chk_minimize_tray.setChecked(Config.DEFAULT_MINIMIZE_TO_TRAY)
        g6.addWidget(self.chk_minimize_tray, 0, 2, 1, 3)

        self.chk_use_sound = QCheckBox("사운드 알림")
        self.chk_use_sound.setToolTip("매수/매도 시 알림음 재생")
        self.chk_use_sound.stateChanged.connect(self._on_sound_changed)
        g6.addWidget(self.chk_use_sound, 1, 0, 1, 2)

        self.chk_sync_history_flush_on_exit = QCheckBox("종료 시 거래내역 동기 저장")
        self.chk_sync_history_flush_on_exit.setToolTip("강제 종료 직전 거래내역을 동기 저장하여 유실을 줄입니다.")
        self.chk_sync_history_flush_on_exit.setChecked(
            bool(getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True))
        )
        g6.addWidget(self.chk_sync_history_flush_on_exit, 1, 2, 1, 3)

        grp_sys.setLayout(g6)
        system_layout.addWidget(grp_sys)

        # === 이벤트 연결 및 초기 상태 설정 ===
        self.chk_use_rsi.toggled.connect(lambda s: self.spin_rsi_upper.setEnabled(s))
        self.chk_use_rsi.toggled.connect(lambda s: self.spin_rsi_period.setEnabled(s))
        self.spin_rsi_upper.setEnabled(self.chk_use_rsi.isChecked())
        self.spin_rsi_period.setEnabled(self.chk_use_rsi.isChecked())

        self.chk_use_bb.toggled.connect(lambda s: self.spin_bb_k.setEnabled(s))
        self.spin_bb_k.setEnabled(self.chk_use_bb.isChecked())

        self.chk_use_dmi.toggled.connect(lambda s: self.spin_adx.setEnabled(s))
        self.spin_adx.setEnabled(self.chk_use_dmi.isChecked())

        self.chk_use_volume.toggled.connect(lambda s: self.spin_volume_mult.setEnabled(s))
        self.spin_volume_mult.setEnabled(self.chk_use_volume.isChecked())

        self.chk_use_risk.toggled.connect(lambda s: self.spin_max_loss.setEnabled(s))
        self.chk_use_risk.toggled.connect(lambda s: self.spin_max_holdings.setEnabled(s))
        self.spin_max_loss.setEnabled(self.chk_use_risk.isChecked())
        self.spin_max_holdings.setEnabled(self.chk_use_risk.isChecked())

        self.chk_use_ma.toggled.connect(lambda s: self.spin_ma_short.setEnabled(s))
        self.chk_use_ma.toggled.connect(lambda s: self.spin_ma_long.setEnabled(s))
        self.spin_ma_short.setEnabled(self.chk_use_ma.isChecked())
        self.spin_ma_long.setEnabled(self.chk_use_ma.isChecked())

        self.chk_use_atr_sizing.toggled.connect(lambda s: self.spin_risk_percent.setEnabled(s))
        self.spin_risk_percent.setEnabled(self.chk_use_atr_sizing.isChecked())

        self.chk_use_split.toggled.connect(lambda s: self.spin_split_count.setEnabled(s))
        self.chk_use_split.toggled.connect(lambda s: self.spin_split_percent.setEnabled(s))
        self.spin_split_count.setEnabled(self.chk_use_split.isChecked())
        self.spin_split_percent.setEnabled(self.chk_use_split.isChecked())

        self.chk_use_stoch_rsi.toggled.connect(lambda s: self.spin_stoch_upper.setEnabled(s))
        self.chk_use_stoch_rsi.toggled.connect(lambda s: self.spin_stoch_lower.setEnabled(s))
        self.spin_stoch_upper.setEnabled(self.chk_use_stoch_rsi.isChecked())
        self.spin_stoch_lower.setEnabled(self.chk_use_stoch_rsi.isChecked())

        self.chk_use_market_limit.toggled.connect(lambda s: self.spin_market_limit.setEnabled(s))
        self.spin_market_limit.setEnabled(self.chk_use_market_limit.isChecked())

        self.chk_use_sector_limit.toggled.connect(lambda s: self.spin_sector_limit.setEnabled(s))
        self.spin_sector_limit.setEnabled(self.chk_use_sector_limit.isChecked())

        self.chk_use_atr_stop.toggled.connect(lambda s: self.spin_atr_mult.setEnabled(s))
        self.spin_atr_mult.setEnabled(self.chk_use_atr_stop.isChecked())

        self.chk_use_liquidity.toggled.connect(lambda s: self.spin_min_value.setEnabled(s))
        self.spin_min_value.setEnabled(self.chk_use_liquidity.isChecked())

        self.chk_use_spread.toggled.connect(lambda s: self.spin_spread_max.setEnabled(s))
        self.spin_spread_max.setEnabled(self.chk_use_spread.isChecked())

        self.chk_use_breakout_confirm.toggled.connect(lambda s: self.spin_breakout_ticks.setEnabled(s))
        self.spin_breakout_ticks.setEnabled(self.chk_use_breakout_confirm.isChecked())

        self.chk_use_cooldown.toggled.connect(lambda s: self.spin_cooldown_min.setEnabled(s))
        self.spin_cooldown_min.setEnabled(self.chk_use_cooldown.isChecked())

        self.chk_use_time_stop.toggled.connect(lambda s: self.spin_time_stop_min.setEnabled(s))
        self.spin_time_stop_min.setEnabled(self.chk_use_time_stop.isChecked())

        self.chk_use_entry_score.toggled.connect(lambda s: self.spin_entry_score_threshold.setEnabled(s))
        self.spin_entry_score_threshold.setEnabled(self.chk_use_entry_score.isChecked())

        self.chk_use_shock_guard.toggled.connect(lambda s: self.spin_shock_1m.setEnabled(s))
        self.chk_use_shock_guard.toggled.connect(lambda s: self.spin_shock_5m.setEnabled(s))
        self.chk_use_shock_guard.toggled.connect(lambda s: self.spin_shock_cooldown.setEnabled(s))
        self.spin_shock_1m.setEnabled(self.chk_use_shock_guard.isChecked())
        self.spin_shock_5m.setEnabled(self.chk_use_shock_guard.isChecked())
        self.spin_shock_cooldown.setEnabled(self.chk_use_shock_guard.isChecked())
        self.chk_use_vi_guard.toggled.connect(lambda s: self.spin_vi_cooldown.setEnabled(s))
        self.spin_vi_cooldown.setEnabled(self.chk_use_vi_guard.isChecked())
        self.chk_use_slippage_guard.toggled.connect(lambda s: self.spin_max_slippage_bps.setEnabled(s))
        self.spin_max_slippage_bps.setEnabled(self.chk_use_slippage_guard.isChecked())

        entry_layout.addStretch()
        risk_layout.addStretch()
        order_layout.addStretch()
        pack_layout.addStretch()
        guard_layout.addStretch()
        system_layout.addStretch()
        return main_widget

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
        
        self.chart_type_combo = NoScrollComboBox()
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
        chart_header = self.chart_table.horizontalHeader()
        if chart_header is not None:
            chart_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        ask_vertical_header = self.ask_table.verticalHeader()
        ask_horizontal_header = self.ask_table.horizontalHeader()
        if ask_vertical_header is not None:
            ask_vertical_header.setVisible(False)  # 행 번호 숨김
        if ask_horizontal_header is not None:
            ask_horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ask_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ask_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ask_table.setFixedHeight(320)
        for i in range(10):
            self.ask_table.setRowHeight(i, 28)
        hoga_layout.addWidget(self.ask_table)
        
        # 매수 호가 테이블
        self.bid_table = QTableWidget(10, 2)
        self.bid_table.setHorizontalHeaderLabels(["매수호가", "잔량"])
        bid_vertical_header = self.bid_table.verticalHeader()
        bid_horizontal_header = self.bid_table.horizontalHeader()
        if bid_vertical_header is not None:
            bid_vertical_header.setVisible(False)  # 행 번호 숨김
        if bid_horizontal_header is not None:
            bid_horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        self.condition_combo = NoScrollComboBox()
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
        condition_header = self.condition_table.horizontalHeader()
        if condition_header is not None:
            condition_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        self.ranking_type = NoScrollComboBox()
        self.ranking_type.addItems(["거래량 상위", "상승률 상위", "하락률 상위"])
        ctrl_layout.addWidget(self.ranking_type)
        
        self.ranking_market = NoScrollComboBox()
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
        ranking_header = self.ranking_table.horizontalHeader()
        if ranking_header is not None:
            ranking_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ranking_table)
        
        return widget

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
        history_header = self.history_table.horizontalHeader()
        if history_header is not None:
            history_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

    def _create_diagnostics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        action_row = QHBoxLayout()
        self.btn_diag_resync_selected = QPushButton("선택 종목 재동기화")
        self.btn_diag_resync_selected.clicked.connect(self._on_diagnostic_resync_selected)
        action_row.addWidget(self.btn_diag_resync_selected)
        self.btn_diag_release_sync_failed = QPushButton("동기화 실패 해제 요청")
        self.btn_diag_release_sync_failed.clicked.connect(self._on_diagnostic_release_sync_failed_selected)
        action_row.addWidget(self.btn_diag_release_sync_failed)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.diagnostic_table = QTableWidget()
        cols = [
            "코드",
            "종목명",
            "대기 주문 방향",
            "대기 주문 사유",
            "대기 만료 시각",
            "동기화 상태",
            "재시도 횟수",
            "마지막 동기화 오류",
            "최근 갱신",
            "외부 데이터 상태",
            "외부 데이터 시각",
            "외부 데이터 경과(초)",
            "시장 상태",
            "보호 사유",
            "인텔리전스 소스 상태",
            "자동매매 정책",
            "수량 배수",
            "청산 정책",
            "마지막 이벤트 ID",
            "시장 위험 모드",
            "주문 안정성 모드",
            "대기 주문 상태",
            "미체결 수량",
            "동기화 실패 사유",
        ]
        self.diagnostic_table.setColumnCount(len(cols))
        self.diagnostic_table.setHorizontalHeaderLabels(cols)
        diagnostic_header = self.diagnostic_table.horizontalHeader()
        diagnostic_vertical_header = self.diagnostic_table.verticalHeader()
        if diagnostic_header is not None:
            diagnostic_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if diagnostic_vertical_header is not None:
            diagnostic_vertical_header.setVisible(False)
        self.diagnostic_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diagnostic_table.itemSelectionChanged.connect(self._on_diagnostic_selection_changed)
        layout.addWidget(self.diagnostic_table)

        self.diag_detail_panel = QPlainTextEdit()
        self.diag_detail_panel.setReadOnly(True)
        self.diag_detail_panel.setMaximumHeight(180)
        self.diag_detail_panel.setPlainText("선택된 종목이 없습니다.")
        layout.addWidget(self.diag_detail_panel)

        info = QLabel("주문/동기화 상태를 실시간으로 진단합니다. 이 화면은 읽기 전용입니다.")
        info.setWordWrap(True)
        layout.addWidget(info)
        return widget

    def _create_api_tab(self):
        """API/알림 설정 탭"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # API 인증
        group1 = QGroupBox("🔐 키움 REST API 인증")
        form1 = QFormLayout()
        self.input_app_key = QLineEdit()
        self.input_app_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_app_key.setPlaceholderText("키움 App Key")
        form1.addRow("앱 키:", self.input_app_key)
        self.input_secret = QLineEdit()
        self.input_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_secret.setPlaceholderText("키움 Secret Key")
        form1.addRow("시크릿 키:", self.input_secret)
        self.chk_mock = QCheckBox("모의투자 사용")
        form1.addRow("", self.chk_mock)
        group1.setLayout(form1)
        layout.addWidget(group1)
        
        # 텔레그램
        group2 = QGroupBox("📱 텔레그램 알림")
        form2 = QFormLayout()
        self.input_tg_token = QLineEdit()
        self.input_tg_token.setPlaceholderText("텔레그램 Bot Token")
        form2.addRow("봇 토큰:", self.input_tg_token)
        self.input_tg_chat = QLineEdit()
        self.input_tg_chat.setPlaceholderText("텔레그램 Chat ID")
        form2.addRow("챗 ID:", self.input_tg_chat)
        self.chk_use_telegram = QCheckBox("텔레그램 알림 사용")
        form2.addRow("", self.chk_use_telegram)
        group2.setLayout(form2)
        layout.addWidget(group2)

        group3 = QGroupBox("ℹ️ 안내")
        form3 = QFormLayout()
        info_auto_start = QLabel(
            "시장 인텔리전스 관련 설정은 [🧠 인텔리전스 설정] 탭에서 관리합니다.\n자동 실행과 앱 동작 설정은 [🛠 상세 설정 > 시스템]에서 변경합니다."
        )
        info_auto_start.setWordWrap(True)
        form3.addRow("", info_auto_start)

        group3.setLayout(form3)
        layout.addWidget(group3)
        
        btn_save = QPushButton("💾 전체 설정 저장")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)
        layout.addStretch()
        
        scroll.setWidget(content_widget)
        tab_layout.addWidget(scroll)
        
        return tab_widget

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


