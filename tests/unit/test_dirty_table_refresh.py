import unittest

from app.mixins.trading_session import TradingSessionMixin


class _DummyTable:
    def __init__(self):
        self.row_count = 0
        self.updates_enabled = True

    def setUpdatesEnabled(self, value):
        self.updates_enabled = bool(value)

    def setRowCount(self, value):
        self.row_count = int(value)


class _Harness(TradingSessionMixin):
    def __init__(self):
        self.universe = {"005930": {}, "000660": {}}
        self._dirty_codes = {"005930"}
        self._code_to_row = {"005930": 0, "000660": 1}
        self.table = _DummyTable()
        self.updated = []

    def _update_row(self, row, code):
        self.updated.append((row, code))


class TestDirtyTableRefresh(unittest.TestCase):
    def test_refresh_updates_only_dirty_codes(self):
        trader = _Harness()

        trader._refresh_table()

        self.assertEqual(trader.updated, [(0, "005930")])
        self.assertEqual(trader._dirty_codes, set())


if __name__ == "__main__":
    unittest.main()
