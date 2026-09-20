"""키움 공식 REST/WebSocket 계약 (Kiwoom-Securities/Kiwoom-REST-API 예제 기준)."""
import unittest
from unittest.mock import MagicMock, patch

from api.auth import KiwoomAuth
from api.models import OrderType, PriceType
from api.rest_client import KiwoomRESTClient
from api.websocket_client import KiwoomWebSocketClient


class TestKiwoomOfficialRestContract(unittest.TestCase):
    def setUp(self):
        self.auth = MagicMock(spec=KiwoomAuth)
        self.auth.base_url = "https://mockapi.kiwoom.com"
        self.auth.get_auth_header.return_value = {"Authorization": "bearer TEST_TOKEN"}
        self.auth.session_namespace = "kiwoom_mock"
        self.client = KiwoomRESTClient(self.auth)

    def _json_ok(self, payload):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        return mock_resp

    @patch("requests.Session.post")
    def test_buy_limit_uses_official_kt10000_body(self, mock_post):
        mock_post.return_value = self._json_ok({"return_code": 0, "ord_no": "0000141"})

        result = self.client.send_order(
            account_no="87654321",
            code="005930",
            order_type=OrderType.BUY,
            quantity=10,
            price=70000,
            price_type=PriceType.LIMIT,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.order_no, "0000141")
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/ordr"))
        self.assertEqual(headers.get("api-id"), "kt10000")
        self.assertEqual(body["dmst_stex_tp"], "KRX")
        self.assertEqual(body["stk_cd"], "005930")
        self.assertEqual(body["ord_qty"], "10")
        self.assertEqual(body["trde_tp"], "0")
        self.assertEqual(body["ord_uv"], "70000")
        self.assertNotIn("tr_cd", body)
        self.assertNotIn("acnt_no", body)

    @patch("requests.Session.post")
    def test_market_sell_uses_trde_tp_3(self, mock_post):
        mock_post.return_value = self._json_ok({"return_code": 0, "ord_no": "0000142"})

        result = self.client.sell_market("87654321", "005930", 5)

        self.assertTrue(result.success)
        body = mock_post.call_args[1]["json"]
        self.assertEqual(mock_post.call_args[1]["headers"].get("api-id"), "kt10001")
        self.assertEqual(body["trde_tp"], "3")
        self.assertEqual(body["ord_uv"], "")

    @patch("requests.Session.post")
    def test_cancel_order_uses_official_kt10003_body(self, mock_post):
        mock_post.return_value = self._json_ok({"return_code": 0, "ord_no": "0000143"})

        result = self.client.cancel_order("87654321", "0000140", "005930", 1)

        self.assertTrue(result.success)
        body = mock_post.call_args[1]["json"]
        self.assertEqual(mock_post.call_args[1]["headers"].get("api-id"), "kt10003")
        self.assertEqual(body["orig_ord_no"], "0000140")
        self.assertEqual(body["cncl_qty"], "1")
        self.assertEqual(body["dmst_stex_tp"], "KRX")
        self.assertNotIn("tr_cd", body)

    @patch("requests.Session.post")
    def test_open_orders_use_ka10075_acnt_path(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "oso": [
                    {
                        "ord_no": "O111",
                        "stk_cd": "005930",
                        "trde_tp": "2",
                        "ord_qty": "10",
                        "oso_qty": "7",
                        "ord_pric": "70,000",
                        "ord_stt": "접수",
                    }
                ],
            }
        )

        orders = self.client.get_open_orders("12345678")

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side, "buy")
        self.assertEqual(orders[0].remaining_qty, 7)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/acnt"))
        self.assertEqual(headers.get("api-id"), "ka10075")
        self.assertEqual(body["all_stk_tp"], "0")
        self.assertEqual(body["trde_tp"], "0")
        self.assertEqual(body["stex_tp"], "0")
        self.assertNotIn("tr_cd", body)

    @patch("requests.Session.post")
    def test_account_list_uses_ka00001(self, mock_post):
        mock_post.return_value = self._json_ok({"return_code": 0, "acctNo": ["11111111", "22222222"]})

        accounts = self.client.get_account_list()

        self.assertEqual(accounts, ["11111111", "22222222"])
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        self.assertTrue(url.endswith("/api/dostk/acnt"))
        self.assertEqual(headers.get("api-id"), "ka00001")

    @patch("requests.Session.post")
    def test_positions_use_kt00018(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "tot_pur_amt": "210000",
                "acnt_evlt_remn_indv_tot": [
                    {
                        "stk_cd": "005930",
                        "stk_nm": "삼성전자",
                        "rmnd_qty": "3",
                        "trde_able_qty": "3",
                        "pur_pric": "70000",
                        "cur_prc": "71000",
                        "pur_amt": "210000",
                        "evlt_amt": "213000",
                        "evltv_prft": "3000",
                        "prft_rt": "1.43",
                    }
                ],
            }
        )

        positions = self.client.get_positions("12345678")

        self.assertIsNotNone(positions)
        assert positions is not None
        self.assertEqual(positions[0].code, "005930")
        self.assertEqual(positions[0].quantity, 3)
        self.assertEqual(positions[0].buy_price, 70000)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/acnt"))
        self.assertEqual(headers.get("api-id"), "kt00018")
        self.assertEqual(body["qry_tp"], "1")
        self.assertEqual(body["dmst_stex_tp"], "KRX")

    @patch("requests.Session.post")
    def test_stock_quote_uses_ka10001_stkinfo(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "stk_nm": "삼성전자",
                "cur_prc": "-70000",
                "pred_pre": "-500",
                "flu_rt": "-0.71",
                "open_pric": "70500",
                "high_pric": "71000",
                "low_pric": "69500",
                "trde_qty": "123456",
            }
        )

        quote = self.client.get_stock_quote("005930")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.name, "삼성전자")
        self.assertEqual(quote.current_price, 70000)
        self.assertEqual(quote.change, -500)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/stkinfo"))
        self.assertEqual(headers.get("api-id"), "ka10001")
        self.assertEqual(body, {"stk_cd": "005930"})

    @patch("requests.Session.post")
    def test_volume_ranking_uses_ka10030_rkinfo(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "tdy_trde_qty_upper": [
                    {
                        "stk_cd": "005930",
                        "stk_nm": "삼성전자",
                        "cur_prc": "70,000",
                        "flu_rt": "1.20",
                        "trde_qty": "1,000,000",
                        "trde_tern_rt": "0.51",
                    }
                ],
            }
        )

        rows = self.client.get_volume_ranking("0", 30)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "005930")
        self.assertEqual(rows[0]["volume"], 1000000)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/rkinfo"))
        self.assertEqual(headers.get("api-id"), "ka10030")
        self.assertEqual(body["mrkt_tp"], "000")
        self.assertEqual(body["sort_tp"], "1")
        self.assertEqual(body["stex_tp"], "3")
        self.assertNotIn("mkt_tp", body)

    @patch("requests.Session.post")
    def test_fluctuation_ranking_maps_down_sort_to_official_3(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "pred_pre_flu_rt_upper": [
                    {
                        "stk_cd": "000660",
                        "stk_nm": "SK하이닉스",
                        "cur_prc": "120000",
                        "pred_pre": "-1000",
                        "flu_rt": "-0.83",
                        "now_trde_qty": "5000",
                    }
                ],
            }
        )

        rows = self.client.get_fluctuation_ranking("2", "2", 10)

        self.assertEqual(rows[0]["code"], "000660")
        self.assertEqual(rows[0]["change"], -1000)
        body = mock_post.call_args[1]["json"]
        self.assertEqual(mock_post.call_args[1]["headers"].get("api-id"), "ka10027")
        self.assertTrue(mock_post.call_args[0][0].endswith("/api/dostk/rkinfo"))
        self.assertEqual(body["mrkt_tp"], "101")
        self.assertEqual(body["sort_tp"], "3")

    @patch("requests.Session.post")
    def test_investor_trading_uses_ka10045_mrkcond(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "stk_orgn_trde_trnsn": [
                    {
                        "dt": "20260914",
                        "orgn_daly_nettrde_qty": "1200",
                        "for_daly_nettrde_qty": "-800",
                    }
                ],
            }
        )

        data = self.client.get_investor_trading("005930")

        self.assertEqual(data["institution_net"], 1200)
        self.assertEqual(data["foreign_net"], -800)
        self.assertEqual(data["individual_net"], 0)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/mrkcond"))
        self.assertEqual(headers.get("api-id"), "ka10045")
        self.assertEqual(body["stk_cd"], "005930")
        self.assertIn("strt_dt", body)
        self.assertIn("end_dt", body)

    @patch("requests.Session.post")
    def test_program_trading_uses_ka90013_mrkcond(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "stk_daly_prm_trde_trnsn": [
                    {
                        "prm_buy_qty": "3000",
                        "prm_sell_qty": "1000",
                        "prm_netprps_qty": "2000",
                    }
                ],
            }
        )

        data = self.client.get_program_trading("005930")

        self.assertEqual(data["total_buy"], 3000)
        self.assertEqual(data["total_sell"], 1000)
        self.assertEqual(data["net"], 2000)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/mrkcond"))
        self.assertEqual(headers.get("api-id"), "ka90013")
        self.assertEqual(body["stk_cd"], "005930")

    @patch("requests.Session.post")
    def test_index_quote_uses_ka20001_sect(self, mock_post):
        mock_post.return_value = self._json_ok(
            {
                "return_code": 0,
                "cur_prc": "2700.50",
                "pred_pre": "12.30",
                "flu_rt": "0.46",
                "open_pric": "2690.00",
                "high_pric": "2710.00",
                "low_pric": "2680.00",
                "trde_qty": "12345",
                "trde_prica": "890000",
            }
        )

        quote = self.client.get_index_quote("001")

        self.assertEqual(quote["cur_idx"], 2700.5)
        self.assertEqual(quote["chg_rt"], 0.46)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/sect"))
        self.assertEqual(headers.get("api-id"), "ka20001")
        self.assertEqual(body["mrkt_tp"], "0")
        self.assertEqual(body["inds_cd"], "001")

    @patch("requests.Session.post")
    def test_market_status_does_not_call_invented_rest(self, mock_post):
        self.assertEqual(self.client.get_market_status(), {})
        mock_post.assert_not_called()

    def test_condition_list_uses_websocket_cnsrlst(self):
        ws = MagicMock()
        ws.request_once.return_value = {
            "trnm": "CNSRLST",
            "data": [{"seq": "1", "name": "급등주"}, ["2", "거래량폭증"]],
        }
        self.client.ws_client = ws

        conditions = self.client.get_condition_list()

        self.assertEqual(conditions[0], {"index": 1, "name": "급등주"})
        self.assertEqual(conditions[1], {"index": 2, "name": "거래량폭증"})
        body = ws.request_once.call_args[0][0]
        self.assertEqual(body["trnm"], "CNSRLST")

    def test_condition_search_uses_websocket_cnsrreq(self):
        ws = MagicMock()
        ws.request_once.return_value = {
            "trnm": "CNSRREQ",
            "data": [{"9001": "A005930", "302": "삼성전자", "10": "70000", "12": "1.2", "13": "1000"}],
        }
        self.client.ws_client = ws

        stocks = self.client.search_by_condition(4, "급등주")

        self.assertEqual(stocks[0]["code"], "005930")
        self.assertEqual(stocks[0]["name"], "삼성전자")
        self.assertEqual(stocks[0]["current_price"], 70000)
        body = ws.request_once.call_args[0][0]
        self.assertEqual(body["trnm"], "CNSRREQ")
        self.assertEqual(body["seq"], "4")
        self.assertEqual(body["search_type"], "0")
        self.assertEqual(body["stex_tp"], "K")


