"""
Telegram notifier for Kiwoom Pro Algo-Trader.
"""

import logging
import queue
import threading
from typing import Optional


class TelegramNotifier:
    """비동기 텔레그램 알림 클래스"""
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        if self.enabled:
            self._start_worker()

    def _start_worker(self):
        """백그라운드 전송 스레드 시작"""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        """메시지 전송 워커"""
        import requests
        while not self._stop:
            try:
                text = self._queue.get(timeout=1)
                if text is None:
                    break
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                requests.post(url, data={'chat_id': self.chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=5)
            except queue.Empty:
                continue
            except requests.RequestException as e:
                logging.getLogger('Telegram').warning(f"전송 실패: {e}")
            except Exception as e:
                logging.getLogger('Telegram').error(f"오류: {e}")

    def send(self, text: str):
        """비동기 메시지 전송 (큐에 추가)"""
        if self.enabled:
            self._queue.put(text)

    def stop(self):
        """워커 종료"""
        self._stop = True
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)
