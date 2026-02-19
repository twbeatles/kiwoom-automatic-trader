import importlib
import unittest
import warnings
from pathlib import Path

from api.auth import KiwoomAuth
from config import Config


class TestPathAndWebsocketCompat(unittest.TestCase):
    def test_config_paths_are_absolute(self):
        for value in (
            Config.BASE_DIR,
            Config.DATA_DIR,
            Config.SETTINGS_FILE,
            Config.PRESETS_FILE,
            Config.TRADE_HISTORY_FILE,
            Config.LOG_DIR,
        ):
            self.assertTrue(Path(value).is_absolute(), msg=value)

    def test_auth_cache_defaults_to_base_dir(self):
        auth = KiwoomAuth()
        self.assertEqual(Path(auth.cache_dir).resolve(), Path(Config.BASE_DIR).resolve())
        self.assertEqual(auth.cache_path.parent.resolve(), Path(Config.BASE_DIR).resolve())

    def test_websocket_module_import_has_no_legacy_deprecation(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            module = importlib.import_module("api.websocket_client")
            importlib.reload(module)

        legacy_warnings = [
            w for w in caught if "websockets.legacy" in str(w.message).lower() or "websocketclientprotocol" in str(w.message)
        ]
        self.assertEqual(legacy_warnings, [])


if __name__ == "__main__":
    unittest.main()
