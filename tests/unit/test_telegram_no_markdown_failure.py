"""C2: Telegram Markdown 이스케이프 검증.

parse_mode='Markdown' 이 제거되었으므로, 특수문자(_, *, `)가 포함된 메시지도
data 에 parse_mode 키 없이 text 만 전송되어야 한다.
"""
import unittest
from unittest.mock import MagicMock, patch

import telegram_notifier


class TestTelegramNoMarkdownFailure(unittest.TestCase):
    def test_send_special_chars_does_not_use_parse_mode(self):
        notifier = telegram_notifier.TelegramNotifier("token", "chat")
        captured = {}

        def fake_post(url, data=None, timeout=None):
            captured["url"] = url
            captured["data"] = dict(data or {})
            return MagicMock()

        # 워커가 큐에서 메시지를 꺼내 처리하도록 requests.post 를 가로챈다.
        with patch("requests.post", side_effect=fake_post):
            notifier.send("종목_이름 *강조* `코드` 100% 손익")
            # 워커가 처리할 시간을 준다(동기 큐 처리).
            notifier.stop()

        self.assertIn("data", captured)
        # parse_mode 키가 전송 데이터에 없다.
        self.assertNotIn("parse_mode", captured["data"])
        # text 는 그대로 전달된다.
        self.assertIn("종목_이름", captured["data"]["text"])
        self.assertEqual(captured["data"]["chat_id"], "chat")
        # URL 이 telegram bot api 를 가리킨다.
        self.assertIn("api.telegram.org", captured["url"])

    def test_disabled_notifier_does_not_send(self):
        notifier = telegram_notifier.TelegramNotifier("", "")
        self.assertFalse(notifier.enabled)
        # enabled=False 면 send 가 큐에 넣지 않는다(워커도 시작 안 됨).
        with patch("requests.post") as mock_post:
            notifier.send("ignored")
        mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
