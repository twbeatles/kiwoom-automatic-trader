"""Issue #4: OHLC bounds and daily/tick history separation."""
import unittest
from copy import deepcopy
from types import SimpleNamespace

from config import Config, TradingConfig
from strategy_manager import StrategyManager
from strategies.manager_mixins.indicators import StrategyManagerIndicatorMixin


class TestIndicatorBounds(unittest.TestCase):
    def setUp(self):
        self.manager = StrategyManagerIndicatorMixin()

    def test_short_close_returns_unavailable(self):
        for count in (0, 14, 15, 58):
            with self.subTest(count=count):
                for name, expected in (("calculate_atr", 0), ("calculate_dmi", (0, 0, 0))):
                    with self.subTest(method=name):
                        self.assertEqual(getattr(self.manager, name)([110] * 60, [90] * 60, [100] * count), expected)

    def test_short_low_returns_unavailable(self):
        for name, expected in (("calculate_atr", 0), ("calculate_dmi", (0, 0, 0))):
            with self.subTest(method=name):
                self.assertEqual(getattr(self.manager, name)([110] * 60, [90] * 59, [100] * 60), expected)

    def test_previous_close_boundary_and_longer_close_preserved(self):
        for count in (59, 60, 61, 100, 120):
            with self.subTest(count=count):
                self.assertEqual(self.manager.calculate_atr([110] * 60, [90] * 60, [100] * count), 20)
                self.assertEqual(self.manager.calculate_dmi([110] * 60, [90] * 60, [100] * count), (0, 0, 0))

    def test_period_boundary(self):
        for period in (14, 20):
            with self.subTest(period=period):
                self.assertEqual(self.manager.calculate_atr([110] * period, [90] * period, [100] * period, period), 0)
                self.assertEqual(self.manager.calculate_dmi([110] * period, [90] * period, [100] * period, period), (0, 0, 0))
                count = period + 1
                self.assertEqual(self.manager.calculate_atr([110] * count, [90] * count, [100] * count, period), 20)

    def test_known_values_and_inputs_unchanged(self):
        high = [102 + i for i in range(60)]
        low = [98 + i for i in range(60)]
        close = [100 + i for i in range(60)]
        before = deepcopy((high, low, close))
        self.assertEqual(self.manager.calculate_atr(high, low, close), 4)
        self.assertEqual(self.manager.calculate_dmi(high, low, close), (25, 0, 100))
        self.assertEqual((high, low, close), before)

    def test_flat_prices(self):
        self.assertEqual(self.manager.calculate_atr([100] * 15, [100] * 15, [100] * 15), 0)
        self.assertEqual(self.manager.calculate_dmi([100] * 15, [100] * 15, [100] * 15), (0, 0, 0))


class TestDailyIndicatorHistory(unittest.TestCase):
    def setUp(self):
        self.info = {
            "name": "TEST", "current": 100, "buy_price": 100,
            "max_profit_rate": 0, "market_type": "KOSPI", "sector": "TEST",
            "high_history": [102 + i for i in range(60)],
            "low_history": [98 + i for i in range(60)],
            "daily_prices": [100 + i for i in range(60)],
            "price_history": [100 + i for i in range(60)],
        }
        self.trader = SimpleNamespace(universe={"005930": self.info}, deposit=100_000, log=lambda _msg: None)
        self.config = TradingConfig(
            use_dmi=True, use_regime_sizing=True, betting_ratio=100,
            regime_elevated_atr_pct=10, regime_extreme_atr_pct=20,
            feature_flags={"use_modular_strategy_pack": False},
            use_entry_scoring=False,
        )
        self.manager = StrategyManager(self.trader, self.config)

    def test_atr_stop_uses_daily_closes(self):
        self.info["price_history"] = [1000] * 100
        self.assertEqual(self.manager.calculate_atr_stop_loss("005930"), 92)

    def test_chandelier_uses_daily_closes(self):
        self.info["price_history"] = [1000] * 100
        self.assertEqual(self.manager.calculate_chandelier_stop("005930", multiplier=2), 92)

    def test_dmi_filter_uses_daily_closes(self):
        self.info["price_history"] = [1000] * 58
        self.assertTrue(self.manager.check_dmi_condition("005930"))

    def test_regime_uses_daily_closes(self):
        self.info["price_history"] = [1000] * 100
        self.assertEqual(self.manager.get_regime_profile("005930")[2], 4)

    def test_position_size_uses_daily_closes(self):
        self.info["price_history"] = [1000] * 100
        self.assertEqual(self.manager.calculate_position_size("005930"), 125)

    def test_legacy_evaluation_uses_daily_closes(self):
        self.info["price_history"] = [1000] * 100
        _, conditions, metrics = self.manager.evaluate_buy_conditions("005930", now_ts=1000)
        self.assertEqual(metrics["dmi_pdi"], 25)
        self.assertEqual(metrics["dmi_mdi"], 0)
        self.assertEqual(metrics["dmi_adx"], 100)
        self.assertTrue(conditions["dmi"])

    def test_tick_growth_and_trim_leave_daily_indicators_stable(self):
        before = (
            self.manager.calculate_atr_stop_loss("005930"),
            self.manager.calculate_chandelier_stop("005930"),
            self.manager.check_dmi_condition("005930"),
            self.manager.get_regime_profile("005930"),
            self.manager.calculate_position_size("005930"),
        )
        daily_before = self.info["daily_prices"][:]
        max_len = int(Config.MAX_PRICE_HISTORY)
        threshold = max_len + max(5, int(Config.TABLE_BATCH_LIMIT // 10))
        series = self.info["price_history"]
        for tick in range(threshold - len(series) + 1):
            series.append(1000 + tick)
            if len(series) > threshold:
                del series[:-max_len]
        self.assertEqual(len(series), max_len)
        self.assertEqual(self.info["daily_prices"], daily_before)
        self.assertEqual((
            self.manager.calculate_atr_stop_loss("005930"),
            self.manager.calculate_chandelier_stop("005930"),
            self.manager.check_dmi_condition("005930"),
            self.manager.get_regime_profile("005930"),
            self.manager.calculate_position_size("005930"),
        ), before)
        _, _, metrics = self.manager.evaluate_buy_conditions("005930", now_ts=1000)
        self.assertEqual(metrics["dmi_pdi"], 25)

    def test_missing_daily_key_keeps_legacy_fallback(self):
        del self.info["daily_prices"]
        self.assertEqual(self.manager.calculate_atr_stop_loss("005930"), 92)
        self.assertEqual(self.manager.calculate_chandelier_stop("005930", multiplier=2), 92)
        self.assertTrue(self.manager.check_dmi_condition("005930"))
        self.assertEqual(self.manager.get_regime_profile("005930")[2], 4)
        self.assertEqual(self.manager.calculate_position_size("005930"), 125)
        _, _, metrics = self.manager.evaluate_buy_conditions("005930", now_ts=1000)
        self.assertEqual(metrics["dmi_pdi"], 25)

    def test_empty_daily_does_not_use_unaligned_ticks(self):
        self.info["daily_prices"] = []
        self.config.loss_cut = 3
        self.assertEqual(self.manager.calculate_atr_stop_loss("005930"), 97)
        self.assertEqual(self.manager.calculate_chandelier_stop("005930"), 0)
        self.assertFalse(self.manager.check_dmi_condition("005930"))
        self.assertEqual(self.manager.get_regime_profile("005930"), ("normal", 1, 0))


if __name__ == "__main__":
    unittest.main()
