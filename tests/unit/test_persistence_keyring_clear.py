import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("keyring", MagicMock())

from app.mixins.persistence_settings import PersistenceSettingsMixin


class _DummyAny:
    def __init__(self, text="", checked=False, value=0):
        self._text = text
        self._checked = checked
        self._value = value

    def text(self):
        return self._text

    def isChecked(self):
        return self._checked

    def value(self):
        return self._value

    def currentText(self):
        return str(self._text)


class _DummyLogger:
    def warning(self, _msg):
        return None

    def error(self, _msg):
        return None


class _Harness(PersistenceSettingsMixin):
    def __init__(self):
        self.logger = _DummyLogger()
        self.current_theme = "dark"
        self.schedule = {"enabled": False, "start": "09:00", "end": "15:19", "liquidate": True}
        self.config = type(
            "Cfg",
            (),
            {
                "strategy_pack": {},
                "strategy_params": {},
                "portfolio_mode": "single_strategy",
                "short_enabled": False,
                "asset_scope": "kr_stock_live",
                "backtest_config": {},
                "feature_flags": {},
                "execution_policy": "market",
            },
        )()
        self.input_app_key = _DummyAny(text="")
        self.input_secret = _DummyAny(text="")
        self.logged = []

    def __getattr__(self, _name):
        return _DummyAny()

    def _set_auto_start(self, _enabled):
        return None

    def log(self, msg):
        self.logged.append(str(msg))


class TestPersistenceKeyringClear(unittest.TestCase):
    def test_save_settings_empty_credentials_deletes_keyring_entries(self):
        trader = _Harness()

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"
            settings_path.write_text(
                json.dumps({"app_key": "legacy", "secret_key": "legacy"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("app.mixins.persistence_settings.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.mixins.persistence_settings.KEYRING_AVAILABLE", True
            ), patch("app.mixins.persistence_settings.keyring.delete_password") as mock_delete:
                trader._save_settings()

            self.assertEqual(mock_delete.call_count, 2)
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertNotIn("app_key", payload)
            self.assertNotIn("secret_key", payload)


if __name__ == "__main__":
    unittest.main()
