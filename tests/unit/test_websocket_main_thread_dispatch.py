import logging
import threading
import time
import unittest

from PyQt6.QtCore import QCoreApplication, QThread

from api.websocket_client import KiwoomWebSocketClient, _main_thread_dispatcher


class TestWebSocketMainThreadDispatch(unittest.TestCase):
    def test_background_callback_is_queued_to_qt_thread(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        client = KiwoomWebSocketClient.__new__(KiwoomWebSocketClient)
        client.logger = logging.getLogger("test.websocket.dispatch")
        client._qt_dispatcher = _main_thread_dispatcher()
        seen = []

        def callback():
            seen.append(QThread.currentThread() == app.thread())

        thread = threading.Thread(target=lambda: client._invoke_on_main_thread(callback))
        thread.start()
        deadline = time.time() + 2.0
        while not seen and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)
        thread.join(timeout=1.0)

        self.assertEqual(seen, [True])


if __name__ == "__main__":
    unittest.main()
