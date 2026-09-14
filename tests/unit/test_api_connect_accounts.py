import unittest
from unittest.mock import MagicMock, patch

from app.mixins.api_account import APIAccountMixin


class _Harness(APIAccountMixin):
    pass


class TestAPIConnectAccounts(unittest.TestCase):
    @patch("app.mixins.api_account.KiwoomWebSocketClient")
    @patch("app.mixins.api_account.KiwoomRESTClient")
    @patch("app.mixins.api_account.KiwoomAuth")
    def test_connect_worker_fails_when_account_list_empty(self, auth_cls, rest_cls, ws_cls):
        auth = MagicMock()
        auth.test_connection.return_value = {"success": True}
        auth_cls.return_value = auth

        rest = MagicMock()
        rest.get_account_list.return_value = []
        rest_cls.return_value = rest
        ws_cls.return_value = MagicMock()

        with self.assertRaises(RuntimeError):
            _Harness()._connect_api_worker("app", "secret", False)

    @patch("app.mixins.api_account.KiwoomWebSocketClient")
    @patch("app.mixins.api_account.KiwoomRESTClient")
    @patch("app.mixins.api_account.KiwoomAuth")
    def test_connect_worker_returns_accounts_on_success(self, auth_cls, rest_cls, ws_cls):
        auth = MagicMock()
        auth.test_connection.return_value = {"success": True}
        auth_cls.return_value = auth

        rest = MagicMock()
        rest.get_account_list.return_value = ["12345678"]
        rest_cls.return_value = rest
        ws = MagicMock()
        ws_cls.return_value = ws

        payload = _Harness()._connect_api_worker("app", "secret", False)

        self.assertEqual(payload["accounts"], ["12345678"])
        self.assertIs(payload["auth"], auth)
        self.assertIs(payload["rest_client"], rest)
        self.assertIs(payload["ws_client"], ws)
        self.assertIs(rest.ws_client, ws)

    @patch("app.mixins.api_account.QMessageBox.warning")
    def test_connect_failure_guides_8030_mode_mismatch(self, warning):
        trader = _Harness()
        trader.ws_client = None
        trader.telegram = None
        trader.is_connected = True
        trader.btn_start = MagicMock()
        trader.btn_connect = MagicMock()
        trader.lbl_status = MagicMock()
        trader._last_connection_mode = "connecting"
        trader._account_refresh_pending = False
        trader._last_account_refresh_ts = 0.0
        trader._connect_inflight = True
        trader._last_profit_sign = None
        trader.logs = []
        trader.log = lambda msg: trader.logs.append(str(msg))

        trader._on_connect_api_failure(
            RuntimeError("입력 값 오류입니다[8030:투자구분(실전/모의)이 달라서 Appkey를 사용할수가 없습니다]")
        )

        self.assertTrue(warning.called)
        dialog_text = str(warning.call_args[0][2])
        self.assertIn("모의투자", dialog_text)
        self.assertIn("AppKey", dialog_text)


if __name__ == "__main__":
    unittest.main()
