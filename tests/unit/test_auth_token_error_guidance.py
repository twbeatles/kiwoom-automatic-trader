"""Issue #1: 토큰 8030(실전/모의 불일치) 안내가 사용자에게 전달되는지 검증."""
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from api.auth import KiwoomAuth
from api.endpoints import MOCK_REST_BASE_URL


def _json_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


_8030_MSG = "입력 값 오류입니다[8030:투자구분(실전/모의)이 달라서 Appkey를 사용할수가 없습니다]"


class TestAuthTokenErrorGuidance(unittest.TestCase):
    def test_8030_failure_explains_mock_live_appkey_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = KiwoomAuth("mock-app", "secret", is_mock=True, cache_dir=tmpdir)
            payload = {"return_code": 8030, "return_msg": _8030_MSG}
            with patch("api.auth.requests.post", return_value=_json_response(payload)):
                token = auth.get_token(force_refresh=True)

            self.assertIsNone(token)
            message = getattr(auth, "_last_error", "")
            self.assertIn("8030", message)
            self.assertIn("모의투자", message)
            self.assertIn(MOCK_REST_BASE_URL, message)

    def test_test_connection_returns_8030_guidance_instead_of_generic_secret_hint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = KiwoomAuth("mock-app", "secret", is_mock=True, cache_dir=tmpdir)
            payload = {"return_code": 8030, "return_msg": _8030_MSG}
            with patch("api.auth.requests.post", return_value=_json_response(payload)):
                result = auth.test_connection()

            self.assertFalse(result["success"])
            self.assertIn("8030", result["message"])
            self.assertIn("모의투자", result["message"])
            self.assertNotIn("App Key/Secret Key를 확인해주세요.", result["message"])


if __name__ == "__main__":
    unittest.main()
