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


class _DummyLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)


class _Harness(PersistenceSettingsMixin):
    def __init__(self):
        self.logger = _DummyLogger()
        self.current_theme = "dark"
        self.schedule = {"enabled": False, "start": "09:00", "end": "15:19", "liquidate": True}
        self.applied_styles = []
        self.logged = []

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

    def log(self, msg):
        self.logged.append(msg)

    def setStyleSheet(self, style):
        self.applied_styles.append(style)


class TestSettingsSchemaCompat(unittest.TestCase):
    def test_loads_legacy_betting_key(self):
        trader = _Harness()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"
            settings_path.write_text(
                json.dumps({"betting": 12.5, "codes": "005930"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("app.mixins.persistence_settings.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.mixins.persistence_settings.keyring.get_password", side_effect=RuntimeError("no keyring")
            ):
                trader._load_settings()

        self.assertEqual(trader.spin_betting.value(), 12.5)

    def test_prefers_betting_ratio_and_normalizes_schedule(self):
        trader = _Harness()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "betting": 12.5,
                        "betting_ratio": 7.5,
                        "schedule": {"enabled": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("app.mixins.persistence_settings.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.mixins.persistence_settings.keyring.get_password", return_value=""
            ):
                trader._load_settings()

        self.assertEqual(trader.spin_betting.value(), 7.5)
        self.assertEqual(
            trader.schedule,
            {"enabled": True, "start": "09:00", "end": "15:19", "liquidate": True},
        )


if __name__ == "__main__":
    unittest.main()
