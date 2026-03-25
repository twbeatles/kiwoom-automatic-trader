import unittest
from unittest.mock import patch

from data.providers.news_provider import NewsProvider


class _Response:
    def __init__(self, payload=None, error=None):
        self._payload = payload or {}
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise RuntimeError(self._error)

    def json(self):
        return self._payload


class TestMarketIntelligenceProviderStatus(unittest.TestCase):
    def test_news_provider_marks_empty_response(self):
        provider = NewsProvider("id", "secret")
        with patch("data.providers.news_provider.requests.get", return_value=_Response({"items": []})):
            result = provider.search("삼성전자")

        self.assertEqual(result, [])
        self.assertEqual(provider.last_status, "ok_empty")
        self.assertEqual(provider.last_error, "")

    def test_news_provider_marks_error_response(self):
        provider = NewsProvider("id", "secret")
        with patch("data.providers.news_provider.requests.get", return_value=_Response(error="boom")):
            result = provider.search("삼성전자")

        self.assertEqual(result, [])
        self.assertEqual(provider.last_status, "error")
        self.assertIn("boom", provider.last_error)


if __name__ == "__main__":
    unittest.main()
