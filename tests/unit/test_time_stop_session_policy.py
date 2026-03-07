import datetime
import unittest

from api.models import ExecutionData
from app.mixins.execution_engine import ExecutionEngineMixin
from config import TradingConfig


class _StrategyStub:
    def check_atr_stop_loss(self, _code):
        return False, 0

    def calculate_partial_take_profit(self, _code, _profit_rate):
        return None

    def evaluate_buy_conditions(self, _code, _now_ts):
        return False, {}, {}


class _SignalStub:
    def emit(self):
        return None


class _Harness(ExecutionEngineMixin):
    def __init__(self, time_stop_eligible: bool):
        self.is_running = True
        self.strategy = _StrategyStub()
        self.config = TradingConfig(use_time_stop=True, time_stop_min=1)
        self.universe = {
            "005930": {
                "name": "SAMSUNG",
                "status": "holding",
                "held": 3,
                "target": 0,
                "buy_price": 1000,
                "buy_time": datetime.datetime.now() - datetime.timedelta(minutes=10),
                "max_profit_rate": 0.0,
                "time_stop_eligible": bool(time_stop_eligible),
                "price_history": [],
                "minute_prices": [],
                "ask_price": 1000,
                "bid_price": 999,
            }
        }
        self._pending_order_state = {}
        self._sync_failed_codes = set()
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self.sig_update_table = _SignalStub()
        self.sell_calls = []

    def _execute_sell(self, code, quantity, price, reason):
        self.sell_calls.append((code, quantity, price, reason))


class TestTimeStopSessionPolicy(unittest.TestCase):
    def test_session_inbound_position_is_excluded_from_time_stop(self):
        trader = _Harness(time_stop_eligible=False)
        trader._on_execution(
            ExecutionData(code="005930", name="SAMSUNG", exec_price=1000, total_volume=1, ask_price=1000, bid_price=999)
        )
        self.assertEqual(trader.sell_calls, [])

    def test_session_new_position_applies_time_stop(self):
        trader = _Harness(time_stop_eligible=True)
        trader._on_execution(
            ExecutionData(code="005930", name="SAMSUNG", exec_price=1000, total_volume=1, ask_price=1000, bid_price=999)
        )
        self.assertEqual(len(trader.sell_calls), 1)
        self.assertIn("TIME_STOP", trader.sell_calls[0][3])


if __name__ == "__main__":
    unittest.main()
