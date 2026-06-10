"""Main window class assembled from mixins."""

from collections import deque
import datetime
from typing import Any, Deque, Dict, List, Optional, Set, cast

from PyQt6.QtCore import QThreadPool, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QMainWindow

from config import Config, TradingConfig
from profile_manager import ProfileManager
from sound_notifier import SoundNotifier
from strategies.manager import StrategyManager
from telegram_notifier import TelegramNotifier

from api import KiwoomAuth, KiwoomRESTClient, KiwoomWebSocketClient

from app.support.ui_text import combo_value
from app.mixins.api_account import APIAccountMixin
from app.mixins.dialogs_profiles import DialogsProfilesMixin
from app.features.execution import ExecutionEngineMixin
from app.mixins.market_data_tabs import MarketDataTabsMixin
from app.features.market_intelligence import MarketIntelligenceMixin
from app.features.order_sync import OrderSyncMixin
from app.features.persistence import PersistenceSettingsMixin
from app.mixins.system_shell import SystemShellMixin
from app.features.trading_session import TradingSessionMixin
from app.features.ui_build import UIBuildMixin
from app.features.diagnostics import DiagnosticsMixin


def _dict_or_empty(value: object) -> Dict[str, Any]:
    return cast(Dict[str, Any], value) if isinstance(value, dict) else {}


