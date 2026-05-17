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
    def __init__(self, response):
        super().__init__(cast(KiwoomAuth, _Auth()))
        self.response = response

    def _request(self, *_args, **_kwargs):
        return self.response


class TestRESTClientSafeParsing(unittest.TestCase):
    def test_quote_parses_commas_empty_and_signed_fields(self):
        client = _Client(
            {
                "return_code": 0,
                "output": {
                    "stk_nm": "Samsung",
                    "cur_prc": "-70,000",
                    "chg_amt": "",
                    "chg_rt": "1.25%",
                    "open_prc": "69,000",
                    "high_prc": "",
                    "low_prc": "-68,500",
                    "acc_vol": "1,234,567",
                    "yes_prc": "69,500",
                },
            }
        )

        quote = client.get_stock_quote("005930")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.current_price, 70000)
        self.assertEqual(quote.change, 0)
        self.assertEqual(quote.change_rate, 1.25)
        self.assertEqual(quote.low_price, 68500)
        self.assertEqual(quote.volume, 1234567)

    def test_positions_tolerate_missing_numeric_values(self):
        client = _Client(
            {
                "return_code": 0,
                "stocks": [
                    {
                        "stk_cd": "005930",
                        "stk_nm": "Samsung",
                        "hold_qty": "1,000",
                        "sell_psbl_qty": "",
                        "buy_prc": "70,000",
                        "cur_prc": "-71,000",
                        "eval_pl_rt": "--",
                    }
                ],
            }
        )

        positions = client.get_positions("ACC")

        self.assertIsNotNone(positions)
        assert positions is not None
        self.assertEqual(positions[0].quantity, 1000)
        self.assertEqual(positions[0].available_qty, 0)
        self.assertEqual(positions[0].current_price, 71000)
        self.assertEqual(positions[0].profit_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
