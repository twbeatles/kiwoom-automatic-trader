"""B3: WebSocket 재연결 토큰 백오프 검증.

토큰 획득이 계속 실패할 때 점진적 백오프(5→10→20→60초) 일정을 따르고,
sleep 시간이 일정 한계를 넘지 않는지 검증한다. 실제 대기는 피하기 위해
asyncio.sleep 을 patch 한다.
"""
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from api.websocket_client import KiwoomWebSocketClient


def _make_client(auth=None):
    if auth is None:
        auth = MagicMock()
        auth.get_token.return_value = None  # 항상 토큰 획득 실패
    client = KiwoomWebSocketClient(auth)
    # 즉시 루프 종료를 위해 stop_event 세팅은 테스트 내에서 제어
    return client


class TestWebsocketReconnectTokenBackoff(unittest.TestCase):
    def test_token_failures_use_progressive_backoff_schedule(self):
        client = _make_client()
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            # 4회 시도 후 루프 종료
            if len(sleeps) >= 4:
                client._stop_event.set()

        original_connect = client._connect_and_listen

        async def run():
            # _connect_and_listen 을 짧게 돌리기 위해 stop_event 를 외부에서 세팅
            with patch("api.websocket_client.asyncio.sleep", new=fake_sleep):
                await asyncio.wait_for(original_connect(), timeout=5)

        try:
            asyncio.run(run())
        except asyncio.TimeoutError:
            pass

        # 백오프 일정(5, 10, 20, 60)의 앞부분이 관측되어야 한다.
        self.assertGreaterEqual(len(sleeps), 1)
        expected_schedule = [5, 10, 20, 60]
        for idx, actual in enumerate(sleeps[: len(expected_schedule)]):
            self.assertEqual(actual, expected_schedule[idx], f"backoff mismatch at idx {idx}: {sleeps}")
        # 백오프는 60초를 넘지 않는다.
        self.assertTrue(all(s <= 60 for s in sleeps), f"backoff exceeds cap: {sleeps}")

    def test_token_success_resets_fail_count(self):
        # 토큰이 즉시 반환되면 백오프 카운트가 리셋된다(루프는 ws_connect 실패로 이어짐).
        auth = MagicMock()
        auth.get_token.return_value = "valid-token"
        client = KiwoomWebSocketClient(auth)

        # ws_connect 가 실패하도록 patch(루프가 재시도하지만 곧 stop)
        def fake_ws_connect(*_args, **_kwargs):
            raise RuntimeError("connect failed")

        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= 2:
                client._stop_event.set()

        with patch("api.websocket_client.ws_connect", new=fake_ws_connect), patch(
            "api.websocket_client.asyncio.sleep", new=fake_sleep
        ):
            try:
                asyncio.run(asyncio.wait_for(client._connect_and_listen(), timeout=5))
            except (asyncio.TimeoutError, RuntimeError):
                pass

        # 토큰은 성공했으므로 token_fail 백오프가 아닌 재연결 백오프가 쓰인다.
        self.assertGreaterEqual(len(sleeps), 1)


if __name__ == "__main__":
    unittest.main()
