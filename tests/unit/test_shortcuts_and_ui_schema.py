import re
import unittest
from pathlib import Path
from unittest.mock import patch

from app.mixins.system_shell import SystemShellMixin
from config import Config


class _DummySignal:
    def __init__(self, key, sink):
        self._key = key
        self._sink = sink

    def connect(self, fn):
        self._sink.append((self._key, fn))


class _DummyShortcut:
    def __init__(self, key, _parent, sink):
        self.activated = _DummySignal(key, sink)


class _Harness(SystemShellMixin):
    def __init__(self):
        self.current_account = "12345678"

    def connect_api(self):
        return None

    def start_trading(self):
        return None

    def stop_trading(self):
        return None

    def _emergency_liquidate(self):
        return None

    def _on_account_changed(self, _account):
        return None

    def _export_csv(self):
        return None

    def _open_profile_manager(self):
        return None

    def _open_presets(self):
        return None

    def _toggle_theme(self):
        return None

    def _open_stock_search(self):
        return None

    def _open_manual_order(self):
        return None


class TestShortcutsAndUISchema(unittest.TestCase):
    def test_shortcut_ctrl_p_opens_profile_manager(self):
        self.assertEqual(Config.SHORTCUTS.get("open_profile_manager"), "Ctrl+P")
        self.assertEqual(Config.SHORTCUTS.get("open_presets"), "Ctrl+Shift+P")

        records = []
        with patch("app.mixins.system_shell.QKeySequence", side_effect=lambda key: key), patch(
            "app.mixins.system_shell.QShortcut",
            side_effect=lambda key, parent: _DummyShortcut(key, parent, records),
        ):
            _Harness()._setup_shortcuts()

        self.assertTrue(any(key == "Ctrl+P" and fn.__name__ == "_open_profile_manager" for key, fn in records))
        self.assertTrue(any(key == "Ctrl+Shift+P" and fn.__name__ == "_open_presets" for key, fn in records))

    def test_auto_start_widget_single_source_of_truth(self):
        path = Path("app/mixins/ui_build.py")
        text = path.read_text(encoding="utf-8")
        count = len(re.findall(r"self\.chk_auto_start\s*=\s*QCheckBox", text))
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