class TestKiwoomOfficialWebsocketContract(unittest.TestCase):
    def test_real_types_match_official_codes(self):
        self.assertEqual(KiwoomWebSocketClient.REAL_TYPE["EXECUTION"], "0B")
        self.assertEqual(KiwoomWebSocketClient.REAL_TYPE["HOGA"], "0D")
        self.assertEqual(KiwoomWebSocketClient.REAL_TYPE["ORDER_EXEC"], "00")
        self.assertEqual(KiwoomWebSocketClient.REAL_TYPE["INDEX"], "0J")
        self.assertEqual(KiwoomWebSocketClient.REAL_TYPE["VI"], "1h")

    def test_reg_subscribe_payload_uses_official_trnm(self):
        auth = MagicMock(spec=KiwoomAuth)
        auth.ws_url = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
        client = KiwoomWebSocketClient(auth)
        payload = client._build_reg_payload(["005930", "000660"], "0B", register=True)
        self.assertEqual(payload["trnm"], "REG")
        self.assertEqual(payload["data"][0]["item"], ["005930", "000660"])
        self.assertEqual(payload["data"][0]["type"], ["0B"])

        remove = client._build_reg_payload(["005930"], "0B", register=False)
        self.assertEqual(remove["trnm"], "REMOVE")

    def test_request_once_without_token_returns_none(self):
        auth = MagicMock(spec=KiwoomAuth)
        auth.ws_url = "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
        auth.get_token.return_value = None
        client = KiwoomWebSocketClient(auth)
        self.assertIsNone(client.request_once({"trnm": "CNSRLST"}))


if __name__ == "__main__":
    unittest.main()
