import unittest
from collections import deque

from api.models import ExecutionData
from app.mixins.execution_engine import ExecutionEngineMixin


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.is_running = True
        self.universe = {
            "005930": {
                "name": "AAA",
                "status": "sync_failed",
                "held": 0,
                "target": 0,
                "buy_price": 0,
                "price_history": [],
                "minute_prices": [],
                "market_type": "KOSPI",
            },
            "000660": {
                "name": "BBB",
                "status": "sync_failed",
                "held": 0,
                "target": 0,
                "buy_price": 0,
                "price_history": [],
                "minute_prices": [],
                "market_type": "KOSPI",
            },
        }
        self._pending_order_state = {}
        self._sync_failed_codes = {"005930", "000660"}
        self._dirty_codes = set()
        self._index_ticks_by_market = {"KOSPI": deque(maxlen=1800)}
        self._shock_fallback_rep_by_market = {}

    def _update_market_state_from_execution(self, *_args, **_kwargs):
        return None

    def _market_key_from_info(self, _info):
        return "KOSPI"

    def _get_index_series(self, market_key):
        return self._index_ticks_by_market[market_key]

    def _update_shock_mode(self, *_args, **_kwargs):
        return None


class TestShockFallbackRepresentative(unittest.TestCase):
    def test_fallback_uses_single_representative_symbol_per_market(self):
        trader = _Harness()
        trader._on_execution(ExecutionData(code="005930", name="AAA", exec_price=1000))
        trader._on_execution(ExecutionData(code="000660", name="BBB", exec_price=2000))

        series = trader._index_ticks_by_market["KOSPI"]
        self.assertEqual(len(series), 1)
        self.assertEqual(trader._shock_fallback_rep_by_market.get("KOSPI"), "005930")


if __name__ == "__main__":
    unittest.main()
