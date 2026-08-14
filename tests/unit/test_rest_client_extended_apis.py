"""키움 REST API 확장 메서드 (예수금 상세, 당일 체결, 틱 차트, 지수, VI) 단위 테스트."""
import unittest
from unittest.mock import MagicMock, patch

from api.auth import KiwoomAuth
from api.models import (
    DepositDetail, ExecutedOrder, TickCandle, SectorQuote, VIEvent
)
from api.rest_client import KiwoomRESTClient
from api.websocket_client import KiwoomWebSocketClient


class TestRestClientExtendedAPIs(unittest.TestCase):
    def setUp(self):
        self.auth = MagicMock(spec=KiwoomAuth)
        self.auth.base_url = "https://mockapi.kiwoom.com"
        self.auth.get_auth_header.return_value = {"Authorization": "bearer TEST_TOKEN"}
        self.auth.session_namespace = "kiwoom_mock"
        self.client = KiwoomRESTClient(self.auth)

    @patch("requests.Session.post")
    def test_get_deposit_detail_parses_fields(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "return_code": 0,
            "output": {
                "deposit": "10,000,000",
                "d1_deposit": "9,500,000",
                "d2_deposit": "9,000,000",
                "draw_psbl_amt": "8,500,000",
                "ord_psbl_amt": "9,000,000",
                "rcvbl_amt": "0",
                "subst_amt": "1,000,000",
                "tot_eval_amt": "5,000,000",
                "tot_asst_amt": "15,000,000",
            },
        }
        mock_post.return_value = mock_resp

        detail = self.client.get_deposit_detail("12345678")

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.account_no, "12345678")
        self.assertEqual(detail.deposit, 10000000)
        self.assertEqual(detail.d1_deposit, 9500000)
        self.assertEqual(detail.d2_deposit, 9000000)
        self.assertEqual(detail.withdrawable_amount, 8500000)
        self.assertEqual(detail.order_available_amount, 9000000)
        self.assertEqual(detail.stock_eval_amount, 5000000)
        self.assertEqual(detail.total_assets, 15000000)

        # 헤더와 TR 코드 검증
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "ka30002")

    @patch("requests.Session.post")
    def test_get_executed_orders_parses_list(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "return_code": 0,
            "output": [
                {
                    "exec_no": "E1001",
                    "ord_no": "O2001",
                    "stk_cd": "005930",
                    "stk_nm": "삼성전자",
                    "ord_tp": "1",
                    "prc_tp": "00",
                    "ord_qty": "10",
                    "exec_qty": "10",
                    "exec_prc": "70,000",
                    "exec_amt": "700,000",
                    "exec_tm": "091530",
                    "fee": "105",
                    "tax": "0",
                },
                {
                    "exec_no": "E1002",
                    "ord_no": "O2002",
                    "stk_cd": "000660",
                    "stk_nm": "SK하이닉스",
                    "ord_tp": "2",
                    "prc_tp": "03",
                    "ord_qty": "5",
                    "exec_qty": "5",
                    "exec_prc": "120,000",
                    "exec_amt": "600,000",
                    "exec_tm": "102000",
                    "fee": "90",
                    "tax": "1200",
                }
            ]
        }
        mock_post.return_value = mock_resp

        executed = self.client.get_executed_orders("12345678", "20260814")

        self.assertEqual(len(executed), 2)
        e1 = executed[0]
        self.assertEqual(e1.exec_no, "E1001")
        self.assertEqual(e1.order_no, "O2001")
        self.assertEqual(e1.code, "005930")
        self.assertEqual(e1.name, "삼성전자")
        self.assertEqual(e1.side, "buy")
        self.assertEqual(e1.exec_quantity, 10)
        self.assertEqual(e1.exec_price, 70000)
        self.assertEqual(e1.fee, 105)

        e2 = executed[1]
        self.assertEqual(e2.side, "sell")
        self.assertEqual(e2.exec_price, 120000)
        self.assertEqual(e2.tax, 1200)

        # TR 코드 검증
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "ka10076")

    @patch("requests.Session.post")
    def test_get_tick_chart_parses_candles(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "return_code": 0,
            "output": [
                {
                    "stk_tm": "093000",
                    "cur_prc": "70,500",
                    "vol": "150",
                    "chg_amt": "+500",
                    "chg_rt": "+0.71",
                    "cntr_tp": "+1",
                    "acc_vol": "500000",
                }
            ]
        }
        mock_post.return_value = mock_resp

        ticks = self.client.get_tick_chart("005930", count=10)

        self.assertEqual(len(ticks), 1)
        t = ticks[0]
        self.assertEqual(t.time, "093000")
        self.assertEqual(t.price, 70500)
        self.assertEqual(t.volume, 150)
        self.assertEqual(t.change, 500)
        self.assertEqual(t.change_rate, 0.71)
        self.assertEqual(t.side, "+1")
        self.assertEqual(t.cum_volume, 500000)

        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "ka10007")

    @patch("requests.Session.post")
    def test_get_vi_status_parses_events(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "return_code": 0,
            "output": [
                {
                    "stk_cd": "005930",
                    "stk_nm": "삼성전자",
                    "vi_tp": "정적",
                    "vi_st": "발동",
                    "trg_tm": "090512",
                    "rls_tm": "090712",
                    "trg_prc": "75,000",
                    "base_prc": "70,000",
                    "dev_rt": "7.14",
                }
            ]
        }
        mock_post.return_value = mock_resp

        events = self.client.get_vi_status("0")

        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.code, "005930")
        self.assertEqual(ev.name, "삼성전자")
        self.assertEqual(ev.vi_type, "정적")
        self.assertEqual(ev.vi_status, "발동")
        self.assertEqual(ev.trigger_time, "090512")
        self.assertEqual(ev.trigger_price, 75000)
        self.assertEqual(ev.base_price, 70000)
        self.assertEqual(ev.deviance_rate, 7.14)

        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers.get("api-id"), "ka20009")

    @patch("api.rest_client.KiwoomRESTClient.get_index_quote")
    def test_get_market_indexes_returns_major_quotes(self, mock_quote):
        def side_effect(idx_cd):
            if idx_cd == "001":
                return {"idx_nm": "코스피", "cur_idx": "2,700.50", "chg_rt": "0.5"}
            elif idx_cd == "101":
                return {"idx_nm": "코스닥", "cur_idx": "850.20", "chg_rt": "-0.2"}
            elif idx_cd == "201":
                return {"idx_nm": "코스피200", "cur_idx": "360.10", "chg_rt": "0.4"}
            return {}

        mock_quote.side_effect = side_effect

        indexes = self.client.get_market_indexes()
        self.assertEqual(len(indexes), 3)
        self.assertEqual(indexes[0].name, "코스피")
        self.assertEqual(indexes[0].current_price, 2700.5)
        self.assertEqual(indexes[1].name, "코스닥")
        self.assertEqual(indexes[1].current_price, 850.2)
        self.assertEqual(indexes[2].name, "코스피200")


class TestWebSocketExtendedSubscriptions(unittest.TestCase):
    def setUp(self):
        self.auth = MagicMock(spec=KiwoomAuth)
        self.auth.ws_url = "wss://mockapi.kiwoom.com/ws"
        self.ws_client = KiwoomWebSocketClient(self.auth)

    def test_subscribe_vi_events_registers_callback(self):
        cb = MagicMock()
        self.ws_client.subscribe_vi_events(["005930", "000660"], cb)

        self.assertIn("vi_005930", self.ws_client._subscriptions)
        self.assertIn("vi_000660", self.ws_client._subscriptions)
        self.assertEqual(self.ws_client._on_vi, cb)

    def test_subscribe_orderbook_delegates_to_hoga(self):
        cb = MagicMock()
        self.ws_client.subscribe_orderbook(["005930"], cb)

        self.assertIn("hoga_005930", self.ws_client._subscriptions)
        self.assertEqual(self.ws_client._on_hoga, cb)


if __name__ == "__main__":
    unittest.main()
