"""P0 Kiwoom API gap adapters (공식 TOC 기준 추가분).

Covered gaps:
- REST ka10074 일자별실현손익 / ka10072 일자별종목별실현손익_일자 /
  ka10073 일자별종목별실현손익_기간
- REST ka10078 증권사별종목매매동향
- REST ka10100 종목정보조회 / ka10101 업종코드 / ka10102 회원사
- WS ka10173 조건검색 실시간 등록 / ka10174 실시간 해제
- WS REAL `0s` 장시작시간 구독 + get_market_status 스냅샷 연동
"""
import asyncio
import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from api.auth import KiwoomAuth
from api.rest_client import KiwoomRESTClient
from api.websocket_client import KiwoomWebSocketClient


PRE_EXISTING_REST_METHODS = [
    "__init__", "_condition_ws", "_create_session", "_index_market_tp",
    "_order_no_from_result", "_parse_market_type", "_parse_order_side",
    "_rank_market_tp", "_rate_limit", "_request", "_stk_cd",
    "buy_limit", "buy_market", "cancel_order",
    "get_account_info", "get_account_list", "get_condition_list",
    "get_daily_chart", "get_deposit_detail", "get_executed_orders",
    "get_fluctuation_ranking", "get_index_quote", "get_investor_trading",
    "get_market_indexes", "get_market_status", "get_minute_chart",
    "get_open_orders", "get_order_book", "get_positions",
    "get_program_trading", "get_stock_name", "get_stock_quote",
    "get_tick_chart", "get_vi_status", "get_volume_ranking",
    "get_weekly_chart", "modify_order", "search_by_condition",
    "sell_limit", "sell_market", "send_order", "supports_open_orders",
]

NEW_REST_METHODS = [
    "get_realized_pnl", "get_realized_pnl_by_stock",
    "get_realized_pnl_by_stock_period", "_parse_stock_pnl_row",
    "get_stock_info_detail", "get_sector_code_list", "get_member_list",
    "get_broker_stock_trend", "request_condition_realtime",
    "stop_condition_realtime", "_parse_condition_stock_rows",
]


def _make_client():
    auth = MagicMock(spec=KiwoomAuth)
    auth.base_url = "https://mockapi.kiwoom.com"
    auth.get_auth_header.return_value = {"Authorization": "Bearer test"}
    auth.session_namespace = "kiwoom_mock"
    return KiwoomRESTClient(auth)


def _json_ok(payload):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    return mock_resp


def _make_ws():
    ws = KiwoomWebSocketClient.__new__(KiwoomWebSocketClient)
    ws.logger = logging.getLogger("test.api_gap_p0")
    ws._subscriptions = {}
    ws._subscribed_codes = set()
    ws._condition_realtime = {}
    ws._market_status_cache = {}
    ws._on_market_status = None
    ws._on_execution = None
    ws._on_hoga = None
    ws._on_order_exec = None
    ws._on_index = None
    ws._on_vi = None
    ws._qt_dispatcher = None
    ws._connected = False
    ws._loop = None
    ws._ws = None
    return ws


class TestGapTrCodes(unittest.TestCase):
    def test_new_tr_codes_present(self):
        codes = KiwoomRESTClient.TR_CODES
        self.assertEqual(codes["PNL_DAILY"], "ka10074")
        self.assertEqual(codes["PNL_STOCK_DATE"], "ka10072")
        self.assertEqual(codes["PNL_STOCK_PERIOD"], "ka10073")
        self.assertEqual(codes["BROKER_STOCK_TREND"], "ka10078")
        self.assertEqual(codes["STOCK_INFO_DETAIL"], "ka10100")
        self.assertEqual(codes["SECTOR_CODE_LIST"], "ka10101")
        self.assertEqual(codes["MEMBER_LIST"], "ka10102")
        self.assertEqual(codes["CONDITION_REALTIME"], "ka10173")
        self.assertEqual(codes["CONDITION_REALTIME_STOP"], "ka10174")


