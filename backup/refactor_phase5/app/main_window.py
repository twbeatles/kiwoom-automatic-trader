"""Main window class assembled from mixins."""

from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

from config import Config, TradingConfig
from profile_manager import ProfileManager
from sound_notifier import SoundNotifier
from strategy_manager import StrategyManager
from telegram_notifier import TelegramNotifier

from api import KiwoomAuth, KiwoomRESTClient, KiwoomWebSocketClient

from .mixins.api_account import APIAccountMixin
from .mixins.dialogs_profiles import DialogsProfilesMixin
from .mixins.execution_engine import ExecutionEngineMixin
from .mixins.market_data_tabs import MarketDataTabsMixin
from .mixins.order_sync import OrderSyncMixin
from .mixins.persistence_settings import PersistenceSettingsMixin
from .mixins.system_shell import SystemShellMixin
from .mixins.trading_session import TradingSessionMixin
from .mixins.ui_build import UIBuildMixin


class KiwoomProTrader(
    UIBuildMixin,
    MarketDataTabsMixin,
    SystemShellMixin,
    APIAccountMixin,
    TradingSessionMixin,
    OrderSyncMixin,
    ExecutionEngineMixin,
    PersistenceSettingsMixin,
    DialogsProfilesMixin,
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
        self.deposit = 0
        self.initial_deposit = 0
        self.is_running = False
        self.is_connected = False
        self.daily_loss_triggered = False
        self.time_liquidate_executed = False
        self.total_realized_profit = 0
        self.trade_count = 0
        self.win_count = 0
        self._history_dirty = False
        self._position_sync_pending: Set[str] = set()
        self._pending_order_state: Dict[str, Dict[str, Any]] = {}
        self._last_exec_event: Dict[str, Dict[str, Any]] = {}
        self._account_refresh_pending = False
        self._last_account_refresh_ts = 0.0
        
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
        self.strategy = StrategyManager(self)
        
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
        
        self.logger.info("프로그램 초기화 완료 (v4.3)")

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
        self.spin_max_holdings.valueChanged.connect(lambda v: setattr(self.config, 'max_holdings', v))
        
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

        # Entry Scoring
        self.chk_use_entry_score.toggled.connect(lambda v: setattr(self.config, 'use_entry_scoring', v))
        self.spin_entry_score_threshold.valueChanged.connect(lambda v: setattr(self.config, 'entry_score_threshold', v))

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
        self.config.max_holdings = self.spin_max_holdings.value()
        self.config.use_risk_mgmt = self.chk_use_risk.isChecked()
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

