import unittest
from unittest.mock import MagicMock, patch

from app.mixins.api_account import APIAccountMixin


class _Harness(APIAccountMixin):
    def __init__(self):
        self.ws_client = None
        self.telegram = None
        self.is_connected = True
        self.auth = object()
        self.rest_client = object()
        self.current_account = "12345678"
        self._account_refresh_pending = True
        self._last_account_refresh_ts = 1.0
        self._connect_inflight = True
        self._last_connection_mode = "connected"
        self._last_profit_sign = 1
        self._reserved_cash_by_code = {"005930": 1000}
        self.external_positions = {"123456": {"held": 1}}
        self._diagnostics_by_code = {"005930": {}}
        self._diagnostics_dirty_codes = {"005930"}
        self.btn_start = MagicMock()
        self.btn_connect = MagicMock()


class TestNotifierReset(unittest.TestCase):
    def test_reset_connection_state_stops_existing_telegram_notifier(self):
        trader = _Harness()
        old_telegram = MagicMock()
        trader.telegram = old_telegram

        trader._reset_connection_state()

        old_telegram.stop.assert_called_once()
        self.assertIsNone(trader.telegram)
        self.assertFalse(trader.is_connected)

    @patch("app.mixins.api_account.TelegramNotifier")
    def test_connect_success_replaces_existing_telegram_notifier(self, telegram_cls):
        old_telegram = MagicMock()
        new_telegram = MagicMock()
        telegram_cls.return_value = new_telegram
        trader = _Harness()
        trader.telegram = old_telegram
        trader.combo_acc = MagicMock()
        trader.combo_acc.count.return_value = 0
        trader.chk_use_telegram = MagicMock()
        trader.chk_use_telegram.isChecked.return_value = True
        trader.input_tg_token = MagicMock()
        trader.input_tg_token.text.return_value = "token"
        trader.input_tg_chat = MagicMock()
        trader.input_tg_chat.text.return_value = "chat"
        trader._set_connection_status = MagicMock()
        trader.log = MagicMock()

        trader._on_connect_api_success({"auth": object(), "rest_client": object(), "ws_client": object(), "accounts": []})

        old_telegram.stop.assert_called_once()
        new_telegram.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
