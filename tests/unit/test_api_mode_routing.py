import unittest

from api.auth import KiwoomAuth
from api.endpoints import LIVE_REST_BASE_URL, LIVE_WS_URL, MOCK_REST_BASE_URL, MOCK_WS_URL
from api.rest_client import KiwoomRESTClient


class TestAPIModeRouting(unittest.TestCase):
    def test_auth_resolves_live_and_mock_endpoints_and_cache_paths(self):
        live_auth = KiwoomAuth(app_key="live-app", secret_key="secret", is_mock=False)
        mock_auth = KiwoomAuth(app_key="mock-app", secret_key="secret", is_mock=True)

        self.assertEqual(live_auth.base_url, LIVE_REST_BASE_URL)
        self.assertEqual(live_auth.ws_url, LIVE_WS_URL)
        self.assertTrue(str(live_auth.cache_path).endswith("kiwoom_token_cache_live.json"))
        self.assertEqual(mock_auth.base_url, MOCK_REST_BASE_URL)
        self.assertEqual(mock_auth.ws_url, MOCK_WS_URL)
        self.assertTrue(str(mock_auth.cache_path).endswith("kiwoom_token_cache_mock.json"))

    def test_rest_client_uses_auth_mode_specific_base_url(self):
        live_client = KiwoomRESTClient(KiwoomAuth(app_key="live-app", secret_key="secret", is_mock=False))
        mock_client = KiwoomRESTClient(KiwoomAuth(app_key="mock-app", secret_key="secret", is_mock=True))

        self.assertEqual(live_client.base_url, LIVE_REST_BASE_URL)
        self.assertEqual(mock_client.base_url, MOCK_REST_BASE_URL)


if __name__ == "__main__":
    unittest.main()
