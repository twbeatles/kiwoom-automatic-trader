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


if __name__ == "__main__":
    unittest.main()
