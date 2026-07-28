"""C3: 미체결 주문 REST adapter 검증.

- supports_open_orders 가 True 를 반환한다.
- get_open_orders 가 ka400008 응답을 OpenOrder 리스트로 파싱한다.
- 파싱 실패/빈 응답 시 예외를 전가하지 않고 빈 리스트를 반환한다.
"""
import unittest
from typing import cast

from api.auth import KiwoomAuth
from api.rest_client import KiwoomRESTClient


class _Auth:
    base_url = "https://example.invalid"
    session_namespace = "test"

    def get_auth_header(self):
        return {"Authorization": "bearer token"}


class _Client(KiwoomRESTClient):
    def __init__(self, response=None, raise_exc=None):
        super().__init__(cast(KiwoomAuth, _Auth()))
        self.response = response
        self.raise_exc = raise_exc
        self.requested = []

    def _request(self, method, endpoint, data=None, params=None):
        self.requested.append((method, endpoint, data))
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


class TestOpenOrdersRestAdapter(unittest.TestCase):
    def test_supports_open_orders_is_true(self):
        client = _Client()
        self.assertTrue(client.supports_open_orders)

    def test_parses_open_orders_list(self):
        response = {
            "return_code": 0,
            "output": [
                {
                    "ord_no": "O111",
                    "stk_cd": "005930",
                    "ord_tp": "1",
                    "ord_qty": "10",
                    "unexec_qty": "7",
                    "ord_prc": "70,000",
                    "ord_st": "접수",
                },
                {
                    "ord_no": "O222",
                    "stk_cd": "000660",
                    "ord_tp": "2",
                    "ord_qty": "5",
                    "not_cncl_qty": "5",
                    "ord_prc": "120000",
                    "cnf_tp": "체결",
                },
            ],
        }
        client = _Client(response)
        orders = client.get_open_orders("12345678")

        self.assertEqual(len(orders), 2)
        o1 = orders[0]
        self.assertEqual(o1.order_no, "O111")
        self.assertEqual(o1.code, "005930")
        self.assertEqual(o1.side, "buy")
        self.assertEqual(o1.quantity, 10)
        self.assertEqual(o1.remaining_qty, 7)
        self.assertEqual(o1.price, 70000)
        self.assertEqual(o1.status, "접수")

        o2 = orders[1]
        self.assertEqual(o2.order_no, "O222")
        self.assertEqual(o2.side, "sell")
        self.assertEqual(o2.remaining_qty, 5)

        # 올바른 TR/엔드포인트 사용
        method, endpoint, data = client.requested[0]
        self.assertEqual(method, "POST")
        self.assertEqual(endpoint, "/api/dostk/ordunfilled")
        self.assertEqual(data["tr_cd"], "ka400008")
        self.assertEqual(data["acnt_no"], "12345678")

    def test_non_zero_return_code_returns_empty(self):
        client = _Client({"return_code": 1, "return_msg": "error"})
        self.assertEqual(client.get_open_orders("12345678"), [])

    def test_none_response_returns_empty(self):
        client = _Client(None)
        self.assertEqual(client.get_open_orders("12345678"), [])

    def test_request_exception_returns_empty(self):
        client = _Client(raise_exc=RuntimeError("network"))
        self.assertEqual(client.get_open_orders("12345678"), [])

    def test_single_dict_output_normalized_to_list(self):
        client = _Client(
            {
                "return_code": 0,
                "output": {  # 단건 dict
                    "ord_no": "O333",
                    "stk_cd": "035420",
                    "ord_tp": "1",
                    "ord_qty": "3",
                    "ord_prc": "50000",
                },
            }
        )
        orders = client.get_open_orders("12345678")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].code, "035420")

    def test_rows_missing_order_no_skipped(self):
        client = _Client(
            {
                "return_code": 0,
                "output": [
                    {"ord_no": "", "stk_cd": "005930", "ord_qty": "1"},  # 주문번호 없음
                    {"ord_no": "O444", "stk_cd": "", "ord_qty": "1"},  # 종목 없음
                    {"ord_no": "O555", "stk_cd": "005930", "ord_qty": "1", "ord_tp": "1"},
                ],
            }
        )
        orders = client.get_open_orders("12345678")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_no, "O555")


if __name__ == "__main__":
    unittest.main()