class TestRealizedPnlAdapters(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    @patch("requests.Session.post")
    def test_get_realized_pnl_uses_ka10074(self, mock_post):
        mock_post.return_value = _json_ok({
            "return_code": 0,
            "dt_rlzt_pl": [
                {
                    "dt": "20260924",
                    "buy_amt": "1,000,000",
                    "sell_amt": "1,100,000",
                    "tdy_sell_pl": "100,000",
                    "tdy_trde_cmsn": "1,000",
                    "tdy_trde_tax": "2,000",
                }
            ],
        })

        rows = self.client.get_realized_pnl("12345678", "20260901", "20260924")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "20260924")
        self.assertEqual(rows[0]["buy_amount"], 1000000)
        self.assertEqual(rows[0]["sell_amount"], 1100000)
        self.assertEqual(rows[0]["realized_pnl"], 100000)
        self.assertEqual(rows[0]["commission"], 1000)
        self.assertEqual(rows[0]["tax"], 2000)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/acnt"))
        self.assertEqual(headers.get("api-id"), "ka10074")
        self.assertEqual(body["strt_dt"], "20260901")
        self.assertEqual(body["end_dt"], "20260924")

    @patch("requests.Session.post")
    def test_get_realized_pnl_failure_returns_empty(self, mock_post):
        mock_post.return_value = _json_ok({"return_code": -1, "return_msg": "err"})
        self.assertEqual(self.client.get_realized_pnl("12345678"), [])

    @patch("requests.Session.post")
    def test_get_realized_pnl_by_stock_uses_ka10072(self, mock_post):
        mock_post.return_value = _json_ok({
            "return_code": 0,
            "dt_stk_dly_rlzt_pl": [
                {
                    "stk_cd": "005930",
                    "stk_nm": "삼성전자",
                    "cntr_qty": "10",
                    "buy_uv": "70,000",
                    "cntr_pric": "69,000",
                    "tdy_sell_pl": "-10,000",
                    "pl_rt": "-1.43",
                    "tdy_trde_cmsn": "500",
                    "tdy_trde_tax": "300",
                }
            ],
        })

        rows = self.client.get_realized_pnl_by_stock("12345678", "005930", "20260924")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "005930")
        self.assertEqual(rows[0]["name"], "삼성전자")
        self.assertEqual(rows[0]["exec_quantity"], 10)
        self.assertEqual(rows[0]["buy_price"], 70000)
        self.assertEqual(rows[0]["realized_pnl"], -10000)
        self.assertAlmostEqual(rows[0]["profit_rate"], -1.43)
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertEqual(headers.get("api-id"), "ka10072")
        self.assertEqual(body["stk_cd"], "005930")
        self.assertEqual(body["strt_dt"], "20260924")

    @patch("requests.Session.post")
    def test_get_realized_pnl_by_stock_period_uses_ka10073(self, mock_post):
        mock_post.return_value = _json_ok({"return_code": 0, "output": []})

        rows = self.client.get_realized_pnl_by_stock_period("12345678", "005930", "20260901", "20260924")

        self.assertEqual(rows, [])
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertEqual(headers.get("api-id"), "ka10073")
        self.assertEqual(body["stk_cd"], "005930")
        self.assertEqual(body["strt_dt"], "20260901")
        self.assertEqual(body["end_dt"], "20260924")


class TestBrokerStockTrend(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    @patch("requests.Session.post")
    def test_get_broker_stock_trend_uses_ka10078(self, mock_post):
        mock_post.return_value = _json_ok({
            "return_code": 0,
            "sec_stk_trde_trend": [
                {
                    "dt": "20260924",
                    "cur_prc": "70,000",
                    "pred_pre": "-500",
                    "flu_rt": "-0.71",
                    "acc_trde_qty": "123456",
                    "netprps_qty": "1000",
                    "buy_qty": "5000",
                    "sell_qty": "4000",
                },
                {
                    "dt": "20260923",
                    "cur_prc": "70500",
                    "buy_qty": "3000",
                    "sell_qty": "1000",
                },
            ],
        })

        rows = self.client.get_broker_stock_trend(
            "005930", member_code="039", start_date="20260923", end_date="20260924")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], "20260924")
        self.assertEqual(rows[0]["current_price"], 70000)
        self.assertEqual(rows[0]["net_buy_qty"], 1000)
        # net 누락 시 buy-sell 폴백
        self.assertEqual(rows[1]["net_buy_qty"], 2000)
        url = mock_post.call_args[0][0]
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertTrue(url.endswith("/api/dostk/mrkcond"))
        self.assertEqual(headers.get("api-id"), "ka10078")
        self.assertEqual(body["stk_cd"], "005930")
        self.assertEqual(body["mbrm_cd"], "039")

    @patch("requests.Session.post")
    def test_get_broker_stock_trend_empty_code(self, mock_post):
        self.assertEqual(self.client.get_broker_stock_trend(""), [])
        mock_post.assert_not_called()


