import datetime
import unittest
from pathlib import Path
from unittest.mock import patch

from app.main_window import KiwoomProTrader


class _DummyItem:
    def __init__(self, text=""):
        self._text = str(text)
        self.foreground = None

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)

    def setTextAlignment(self, *_args, **_kwargs):
        return None

    def setForeground(self, color):
        self.foreground = color


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
        now = datetime.datetime.now() - datetime.timedelta(seconds=12)
        self.universe = {
            "005930": {
                "name": "삼성전자",
                "status": "watch",
                "external_status": "fresh",
                "external_updated_at": now,
                "external_error": "",
            }
        }
        self._diagnostics_by_code = {"005930": {"last_update": datetime.datetime.now()}}
        self._pending_order_state = {}
        self._diagnostics_dirty_codes = {"005930"}
        self.diagnostic_table = _DummyTable()


class TestDiagnosticsExternalColumns(unittest.TestCase):
    def test_diagnostics_schema_contains_external_columns(self):
        cols = [
            "external status",
            "external updated",
            "external age(sec)",
        ]
        source = Path("app/mixins/ui_build.py").read_text(encoding="utf-8")
        for col in cols:
            self.assertIn(col, source)

    def test_refresh_diagnostics_populates_external_values(self):
        trader = _Harness()
        with patch("app.main_window.QTableWidgetItem", _DummyItem):
            trader._refresh_diagnostics()

        status = trader.diagnostic_table.item(0, 9).text()
        updated = trader.diagnostic_table.item(0, 10).text()
        age = trader.diagnostic_table.item(0, 11).text()

        self.assertEqual(status, "fresh")
        self.assertTrue(updated)
        self.assertTrue(age.isdigit())


if __name__ == "__main__":
    unittest.main()
