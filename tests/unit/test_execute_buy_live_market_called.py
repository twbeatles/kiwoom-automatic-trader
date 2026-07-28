"""live 경로에서 정상 가격일 때 buy_market 이 1회 호출됨을 검증(단언 보강).

A1 가드와 함께, 가격이 정상(>0)일 때는 잔액 충분 시 live 모드 주문이 정상
전송되는 경로가 유지됨을 고정한다. 회귀로 인해 정상 주문 경로가 막히지 않도록 방어.
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

    def start(self, worker):
        self.started += 1
        # Worker 를 동기 실행하여 buy_fn 이 실제로 호출되게 한다.
        worker.run()


class _DummyResult:
    def __init__(self, success=True, order_no="A1", message=""):
        self.success = bool(success)
        self.order_no = str(order_no)
        self.message = str(message)


class _RESTSpy:
    def __init__(self):
        self.calls = []

    def buy_market(self, account, code, quantity):
        self.calls.append(("buy_market", account, code, quantity))
        return _DummyResult(True, "O1")


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "watch",
                "held": 0,
                "current": 10000,
                "cooldown_until": None,
            }
        }
        self._pending_order_state = {}
        self._reserved_cash_by_code = {}
        self._dirty_codes = set()
        self._holding_or_pending_count = 0
        self.rest_client = _RESTSpy()
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


class TestExecuteBuyLiveMarketCalled(unittest.TestCase):
    def test_live_buy_with_valid_price_calls_buy_market_once(self):
        trader = _Harness()

        trader._execute_buy("005930", quantity=2, price=10000)

        # Worker 가 시작되고 buy_market 이 정확히 1회 호출된다.
        self.assertEqual(trader.threadpool.started, 1)
        self.assertEqual(len(trader.rest_client.calls), 1)
        call = trader.rest_client.calls[0]
        self.assertEqual(call[0], "buy_market")
        self.assertEqual(call[1], "12345678")
        self.assertEqual(call[2], "005930")
        self.assertEqual(call[3], 2)
        # 예약금이 잡혔다(2 * 10000 = 20000).
        self.assertEqual(trader._reserved_cash_by_code.get("005930"), 20000)
        self.assertEqual(trader.virtual_deposit, 30000)  # 50000 - 20000
        # Worker 동기 실행 시 _on_buy_result 까지 수행되어 buy_submitted 로 전환된다.
        # (Worker 미실행 환경이면 buying, 동기 실행 환경이면 buy_submitted — 둘 다 정상 경로)
        self.assertIn(trader.universe["005930"]["status"], {"buying", "buy_submitted"})


if __name__ == "__main__":
    unittest.main()
