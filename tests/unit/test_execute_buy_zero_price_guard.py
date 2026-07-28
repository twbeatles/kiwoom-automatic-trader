"""A1: _execute_buy 가격 0 가드 검증.

current_price 가 0일 때(인자 price=0 이고 universe current 도 0) 시장가 주문이
전송되지 않고 잔액 검증 우회도 일어나지 않아야 한다.
"""
import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from config import TradingConfig


class _DummySignal:
    def emit(self):
        return None


class _DummyThreadPool:
    def __init__(self):
        self.started = 0

    def start(self, _worker):
        self.started += 1


class _DummyREST:
    def __init__(self):
        self.calls = []

    def buy_market(self, *args):
        self.calls.append(("buy_market", args))
        return None

    def buy_limit(self, *args):
        self.calls.append(("buy_limit", args))
        return None


class _Harness(ExecutionEngineMixin):
    def __init__(self, current_price=0):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "watch",
                "held": 0,
                "current": current_price,
                "cooldown_until": None,
            }
        }
        self._pending_order_state = {}
        self._reserved_cash_by_code = {}
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self.rest_client = _DummyREST()
        self.current_account = "12345678"
        self.deposit = 50000
        self.virtual_deposit = self.deposit
        self.threadpool = _DummyThreadPool()
        self.sig_update_table = _DummySignal()
        self.config = TradingConfig(execution_mode="live")
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))

    def _clear_pending_order(self, code):
        self._pending_order_state.pop(code, None)

    def _set_pending_order(self, *_args, **_kwargs):
        return None

    def _sync_position_from_account(self, *_args, **_kwargs):
        return None


class TestExecuteBuyZeroPriceGuard(unittest.TestCase):
    def test_price_zero_and_current_zero_blocks_order(self):
        trader = _Harness(current_price=0)

        trader._execute_buy("005930", quantity=1, price=0)

        info = trader.universe["005930"]
        # 주문이 전송되지 않는다.
        self.assertEqual(trader.rest_client.calls, [])
        self.assertEqual(trader.threadpool.started, 0)
        # 잔액 검증 우회 없이 예약금도 잡히지 않는다.
        self.assertEqual(trader._reserved_cash_by_code, {})
        self.assertEqual(trader.virtual_deposit, trader.deposit)
        # 상태가 buying 으로 바뀌지 않는다.
        self.assertEqual(info["status"], "watch")
        self.assertTrue(any("price unavailable" in m for m in trader.logs))

    def test_price_zero_falls_back_to_current_when_available(self):
        # price=0 이더라도 universe current 가 있으면 정상 경로로 진입한다.
        trader = _Harness(current_price=10000)

        trader._execute_buy("005930", quantity=1, price=0)

        # live 모드이므로 Worker 가 시작된다(주문 전송 경로 진입).
        self.assertEqual(trader.threadpool.started, 1)
        # 가드 로그가 남지 않는다.
        self.assertFalse(any("price unavailable" in m for m in trader.logs))


if __name__ == "__main__":
    unittest.main()
