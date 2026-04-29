import tempfile
import unittest
from pathlib import Path

from api.auth import KiwoomAuth
from api.endpoints import LIVE_REST_BASE_URL, LIVE_WS_URL, MOCK_REST_BASE_URL, MOCK_WS_URL
from api.rest_client import KiwoomRESTClient
from api.websocket_client import KiwoomWebSocketClient, WEBSOCKETS_AVAILABLE
from config import Config


class TestAPIModeRouting(unittest.TestCase):
    def test_auth_resolves_live_and_mock_endpoints_and_cache_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            live_auth = KiwoomAuth(app_key="live-app", secret_key="secret", is_mock=False, cache_dir=tmpdir)
            mock_auth = KiwoomAuth(app_key="mock-app", secret_key="secret", is_mock=True, cache_dir=tmpdir)

            self.assertEqual(live_auth.mode, "live")
            self.assertEqual(live_auth.base_url, LIVE_REST_BASE_URL)
            self.assertEqual(live_auth.ws_url, LIVE_WS_URL)
            self.assertTrue(str(live_auth.cache_path).endswith("kiwoom_token_cache_live.json"))
            self.assertEqual(mock_auth.mode, "mock")
            self.assertEqual(mock_auth.base_url, MOCK_REST_BASE_URL)
            self.assertEqual(mock_auth.ws_url, MOCK_WS_URL)
            self.assertTrue(str(mock_auth.cache_path).endswith("kiwoom_token_cache_mock.json"))
            self.assertNotEqual(live_auth.cache_path.name, mock_auth.cache_path.name)

    def test_rest_and_websocket_clients_use_auth_mode_endpoints(self):
        live_auth = KiwoomAuth(app_key="live-app", secret_key="secret", is_mock=False)
        mock_auth = KiwoomAuth(app_key="mock-app", secret_key="secret", is_mock=True)

        live_rest = KiwoomRESTClient(live_auth)
        mock_rest = KiwoomRESTClient(mock_auth)
        self.assertEqual(live_rest.base_url, LIVE_REST_BASE_URL)
        self.assertEqual(mock_rest.base_url, MOCK_REST_BASE_URL)

        override_rest = KiwoomRESTClient(live_auth, base_url="https://example.test/")
        self.assertEqual(override_rest.base_url, "https://example.test")

        if WEBSOCKETS_AVAILABLE:
            live_ws = KiwoomWebSocketClient(live_auth)
            mock_ws = KiwoomWebSocketClient(mock_auth)
            self.assertEqual(live_ws.ws_url, LIVE_WS_URL)
            self.assertEqual(mock_ws.ws_url, MOCK_WS_URL)

            override_ws = KiwoomWebSocketClient(live_auth, ws_url="wss://example.test/ws")
            self.assertEqual(override_ws.ws_url, "wss://example.test/ws")

    def test_config_keeps_backward_compatible_endpoint_aliases(self):
        self.assertEqual(Config.REST_API_BASE_URL, Config.KIWOOM_LIVE_REST_API_BASE_URL)
        self.assertEqual(Config.WEBSOCKET_URL, Config.KIWOOM_LIVE_WEBSOCKET_URL)

    def test_stock_quote_contract_fixture_maps_fields(self):
        auth = KiwoomAuth(cache_dir=tempfile.gettempdir())
        client = KiwoomRESTClient(auth)
        client._request = lambda *_args, **_kwargs: {
            "return_code": 0,
            "output": {
                "stk_nm": "삼성전자",
                "cur_prc": "-70000",
                "chg_amt": "-500",
                "chg_rt": "-0.71",
                "open_prc": "70500",
                "high_prc": "71000",
                "low_prc": "69500",
                "acc_vol": "123456",
                "yes_prc": "70500",
                "ask_prc": "70010",
                "bid_prc": "70000",
                "stk_tm": "20260429103000",
                "mkt_gb": "1",
                "sect_nm": "전기전자",
            },
        }

        quote = client.get_stock_quote("005930")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.code, "005930")
        self.assertEqual(quote.name, "삼성전자")
        self.assertEqual(quote.current_price, 70000)
        self.assertEqual(quote.market_type, "KOSPI")
        self.assertEqual(quote.sector, "전기전자")

    def test_auth_cache_defaults_to_base_dir_with_mode_suffix(self):
        auth = KiwoomAuth()
        self.assertEqual(Path(auth.cache_dir).resolve(), Path(Config.BASE_DIR).resolve())
        self.assertEqual(auth.cache_path.name, "kiwoom_token_cache_live.json")


if __name__ == "__main__":
    unittest.main()
