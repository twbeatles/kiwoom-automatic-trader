"""Issue #3: WebSocket owns condition search; REST entry points stay compatible."""
import logging
import unittest
from unittest.mock import MagicMock

from api.rest_client import KiwoomRESTClient
from api.websocket_client import KiwoomWebSocketClient


class TestConditionSearchOwnership(unittest.TestCase):
    def setUp(self):
        # No socket/login: mock only the transport, exercise real domain methods.
        self.ws = KiwoomWebSocketClient.__new__(KiwoomWebSocketClient)
        self.ws.logger = logging.getLogger("test.conditions")
        self.ws.request_once = MagicMock()
        self.rest = KiwoomRESTClient.__new__(KiwoomRESTClient)
        self.rest.ws_client = self.ws

    def test_ws_condition_list_parses_dict_and_sequence_rows(self):
        self.ws.request_once.return_value = {
            "data": [{"seq": "1", "name": "급등주"}, ["2", "거래량"]],
        }
        self.assertEqual(self.ws.get_condition_list(), [
            {"index": 1, "name": "급등주"}, {"index": 2, "name": "거래량"},
        ])
        self.ws.request_once.assert_called_once_with({"trnm": "CNSRLST"})

    def test_ws_normal_search_payload_and_stock_normalization(self):
        self.ws.request_once.return_value = {"data": [{
            "9001": "A005930", "302": "삼성전자", "10": "-70,000",
            "12": "1.2%", "13": "1,000",
        }]}
        self.assertEqual(self.ws.search_by_condition(4, "unused"), [{
            "code": "005930", "name": "삼성전자", "current_price": 70000,
            "change_rate": 1.2, "volume": 1000,
        }])
        self.ws.request_once.assert_called_once_with({
            "trnm": "CNSRREQ", "seq": "4", "search_type": "0", "stex_tp": "K",
        })

    def test_ws_realtime_snapshot_uses_same_parser(self):
        self.ws.request_once.return_value = {"output": [
            ["a005930", "삼성전자", "-70,000", "", "", "-1.2", "1000"],
            {"code": "", "name": "invalid"},
        ]}
        rows = self.ws.request_condition_realtime(4)
        self.assertEqual(rows[0]["code"], "005930")
        self.assertEqual(rows[0]["current_price"], 70000)
        self.assertEqual(rows[0]["change_rate"], -1.2)
        self.assertEqual(len(rows), 1)
        self.ws.request_once.assert_called_once_with({
            "trnm": "CNSRREQ", "seq": "4", "search_type": "1", "stex_tp": "K",
        })

    def test_ws_stop_payload(self):
        self.ws.request_once.return_value = {"trnm": "CNSRCLR", "return_code": 0}
        self.assertTrue(self.ws.stop_condition_realtime(4))
        self.ws.request_once.assert_called_once_with({"trnm": "CNSRCLR", "seq": "4"})

    def test_ws_unavailable_response_preserves_empty_results(self):
        for response in (None, [], "invalid"):
            with self.subTest(response=response):
                self.ws.request_once.return_value = response
                self.assertEqual(self.ws.get_condition_list(), [])
                self.assertEqual(self.ws.search_by_condition(1), [])
                self.assertEqual(self.ws.request_condition_realtime(1), [])
                self.assertFalse(self.ws.stop_condition_realtime(1))

    def test_rest_facade_delegates_all_public_methods(self):
        cases = (
            ("get_condition_list", (), [{"index": 1, "name": "test"}]),
            ("search_by_condition", (1, "test"), [{"code": "005930"}]),
            ("request_condition_realtime", (1,), [{"code": "005930"}]),
            ("stop_condition_realtime", (1,), True),
        )
        for name, args, expected in cases:
            with self.subTest(name=name):
                delegate = MagicMock(return_value=expected)
                setattr(self.ws, name, delegate)
                self.assertEqual(getattr(self.rest, name)(*args), expected)
                delegate.assert_called_once_with(*args)
        self.ws.request_once.assert_not_called()

    def test_rest_facade_preserves_no_ws_behavior(self):
        self.rest._condition_ws = MagicMock(return_value=None)
        self.assertEqual(self.rest.get_condition_list(), [])
        self.assertEqual(self.rest.search_by_condition(1), [])
        self.assertEqual(self.rest.request_condition_realtime(1), [])
        self.assertFalse(self.rest.stop_condition_realtime(1))

    def test_rest_parser_entry_point_still_matches_ws(self):
        response = {"data": [{"9001": "A005930", "302": "삼성전자"}]}
        self.assertEqual(
            self.rest._parse_condition_stock_rows(response),
            self.ws._parse_condition_stock_rows(response),
        )


if __name__ == "__main__":
    unittest.main()
