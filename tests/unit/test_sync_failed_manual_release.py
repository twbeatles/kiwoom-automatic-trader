import unittest

from app.main_window import KiwoomProTrader


class _Harness:
    _on_diagnostic_release_sync_failed_selected = KiwoomProTrader._on_diagnostic_release_sync_failed_selected

    def __init__(self):
        self.universe = {
            "005930": {"name": "SAMSUNG", "status": "sync_failed", "sync_failed_reason": "sync timeout"}
        }
        self._sync_failed_codes = {"005930"}
        self.sync_calls = []
        self.logs = []

    def _selected_diagnostic_code(self):
        return "005930"

    def _sync_position_from_account(self, code):
        self.sync_calls.append(code)

    def _render_selected_diagnostic_detail(self):
        return None

    def log(self, msg):
        self.logs.append(str(msg))


class TestSyncFailedManualRelease(unittest.TestCase):
    def test_release_button_requests_resync_without_immediate_state_flip(self):
        trader = _Harness()

        trader._on_diagnostic_release_sync_failed_selected()

        self.assertEqual(trader.sync_calls, ["005930"])
        self.assertEqual(trader.universe["005930"]["status"], "sync_failed")
        self.assertIn("005930", trader._sync_failed_codes)


if __name__ == "__main__":
    unittest.main()