class TestStockInfoAdapters(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    @patch("requests.Session.post")
    def test_get_stock_info_detail_uses_ka10100(self, mock_post):
        mock_post.return_value = _json_ok({
            "return_code": 0,
            "code": "005930",
            "name": "삼성전자",
            "listCount": "5,964,978,686",
            "auditInfo": "정상",
            "regDay": "19750611",
            "lastPrice": "70,000",
            "state": "정상",
            "marketCode": "KRX",
            "marketName": "유가증권",
            "upName": "전기전자",
            "companyClassName": "대형주",
            "orderWarning": "",
            "nxtEnable": "Y",
        })

        info = self.client.get_stock_info_detail("005930")

        self.assertEqual(info["code"], "005930")
        self.assertEqual(info["name"], "삼성전자")
        self.assertEqual(info["listed_shares"], 5964978686)
        self.assertEqual(info["prev_close"], 70000)
        self.assertEqual(info["market_name"], "유가증권")
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertEqual(headers.get("api-id"), "ka10100")
        self.assertEqual(body, {"stk_cd": "005930"})

    @patch("requests.Session.post")
    def test_get_stock_info_detail_empty_code_no_request(self, mock_post):
        self.assertEqual(self.client.get_stock_info_detail(""), {})
        mock_post.assert_not_called()

    @patch("requests.Session.post")
    def test_get_sector_code_list_uses_ka10101(self, mock_post):
        mock_post.return_value = _json_ok({
            "return_code": 0,
            "list": [
                {"marketCode": "KRX", "code": "001", "name": "종합", "group": "지수"},
            ],
        })

        rows = self.client.get_sector_code_list("0")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "001")
        self.assertEqual(rows[0]["name"], "종합")
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertEqual(headers.get("api-id"), "ka10101")
        self.assertEqual(body, {"mrkt_tp": "0"})

    @patch("requests.Session.post")
    def test_get_member_list_uses_ka10102(self, mock_post):
        mock_post.return_value = _json_ok({
            "return_code": 0,
            "list": [
                {"code": "039", "name": "키움증권", "gb": "국내"},
            ],
        })

        rows = self.client.get_member_list()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "039")
        self.assertEqual(rows[0]["name"], "키움증권")
        headers = mock_post.call_args[1]["headers"]
        body = mock_post.call_args[1]["json"]
        self.assertEqual(headers.get("api-id"), "ka10102")
        self.assertEqual(body, {})


