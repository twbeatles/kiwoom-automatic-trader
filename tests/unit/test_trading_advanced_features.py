"""자동 매매 고도화 기능 (Chandelier Exit, Spread Guard, Session Performance Summary) 단위 테스트."""
import datetime
import unittest
from unittest.mock import MagicMock

from app.features.execution.guards import ExecutionGuardsMixin
from app.features.trading_session.lifecycle import TradingSessionLifecycleMixin
from strategies.manager_mixins.indicators import StrategyManagerIndicatorMixin


class _MockTrader:
    def __init__(self):
        self.universe = {}
        self.trade_history = []
        self.log_messages = []
        self.telegram = None
        self.is_running = False

    def log(self, msg: str):
        self.log_messages.append(msg)


class _MockStrategy(StrategyManagerIndicatorMixin):
    def __init__(self, trader, config=None):
        self.trader = trader
        self.config = config

    def log(self, msg: str):
        self.trader.log(msg)


class _MockConfig:
    def __init__(self):
        self.use_chandelier_exit = True
        self.chandelier_mult = 2.0
        self.use_atr_stop = False
        self.use_rsi = False
        self.use_spread = True
        self.max_spread = 1.0
        self.use_liquidity_stress_guard = False


class TestChandelierExitAndIndicators(unittest.TestCase):
    def setUp(self):
        self.trader = _MockTrader()
        self.config = _MockConfig()
        self.strategy = _MockStrategy(self.trader, self.config)

    def test_calculate_chandelier_stop_tracks_highest_and_atr(self):
        self.trader.universe["005930"] = {
            "name": "삼성전자",
            "current": 70000,
            "buy_price": 68000,
            "max_profit_rate": 5.0,  # 최고가 68000 * 1.05 = 71400
            "high_history": [70000, 71000, 71500] * 5,
            "low_history": [68000, 68500, 69000] * 5,
            "price_history": [69000, 70000, 70500] * 5,
        }

        stop_price = self.strategy.calculate_chandelier_stop("005930", multiplier=2.0)
        self.assertGreater(stop_price, 0)
        # stop_price should be below highest_price (71400)
        self.assertLess(stop_price, 71400)

    def test_chandelier_stop_does_not_trigger_on_entry_even_with_high_past_prices(self):
        # 과거 캔들 고가가 100,000원이고 진입가가 80,000원인 경우,
        # 과거 고가를 기준으로 잡으면 스탑가가 90,000원 이상이 되어 진입 즉시 손절되는 버그가 방지되어야 함.
        self.trader.universe["005930"] = {
            "name": "삼성전자",
            "current": 80000,
            "buy_price": 80000,
            "max_profit_rate": 0.0,
            "high_history": [100000] * 20,
            "low_history": [79000] * 20,
            "price_history": [80000] * 20,
        }

        triggered, stop_price = self.strategy.check_chandelier_exit("005930")
        self.assertFalse(triggered, "진입 직후 과거 고가로 인해 즉시 청산되어서는 안 됨")
        # stop_price should be below buy_price (80000)
        self.assertLess(stop_price, 80000)

    def test_check_chandelier_exit_triggers_when_price_drops_below_stop(self):
        # buy_price = 70000, max_profit = 7.142857% (highest = 75000), ATR = 1000, mult = 2.0 -> stop_price = 73000
        # current = 72000 -> trigger!
        self.trader.universe["005930"] = {
            "name": "삼성전자",
            "current": 72000,
            "buy_price": 70000,
            "max_profit_rate": (75000 - 70000) / 70000 * 100.0,
            "high_history": [75000] * 20,
            "low_history": [74000] * 20,
            "price_history": [74500] * 20,
        }

        triggered, stop_price = self.strategy.check_chandelier_exit("005930")
        self.assertTrue(triggered)
        self.assertAlmostEqual(stop_price, 73000.0, places=1)


