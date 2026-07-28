"""A3 + A4: 설정 저장 atomic write 및 평문 secret fallback 검증.

- A3: 저장 중 예외 발생 시 기존 파일이 이전 내용으로 보존된다(tmp -> os.replace).
- A4: is_mock=True 이더라도 allow_plaintext_secret_fallback=False 이면 secret 이
  평문으로 settings 에 쓰이지 않는다.
"""
import json
import shutil
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


class _DummyCheck:
    """isChecked 가 __getattr__ 기본값(False)과 구분되도록 명시적 체크 위젯."""

    def __init__(self, checked=False):
        self._checked = bool(checked)

    def isChecked(self):
        return self._checked

    def text(self):
        return ""

    def value(self):
        return 0

    def currentText(self):
        return ""


class _DummyLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(str(msg))

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
        # _save_settings 가 읽는 체크 위젯들을 명시적으로 세팅(__getattr__ 기본값 False 와 구분).
        self.chk_mock = _DummyCheck(checked=False)
        self.chk_allow_plaintext_secret_fallback = _DummyCheck(checked=False)
        self.chk_use_risk = _DummyCheck(checked=False)
        self.chk_auto_start = _DummyCheck(checked=False)
        self.logged = []

    def __getattr__(self, _name):
        return _DummyAny()

    def _set_auto_start(self, _enabled):
        return None

    def log(self, msg):
        self.logged.append(str(msg))


class TestSaveSettingsAtomic(unittest.TestCase):
    def test_save_failure_preserves_existing_file(self):
        """A3: atomic write - 저장 중 예외 시 기존 파일이 보존된다."""
        trader = _Harness()

        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"
            # 기존 파일 존재
            original_payload = {"settings_version": 7, "codes": "005930", "original": True}
            settings_path.write_text(
                json.dumps(original_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # _atomic_write_json 이 실패하도록 patch
            with patch("app.features.persistence.settings_io.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.features.persistence.settings_io.KEYRING_AVAILABLE", True
            ), patch.object(
                PersistenceSettingsMixin, "_atomic_write_json", side_effect=OSError("disk full")
            ):
                trader._save_settings()

            # 오류 로그가 남는다.
            self.assertTrue(any("저장 실패" in m for m in trader.logged))
            # 기존 파일이 그대로 보존된다(atomic write 이므로 절반만 쓰이지 않는다).
            preserved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(preserved, original_payload)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_atomic_write_uses_tmp_then_replace(self):
        """A3: 정상 저장 시 _atomic_write_json 이 호출된다(직접 open+dump 가 아님)."""
        trader = _Harness()

        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"

            with patch("app.features.persistence.settings_io.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.features.persistence.settings_io.KEYRING_AVAILABLE", True
            ), patch.object(
                PersistenceSettingsMixin, "_atomic_write_json"
            ) as mock_atomic:
                trader._save_settings()

            self.assertEqual(mock_atomic.call_count, 1)
            args, _kwargs = mock_atomic.call_args
            # 첫 인자가 설정 파일 경로, 둘째가 payload dict
            self.assertEqual(args[0], str(settings_path))
            self.assertIsInstance(args[1], dict)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSaveSettingsNoPlaintextFallbackForMock(unittest.TestCase):
    def test_mock_mode_without_plaintext_flag_does_not_store_secret(self):
        """A4: is_mock=True 이더라도 allow_plaintext=False 면 secret 이 settings 에 쓰이지 않는다."""
        trader = _Harness()
        # app_key/secret 값을 가진 입력 위젯
        trader.input_app_key = _DummyAny(text="MY_APP_KEY")
        trader.input_secret = _DummyAny(text="MY_SECRET_KEY")
        trader.chk_mock = _DummyCheck(checked=True)  # 모의투자
        trader.chk_allow_plaintext_secret_fallback = _DummyCheck(checked=False)  # 평문 거부

        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"

            # keyring 사용 불가 상황(평문 fallback 유혹 시나리오)
            with patch("app.features.persistence.settings_io.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.features.persistence.settings_io.KEYRING_AVAILABLE", False
            ), patch("app.features.persistence.settings_io.keyring.set_password"):
                trader._save_settings()

            # secret 이 settings 파일에 평문으로 쓰이지 않는다.
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertNotIn("app_key", payload)
            self.assertNotIn("secret_key", payload)
            # 평문 fallback 이 거부되었으므로 설정 파일에 secret 이 없다(핵심 단언).
            # (keyring.set_password 시도 자체는 keyring mock 이 흡수하므로 호출 여부는 부차적)
            # 경고 로그가 모드 라벨과 함께 남는다.
            self.assertTrue(any("disabled for mock mode" in w for w in trader.logger.warnings))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_mock_mode_with_plaintext_flag_stores_secret(self):
        """A4: allow_plaintext_secret_fallback=True 일 때만 평문 저장을 허용한다."""
        trader = _Harness()
        trader.input_app_key = _DummyAny(text="MY_APP_KEY")
        trader.input_secret = _DummyAny(text="MY_SECRET_KEY")
        trader.chk_mock = _DummyCheck(checked=True)
        trader.chk_allow_plaintext_secret_fallback = _DummyCheck(checked=True)  # 명시적 허용

        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            settings_path = Path(tmpdir) / "kiwoom_settings.json"

            with patch("app.features.persistence.settings_io.Config.SETTINGS_FILE", str(settings_path)), patch(
                "app.features.persistence.settings_io.KEYRING_AVAILABLE", False
            ), patch("app.features.persistence.settings_io.keyring.set_password"):
                trader._save_settings()

            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            # 명시적 허용 시에만 평문 저장
            self.assertEqual(payload.get("app_key"), "MY_APP_KEY")
            self.assertEqual(payload.get("secret_key"), "MY_SECRET_KEY")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
