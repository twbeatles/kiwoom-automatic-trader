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


class UIBuildSettingsTabsMixin(TraderMixinBase):
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

        g4.addWidget(QLabel("실행 모드:"), 3, 0)
        self.combo_execution_mode = NoScrollComboBox()
        populate_combo(
            self.combo_execution_mode,
            EXECUTION_MODE_CHOICES,
            getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"),
        )
        self.combo_execution_mode.setToolTip("신호 전용은 주문 API를 호출하지 않고 감사 로그만 남깁니다.")
        g4.addWidget(self.combo_execution_mode, 3, 1, 1, 2)

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
        self.chk_feature_backtest.setToolTip("CSV/JSONL 입력을 이벤트 드리븐 백테스트 엔진으로 실행합니다.")
        self.chk_feature_backtest.setChecked(bool(Config.FEATURE_FLAGS.get("enable_backtest", True)))
        g5.addWidget(self.chk_feature_backtest, 4, 2)
        self.chk_feature_external_data = QCheckBox("외부 데이터 사용")
        self.chk_feature_external_data.setChecked(bool(Config.FEATURE_FLAGS.get("enable_external_data", True)))
        g5.addWidget(self.chk_feature_external_data, 4, 3, 1, 2)

        g5.addWidget(QLabel("가격 CSV:"), 5, 0)
        self.input_backtest_bars_path = QLineEdit()
        self.input_backtest_bars_path.setPlaceholderText("symbol,ts,open,high,low,close,volume")
        g5.addWidget(self.input_backtest_bars_path, 5, 1, 1, 4)
        self.btn_backtest_bars_browse = QPushButton("찾기")
        self.btn_backtest_bars_browse.clicked.connect(self._select_backtest_bars_file)
        g5.addWidget(self.btn_backtest_bars_browse, 5, 5)

        g5.addWidget(QLabel("인텔 JSONL:"), 6, 0)
        self.input_backtest_intel_path = QLineEdit()
        self.input_backtest_intel_path.setPlaceholderText("선택 사항")
        g5.addWidget(self.input_backtest_intel_path, 6, 1, 1, 4)
        self.btn_backtest_intel_browse = QPushButton("찾기")
        self.btn_backtest_intel_browse.clicked.connect(self._select_backtest_intel_file)
        g5.addWidget(self.btn_backtest_intel_browse, 6, 5)

        self.btn_run_backtest = QPushButton("백테스트 실행")
        self.btn_run_backtest.clicked.connect(self._run_backtest_from_ui)
        g5.addWidget(self.btn_run_backtest, 7, 0, 1, 2)
        self.btn_save_backtest = QPushButton("결과 저장")
        self.btn_save_backtest.setEnabled(False)
        self.btn_save_backtest.clicked.connect(self._save_backtest_result)
        g5.addWidget(self.btn_save_backtest, 7, 2, 1, 2)
        self.lbl_backtest_status = QLabel("")
        g5.addWidget(self.lbl_backtest_status, 7, 4, 1, 2)

        self.backtest_metrics_table = QTableWidget(0, 2)
        self.backtest_metrics_table.setHorizontalHeaderLabels(["지표", "값"])
        self.backtest_metrics_table.setMaximumHeight(120)
        g5.addWidget(self.backtest_metrics_table, 8, 0, 1, 6)

        self.backtest_trades_table = QTableWidget(0, 5)
        self.backtest_trades_table.setHorizontalHeaderLabels(["시각", "종목", "구분", "가격", "수량"])
        self.backtest_trades_table.setMaximumHeight(130)
        g5.addWidget(self.backtest_trades_table, 9, 0, 1, 6)

        lbl_pack_note = QLabel(
            "백테스트는 CSV 가격 데이터와 선택적 인텔리전스 JSONL을 사용하며 실거래 API를 호출하지 않습니다."
        )
        lbl_pack_note.setWordWrap(True)
        lbl_pack_note.setStyleSheet("color: #8b949e; font-size: 11px;")
        g5.addWidget(lbl_pack_note, 10, 0, 1, 6)

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

        self.chk_allow_plaintext_secret_fallback = QCheckBox("Keyring 실패 시 평문 secret 저장 허용")
        self.chk_allow_plaintext_secret_fallback.setToolTip("실거래에서는 꺼두는 것이 안전합니다.")
        self.chk_allow_plaintext_secret_fallback.setChecked(
            bool(getattr(Config, "DEFAULT_ALLOW_PLAINTEXT_SECRET_FALLBACK", False))
        )
        g6.addWidget(self.chk_allow_plaintext_secret_fallback, 2, 0, 1, 4)

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
