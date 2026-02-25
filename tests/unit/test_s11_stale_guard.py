import datetime
import unittest

from app.mixins.trading_session import TradingSessionMixin
from config import TradingConfig
from strategy_manager import StrategyManager


class _DummySignal:
    def emit(self):
        return None


class _RESTStub:
    def __init__(self):
        self.calls = 0

    def get_investor_trading(self, _code):
        self.calls += 1
        return {}

    def get_program_trading(self, _code):
        self.calls += 1
        return {}


class _TraderHarness(TradingSessionMixin):
    def __init__(self):
        stale_ts = datetime.datetime.now() - datetime.timedelta(seconds=120)
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "price_history": [70000 + i for i in range(80)],
                "daily_prices": [70000 + i for i in range(80)],
                "minute_prices": [70000 + i for i in range(80)],
                "high_history": [70100 + i for i in range(80)],
                "low_history": [69900 + i for i in range(80)],
                "current": 70500,
                "target": 70400,
                "current_volume": 1_500_000,
                "avg_volume_5": 1_000_000,
                "avg_volume_20": 900_000,
                "avg_value_20": 2_000_000_000,
                "ask_price": 70510,
                "bid_price": 70500,
                "open": 70000,
                "prev_close": 69900,
                "market_type": "KOSPI",
                "sector": "전기전자",
                "investor_net": 1000,
                "program_net": 500,
                "external_updated_at": stale_ts,
                "external_status": "fresh",
                "external_error": "",
            }
        }
        self.rest_client = _RESTStub()
        self.current_account = "12345678"
        self._external_refresh_inflight = set()
        self._external_last_fetch_ts = {}
        self._dirty_codes = set()
        self.sig_update_table = _DummySignal()
        self._log_cooldown_map = {}
        self._holding_or_pending_count = 0
        self.daily_realized_profit = 0
        self.daily_initial_deposit = 100_000_000
        self.initial_deposit = 100_000_000
        self.deposit = 100_000_000
        self.total_realized_profit = 0
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class TestS11StaleGuard(unittest.TestCase):
    def test_stale_data_blocks_entry_and_on_demand_refresh_is_debounced(self):
        trader = _TraderHarness()
        cfg = TradingConfig(
            use_rsi=False,
            use_volume=False,
            use_liquidity=False,
            use_spread=False,
            use_macd=False,
            use_bb=False,
            use_dmi=False,
            use_stoch_rsi=False,
            use_mtf=False,
            use_gap=False,
            use_entry_scoring=False,
        )
        cfg.strategy_pack = {
            "primary_strategy": "investor_program_flow",
            "entry_filters": [],
            "risk_overlays": [],
            "exit_overlays": [],
        }
        cfg.feature_flags["use_modular_strategy_pack"] = True
        cfg.feature_flags["enable_external_data"] = True
        manager = StrategyManager(trader, cfg)

        first_passed, first_conditions, _ = manager.evaluate_buy_conditions("005930", now_ts=1000.0)
        second_passed, second_conditions, _ = manager.evaluate_buy_conditions("005930", now_ts=1001.0)

        self.assertFalse(first_passed)
        self.assertFalse(first_conditions["external_data_fresh"])
        self.assertFalse(second_passed)
        self.assertFalse(second_conditions["external_data_fresh"])
        self.assertEqual(trader.rest_client.calls, 2)  # first evaluation only (investor + program)


if __name__ == "__main__":
    unittest.main()
