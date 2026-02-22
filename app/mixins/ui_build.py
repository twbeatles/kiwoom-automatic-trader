"""UI construction mixin for KiwoomProTrader."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import *

from app.support.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox
from config import Config
from dark_theme import DARK_STYLESHEET

class UIBuildMixin:
    def _init_ui(self):
        self.setWindowTitle("Kiwoom Pro Algo-Trader v4.3 [REST API]")
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
        group = QGroupBox("📊 트레이딩 대시보드")
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
        tabs.addTab(self._create_strategy_tab(), "⚙️ 전략 설정")
        tabs.addTab(self._create_advanced_tab(), "🔬 고급 설정")
        tabs.addTab(self._create_chart_tab(), "📈 차트")
        tabs.addTab(self._create_orderbook_tab(), "📋 호가창")
        tabs.addTab(self._create_condition_tab(), "🔍 조건검색")
        tabs.addTab(self._create_ranking_tab(), "🏆 순위")
        tabs.addTab(self._create_stats_tab(), "📊 통계")
        tabs.addTab(self._create_history_tab(), "📝 내역")
        tabs.addTab(self._create_diagnostics_tab(), "🩺 진단")
        tabs.addTab(self._create_api_tab(), "🔑 API")
        return tabs

    def _create_strategy_tab(self):
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(10)
        
        # 즐겨찾기 콤보박스
        self.combo_favorites = NoScrollComboBox()
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
        self.spin_betting = NoScrollDoubleSpinBox()
        self.spin_betting.setRange(1, 100)
        self.spin_betting.setValue(Config.DEFAULT_BETTING_RATIO)
        self.spin_betting.setSuffix(" %")
        layout.addWidget(self.spin_betting, 1, 1)
        
        layout.addWidget(QLabel("📐 K값:"), 1, 2)
        self.spin_k = NoScrollDoubleSpinBox()
        self.spin_k.setRange(0.1, 1.0)
        self.spin_k.setSingleStep(0.1)
        self.spin_k.setValue(Config.DEFAULT_K_VALUE)
        layout.addWidget(self.spin_k, 1, 3)
        
        layout.addWidget(QLabel("🎯 TS 발동:"), 2, 0)
        self.spin_ts_start = NoScrollDoubleSpinBox()
        self.spin_ts_start.setRange(0.5, 20)
        self.spin_ts_start.setValue(Config.DEFAULT_TS_START)
        self.spin_ts_start.setSuffix(" %")
        layout.addWidget(self.spin_ts_start, 2, 1)
        
        layout.addWidget(QLabel("📉 TS 하락:"), 2, 2)
        self.spin_ts_stop = NoScrollDoubleSpinBox()
        self.spin_ts_stop.setRange(0.5, 10)
        self.spin_ts_stop.setValue(Config.DEFAULT_TS_STOP)
        self.spin_ts_stop.setSuffix(" %")
        layout.addWidget(self.spin_ts_stop, 2, 3)
        
        layout.addWidget(QLabel("🛑 손절률:"), 2, 4)
        self.spin_loss = NoScrollDoubleSpinBox()
        self.spin_loss.setRange(0.5, 10)
        self.spin_loss.setValue(Config.DEFAULT_LOSS_CUT)
        self.spin_loss.setSuffix(" %")
        layout.addWidget(self.spin_loss, 2, 5)
        
        # 버튼들이 대시보드로 이동됨 (v4.4)
        # 공간 확보를 위한 스트레치
        layout.setRowStretch(3, 1)
        
        return widget

    def _create_advanced_tab(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        
        widget = QWidget()
        scroll.setWidget(widget)
        
        layout = QGridLayout(widget)
        layout.setSpacing(10)
        
        # RSI
        self.chk_use_rsi = QCheckBox("RSI 필터")
        self.chk_use_rsi.setChecked(Config.DEFAULT_USE_RSI)
        layout.addWidget(self.chk_use_rsi, 0, 0)
        layout.addWidget(QLabel("과매수:"), 0, 1)
        self.spin_rsi_upper = NoScrollSpinBox()
        self.spin_rsi_upper.setRange(50, 90)
        self.spin_rsi_upper.setValue(Config.DEFAULT_RSI_UPPER)
        layout.addWidget(self.spin_rsi_upper, 0, 2)
        layout.addWidget(QLabel("기간:"), 0, 3)
        self.spin_rsi_period = NoScrollSpinBox()
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
        self.spin_bb_k = NoScrollDoubleSpinBox()
        self.spin_bb_k.setRange(1.0, 3.0)
        self.spin_bb_k.setValue(Config.DEFAULT_BB_STD)
        layout.addWidget(self.spin_bb_k, 2, 2)
        
        # DMI
        self.chk_use_dmi = QCheckBox("DMI/ADX 필터")
        self.chk_use_dmi.setChecked(Config.DEFAULT_USE_DMI)
        layout.addWidget(self.chk_use_dmi, 3, 0)
        layout.addWidget(QLabel("ADX 기준:"), 3, 1)
        self.spin_adx = NoScrollSpinBox()
        self.spin_adx.setRange(10, 50)
        self.spin_adx.setValue(Config.DEFAULT_ADX_THRESHOLD)
        layout.addWidget(self.spin_adx, 3, 2)
        
        # 거래량
        self.chk_use_volume = QCheckBox("거래량 필터")
        self.chk_use_volume.setChecked(Config.DEFAULT_USE_VOLUME)
        layout.addWidget(self.chk_use_volume, 4, 0)
        layout.addWidget(QLabel("배수:"), 4, 1)
        self.spin_volume_mult = NoScrollDoubleSpinBox()
        self.spin_volume_mult.setRange(1.0, 5.0)
        self.spin_volume_mult.setValue(Config.DEFAULT_VOLUME_MULTIPLIER)
        layout.addWidget(self.spin_volume_mult, 4, 2)
        
        # 리스크 관리
        self.chk_use_risk = QCheckBox("일일 손실 한도")
        self.chk_use_risk.setChecked(Config.DEFAULT_USE_RISK_MGMT)
        layout.addWidget(self.chk_use_risk, 5, 0)
        layout.addWidget(QLabel("한도:"), 5, 1)
        self.spin_max_loss = NoScrollDoubleSpinBox()
        self.spin_max_loss.setRange(1, 20)
        self.spin_max_loss.setValue(Config.DEFAULT_MAX_DAILY_LOSS)
        self.spin_max_loss.setSuffix(" %")
        layout.addWidget(self.spin_max_loss, 5, 2)
        layout.addWidget(QLabel("최대보유:"), 5, 3)
        self.spin_max_holdings = NoScrollSpinBox()
        self.spin_max_holdings.setRange(1, 20)
        self.spin_max_holdings.setValue(Config.DEFAULT_MAX_HOLDINGS)
        layout.addWidget(self.spin_max_holdings, 5, 4)
        
        # === 신규 전략 옵션 ===
        layout.addWidget(QLabel(""), 6, 0)  # 구분선
        
        # 이동평균 크로스오버
        self.chk_use_ma = QCheckBox("MA 크로스오버")
        layout.addWidget(self.chk_use_ma, 7, 0)
        layout.addWidget(QLabel("단기:"), 7, 1)
        self.spin_ma_short = NoScrollSpinBox()
        self.spin_ma_short.setRange(3, 20)
        self.spin_ma_short.setValue(5)
        layout.addWidget(self.spin_ma_short, 7, 2)
        layout.addWidget(QLabel("장기:"), 7, 3)
        self.spin_ma_long = NoScrollSpinBox()
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
        self.spin_risk_percent = NoScrollDoubleSpinBox()
        self.spin_risk_percent.setRange(0.5, 5.0)
        self.spin_risk_percent.setValue(1.0)
        self.spin_risk_percent.setSuffix(" %")
        layout.addWidget(self.spin_risk_percent, 8, 4)
        
        # 분할 매수/매도
        self.chk_use_split = QCheckBox("분할 주문")
        layout.addWidget(self.chk_use_split, 9, 0)
        layout.addWidget(QLabel("횟수:"), 9, 1)
        self.spin_split_count = NoScrollSpinBox()
        self.spin_split_count.setRange(2, 5)
        self.spin_split_count.setValue(3)
        layout.addWidget(self.spin_split_count, 9, 2)
        layout.addWidget(QLabel("간격%:"), 9, 3)
        self.spin_split_percent = NoScrollDoubleSpinBox()
        self.spin_split_percent.setRange(0.1, 2.0)
        self.spin_split_percent.setValue(0.5)
        self.spin_split_percent.setSuffix(" %")
        layout.addWidget(self.spin_split_percent, 9, 4)
        
        # === v4.3 신규 전략 옵션 ===
        layout.addWidget(QLabel("─── v4.3 신규 ───"), 10, 0, 1, 5)
        
        # 스토캐스틱 RSI
        self.chk_use_stoch_rsi = QCheckBox("스토캐스틱 RSI")
        self.chk_use_stoch_rsi.setToolTip("RSI보다 민감한 과매수/과매도 감지")
        layout.addWidget(self.chk_use_stoch_rsi, 11, 0)
        layout.addWidget(QLabel("상한:"), 11, 1)
        self.spin_stoch_upper = NoScrollSpinBox()
        self.spin_stoch_upper.setRange(60, 95)
        self.spin_stoch_upper.setValue(80)
        layout.addWidget(self.spin_stoch_upper, 11, 2)
        layout.addWidget(QLabel("하한:"), 11, 3)
        self.spin_stoch_lower = NoScrollSpinBox()
        self.spin_stoch_lower.setRange(5, 40)
        self.spin_stoch_lower.setValue(20)
        layout.addWidget(self.spin_stoch_lower, 11, 4)
        
        # MTF 분석
        self.chk_use_mtf = QCheckBox("다중 시간프레임(MTF)")
        self.chk_use_mtf.setToolTip("일봉+분봉 추세 일치 시에만 진입")
        layout.addWidget(self.chk_use_mtf, 12, 0, 1, 2)
        
        # 단계별 익절
        self.chk_use_partial_profit = QCheckBox("단계별 익절")
        self.chk_use_partial_profit.setToolTip("3%→30%, 5%→30%, 8%→20% 분할 청산")
        layout.addWidget(self.chk_use_partial_profit, 12, 2, 1, 2)
        
        # 갭 분석
        self.chk_use_gap = QCheckBox("갭 분석")
        self.chk_use_gap.setToolTip("갭 상승/하락에 따라 K값 자동 조정")
        layout.addWidget(self.chk_use_gap, 13, 0)
        
        # 동적 포지션 사이징
        self.chk_use_dynamic_sizing = QCheckBox("동적 사이징")
        self.chk_use_dynamic_sizing.setToolTip("연속 손실 시 투자금 자동 축소 (Anti-Martingale)")
        layout.addWidget(self.chk_use_dynamic_sizing, 13, 2, 1, 2)
        
        # 시장 분산
        self.chk_use_market_limit = QCheckBox("시장 분산")
        self.chk_use_market_limit.setToolTip("코스피/코스닥 비중 제한")
        layout.addWidget(self.chk_use_market_limit, 14, 0)
        layout.addWidget(QLabel("최대%:"), 14, 1)
        self.spin_market_limit = NoScrollSpinBox()
        self.spin_market_limit.setRange(50, 100)
        self.spin_market_limit.setValue(70)
        layout.addWidget(self.spin_market_limit, 14, 2)
        
        # 섹터 제한
        self.chk_use_sector_limit = QCheckBox("섹터 제한")
        self.chk_use_sector_limit.setToolTip("동일 업종 투자 비중 제한")
        layout.addWidget(self.chk_use_sector_limit, 14, 3)
        layout.addWidget(QLabel("%:"), 14, 4)
        self.spin_sector_limit = NoScrollSpinBox()
        self.spin_sector_limit.setRange(10, 50)
        self.spin_sector_limit.setValue(30)
        layout.addWidget(self.spin_sector_limit, 14, 5)
        
        # ATR 손절
        self.chk_use_atr_stop = QCheckBox("ATR 손절")
        self.chk_use_atr_stop.setToolTip("변동성 기반 동적 손절선")
        layout.addWidget(self.chk_use_atr_stop, 15, 0)
        layout.addWidget(QLabel("배수:"), 15, 1)
        self.spin_atr_mult = NoScrollDoubleSpinBox()
        self.spin_atr_mult.setRange(1.0, 5.0)
        self.spin_atr_mult.setValue(2.0)
        layout.addWidget(self.spin_atr_mult, 15, 2)
        
        # 사운드 알림
        self.chk_use_sound = QCheckBox("사운드 알림")
        self.chk_use_sound.setToolTip("매수/매도 시 알림음 재생")
        self.chk_use_sound.stateChanged.connect(self._on_sound_changed)
        layout.addWidget(self.chk_use_sound, 15, 3, 1, 2)

        # === v4.3 신규 전략 옵션 ===
        layout.addWidget(QLabel("─── v4.3 신규 ───"), 16, 0, 1, 5)

        # 유동성 필터
        self.chk_use_liquidity = QCheckBox("유동성 필터")
        self.chk_use_liquidity.setToolTip("20일 평균 거래대금 기준")
        self.chk_use_liquidity.setChecked(Config.DEFAULT_USE_LIQUIDITY)
        layout.addWidget(self.chk_use_liquidity, 17, 0)
        layout.addWidget(QLabel("최소(억):"), 17, 1)
        self.spin_min_value = NoScrollDoubleSpinBox()
        self.spin_min_value.setRange(1, 500)
        self.spin_min_value.setValue(Config.DEFAULT_MIN_AVG_VALUE / 100_000_000)
        self.spin_min_value.setSuffix(" 억")
        layout.addWidget(self.spin_min_value, 17, 2)

        # 스프레드 필터
        self.chk_use_spread = QCheckBox("스프레드 필터")
        self.chk_use_spread.setToolTip("호가 스프레드가 좁을 때만 진입")
        self.chk_use_spread.setChecked(Config.DEFAULT_USE_SPREAD)
        layout.addWidget(self.chk_use_spread, 18, 0)
        layout.addWidget(QLabel("최대%:"), 18, 1)
        self.spin_spread_max = NoScrollDoubleSpinBox()
        self.spin_spread_max.setRange(0.05, 2.0)
        self.spin_spread_max.setValue(Config.DEFAULT_MAX_SPREAD_PCT)
        self.spin_spread_max.setSuffix(" %")
        layout.addWidget(self.spin_spread_max, 18, 2)

        # 돌파 확인
        self.chk_use_breakout_confirm = QCheckBox("돌파 확인")
        self.chk_use_breakout_confirm.setToolTip("목표가 돌파 후 N틱 유지 시 진입")
        self.chk_use_breakout_confirm.setChecked(Config.DEFAULT_USE_BREAKOUT_CONFIRM)
        layout.addWidget(self.chk_use_breakout_confirm, 19, 0)
        layout.addWidget(QLabel("틱수:"), 19, 1)
        self.spin_breakout_ticks = NoScrollSpinBox()
        self.spin_breakout_ticks.setRange(1, 10)
        self.spin_breakout_ticks.setValue(Config.DEFAULT_BREAKOUT_TICKS)
        layout.addWidget(self.spin_breakout_ticks, 19, 2)

        # 재진입 쿨다운
        self.chk_use_cooldown = QCheckBox("재진입 쿨다운")
        self.chk_use_cooldown.setToolTip("매도 후 일정 시간 재진입 제한")
        self.chk_use_cooldown.setChecked(Config.DEFAULT_USE_COOLDOWN)
        layout.addWidget(self.chk_use_cooldown, 20, 0)
        layout.addWidget(QLabel("분:"), 20, 1)
        self.spin_cooldown_min = NoScrollSpinBox()
        self.spin_cooldown_min.setRange(1, 120)
        self.spin_cooldown_min.setValue(Config.DEFAULT_COOLDOWN_MINUTES)
        layout.addWidget(self.spin_cooldown_min, 20, 2)

        # 시간 청산
        self.chk_use_time_stop = QCheckBox("시간 청산")
        self.chk_use_time_stop.setToolTip("보유 시간이 기준을 넘으면 자동 청산")
        self.chk_use_time_stop.setChecked(Config.DEFAULT_USE_TIME_STOP)
        layout.addWidget(self.chk_use_time_stop, 21, 0)
        layout.addWidget(QLabel("분:"), 21, 1)
        self.spin_time_stop_min = NoScrollSpinBox()
        self.spin_time_stop_min.setRange(5, 480)
        self.spin_time_stop_min.setValue(Config.DEFAULT_MAX_HOLD_MINUTES)
        layout.addWidget(self.spin_time_stop_min, 21, 2)

        # 진입 점수
        self.chk_use_entry_score = QCheckBox("진입 점수")
        self.chk_use_entry_score.setToolTip("여러 지표 점수가 기준 이상일 때만 진입")
        self.chk_use_entry_score.setChecked(Config.USE_ENTRY_SCORING)
        layout.addWidget(self.chk_use_entry_score, 21, 3)
        self.spin_entry_score_threshold = NoScrollSpinBox()
        self.spin_entry_score_threshold.setRange(40, 100)
        self.spin_entry_score_threshold.setValue(Config.ENTRY_SCORE_THRESHOLD)
        layout.addWidget(self.spin_entry_score_threshold, 21, 4)

        # === v5.0 strategy pack / portfolio / backtest ===
        layout.addWidget(QLabel("=== v5.0 Strategy Pack ==="), 22, 0, 1, 5)

        layout.addWidget(QLabel("Strategy Pack:"), 23, 0)
        self.combo_strategy_pack = NoScrollComboBox()
        self.combo_strategy_pack.addItems([
            "volatility_breakout",
            "time_series_momentum",
            "cross_sectional_momentum",
            "ma_channel_trend",
            "orb_donchian_breakout",
            "pairs_trading_cointegration",
            "stat_arb_residual",
            "rsi_bollinger_reversion",
            "dmi_trend_strength",
            "ff5_factor_ls",
            "quality_value_lowvol",
            "investor_program_flow",
            "volatility_targeting_overlay",
            "risk_parity_portfolio",
            "execution_algo_twap_vwap_pov",
            "market_making_spread",
        ])
        self.combo_strategy_pack.setCurrentText(Config.DEFAULT_STRATEGY_PACK.get("primary_strategy", "volatility_breakout"))
        layout.addWidget(self.combo_strategy_pack, 23, 1, 1, 2)

        layout.addWidget(QLabel("Portfolio:"), 23, 3)
        self.combo_portfolio_mode = NoScrollComboBox()
        self.combo_portfolio_mode.addItems(["single_strategy", "multi_strategy"])
        self.combo_portfolio_mode.setCurrentText(Config.DEFAULT_PORTFOLIO_MODE)
        layout.addWidget(self.combo_portfolio_mode, 23, 4)

        self.chk_short_enabled = QCheckBox("Enable short (sim/backtest)")
        self.chk_short_enabled.setChecked(Config.DEFAULT_SHORT_ENABLED)
        layout.addWidget(self.chk_short_enabled, 24, 0, 1, 2)

        layout.addWidget(QLabel("Asset Scope:"), 24, 2)
        self.combo_asset_scope = NoScrollComboBox()
        self.combo_asset_scope.addItems(["kr_stock_live", "kr_stock_etf", "multi_asset_sim"])
        self.combo_asset_scope.setCurrentText(Config.DEFAULT_ASSET_SCOPE)
        layout.addWidget(self.combo_asset_scope, 24, 3, 1, 2)

        layout.addWidget(QLabel("Execution:"), 25, 0)
        self.combo_execution_policy = NoScrollComboBox()
        self.combo_execution_policy.addItems(["market", "limit"])
        self.combo_execution_policy.setCurrentText(getattr(Config, "DEFAULT_EXECUTION_POLICY", "market"))
        layout.addWidget(self.combo_execution_policy, 25, 1)

        layout.addWidget(QLabel("Backtest TF:"), 25, 2)
        self.combo_backtest_timeframe = NoScrollComboBox()
        self.combo_backtest_timeframe.addItems(["1d", "1m", "5m", "15m"])
        self.combo_backtest_timeframe.setCurrentText(Config.DEFAULT_BACKTEST_CONFIG.get("timeframe", "1d"))
        layout.addWidget(self.combo_backtest_timeframe, 25, 3)

        self.spin_backtest_lookback = NoScrollSpinBox()
        self.spin_backtest_lookback.setRange(60, 5000)
        self.spin_backtest_lookback.setValue(int(Config.DEFAULT_BACKTEST_CONFIG.get("lookback_days", 365)))
        layout.addWidget(self.spin_backtest_lookback, 25, 4)

        layout.addWidget(QLabel("Fee bps:"), 26, 0)
        self.spin_backtest_commission = NoScrollDoubleSpinBox()
        self.spin_backtest_commission.setRange(0.0, 50.0)
        self.spin_backtest_commission.setValue(float(Config.DEFAULT_BACKTEST_CONFIG.get("commission_bps", 5.0)))
        layout.addWidget(self.spin_backtest_commission, 26, 1)

        layout.addWidget(QLabel("Slip bps:"), 26, 2)
        self.spin_backtest_slippage = NoScrollDoubleSpinBox()
        self.spin_backtest_slippage.setRange(0.0, 50.0)
        self.spin_backtest_slippage.setValue(float(Config.DEFAULT_BACKTEST_CONFIG.get("slippage_bps", 3.0)))
        layout.addWidget(self.spin_backtest_slippage, 26, 3)

        self.chk_feature_modular_pack = QCheckBox("Modular pack engine")
        self.chk_feature_modular_pack.setChecked(bool(Config.FEATURE_FLAGS.get("use_modular_strategy_pack", True)))
        layout.addWidget(self.chk_feature_modular_pack, 27, 0, 1, 2)
        self.chk_feature_backtest = QCheckBox("Backtest enabled")
        self.chk_feature_backtest.setChecked(bool(Config.FEATURE_FLAGS.get("enable_backtest", True)))
        layout.addWidget(self.chk_feature_backtest, 27, 2)
        self.chk_feature_external_data = QCheckBox("External data enabled")
        self.chk_feature_external_data.setChecked(bool(Config.FEATURE_FLAGS.get("enable_external_data", True)))
        layout.addWidget(self.chk_feature_external_data, 27, 3, 1, 2)

        
        # === 이벤트 연결 및 초기 상태 설정 ===
        self.chk_use_rsi.toggled.connect(lambda s: self.spin_rsi_upper.setEnabled(s))
        self.chk_use_rsi.toggled.connect(lambda s: self.spin_rsi_period.setEnabled(s))
        self.spin_rsi_upper.setEnabled(self.chk_use_rsi.isChecked())
        self.spin_rsi_period.setEnabled(self.chk_use_rsi.isChecked())
        
        # MACD (입력 필드 없음, 체크박스만 있음)
        
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
        
        # MTF, 단계별 익절, 갭 분석, 동적 사이징 (현재 입력 필드 없음 혹은 로직상 별도 처리)
        
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
        
        # === 시스템 설정 (v4.4 신규) ===
        layout.addWidget(QLabel("─── 시스템 설정 ───"), 28, 0, 1, 5)
        
        self.chk_auto_start = QCheckBox("윈도우 시작 시 자동 실행")
        self.chk_auto_start.setToolTip("윈도우 부팅 시 프로그램이 자동으로 시작됩니다.")
        self.chk_auto_start.toggled.connect(self._set_auto_start)
        layout.addWidget(self.chk_auto_start, 29, 0, 1, 2)
        
        self.chk_minimize_tray = QCheckBox("종료 시 트레이로 최소화")
        self.chk_minimize_tray.setToolTip("창을 닫아도 프로그램이 종료되지 않고 트레이 아이콘으로 숨겨집니다.")
        self.chk_minimize_tray.setChecked(Config.DEFAULT_MINIMIZE_TO_TRAY)
        layout.addWidget(self.chk_minimize_tray, 29, 2, 1, 3)

        layout.setRowStretch(30, 1)
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
        self.ranking_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

    def _create_diagnostics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.diagnostic_table = QTableWidget()
        cols = [
            "코드",
            "종목명",
            "pending side",
            "pending reason",
            "pending until",
            "sync status",
            "retry count",
            "last sync error",
            "last update",
        ]
        self.diagnostic_table.setColumnCount(len(cols))
        self.diagnostic_table.setHorizontalHeaderLabels(cols)
        self.diagnostic_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.diagnostic_table.verticalHeader().setVisible(False)
        self.diagnostic_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.diagnostic_table)

        info = QLabel("주문/동기화 상태를 실시간으로 진단합니다. (읽기 전용)")
        info.setWordWrap(True)
        layout.addWidget(info)
        return widget

    def _create_api_tab(self):
        """API 설정 탭 (스크롤 적용)"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
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

        # API 탭에서는 고급 설정 탭의 자동 실행 값을 안내만 한다.
        group3 = QGroupBox("⚙️ 시스템 설정")
        form3 = QFormLayout()
        info_auto_start = QLabel("자동 실행은 [고급 설정] 탭에서 변경합니다.")
        info_auto_start.setWordWrap(True)
        form3.addRow("", info_auto_start)

        group3.setLayout(form3)
        layout.addWidget(group3)
        
        btn_save = QPushButton("💾 설정 저장")
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
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
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
        
        self.statusBar().addWidget(self.status_time)
        self.statusBar().addWidget(QLabel("  "))  # 간격
        self.statusBar().addWidget(self.status_trading)
        self.statusBar().addPermanentWidget(QLabel("v4.3 REST API"))


