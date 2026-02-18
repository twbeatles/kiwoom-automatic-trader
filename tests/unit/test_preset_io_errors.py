import unittest
from unittest.mock import mock_open, patch

from ui_dialogs import PresetDialog


class _DummyLogger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))


class _DummyDialog:
    def __init__(self):
        self.logger = _DummyLogger()
        self.presets = {"custom_only": {"name": "custom"}}


class TestPresetIOErrors(unittest.TestCase):
    def test_preset_load_error_is_logged_and_reported(self):
        dialog = _DummyDialog()
        with patch("ui_dialogs.os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data="{")
        ), patch("ui_dialogs.QMessageBox.warning") as mock_warning:
            presets = PresetDialog._load_presets(dialog)

        self.assertTrue(mock_warning.called)
        self.assertTrue(dialog.logger.warnings)
        self.assertIn("aggressive", presets)

    def test_preset_save_error_is_logged_and_reported(self):
        dialog = _DummyDialog()
        with patch("builtins.open", side_effect=OSError("disk full")), patch(
            "ui_dialogs.QMessageBox.warning"
        ) as mock_warning:
            PresetDialog._save_presets(dialog)

        self.assertTrue(mock_warning.called)
        self.assertTrue(dialog.logger.errors)


if __name__ == "__main__":
    unittest.main()
