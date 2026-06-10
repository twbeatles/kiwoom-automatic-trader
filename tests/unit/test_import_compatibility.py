from app.core.window import KiwoomProTrader
from app.features.execution import ExecutionEngineMixin
from app.features.market_intelligence import MarketIntelligenceMixin
from app.features.order_sync import OrderSyncMixin
from app.features.persistence import PersistenceSettingsMixin
from app.features.trading_session import BackgroundUniversePayload, TradingSessionMixin
from app.features.ui_build import UIBuildMixin
from app.main_window import KiwoomProTrader as CompatKiwoomProTrader
from app.mixins.execution_engine import ExecutionEngineMixin as CompatExecutionEngineMixin
from app.mixins.market_intelligence import MarketIntelligenceMixin as CompatMarketIntelligenceMixin
from app.mixins.order_sync import OrderSyncMixin as CompatOrderSyncMixin
from app.mixins.persistence_settings import PersistenceSettingsMixin as CompatPersistenceSettingsMixin
from app.mixins.trading_session import (
    BackgroundUniversePayload as CompatBackgroundUniversePayload,
    TradingSessionMixin as CompatTradingSessionMixin,
)
from app.mixins.ui_build import UIBuildMixin as CompatUIBuildMixin
from config import Config, TradingConfig
from strategy_manager import StrategyManager
from strategies.manager import StrategyManager as CanonicalStrategyManager


def test_public_import_paths_remain_compatible():
    assert KiwoomProTrader is CompatKiwoomProTrader
    assert UIBuildMixin is CompatUIBuildMixin
    assert TradingSessionMixin is CompatTradingSessionMixin
    assert BackgroundUniversePayload == CompatBackgroundUniversePayload
    assert ExecutionEngineMixin is CompatExecutionEngineMixin
    assert OrderSyncMixin is CompatOrderSyncMixin
    assert PersistenceSettingsMixin is CompatPersistenceSettingsMixin
    assert MarketIntelligenceMixin is CompatMarketIntelligenceMixin
    assert StrategyManager is CanonicalStrategyManager
    assert Config.SETTINGS_SCHEMA_VERSION == 7
    assert TradingConfig.__name__ == "TradingConfig"
