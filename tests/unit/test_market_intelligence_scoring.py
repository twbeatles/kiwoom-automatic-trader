import datetime
import unittest

from app.mixins.market_intelligence import MarketIntelligenceMixin
from config import Config


class _DummyConfig:
    def __init__(self):
        self.feature_flags = {"enable_external_data": True}
        self.market_intelligence = dict(Config.DEFAULT_MARKET_INTELLIGENCE_CONFIG)


class _Harness(MarketIntelligenceMixin):
    def __init__(self):
        self.config = _DummyConfig()


class TestMarketIntelligenceScoring(unittest.TestCase):
    def test_news_scoring_deduplicates_and_tracks_velocity(self):
        trader = _Harness()
        now = datetime.datetime.now(datetime.timezone.utc)
        info = {"name": "SAMSUNG", "market_intel": dict(Config.DEFAULT_MARKET_INTEL_STATE)}
        items = [
            {"title": "삼성전자 대규모 수주 계약", "published_at": now},
            {"title": "삼성전자 대규모 수주 계약", "published_at": now},
            {"title": "삼성전자 신제품 공개", "published_at": now},
            {"title": "삼성전자 파트너십 확대", "published_at": now},
            {"title": "삼성전자 배당 확대 검토", "published_at": now},
            {"title": "삼성전자 자사주 매입", "published_at": now},
        ]

        result = trader._score_news_items(info, items)

        self.assertEqual(len(result["headlines"]), 5)
        self.assertEqual(result["headline_velocity"], 5)
        self.assertGreaterEqual(result["score"], 60.0)
        self.assertEqual(result["sentiment"], "bullish")

    def test_dart_high_risk_event_is_blocking(self):
        trader = _Harness()
        result = trader._score_dart_events(
            [{"report_nm": "유상증자 결정", "rcept_no": "20260324000123", "rcept_dt": "20260324"}]
        )

        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["blocking"])
        self.assertLessEqual(result["score"], -80.0)
        self.assertEqual(result["events"][0]["tags"], ["유상증자"])

    def test_ai_disabled_falls_back_to_rules(self):
        trader = _Harness()
        info = {
            "name": "SAMSUNG",
            "market_intel": {
                **Config.DEFAULT_MARKET_INTEL_STATE,
                "news_score": -80.0,
                "dart_risk_level": "normal",
            },
        }

        result = trader._maybe_run_ai_summary("005930", info, reason="unit_test")

        self.assertEqual(result["source"], "rules")
        self.assertEqual(result["action_hint"], "block_entry")
        self.assertIn("뉴스 점수", result["summary"])


if __name__ == "__main__":
    unittest.main()
