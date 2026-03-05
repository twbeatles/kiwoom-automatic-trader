import datetime
import unittest

from api.models import ExecutionData
from app.mixins.trading_session import TradingSessionMixin
from config import TradingConfig


class _Harness(TradingSessionMixin):
    def __init__(self):
        self.config = TradingConfig(use_vi_guard=True, vi_proxy_1m_pct=9.0, vi_proxy_spread_pct=9.0)
        self._recent_ticks_by_code = {}
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class TestVIStateMachine(unittest.TestCase):
    def test_vi_to_reopen_cooldown_transition(self):
        trader = _Harness()
        info = {
            "current": 10000,
            "ask_price": 10001,
            "bid_price": 9999,
            "market_state": "normal",
            "market_state_until": None,
        }
        code = "005930"

        trader._update_market_state_from_execution(
            code,
            info,
            ExecutionData(code=code, exec_price=10000, trading_status="VI"),
            datetime.datetime.now(),
        )
        self.assertEqual(info["market_state"], "vi")

        trader._update_market_state_from_execution(
            code,
            info,
            ExecutionData(code=code, exec_price=10000, trading_status="NORMAL"),
            datetime.datetime.now() + datetime.timedelta(seconds=1),
        )
        self.assertEqual(info["market_state"], "reopen_cooldown")
        self.assertIsNotNone(info.get("market_state_until"))


if __name__ == "__main__":
    unittest.main()