class TestConditionRealtimeRest(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    def test_request_condition_realtime_uses_search_type_1(self):
        fake_ws = MagicMock()
        fake_ws.request_once.return_value = {
            "trnm": "CNSRREQ",
            "data": [{"9001": "005930", "302": "삼성전자", "10": "70000", "12": "1.5", "13": "1000"}],
        }
        self.client.ws_client = fake_ws

        rows = self.client.request_condition_realtime(4)

        payload = fake_ws.request_once.call_args[0][0]
        self.assertEqual(payload["trnm"], "CNSRREQ")
        self.assertEqual(payload["seq"], "4")
        self.assertEqual(payload["search_type"], "1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "005930")

    def test_stop_condition_realtime_uses_cnsrclr(self):
        fake_ws = MagicMock()
        fake_ws.request_once.return_value = {"trnm": "CNSRCLR", "return_code": 0}
        self.client.ws_client = fake_ws

        self.assertTrue(self.client.stop_condition_realtime(4))
        payload = fake_ws.request_once.call_args[0][0]
        self.assertEqual(payload, {"trnm": "CNSRCLR", "seq": "4"})

    def test_condition_realtime_without_ws(self):
        self.client.ws_client = None
        with patch.object(KiwoomRESTClient, "_condition_ws", return_value=None):
            self.assertEqual(self.client.request_condition_realtime(1), [])
            self.assertFalse(self.client.stop_condition_realtime(1))


class TestMarketStatusWebSocket(unittest.TestCase):
    def test_real_type_has_market_status(self):
        self.assertEqual(KiwoomWebSocketClient.REAL_TYPE["MARKET_STATUS"], "0s")

    def test_subscribe_market_status_registers(self):
        ws = _make_ws()
        ws.subscribe_market_status(codes=["000"])

        self.assertIn("market_status_000", ws._subscriptions)
        payload = ws._build_reg_payload(["000"], ws.REAL_TYPE["MARKET_STATUS"], register=True)
        self.assertEqual(payload["trnm"], "REG")
        self.assertEqual(payload["data"], [{"item": ["000"], "type": ["0s"]}])

    def test_handle_market_status_caches_snapshot(self):
        ws = _make_ws()
        seen = []
        ws._on_market_status = seen.append

        asyncio.run(ws._handle_market_status({"trd_st": "1", "tm": "090000"}))

        snapshot = ws.get_market_status_snapshot()
        self.assertEqual(snapshot["trading_status"], "1")
        self.assertEqual(snapshot["source"], "websocket_0s")
        self.assertEqual(len(seen), 1)
        # 스냅샷은 복사본이다
        snapshot["trading_status"] = "MUTATED"
        self.assertEqual(ws.get_market_status_snapshot()["trading_status"], "1")

    def test_dispatch_real_type_0s(self):
        ws = _make_ws()
        asyncio.run(ws._dispatch_real_type("0s", {"market_status": "OPEN"}))
        self.assertEqual(ws.get_market_status_snapshot()["trading_status"], "OPEN")

    def test_handle_condition_realtime_push(self):
        ws = _make_ws()
        seen = []
        ws._condition_realtime["4"] = seen.append

        asyncio.run(ws._handle_message(json.dumps({
            "trnm": "CNSRREQ",
            "data": [{"seq": "4", "9001": "005930"}],
        })))

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["9001"], "005930")

    def test_subscribe_condition_realtime_offline_uses_request_once(self):
        ws = _make_ws()
        ws.request_once = MagicMock(return_value={"trnm": "CNSRREQ", "data": []})

        result = ws.subscribe_condition_realtime(7)

        payload = ws.request_once.call_args[0][0]
        self.assertEqual(payload["trnm"], "CNSRREQ")
        self.assertEqual(payload["seq"], "7")
        self.assertEqual(payload["search_type"], "1")
        self.assertEqual(result, {"trnm": "CNSRREQ", "data": []})

    def test_unsubscribe_condition_realtime_offline(self):
        ws = _make_ws()
        ws._condition_realtime["7"] = lambda record: None
        ws.request_once = MagicMock(return_value={"trnm": "CNSRCLR"})

        self.assertTrue(ws.unsubscribe_condition_realtime(7))
        payload = ws.request_once.call_args[0][0]
        self.assertEqual(payload, {"trnm": "CNSRCLR", "seq": "7"})
        self.assertNotIn("7", ws._condition_realtime)


class TestMarketStatusRestIntegration(unittest.TestCase):
    def test_get_market_status_empty_without_ws(self):
        client = _make_client()
        client.ws_client = None
        self.assertEqual(client.get_market_status(), {})

    def test_get_market_status_returns_ws_snapshot(self):
        client = _make_client()
        fake_ws = MagicMock()
        fake_ws.get_market_status_snapshot.return_value = {
            "trading_status": "1", "source": "websocket_0s"}
        client.ws_client = fake_ws
        self.assertEqual(client.get_market_status()["trading_status"], "1")

    def test_get_market_status_snapshot_error_falls_back(self):
        client = _make_client()
        fake_ws = MagicMock()
        fake_ws.get_market_status_snapshot.side_effect = RuntimeError("boom")
        client.ws_client = fake_ws
        self.assertEqual(client.get_market_status(), {})


class TestRestAdditiveParity(unittest.TestCase):
    def test_pre_existing_42_methods_intact(self):
        for name in PRE_EXISTING_REST_METHODS:
            self.assertTrue(
                hasattr(KiwoomRESTClient, name), f"missing pre-existing: {name}")

    def test_new_gap_methods_present(self):
        for name in NEW_REST_METHODS:
            self.assertTrue(
                hasattr(KiwoomRESTClient, name), f"missing new gap adapter: {name}")


if __name__ == "__main__":
    unittest.main()
