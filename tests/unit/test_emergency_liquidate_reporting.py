"""ISSUE-002: emergency liquidation reporting.

- 완료 로그가 결과 집계 이후에만 나간다(선행 "청산 완료" 없음).
- 비동기 cleanup 경로 사용 시 동기 cleanup을 호출하지 않는다.
- live 모드에서 실거래 guard 미통과 시 매도를 제출하지 않는다.
"""
import unittest
from unittest.mock import patch

from app.features.execution.sell_flow import ExecutionSellFlowMixin
from app.features.trading_session import table as table_mod
from app.features.trading_session.table import TradingSessionTableMixin


class _AggHarness(ExecutionSellFlowMixin):
    def __init__(self):
        self._liquidation_batch = {}
        self.logs = []
        self.telegram = None

    def log(self, msg):
        self.logs.append(str(msg))


class _TableHarness(TradingSessionTableMixin):
    def __init__(self):
        self.is_connected = True
        self.logs = []
        self.sound = None
        self.telegram = None
        self._liquidation_batch = {}
        self._emergency_sells_token = None
        self.targets = []
        self.execute_calls = []
        self.cleanup_sync_calls = []
        self.cleanup_async_calls = []
        self.async_result = True
        self.async_available = True
        self.live_guard_required = False
        self.live_guard_pass = True

    def log(self, msg):
        self.logs.append(str(msg))

    def _collect_liquidation_targets(self):
        return list(self.targets)

    def _set_trading_stopped_state(self):
        self.is_running = False

    def _cleanup_active_orders(self, reason):
        self.cleanup_sync_calls.append(reason)
        return {"unresolved_codes": []}

    def _cleanup_active_orders_async(self, reason, on_done=None):
        self.cleanup_async_calls.append(reason)
        if not self.async_available:
            return False
        if callable(on_done):
            on_done({"unresolved_codes": []})
        return self.async_result

    def _execute_sell(self, code, quantity, price, reason):
        self.execute_calls.append((code, quantity, price, reason))

    def _manual_order_live_guard_required(self):
        return self.live_guard_required

    def _confirm_live_trading_guard(self):
        return self.live_guard_pass


def _accept_dialog(*_args, **_kwargs):
    class _Reply:
        pass

    return table_mod.QMessageBox.StandardButton.Yes


class TestLiquidationAggregation(unittest.TestCase):
    def test_final_report_only_after_all_settled(self):
        trader = _AggHarness()
        trader._liquidation_batch = {
            "005930": {"name": "SAMSUNG", "qty": 10, "settled": False, "ok": False, "detail": ""},
            "000660": {"name": "HYNIX", "qty": 5, "settled": False, "ok": False, "detail": ""},
        }
        trader._note_liquidation_settlement("005930", True, "10주 제출")
        # 아직 전건 결착 전이므로 최종 보고가 없고 배치는 유지된다.
        self.assertFalse(any("긴급 청산 결과" in m for m in trader.logs))
        self.assertEqual(set(trader._liquidation_batch), {"005930", "000660"})
        trader._note_liquidation_settlement("000660", False, "거부")
        finals = [m for m in trader.logs if "긴급 청산 결과" in m]
        self.assertEqual(len(finals), 1)
        self.assertIn("1/2", finals[0])
        self.assertIn("HYNIX", finals[0])
        self.assertEqual(trader._liquidation_batch, {})

    def test_non_batch_codes_ignored(self):
        trader = _AggHarness()
        trader._liquidation_batch = {}
        trader._note_liquidation_settlement("005930", True, "10주 제출")
        self.assertEqual(trader.logs, [])


class TestEmergencyLiquidateRouting(unittest.TestCase):
    def test_async_cleanup_path_skips_sync(self):
        trader = _TableHarness()
        trader.targets = [("005930", {"name": "SAMSUNG", "held": 10, "current": 70000})]
        with patch.object(table_mod.QMessageBox, "warning", side_effect=_accept_dialog):
            trader._emergency_liquidate()
        self.assertEqual(trader.cleanup_async_calls, ["emergency_liquidate"])
        self.assertEqual(trader.cleanup_sync_calls, [])
        self.assertEqual(len(trader.execute_calls), 1)
        # 선행 "완료" 로그가 없고 요청 제출 로그가 남는다.
        self.assertFalse(any("청산 완료" in m for m in trader.logs))
        self.assertTrue(any("요청 1건 제출" in m for m in trader.logs))

    def test_sync_fallback_when_async_unavailable(self):
        trader = _TableHarness()
        trader.async_result = False
        trader.async_available = False
        trader.targets = [("005930", {"name": "SAMSUNG", "held": 10, "current": 70000})]
        with patch.object(table_mod.QMessageBox, "warning", side_effect=_accept_dialog):
            trader._emergency_liquidate()
        self.assertEqual(trader.cleanup_sync_calls, ["emergency_liquidate"])
        self.assertEqual(len(trader.execute_calls), 1)

    def test_live_guard_blocks_without_confirmation(self):
        trader = _TableHarness()
        trader.live_guard_required = True
        trader.live_guard_pass = False
        trader.targets = [("005930", {"name": "SAMSUNG", "held": 10, "current": 70000})]
        with patch.object(table_mod.QMessageBox, "warning", side_effect=_accept_dialog):
            trader._emergency_liquidate()
        self.assertEqual(trader.execute_calls, [])
        self.assertEqual(trader.cleanup_async_calls, [])


if __name__ == "__main__":
    unittest.main()
