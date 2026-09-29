"""Phase-3: external holding loss watch (alert only, no orders)."""
import unittest

from app.features.trading_session.positions import TradingSessionPositionsMixin


class _Harness(TradingSessionPositionsMixin):
    def __init__(self, loss_cut=2.0, running=True):
        self.is_running = running
        self.config = type("Cfg", (), {"loss_cut": loss_cut})()
        self._log_cooldown_map = {}
        self.logs = []

    def log(self, msg):
        self.logs.append(str(msg))


class TestExternalLossWatch(unittest.TestCase):
    def test_warns_below_stop_threshold(self):
        trader = _Harness()
        info = {"name": "EXT", "held": 10, "buy_price": 10000, "current": 9700}
        trader._watch_external_loss("000001", info)
        self.assertTrue(any("외부보유 경고" in m for m in trader.logs))
        self.assertIn("-3.00%", trader.logs[0])

    def test_silent_above_threshold(self):
        trader = _Harness()
        info = {"name": "EXT", "held": 10, "buy_price": 10000, "current": 9950}
        trader._watch_external_loss("000001", info)
        self.assertEqual(trader.logs, [])

    def test_silent_when_not_running_or_no_price(self):
        trader = _Harness(running=False)
        trader._watch_external_loss(
            "000001", {"name": "EXT", "held": 10, "buy_price": 10000, "current": 9000}
        )
        trader2 = _Harness()
        trader2._watch_external_loss(
            "000001", {"name": "EXT", "held": 10, "buy_price": 0, "current": 9000}
        )
        self.assertEqual(trader.logs, [])
        self.assertEqual(trader2.logs, [])

    def test_dedup_within_cooldown(self):
        trader = _Harness()
        info = {"name": "EXT", "held": 10, "buy_price": 10000, "current": 9000}
        trader._watch_external_loss("000001", info)
        trader._watch_external_loss("000001", info)
        self.assertEqual(len(trader.logs), 1)


if __name__ == "__main__":
    unittest.main()
