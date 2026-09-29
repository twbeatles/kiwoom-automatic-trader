"""Phase-2: token cache secret binding + reject classification + stale cancel."""
import datetime
import time
import unittest
from typing import Any
from unittest.mock import patch

from api.auth import KiwoomAuth
from api.models import OrderResult
from app.mixins.order_sync import OrderSyncMixin


class _DummySignal:
    def emit(self):
        return None


class _DummyLogger:
    def warning(self, _msg):
        return None

    def error(self, _msg):
        return None


class _SyncThreadpool:
    def start(self, worker):
        worker.run()


class TestSecretBinding(unittest.TestCase):
    def test_rotated_secret_invalidates_cache(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            first = KiwoomAuth(app_key="K", secret_key="S1", is_mock=True, cache_dir=tmp)
            first._access_token = "T1"
            first._expires_at = time.time() + 3600
            first._save_token_cache()
            second = KiwoomAuth(app_key="K", secret_key="S2", is_mock=True, cache_dir=tmp)
            self.assertIsNone(second._access_token)
            third = KiwoomAuth(app_key="K", secret_key="S1", is_mock=True, cache_dir=tmp)
            self.assertEqual(third._access_token, "T1")


class _Harness(OrderSyncMixin):
    def __init__(self):
        self.universe = {
            "005930": {"name": "SAMSUNG", "status": "buy_submitted", "held": 0},
        }
        self._pending_order_state = {}
        self._manual_pending_state = {}
        self._sync_failed_codes = set()
        self._dirty_codes = set()
        self._log_cooldown_map = {}
        self.is_running = True
        self.current_account = "00000000"
        self.rest_client: Any = None
        self.threadpool: Any = None
        self.logs = []
        self.logger = _DummyLogger()
        self.sig_update_table = _DummySignal()

    def log(self, msg):
        self.logs.append(str(msg))

    def _diag_touch(self, _code, **_fields):
        return None

    def _diag_clear_pending(self, _code):
        return None


class TestRejectClassification(unittest.TestCase):
    def test_transient_final_unknown(self):
        cases = {
            "network timeout, try again": "transient",
            "일시적인 오류입니다": "transient",
            "주문가능금액이 부족합니다": "final",
            "잔고 부족": "final",
            "HTTP 503": "transient",
            "알 수 없는 거부": "unknown",
            "": "unknown",
            None: "unknown",
        }
        for message, expected in cases.items():
            self.assertEqual(
                OrderSyncMixin._classify_order_reject(message), expected, message
            )

    def test_note_records_universe_fields(self):
        trader = _Harness()
        klass = trader._note_order_reject("005930", "잔고 부족으로 거부")
        self.assertEqual(klass, "final")
        self.assertEqual(trader.universe["005930"]["last_reject_class"], "final")
        self.assertIsInstance(
            trader.universe["005930"]["last_reject_at"], datetime.datetime
        )


class _CancelClient:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def cancel_order(self, account_no, order_no, code, quantity):
        self.calls.append((account_no, order_no, code, quantity))
        return OrderResult(success=self.ok, order_no=order_no, code=code, message="취소 성공")


class TestStaleLimitCancel(unittest.TestCase):
    def _trader(self, ok=True):

        trader = _Harness()
        trader.rest_client = _CancelClient(ok=ok)
        trader.threadpool = _SyncThreadpool()
        return trader

    def test_disabled_by_default(self):
        trader = self._trader()
        trader._set_pending_order(
            "005930", "buy", "BUY", expected_price=1000, submitted_qty=5, order_no="O1"
        )
        trader._pending_order_state["005930"]["updated_at"] = (
            datetime.datetime.now() - datetime.timedelta(hours=2)
        )
        self.assertEqual(trader._sweep_stale_limit_orders(), 0)
        self.assertEqual(trader.rest_client.calls, [])

    def test_aged_pending_cancel_requested(self):
        import config as config_mod

        trader = self._trader()
        trader._set_pending_order(
            "005930", "buy", "BUY", expected_price=1000, submitted_qty=5, order_no="O1"
        )
        trader._pending_order_state["005930"]["updated_at"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=3600)
        )
        with patch.object(
            config_mod.Config, "STALE_LIMIT_ORDER_CANCEL_SEC", 60
        ):
            self.assertEqual(trader._sweep_stale_limit_orders(), 1)
        self.assertEqual(
            trader.rest_client.calls, [("00000000", "O1", "005930", 5)]
        )
        self.assertTrue(any("[자동취소]" in m for m in trader.logs))
        # 같은 창에서는 중복 요청하지 않는다.
        with patch.object(
            config_mod.Config, "STALE_LIMIT_ORDER_CANCEL_SEC", 60
        ):
            self.assertEqual(trader._sweep_stale_limit_orders(), 0)
        self.assertEqual(len(trader.rest_client.calls), 1)

    def test_fresh_pending_untouched(self):
        import config as config_mod

        trader = self._trader()
        trader._set_pending_order(
            "005930", "buy", "BUY", expected_price=1000, submitted_qty=5, order_no="O1"
        )
        with patch.object(
            config_mod.Config, "STALE_LIMIT_ORDER_CANCEL_SEC", 60
        ):
            self.assertEqual(trader._sweep_stale_limit_orders(), 0)
        self.assertEqual(trader.rest_client.calls, [])


if __name__ == "__main__":
    unittest.main()
