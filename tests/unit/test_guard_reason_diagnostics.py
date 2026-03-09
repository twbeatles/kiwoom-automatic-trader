import datetime
import unittest
from unittest.mock import patch

from app.main_window import KiwoomProTrader


class _DummyItem:
    def __init__(self, text=""):
        self._text = str(text)

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)

    def setTextAlignment(self, *_args, **_kwargs):
        return None

    def setForeground(self, _color):
        return None


class _DummyTable:
    def __init__(self):
        self._rows = 0
        self._items = {}

    def rowCount(self):
        return self._rows

    def setRowCount(self, rows):
        self._rows = int(rows)

    def setUpdatesEnabled(self, _enabled):
        return None

    def item(self, row, col):
        return self._items.get((row, col))

    def setItem(self, row, col, item):
        self._items[(row, col)] = item


class _Harness:
    _diag_fmt_dt = staticmethod(KiwoomProTrader._diag_fmt_dt)
    _diag_age_seconds = staticmethod(KiwoomProTrader._diag_age_seconds)
    _refresh_diagnostics = KiwoomProTrader._refresh_diagnostics

    def __init__(self):
        now = datetime.datetime.now() - datetime.timedelta(seconds=2)
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "watch",
                "external_status": "fresh",
                "external_updated_at": now,
                "external_error": "",
                "market_state": "normal",
                "last_guard_reason": "shock_guard",
            }
        }
        self._diagnostics_by_code = {"005930": {"last_update": datetime.datetime.now()}}
        self._pending_order_state = {}
        self._diagnostics_dirty_codes = {"005930"}
        self._guard_reason_by_code = {}
        self._global_risk_mode = "shock"
        self._order_health_mode = "normal"
        self.diagnostic_table = _DummyTable()


class TestGuardReasonDiagnostics(unittest.TestCase):
    def test_guard_reason_column_is_populated(self):
        trader = _Harness()
        with patch("app.main_window.QTableWidgetItem", _DummyItem):
            trader._refresh_diagnostics()

        market_state_item = trader.diagnostic_table.item(0, 12)
        guard_reason_item = trader.diagnostic_table.item(0, 13)
        risk_mode_item = trader.diagnostic_table.item(0, 14)
        self.assertIsNotNone(market_state_item)
        self.assertIsNotNone(guard_reason_item)
        self.assertIsNotNone(risk_mode_item)
        assert market_state_item is not None
        assert guard_reason_item is not None
        assert risk_mode_item is not None
        self.assertEqual(market_state_item.text(), "normal")
        self.assertEqual(guard_reason_item.text(), "shock_guard")
        self.assertEqual(risk_mode_item.text(), "shock")


if __name__ == "__main__":
    unittest.main()
