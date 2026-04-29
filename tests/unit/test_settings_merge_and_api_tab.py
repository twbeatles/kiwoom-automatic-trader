import unittest
from typing import Any, cast

from app.mixins.api_account import APIAccountMixin
from app.mixins.persistence_settings import PersistenceSettingsMixin
from config import Config


class _SettingsHarness(PersistenceSettingsMixin):
    pass


class _Widget:
    def __init__(self, name=""):
        self._name = name

    def objectName(self):
        return self._name


class _Tabs:
    def __init__(self):
        self.current = None
        self.widgets = [_Widget("strategy_tab"), _Widget("api_tab")]
        self.titles = ["전략", "API/알림"]

    def count(self):
        return len(self.widgets)

    def widget(self, index):
        return self.widgets[index]

    def tabText(self, index):
        return self.titles[index]

    def setCurrentIndex(self, index):
        self.current = index


class _Central:
    def __init__(self, tabs):
        self.tabs = tabs

    def findChild(self, _cls):
        return self.tabs


class _APIHarness:
    def __init__(self):
        self.tabs = _Tabs()

    def centralWidget(self):
        return _Central(self.tabs)


class TestSettingsMergeAndAPITab(unittest.TestCase):
    def test_schema_migration_deep_merges_nested_defaults(self):
        settings = {
            "settings_version": Config.SETTINGS_SCHEMA_VERSION,
            "strategy_pack": {"primary_strategy": "ma_channel_trend"},
            "backtest_config": {"commission_bps": 1.0},
            "feature_flags": {"enable_backtest": False},
        }

        _SettingsHarness()._apply_settings_schema_migration(settings)

        self.assertEqual(settings["strategy_pack"]["primary_strategy"], "ma_channel_trend")
        self.assertIn("risk_overlays", settings["strategy_pack"])
        self.assertIn("intel_fresh_guard", settings["strategy_pack"]["risk_overlays"])
        self.assertEqual(settings["backtest_config"]["commission_bps"], 1.0)
        self.assertIn("slippage_bps", settings["backtest_config"])
        self.assertFalse(settings["feature_flags"]["enable_backtest"])
        self.assertIn("enable_external_data", settings["feature_flags"])

    def test_api_tab_helper_finds_tab_without_hardcoded_index(self):
        trader = _APIHarness()

        self.assertTrue(APIAccountMixin._focus_api_tab(cast(Any, trader)))
        self.assertEqual(trader.tabs.current, 1)


if __name__ == "__main__":
    unittest.main()
