import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("keyring", MagicMock())

from app.mixins.persistence_settings import PersistenceSettingsMixin


class _DummyText:
    def __init__(self, value=""):
        self._value = value

    def setText(self, value):
        self._value = value

    def text(self):
        return self._value


class _DummyCheck:
    def __init__(self, value=False):
        self._value = bool(value)

    def setChecked(self, value):
        self._value = bool(value)

    def isChecked(self):
        return self._value


class _DummySpin:
    def __init__(self, value=0):
        self._value = value

    def setValue(self, value):
        self._value = value

    def value(self):
        return self._value


class _DummyCombo:
    def __init__(self, value=""):
        self._value = value

    def setCurrentText(self, value):
        self._value = str(value)

    def currentText(self):
        return self._value


class _DummyLogger:
    def warning(self, _msg):
        return None


class _DummyConfig:
    def __init__(self):
        self.strategy_pack = {}
        self.strategy_params = {}
        self.portfolio_mode = "single_strategy"
        self.short_enabled = False
        self.asset_scope = "kr_stock_live"
        self.backtest_config = {}
        self.feature_flags = {}
        self.execution_policy = "market"


class _Harness(PersistenceSettingsMixin):
    def __init__(self):
        self.logger = _DummyLogger()
        self.current_theme = "dark"
        self.schedule = {"enabled": False, "start": "09:00", "end": "15:19", "liquidate": True}
        self.config = _DummyConfig()

        self.input_app_key = _DummyText()
        self.input_secret = _DummyText()
        self.chk_mock = _DummyCheck()
        self.chk_auto_start = _DummyCheck()
        self.input_codes = _DummyText()
        self.spin_betting = _DummySpin()
        self.spin_k = _DummySpin()
        self.spin_ts_start = _DummySpin()
        self.spin_ts_stop = _DummySpin()
        self.spin_loss = _DummySpin()
        self.chk_use_rsi = _DummyCheck()
        self.spin_rsi_upper = _DummySpin()
        self.spin_rsi_period = _DummySpin()
        self.chk_use_macd = _DummyCheck()
        self.chk_use_bb = _DummyCheck()
        self.spin_bb_k = _DummySpin()
        self.chk_use_dmi = _DummyCheck()
        self.spin_adx = _DummySpin()
        self.chk_use_volume = _DummyCheck()
        self.spin_volume_mult = _DummySpin()
        self.chk_use_risk = _DummyCheck()
        self.spin_max_loss = _DummySpin()
        self.spin_max_holdings = _DummySpin()
        self.input_tg_token = _DummyText()
        self.input_tg_chat = _DummyText()
        self.chk_use_telegram = _DummyCheck()
        self.combo_daily_loss_basis = _DummyCombo("total_equity")

        self.chk_use_shock_guard = _DummyCheck()
        self.spin_shock_1m = _DummySpin()
        self.spin_shock_5m = _DummySpin()
        self.spin_shock_cooldown = _DummySpin()
        self.chk_use_vi_guard = _DummyCheck()
        self.spin_vi_cooldown = _DummySpin()
        self.chk_use_regime_sizing = _DummyCheck()
        self.chk_use_liquidity_stress_guard = _DummyCheck()
        self.chk_use_slippage_guard = _DummyCheck()
        self.spin_max_slippage_bps = _DummySpin()
        self.chk_use_order_health_guard = _DummyCheck()

    def log(self, _msg):
        return None

    def setStyleSheet(self, styleSheet):
        return None


class TestSettingsSchemaV4Compat(unittest.TestCase):
    def test_v3_file_loads_with_v4_guard_defaults(self):
        trader = _Harness()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"
            settings_path.write_text(json.dumps({"settings_version": 3, "codes": "005930"}), encoding="utf-8")

            with patch("app.mixins.persistence_settings.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.mixins.persistence_settings.keyring.get_password", return_value=""
            ):
                trader._load_settings()

        self.assertTrue(trader.chk_use_shock_guard.isChecked())
        self.assertTrue(trader.chk_use_vi_guard.isChecked())
        self.assertTrue(trader.chk_use_order_health_guard.isChecked())
        self.assertGreater(float(trader.spin_max_slippage_bps.value()), 0.0)
        self.assertTrue(getattr(trader.config, "use_shock_guard", False))


if __name__ == "__main__":
    unittest.main()
