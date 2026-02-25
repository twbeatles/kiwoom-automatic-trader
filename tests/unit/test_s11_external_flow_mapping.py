import datetime
import unittest

from app.mixins.trading_session import TradingSessionMixin


class _DummySignal:
    def emit(self):
        return None


class _Harness(TradingSessionMixin):
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "external_status": "idle",
                "external_error": "",
                "external_updated_at": None,
                "investor_net": 0,
                "program_net": 0,
            }
        }
        self._external_refresh_inflight = {"005930"}
        self._external_last_fetch_ts = {}
        self._dirty_codes = set()
        self.sig_update_table = _DummySignal()
        self._log_cooldown_map = {}

    def log(self, _msg):
        return None


class TestS11ExternalFlowMapping(unittest.TestCase):
    def test_maps_raw_investor_program_fields_to_canonical(self):
        trader = _Harness()
        payload = {
            "005930": {
                "investor": {
                    "individual_net": 100,
                    "foreign_net": -20,
                    "institution_net": 30,
                },
                "program": {
                    "net": 55,
                },
                "error": "",
            }
        }

        trader._on_external_flow_result(["005930"], payload)

        info = trader.universe["005930"]
        self.assertEqual(info["investor_net"], 110)
        self.assertEqual(info["program_net"], 55)
        self.assertEqual(info["external_status"], "fresh")
        self.assertEqual(info["external_error"], "")
        self.assertIsInstance(info["external_updated_at"], datetime.datetime)
        self.assertNotIn("005930", trader._external_refresh_inflight)


if __name__ == "__main__":
    unittest.main()
