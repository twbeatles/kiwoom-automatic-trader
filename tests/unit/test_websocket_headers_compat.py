"""websockets 14+ 헤더 인자명(additional_headers) 호환 회귀 테스트.

websockets 14에서 ``connect()``의 ``extra_headers``가
``additional_headers``로 바뀌었고, 구 인자명은 14+에서 TypeError를
일으킨다(16.1.1에서 재현 확인). 연결 헬퍼가 버전에 맞는 인자명을
고르는지, 1회성 요청 경로가 신버전 스타일 fake 연결과 동작하는지 검증한다.
"""
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from api import websocket_client
from api.websocket_client import KiwoomWebSocketClient


def _modern_connect(url, additional_headers=None, **kwargs):
    del url, kwargs
    return additional_headers


def _legacy_connect(url, extra_headers=None, **kwargs):
    del url, kwargs
    return extra_headers


class TestConnectHeadersKwarg(unittest.TestCase):
    def test_modern_signature_uses_additional_headers(self):
        headers = {"Authorization": "bearer tok"}
        self.assertEqual(
            websocket_client._connect_kwargs(headers, _modern_connect),
            {"additional_headers": headers},
        )

    def test_legacy_signature_falls_back_to_extra_headers(self):
        headers = {"Authorization": "bearer tok"}
        self.assertEqual(
            websocket_client._connect_kwargs(headers, _legacy_connect),
            {"extra_headers": headers},
        )

    def test_none_connect_defaults_to_additional_headers(self):
        self.assertEqual(
            websocket_client._headers_kw_for(None), "additional_headers"
        )

    def test_real_connect_resolves_to_supported_kwarg(self):
        if websocket_client.ws_connect is None:
            self.skipTest("websockets not installed")
        kw = websocket_client._headers_kw_for(websocket_client.ws_connect)
        self.assertIn(kw, ("additional_headers", "extra_headers"))


class _FakeWS:
    """LOGIN ack 후 지정 응답을 돌려주는 가짜 소켓."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.sent = []

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        if not self._replies:
            raise asyncio.TimeoutError()
        return self._replies.pop(0)


class TestRequestOnceModernWebsockets(unittest.TestCase):
    def test_request_once_works_with_additional_headers_style(self):
        captured = {}
        replies = [
            json.dumps({"trnm": "LOGIN", "return_code": 0}),
            json.dumps({"trnm": "CNSRLST", "data": [{"seq": 1}]}),
        ]

        def fake_connect(url, **kwargs):
            captured.update(kwargs)
            if "extra_headers" in kwargs:
                raise TypeError(
                    "BaseEventLoop.create_connection() got an unexpected "
                    "keyword argument 'extra_headers'"
                )

            ws = _FakeWS(replies)

            class _CM:
                async def __aenter__(self):
                    return ws

                async def __aexit__(self, *exc):
                    return False

            return _CM()

        auth = MagicMock()
        auth.get_token.return_value = "tok"
        auth.ws_url = "ws://127.0.0.1:9"
        auth.session_namespace = "test"
        client = KiwoomWebSocketClient(auth)

        with patch.object(websocket_client, "ws_connect", new=fake_connect):
            result = asyncio.run(
                client._request_once_async({"trnm": "CNSRLST"}, timeout=5)
            )

        self.assertIsNotNone(result)
        self.assertEqual((result or {}).get("trnm"), "CNSRLST")
        self.assertNotIn("extra_headers", captured)
        self.assertEqual(
            captured.get("additional_headers"),
            {"Authorization": "bearer tok"},
        )


if __name__ == "__main__":
    unittest.main()
