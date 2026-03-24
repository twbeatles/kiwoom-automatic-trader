import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from data.providers.stock_cache_provider import StockMasterCacheProvider
from ui_dialogs import StockSearchDialog


class _DummyInput:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _DummyStatus:
    def __init__(self):
        self.text_value = ""

    def setText(self, text):
        self.text_value = str(text)


class _DummyQuote:
    def __init__(self, code, name, current_price, market_type):
        self.code = code
        self.name = name
        self.current_price = current_price
        self.market_type = market_type


class _DummyRestClient:
    def __init__(self):
        self.calls = []

    def get_stock_quote(self, code):
        self.calls.append(code)
        if code == "005930":
            return _DummyQuote("005930", "삼성전자", 71000, "KOSPI")
        return None


class _Harness:
    _search_code_via_api = StockSearchDialog._search_code_via_api

    def __init__(self, keyword, cache_provider, rest_client=None):
        self.rest_client = rest_client
        self.cache_provider = cache_provider
        self.search_input = _DummyInput(keyword)
        self.search_status = _DummyStatus()
        self._last_results = []
        self.rendered_rows = []

    def _render_results(self, rows):
        self.rendered_rows = list(rows)


def _build_harness(keyword, cache_provider, rest_client=None):
    return _Harness(keyword, cache_provider, rest_client=rest_client)


class TestStockSearchDialog(unittest.TestCase):
    def test_stock_search_code_query_uses_rest_quote(self):
        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            cache_path = Path(tmpdir) / "stock_master_cache.json"
            cache_provider = StockMasterCacheProvider(str(cache_path))
            rest_client = _DummyRestClient()
            harness = _build_harness("005930", cache_provider, rest_client)

            StockSearchDialog._search(cast(Any, harness))

            self.assertEqual(rest_client.calls, ["005930"])
            self.assertEqual(len(harness.rendered_rows), 1)
            self.assertEqual(harness.rendered_rows[0]["code"], "005930")
            self.assertEqual(harness.rendered_rows[0]["source"], "api")
            self.assertIn("API 확인 결과 1건", harness.search_status.text_value)

            cached = cache_provider.search("005930")
            self.assertTrue(any(row.get("code") == "005930" for row in cached))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_stock_search_name_query_uses_local_cache(self):
        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            cache_path = Path(tmpdir) / "stock_master_cache.json"
            cache_provider = StockMasterCacheProvider(str(cache_path))
            cache_provider.upsert("005930", "삼성전자", "KOSPI", 71000)
            cache_provider.upsert("000660", "SK하이닉스", "KOSPI", 120000)

            harness = _build_harness("삼성", cache_provider, rest_client=None)
            StockSearchDialog._search(cast(Any, harness))

            self.assertEqual(len(harness.rendered_rows), 1)
            self.assertEqual(harness.rendered_rows[0]["code"], "005930")
            self.assertEqual(harness.rendered_rows[0]["source"], "cache")
            self.assertIn("캐시 검색 1건", harness.search_status.text_value)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