class KiwoomProTrader(
    UIBuildMixin,
    MarketDataTabsMixin,
    SystemShellMixin,
    APIAccountMixin,
    MarketIntelligenceMixin,
    TradingSessionMixin,
    OrderSyncMixin,
    ExecutionEngineMixin,
    PersistenceSettingsMixin,
    DialogsProfilesMixin,
    DiagnosticsMixin,
    QMainWindow,
):
    sig_log = pyqtSignal(str)
    sig_execution = pyqtSignal(object)
    sig_order_execution = pyqtSignal(object)
    sig_update_table = pyqtSignal()

    def __init__(self):
        super().__init__()

        # 상태 변수
        self.universe: Dict[str, Dict[str, Any]] = {}
        self.external_positions: Dict[str, Dict[str, Any]] = {}
        self.deposit = 0
        self.initial_deposit = 0
        self.is_running = False
        self.is_connected = False
        self.daily_loss_triggered = False
        self.time_liquidate_executed = False
        self.total_realized_profit = 0
        self.daily_realized_profit = 0
        self.daily_initial_deposit = 0
        self.trade_count = 0
        self.win_count = 0
        self._trading_day = datetime.date.today()
        self._history_dirty = False
        self._history_save_inflight = False
        self._history_save_pending_snapshot = None
        self._position_sync_pending: Set[str] = set()
        self._position_sync_batch: Set[str] = set()
        self._position_sync_scheduled = False
        self._position_sync_retry_count = 0
        self._pending_order_state: Dict[str, Dict[str, Any]] = {}
        self._manual_pending_state: Dict[str, Dict[str, Any]] = {}
        self._last_exec_event: Dict[str, Dict[str, Any]] = {}
        self._reserved_cash_by_code: Dict[str, int] = {}
        self._diagnostics_by_code: Dict[str, Dict[str, Any]] = {}
        self._diagnostics_dirty_codes: Set[str] = set()
        self._account_refresh_pending = False
        self._last_account_refresh_ts = 0.0
        self._external_refresh_inflight: Set[str] = set()
        self._external_last_fetch_ts: Dict[str, float] = {}
        self._external_refresh_timer: Optional[QTimer] = None
        self._market_intel_timer: Optional[QTimer] = None
        self._market_intel_sources: Dict[str, Dict[str, Any]] = {}
        self._market_intel_dirty_codes: Set[str] = set()
        self._market_intel_row_to_code: Dict[int, str] = {}
        self._last_market_intel_fetch_ts = 0.0
        self._market_intel_alert_ts: Dict[str, float] = {}
        self._market_ai_usage: Dict[str, Any] = {}
        self._market_briefing_sent_day = ""
        self._market_macro_cache: Dict[str, Any] = {"values": {}, "ts": 0.0}
        self._market_dart_cursor_by_code: Dict[str, str] = {}
        self._market_risk_mode = "neutral"
        self._portfolio_budget_scale = 1.0
        self._sector_blocks: Dict[str, Dict[str, Any]] = {}
        self._theme_heat_map: Dict[str, float] = {}
        self._aggregate_news_risk = 0.0
        self._candidate_universe: Dict[str, Dict[str, Any]] = {}
        self._active_market_candidates: Dict[str, Dict[str, Any]] = {}
        self._candidate_last_refresh_ts = 0.0
        self._market_replay_event_records: List[Dict[str, Any]] = []
        self._market_replay_audit_records: List[Dict[str, Any]] = []
        self._market_replay_event_row_to_index: Dict[int, int] = {}
        self._market_replay_audit_row_to_index: Dict[int, int] = {}
        self._market_replay_refresh_scheduled = False
        self._last_time_strategy_phase: Optional[str] = None
        self._force_quit_requested = False
        self._shutdown_in_progress = False
        self._connect_inflight = False
        self._trading_start_inflight = False
        self._scheduled_start_requested = False
        self._dirty_codes: Set[str] = set()
        self._code_to_row: Dict[str, int] = {}
        self._last_status_badge = None
        self._last_profit_sign: Optional[int] = None
        self._last_connection_mode: Optional[str] = None
        self._log_cooldown_map: Dict[str, float] = {}
        self._holding_or_pending_count = 0
        self._sync_failed_codes: Set[str] = set()
        self.total_equity = 0
        self._global_risk_mode = "normal"
        self._global_risk_until: Optional[datetime.datetime] = None
        self._order_health_mode = "normal"
        self._order_health_until: Optional[datetime.datetime] = None
        self._recent_slippage_bps: Deque[float] = deque(maxlen=300)
        self._order_fail_events: Deque[float] = deque(maxlen=500)
        self._index_ticks_by_market: Dict[str, Deque[tuple]] = {}
        self._shock_fallback_rep_by_market: Dict[str, str] = {}
        self._recent_ticks_by_code: Dict[str, Deque[tuple]] = {}
        self._guard_reason_by_code: Dict[str, str] = {}
        self._market_status_probe_logged = False
        self._diagnostic_row_to_code: Dict[int, str] = {}

        # v4.3 신규 상태
        self.current_theme = Config.DEFAULT_THEME
        self.schedule = {'enabled': False, 'start': '09:00', 'end': '15:19', 'liquidate': True}
        self.schedule_started = False

        # API
        self.auth: Optional[KiwoomAuth] = None
        self.rest_client: Optional[KiwoomRESTClient] = None
        self.ws_client: Optional[KiwoomWebSocketClient] = None
        self.current_account = ""

        # 데이터
        self.trade_history = []
        self.price_history = {}
        self.telegram: Optional[TelegramNotifier] = None

        # v4.3 신규 컴포넌트
        self.sound: Optional[SoundNotifier] = None
        self.profile_manager = ProfileManager(Config.DATA_DIR)

        # v4.5 아키텍처 개선 (TradingConfig)
        self.config = TradingConfig()

        # 로깅
        self._setup_logging()
        self._load_trade_history()

        # 시그널 연결
        self.sig_log.connect(self._append_log)
        self.sig_execution.connect(self._on_execution)
        self.sig_order_execution.connect(self._on_order_execution)
        self.sig_update_table.connect(self._refresh_table)
        self.sig_update_table.connect(self._refresh_diagnostics)
        self.sig_update_table.connect(self._refresh_market_intelligence_table)

        # 전략 매니저 (Config 전달)
        self.strategy = StrategyManager(self, self.config)

        # UI
        self._init_ui()
        self._create_menu()
        self._create_tray()
        self._setup_timers()
        self._setup_shortcuts()  # v4.3 키보드 단축키
        self._load_settings()
        self._connect_config_signals()  # 설정 UI 시그널 연결

        # 사운드 초기화
        self.sound = SoundNotifier(enabled=False)

        # 스레드 풀 초기화
        self.threadpool = QThreadPool()
        self._ui_flush_timer = QTimer(self)
        self._ui_flush_timer.setInterval(Config.UI_REFRESH_INTERVAL_MS)
        self._ui_flush_timer.timeout.connect(self.sig_update_table.emit)
        self._ui_flush_timer.start()

        self.logger.info("프로그램 초기화 완료 (v4.5)")

    def _connect_config_signals(self):
        """UI 변경사항을 TradingConfig에 실시간 반영"""
        # 기본 설정
        self.spin_betting.valueChanged.connect(lambda v: setattr(self.config, 'betting_ratio', v))
        self.spin_k.valueChanged.connect(lambda v: setattr(self.config, 'k_value', v))
        self.spin_ts_start.valueChanged.connect(lambda v: setattr(self.config, 'ts_start', v))
        self.spin_ts_stop.valueChanged.connect(lambda v: setattr(self.config, 'ts_stop', v))
        self.spin_loss.valueChanged.connect(lambda v: setattr(self.config, 'loss_cut', v))

        # RSI
        self.chk_use_rsi.toggled.connect(lambda v: setattr(self.config, 'use_rsi', v))
        self.spin_rsi_upper.valueChanged.connect(lambda v: setattr(self.config, 'rsi_upper', v))
        self.spin_rsi_period.valueChanged.connect(lambda v: setattr(self.config, 'rsi_period', v))

        # MACD
        self.chk_use_macd.toggled.connect(lambda v: setattr(self.config, 'use_macd', v))

        # 볼린저
        self.chk_use_bb.toggled.connect(lambda v: setattr(self.config, 'use_bb', v))
        self.spin_bb_k.valueChanged.connect(lambda v: setattr(self.config, 'bb_k', v))

        # 거래량
        self.chk_use_volume.toggled.connect(lambda v: setattr(self.config, 'use_volume', v))
        self.spin_volume_mult.valueChanged.connect(lambda v: setattr(self.config, 'volume_mult', v))

        # 리스크
        self.chk_use_risk.toggled.connect(lambda v: setattr(self.config, 'use_risk_mgmt', v))
        self.spin_max_loss.valueChanged.connect(lambda v: setattr(self.config, 'max_daily_loss', float(v)))
        self.spin_max_holdings.valueChanged.connect(lambda v: setattr(self.config, 'max_holdings', v))
        if hasattr(self, "combo_daily_loss_basis"):
            self.combo_daily_loss_basis.currentTextChanged.connect(
                lambda _v: setattr(self.config, "daily_loss_basis", combo_value(self.combo_daily_loss_basis, "total_equity"))
            )

        # 신규 전략들
        self.chk_use_stoch_rsi.toggled.connect(lambda v: setattr(self.config, 'use_stoch_rsi', v))
        self.spin_stoch_upper.valueChanged.connect(lambda v: setattr(self.config, 'stoch_upper', v))
        self.spin_stoch_lower.valueChanged.connect(lambda v: setattr(self.config, 'stoch_lower', v))

        self.chk_use_mtf.toggled.connect(lambda v: setattr(self.config, 'use_mtf', v))
        self.chk_use_gap.toggled.connect(lambda v: setattr(self.config, 'use_gap', v))
        self.chk_use_partial_profit.toggled.connect(lambda v: setattr(self.config, 'use_partial_profit', v))
        self.chk_use_dynamic_sizing.toggled.connect(lambda v: setattr(self.config, 'use_dynamic_sizing', v))

        self.chk_use_atr_stop.toggled.connect(lambda v: setattr(self.config, 'use_atr_stop', v))
        self.spin_atr_mult.valueChanged.connect(lambda v: setattr(self.config, 'atr_mult', v))

        self.chk_use_liquidity.toggled.connect(lambda v: setattr(self.config, 'use_liquidity', v))
        self.spin_min_value.valueChanged.connect(lambda v: setattr(self.config, 'min_avg_value', int(v)))

        self.chk_use_spread.toggled.connect(lambda v: setattr(self.config, 'use_spread', v))
        self.spin_spread_max.valueChanged.connect(lambda v: setattr(self.config, 'max_spread', v))

        self.chk_use_market_limit.toggled.connect(lambda v: setattr(self.config, 'use_market_limit', v))
        self.spin_market_limit.valueChanged.connect(lambda v: setattr(self.config, 'market_limit', v))

        self.chk_use_sector_limit.toggled.connect(lambda v: setattr(self.config, 'use_sector_limit', v))
        self.spin_sector_limit.valueChanged.connect(lambda v: setattr(self.config, 'sector_limit', v))

        # DMI
        self.chk_use_dmi.toggled.connect(lambda v: setattr(self.config, 'use_dmi', v))
        self.spin_adx.valueChanged.connect(lambda v: setattr(self.config, 'adx_threshold', v))

        # MA Crossover
        self.chk_use_ma.toggled.connect(lambda v: setattr(self.config, 'use_ma', v))
        self.spin_ma_short.valueChanged.connect(lambda v: setattr(self.config, 'ma_short', v))
        self.spin_ma_long.valueChanged.connect(lambda v: setattr(self.config, 'ma_long', v))

        # Split Orders
        self.chk_use_split.toggled.connect(lambda v: setattr(self.config, 'use_split', v))
        self.spin_split_count.valueChanged.connect(lambda v: setattr(self.config, 'split_count', v))
        self.spin_split_percent.valueChanged.connect(lambda v: setattr(self.config, 'split_percent', v))

        # Time Strategy
        self.chk_use_time_strategy.toggled.connect(lambda v: setattr(self.config, 'use_time_strategy', v))

        # ATR Sizing
        if hasattr(self, "chk_use_atr_sizing"):
            self.chk_use_atr_sizing.toggled.connect(lambda v: setattr(self.config, 'use_atr_sizing', v))
        if hasattr(self, "spin_risk_percent"):
            self.spin_risk_percent.valueChanged.connect(lambda v: setattr(self.config, 'risk_percent', v))

        # Breakout/Cooldown/Time-stop
        if hasattr(self, "chk_use_breakout_confirm"):
            self.chk_use_breakout_confirm.toggled.connect(lambda v: setattr(self.config, 'use_breakout_confirm', v))
        if hasattr(self, "spin_breakout_ticks"):
            self.spin_breakout_ticks.valueChanged.connect(lambda v: setattr(self.config, 'breakout_ticks', v))
        if hasattr(self, "chk_use_cooldown"):
            self.chk_use_cooldown.toggled.connect(lambda v: setattr(self.config, 'use_cooldown', v))
        if hasattr(self, "spin_cooldown_min"):
            self.spin_cooldown_min.valueChanged.connect(lambda v: setattr(self.config, 'cooldown_min', v))
        if hasattr(self, "chk_use_time_stop"):
            self.chk_use_time_stop.toggled.connect(lambda v: setattr(self.config, 'use_time_stop', v))
        if hasattr(self, "spin_time_stop_min"):
            self.spin_time_stop_min.valueChanged.connect(lambda v: setattr(self.config, 'time_stop_min', v))

        # Entry Scoring
        self.chk_use_entry_score.toggled.connect(lambda v: setattr(self.config, 'use_entry_scoring', v))
        self.spin_entry_score_threshold.valueChanged.connect(lambda v: setattr(self.config, 'entry_score_threshold', v))

        # Extended strategy/backtest controls (v5.0)
        if hasattr(self, "combo_strategy_pack"):
            self.combo_strategy_pack.currentTextChanged.connect(
                lambda _v: self.config.strategy_pack.update({"primary_strategy": combo_value(self.combo_strategy_pack, "volatility_breakout")})
            )
        if hasattr(self, "combo_portfolio_mode"):
            self.combo_portfolio_mode.currentTextChanged.connect(
                lambda _v: setattr(self.config, 'portfolio_mode', combo_value(self.combo_portfolio_mode, "single_strategy"))
            )
        if hasattr(self, "chk_short_enabled"):
            self.chk_short_enabled.toggled.connect(lambda v: setattr(self.config, 'short_enabled', bool(v)))
        if hasattr(self, "combo_asset_scope"):
            self.combo_asset_scope.currentTextChanged.connect(
                lambda _v: setattr(self.config, 'asset_scope', combo_value(self.combo_asset_scope, "kr_stock_live"))
            )
        if hasattr(self, "combo_execution_policy"):
            self.combo_execution_policy.currentTextChanged.connect(
                lambda _v: setattr(self.config, 'execution_policy', combo_value(self.combo_execution_policy, "market"))
            )
        if hasattr(self, "combo_execution_mode"):
            self.combo_execution_mode.currentTextChanged.connect(
                lambda _v: setattr(
                    self.config,
                    "execution_mode",
                    combo_value(self.combo_execution_mode, getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only")),
                )
            )
        if hasattr(self, "combo_backtest_timeframe"):
            self.combo_backtest_timeframe.currentTextChanged.connect(
                lambda _v: self.config.backtest_config.update({"timeframe": combo_value(self.combo_backtest_timeframe, "1d")})
            )
        if hasattr(self, "spin_backtest_lookback"):
            self.spin_backtest_lookback.valueChanged.connect(
                lambda v: self.config.backtest_config.update({"lookback_days": int(v)})
            )
        if hasattr(self, "spin_backtest_commission"):
            self.spin_backtest_commission.valueChanged.connect(
                lambda v: self.config.backtest_config.update({"commission_bps": float(v)})
            )
        if hasattr(self, "spin_backtest_slippage"):
            self.spin_backtest_slippage.valueChanged.connect(
                lambda v: self.config.backtest_config.update({"slippage_bps": float(v)})
            )
        if hasattr(self, "chk_feature_modular_pack"):
            self.chk_feature_modular_pack.toggled.connect(
                lambda v: self.config.feature_flags.update({"use_modular_strategy_pack": bool(v)})
            )
        if hasattr(self, "chk_feature_backtest"):
            self.chk_feature_backtest.toggled.connect(
                lambda v: self.config.feature_flags.update({"enable_backtest": bool(v)})
            )
        if hasattr(self, "chk_feature_external_data"):
            self.chk_feature_external_data.toggled.connect(
                lambda v: self.config.feature_flags.update({"enable_external_data": bool(v)})
            )
        if hasattr(self, "chk_sync_history_flush_on_exit"):
            self.chk_sync_history_flush_on_exit.toggled.connect(
                lambda v: setattr(self.config, "sync_history_flush_on_exit", bool(v))
            )
        if hasattr(self, "chk_allow_plaintext_secret_fallback"):
            self.chk_allow_plaintext_secret_fallback.toggled.connect(
                lambda v: setattr(self.config, "allow_plaintext_secret_fallback", bool(v))
            )
        if hasattr(self, "chk_use_shock_guard"):
            self.chk_use_shock_guard.toggled.connect(lambda v: setattr(self.config, "use_shock_guard", bool(v)))
        if hasattr(self, "spin_shock_1m"):
            self.spin_shock_1m.valueChanged.connect(lambda v: setattr(self.config, "shock_1m_pct", float(v)))
        if hasattr(self, "spin_shock_5m"):
            self.spin_shock_5m.valueChanged.connect(lambda v: setattr(self.config, "shock_5m_pct", float(v)))
        if hasattr(self, "spin_shock_cooldown"):
            self.spin_shock_cooldown.valueChanged.connect(lambda v: setattr(self.config, "shock_cooldown_min", int(v)))
        if hasattr(self, "chk_use_vi_guard"):
            self.chk_use_vi_guard.toggled.connect(lambda v: setattr(self.config, "use_vi_guard", bool(v)))
        if hasattr(self, "spin_vi_cooldown"):
            self.spin_vi_cooldown.valueChanged.connect(lambda v: setattr(self.config, "vi_cooldown_min", int(v)))
        if hasattr(self, "chk_use_regime_sizing"):
            self.chk_use_regime_sizing.toggled.connect(lambda v: setattr(self.config, "use_regime_sizing", bool(v)))
        if hasattr(self, "chk_use_liquidity_stress_guard"):
            self.chk_use_liquidity_stress_guard.toggled.connect(
                lambda v: setattr(self.config, "use_liquidity_stress_guard", bool(v))
            )
        if hasattr(self, "chk_use_slippage_guard"):
            self.chk_use_slippage_guard.toggled.connect(lambda v: setattr(self.config, "use_slippage_guard", bool(v)))
        if hasattr(self, "spin_max_slippage_bps"):
            self.spin_max_slippage_bps.valueChanged.connect(lambda v: setattr(self.config, "max_slippage_bps", float(v)))
        if hasattr(self, "chk_use_order_health_guard"):
            self.chk_use_order_health_guard.toggled.connect(
                lambda v: setattr(self.config, "use_order_health_guard", bool(v))
            )
        bind_market_intel = getattr(self, "_bind_market_intelligence_signals", None)
        if callable(bind_market_intel):
            bind_market_intel()

        # 현재 UI 값으로 config 초기 동기화
        self.config.betting_ratio = self.spin_betting.value()
        self.config.k_value = self.spin_k.value()
        self.config.ts_start = self.spin_ts_start.value()
        self.config.ts_stop = self.spin_ts_stop.value()
        self.config.loss_cut = self.spin_loss.value()
        self.config.use_rsi = self.chk_use_rsi.isChecked()
        self.config.rsi_period = self.spin_rsi_period.value()
        self.config.rsi_upper = self.spin_rsi_upper.value()
        self.config.use_macd = self.chk_use_macd.isChecked()
        self.config.use_bb = self.chk_use_bb.isChecked()
        self.config.bb_k = self.spin_bb_k.value()
        self.config.use_volume = self.chk_use_volume.isChecked()
        self.config.volume_mult = self.spin_volume_mult.value()
        self.config.max_daily_loss = float(self.spin_max_loss.value())
        self.config.max_holdings = self.spin_max_holdings.value()
        self.config.use_risk_mgmt = self.chk_use_risk.isChecked()
        if hasattr(self, "combo_daily_loss_basis"):
            self.config.daily_loss_basis = combo_value(self.combo_daily_loss_basis, "total_equity")
        self.config.use_stoch_rsi = self.chk_use_stoch_rsi.isChecked()
        self.config.stoch_upper = self.spin_stoch_upper.value()
        self.config.stoch_lower = self.spin_stoch_lower.value()
        self.config.use_mtf = self.chk_use_mtf.isChecked()
        self.config.use_gap = self.chk_use_gap.isChecked()
        self.config.use_partial_profit = self.chk_use_partial_profit.isChecked()
        self.config.use_dynamic_sizing = self.chk_use_dynamic_sizing.isChecked()
        self.config.use_atr_stop = self.chk_use_atr_stop.isChecked()
        self.config.atr_mult = self.spin_atr_mult.value()
        self.config.use_liquidity = self.chk_use_liquidity.isChecked()
        self.config.min_avg_value = int(self.spin_min_value.value())
        self.config.use_spread = self.chk_use_spread.isChecked()
        self.config.max_spread = self.spin_spread_max.value()
        self.config.use_market_limit = self.chk_use_market_limit.isChecked()
        self.config.market_limit = self.spin_market_limit.value()
        self.config.use_sector_limit = self.chk_use_sector_limit.isChecked()
        self.config.sector_limit = self.spin_sector_limit.value()
        self.config.use_dmi = self.chk_use_dmi.isChecked()
        self.config.adx_threshold = self.spin_adx.value()
        self.config.use_ma = self.chk_use_ma.isChecked()
        self.config.ma_short = self.spin_ma_short.value()
        self.config.ma_long = self.spin_ma_long.value()
        self.config.use_split = self.chk_use_split.isChecked()
        self.config.split_count = self.spin_split_count.value()
        self.config.split_percent = self.spin_split_percent.value()
        self.config.use_time_strategy = self.chk_use_time_strategy.isChecked()
        self.config.use_entry_scoring = self.chk_use_entry_score.isChecked()
        self.config.entry_score_threshold = self.spin_entry_score_threshold.value()
        if hasattr(self, "chk_use_atr_sizing"):
            self.config.use_atr_sizing = self.chk_use_atr_sizing.isChecked()
        if hasattr(self, "spin_risk_percent"):
            self.config.risk_percent = self.spin_risk_percent.value()
        if hasattr(self, "chk_use_breakout_confirm"):
            self.config.use_breakout_confirm = self.chk_use_breakout_confirm.isChecked()
        if hasattr(self, "spin_breakout_ticks"):
            self.config.breakout_ticks = self.spin_breakout_ticks.value()
        if hasattr(self, "chk_use_cooldown"):
            self.config.use_cooldown = self.chk_use_cooldown.isChecked()
        if hasattr(self, "spin_cooldown_min"):
            self.config.cooldown_min = self.spin_cooldown_min.value()
        if hasattr(self, "chk_use_time_stop"):
            self.config.use_time_stop = self.chk_use_time_stop.isChecked()
        if hasattr(self, "spin_time_stop_min"):
            self.config.time_stop_min = self.spin_time_stop_min.value()
        if hasattr(self, "combo_strategy_pack"):
            self.config.strategy_pack["primary_strategy"] = combo_value(self.combo_strategy_pack, "volatility_breakout")
        if hasattr(self, "combo_portfolio_mode"):
            self.config.portfolio_mode = combo_value(self.combo_portfolio_mode, "single_strategy")
        if hasattr(self, "chk_short_enabled"):
            self.config.short_enabled = bool(self.chk_short_enabled.isChecked())
        if hasattr(self, "combo_asset_scope"):
            self.config.asset_scope = combo_value(self.combo_asset_scope, "kr_stock_live")
        if hasattr(self, "combo_execution_policy"):
            self.config.execution_policy = combo_value(self.combo_execution_policy, "market")
        if hasattr(self, "combo_execution_mode"):
            self.config.execution_mode = combo_value(
                self.combo_execution_mode,
                getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"),
            )
        if hasattr(self, "combo_backtest_timeframe"):
            self.config.backtest_config["timeframe"] = combo_value(self.combo_backtest_timeframe, "1d")
        if hasattr(self, "spin_backtest_lookback"):
            self.config.backtest_config["lookback_days"] = int(self.spin_backtest_lookback.value())
        if hasattr(self, "spin_backtest_commission"):
            self.config.backtest_config["commission_bps"] = float(self.spin_backtest_commission.value())
        if hasattr(self, "spin_backtest_slippage"):
            self.config.backtest_config["slippage_bps"] = float(self.spin_backtest_slippage.value())
        if hasattr(self, "chk_feature_modular_pack"):
            self.config.feature_flags["use_modular_strategy_pack"] = bool(self.chk_feature_modular_pack.isChecked())
        if hasattr(self, "chk_feature_backtest"):
            self.config.feature_flags["enable_backtest"] = bool(self.chk_feature_backtest.isChecked())
        if hasattr(self, "chk_feature_external_data"):
            self.config.feature_flags["enable_external_data"] = bool(self.chk_feature_external_data.isChecked())
        if hasattr(self, "chk_sync_history_flush_on_exit"):
            self.config.sync_history_flush_on_exit = bool(self.chk_sync_history_flush_on_exit.isChecked())
        if hasattr(self, "chk_allow_plaintext_secret_fallback"):
            self.config.allow_plaintext_secret_fallback = bool(self.chk_allow_plaintext_secret_fallback.isChecked())
        if hasattr(self, "chk_use_shock_guard"):
            self.config.use_shock_guard = bool(self.chk_use_shock_guard.isChecked())
        if hasattr(self, "spin_shock_1m"):
            self.config.shock_1m_pct = float(self.spin_shock_1m.value())
        if hasattr(self, "spin_shock_5m"):
            self.config.shock_5m_pct = float(self.spin_shock_5m.value())
        if hasattr(self, "spin_shock_cooldown"):
            self.config.shock_cooldown_min = int(self.spin_shock_cooldown.value())
        if hasattr(self, "chk_use_vi_guard"):
            self.config.use_vi_guard = bool(self.chk_use_vi_guard.isChecked())
        if hasattr(self, "spin_vi_cooldown"):
            self.config.vi_cooldown_min = int(self.spin_vi_cooldown.value())
        if hasattr(self, "chk_use_regime_sizing"):
            self.config.use_regime_sizing = bool(self.chk_use_regime_sizing.isChecked())
        if hasattr(self, "chk_use_liquidity_stress_guard"):
            self.config.use_liquidity_stress_guard = bool(self.chk_use_liquidity_stress_guard.isChecked())
        if hasattr(self, "chk_use_slippage_guard"):
            self.config.use_slippage_guard = bool(self.chk_use_slippage_guard.isChecked())
        if hasattr(self, "spin_max_slippage_bps"):
            self.config.max_slippage_bps = float(self.spin_max_slippage_bps.value())
        if hasattr(self, "chk_use_order_health_guard"):
            self.config.use_order_health_guard = bool(self.chk_use_order_health_guard.isChecked())
        sync_market_intel = getattr(self, "_update_market_intelligence_config_from_ui", None)
        if callable(sync_market_intel):
            sync_market_intel()
