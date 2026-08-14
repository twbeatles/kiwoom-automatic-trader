"""REST API 요청 헤더 및 주문 TR/URL 패리티 검증."""
import unittest
from unittest.mock import MagicMock, patch

from api.auth import KiwoomAuth
from api.models import OrderType, PriceType
from api.rest_client import KiwoomRESTClient


class TestRestApiHeadersAndTrParity(unittest.TestCase):
    def setUp(self):
        self.auth = MagicMock(spec=KiwoomAuth)
        self.auth.base_url = "https://mockapi.kiwoom.com"
        self.auth.get_auth_header.return_value = {"Authorization": "bearer TEST_TOKEN"}
        self.auth.session_namespace = "kiwoom_mock"
        self.client = KiwoomRESTClient(self.auth)

    @patch("requests.Session.post")
    def test_request_injects_api_id_and_cont_yn_headers(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"return_code": 0, "output": {}}
        mock_post.return_value = mock_resp

        self.client.get_stock_quote("005930")

        self.assertTrue(mock_post.called)
        _url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("Authorization"), "bearer TEST_TOKEN")
        self.assertEqual(headers.get("api-id"), "ka10001")
        self.assertEqual(headers.get("cont-yn"), "N")

    @patch("requests.Session.post")
    def test_send_order_buy_uses_ordr_endpoint_and_kt10000(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"return_code": 0, "output": {"ord_no": "B12345"}}
        mock_post.return_value = mock_resp

        res = self.client.send_order(
            account_no="87654321",
            code="005930",
            order_type=OrderType.BUY,
            quantity=10,
            price=70000,
            price_type=PriceType.LIMIT,
        )

        self.assertTrue(res.success)
        self.assertEqual(res.order_no, "B12345")
        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.endswith("/api/dostk/ordr"))
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "kt10000")
        json_data = mock_post.call_args[1]["json"]
        self.assertEqual(json_data["tr_cd"], "kt10000")
        self.assertEqual(json_data["acnt_no"], "87654321")
        self.assertEqual(json_data["stk_cd"], "005930")

    @patch("requests.Session.post")
    def test_send_order_sell_uses_ordr_endpoint_and_kt10001(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"return_code": 0, "output": {"ord_no": "S12345"}}
        mock_post.return_value = mock_resp

        res = self.client.sell_market(
            account_no="87654321",
            code="005930",
            quantity=5,
        )

        self.assertTrue(res.success)
        self.assertEqual(res.order_no, "S12345")
        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.endswith("/api/dostk/ordr"))
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "kt10001")
        json_data = mock_post.call_args[1]["json"]
        self.assertEqual(json_data["tr_cd"], "kt10001")

    @patch("requests.Session.post")
    def test_cancel_order_uses_ordr_endpoint_and_kt10003(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"return_code": 0, "output": {}}
        mock_post.return_value = mock_resp

        res = self.client.cancel_order(
            account_no="87654321",
            order_no="B12345",
            code="005930",
            quantity=10,
        )

        self.assertTrue(res.success)
        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.endswith("/api/dostk/ordr"))
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "kt10003")
        json_data = mock_post.call_args[1]["json"]
        self.assertEqual(json_data["tr_cd"], "kt10003")

    @patch("requests.Session.post")
    def test_modify_order_uses_ordr_endpoint_and_kt10002(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"return_code": 0, "output": {}}
        mock_post.return_value = mock_resp

        res = self.client.modify_order(
            account_no="87654321",
            order_no="B12345",
            code="005930",
            quantity=10,
            price=71000,
        )

        self.assertTrue(res.success)
        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.endswith("/api/dostk/ordr"))
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "kt10002")
        json_data = mock_post.call_args[1]["json"]
        self.assertEqual(json_data["tr_cd"], "kt10002")


if __name__ == "__main__":
    unittest.main()