class _GuardTester(ExecutionGuardsMixin):
    def __init__(self, config):
        self.config = config
        self._sync_failed_codes = set()
        self._global_risk_mode = "normal"
        self._order_health_mode = "normal"


class TestExecutionGuardsSpreadCheck(unittest.TestCase):
    def setUp(self):
        self.config = _MockConfig()
        self.guard_tester = _GuardTester(self.config)

    def test_can_enter_trade_blocks_when_spread_exceeds_max(self):
        info = {
            "name": "삼성전자",
            "status": "watch",
            "ask_price": 72000,
            "bid_price": 70000,  # spread = (72000 - 70000) / 71000 * 100 = 2.81% > max_spread (1.0%)
            "market_state": "normal",
        }
        allowed, reason = self.guard_tester._can_enter_trade("005930", info, datetime.datetime.now())
        self.assertFalse(allowed)
        self.assertEqual(reason, "wide_spread")

    def test_can_enter_trade_allows_when_spread_is_tight(self):
        info = {
            "name": "삼성전자",
            "status": "watch",
            "ask_price": 70100,
            "bid_price": 70000,  # spread = 100 / 70050 * 100 = 0.14% <= max_spread (1.0%)
            "market_state": "normal",
        }
        allowed, reason = self.guard_tester._can_enter_trade("005930", info, datetime.datetime.now())
        self.assertTrue(allowed)
        self.assertEqual(reason, "")


class _LifecycleTester(TradingSessionLifecycleMixin):
    def __init__(self):
        self.trade_history = []
        self.log_messages = []
        self.telegram = MagicMock()
        self.is_running = False

    def log(self, msg: str):
        self.log_messages.append(msg)


class TestSessionSummaryReport(unittest.TestCase):
    def setUp(self):
        self.lifecycle = _LifecycleTester()

    def test_generate_session_summary_report_calculates_win_rate_and_profit_factor(self):
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        self.lifecycle.trade_history = [
            {"type": "BUY", "name": "삼성전자", "profit": 0, "time": f"{today_str} 09:10:00"},
            {"type": "SELL", "name": "삼성전자", "profit": 50000, "time": f"{today_str} 09:30:00"},
            {"type": "BUY", "name": "SK하이닉스", "profit": 0, "time": f"{today_str} 10:00:00"},
            {"type": "SELL", "name": "SK하이닉스", "profit": -20000, "time": f"{today_str} 10:30:00"},
            {"type": "SELL", "name": "NAVER", "profit": 30000, "time": f"{today_str} 11:00:00"},
        ]

        report = self.lifecycle._generate_session_summary_report()

        self.assertEqual(report["total_trades"], 5)
        self.assertEqual(report["sell_trades_count"], 3)
        self.assertEqual(report["win_count"], 2)
        self.assertEqual(report["loss_count"], 1)
        self.assertAlmostEqual(report["win_rate"], 66.6666, places=2)
        self.assertEqual(report["total_realized_profit"], 60000)
        # Total gains = 80000, Total losses = 20000 -> PF = 4.0
        self.assertAlmostEqual(report["profit_factor"], 4.0, places=2)
        self.assertEqual(report["best_trade"]["name"], "삼성전자")
        self.assertEqual(report["worst_trade"]["name"], "SK하이닉스")

    def test_generate_session_summary_report_handles_empty_trades(self):
        self.lifecycle.trade_history = []
        report = self.lifecycle._generate_session_summary_report()

        self.assertEqual(report["total_trades"], 0)
        self.assertEqual(report["sell_trades_count"], 0)
        self.assertEqual(report["win_count"], 0)
        self.assertEqual(report["loss_count"], 0)
        self.assertEqual(report["win_rate"], 0.0)
        self.assertEqual(report["total_realized_profit"], 0)
        self.assertEqual(report["profit_factor"], 1.0)
        self.assertIsNone(report["best_trade"])
        self.assertIsNone(report["worst_trade"])


if __name__ == "__main__":
    unittest.main()
