import datetime
import unittest

from app.mixins.execution_engine import ExecutionEngineMixin
from config import Config, TradingConfig


class _Harness(ExecutionEngineMixin):
    def __init__(self):
        self.config = TradingConfig()
        self.refresh_requests = []
        self._sync_failed_codes = set()
        self._global_risk_mode = "normal"
        self._global_risk_until = None
        self._order_health_mode = "normal"
        self._order_health_until = None
        self._recent_slippage_bps = []

    def _request_market_intelligence_refresh_batch(self, codes, reason="periodic", force=False):
        self.refresh_requests.append((list(codes), reason, force))
        return True


class TestMarketIntelligenceEntryGuard(unittest.TestCase):
    def _info(self, **state):
        return {
            "status": "watch",
            "market_intel": {
                **Config.DEFAULT_MARKET_INTEL_STATE,
                **state,
            },
            "avg_value_20": 2_000_000_000,
            "ask_price": 1005,
            "bid_price": 1000,
        }

    def test_idle_market_intelligence_relaxed_default_allows_and_requests_refresh(self):
        trader = _Harness()

        allowed, reason = trader._can_enter_trade("005930", self._info(status="idle"), datetime.datetime.now())

        self.assertTrue(allowed)
        self.assertEqual(reason, "")
        self.assertEqual(trader.refresh_requests[0][1], "entry_guard_idle")

    def test_idle_market_intelligence_strict_mode_fails_closed(self):
        trader = _Harness()
        trader.config.market_intelligence["source_policy"]["strict_entry_guard"] = True

        allowed, reason = trader._can_enter_trade("005930", self._info(status="idle"), datetime.datetime.now())

        self.assertFalse(allowed)
        self.assertEqual(reason, "market_intel_fresh_guard")

    def test_high_risk_disclosure_blocks_entry(self):
        trader = _Harness()
        now = datetime.datetime.now()
        info = self._info(status="fresh", intel_status="fresh", intel_updated_at=now, dart_risk_level="high")

        allowed, reason = trader._can_enter_trade("005930", info, now)

        self.assertFalse(allowed)
        self.assertEqual(reason, "market_intel_dart_guard")

    def test_disabled_market_intelligence_does_not_block(self):
        trader = _Harness()
        trader.config.market_intelligence["enabled"] = False

        allowed, reason = trader._can_enter_trade("005930", self._info(status="idle"), datetime.datetime.now())

        self.assertTrue(allowed)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
