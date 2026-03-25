import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.mixins.market_intelligence import MarketIntelligenceMixin
from config import Config


class _DummyConfig:
    def __init__(self):
        self.feature_flags = {"enable_external_data": True}
        self.market_intelligence = dict(Config.DEFAULT_MARKET_INTELLIGENCE_CONFIG)


class _Cell:
    def __init__(self, value):
        self._value = str(value)

    def text(self):
        return self._value


class _Table:
    def __init__(self, rows):
        self._rows = list(rows)

    def rowCount(self):
        return len(self._rows)

    def item(self, row, col):
        try:
            value = self._rows[row][col]
        except Exception:
            return None
        if value is None:
            return None
        return _Cell(value)


class _Harness(MarketIntelligenceMixin):
    def __init__(self):
        self.config = _DummyConfig()
        self.universe = {
            "005930": {
                "name": "SAMSUNG",
                "sector": "전기전자",
                "market_intel": dict(Config.DEFAULT_MARKET_INTEL_STATE),
            }
        }
        self._candidate_universe = {}
        self._active_market_candidates = {}
        self._portfolio_budget_scale = 1.0
        self._market_risk_mode = "neutral"
        self._aggregate_news_risk = 0.0
        self.condition_table = _Table([])
        self.ranking_table = _Table([])

    def log(self, _msg):
        return None


class TestMarketIntelligencePolicyRuntime(unittest.TestCase):
    def test_negative_news_policy_caps_to_reduce_size(self):
        trader = _Harness()
        info = trader.universe["005930"]
        state = trader._ensure_market_intel_state(info)
        state["status"] = "fresh"
        state["news_score"] = -80.0

        policy = trader._resolve_market_intel_policy("005930", info)

        self.assertEqual(policy["action_policy"], "reduce_size")
        self.assertEqual(policy["exit_policy"], "reduce_size")
        self.assertNotEqual(policy["action_policy"], "force_exit")

    def test_high_risk_dart_policy_can_force_exit(self):
        trader = _Harness()
        info = trader.universe["005930"]
        state = trader._ensure_market_intel_state(info)
        state["status"] = "fresh"
        state["dart_risk_level"] = "high"
        state["event_type"] = "funding"

        policy = trader._resolve_market_intel_policy("005930", info)

        self.assertEqual(policy["action_policy"], "force_exit")
        self.assertEqual(policy["exit_policy"], "force_exit")
        self.assertEqual(policy["event_severity"], "critical")

    def test_candidate_universe_promotes_dual_source_candidate(self):
        trader = _Harness()
        trader.condition_table = _Table([["123456", "CANDI"], ["005930", "SAMSUNG"]])
        trader.ranking_table = _Table([[1, "123456", "CANDI"]])

        trader._refresh_candidate_universe_state()

        self.assertIn("123456", trader._candidate_universe)
        self.assertIn("123456", trader._active_market_candidates)
        self.assertNotIn("005930", trader._active_market_candidates)

    def test_decision_audit_writes_snapshot(self):
        trader = _Harness()
        info = trader.universe["005930"]
        state = trader._ensure_market_intel_state(info)
        state["status"] = "fresh"
        state["action_policy"] = "reduce_size"
        state["exit_policy"] = "reduce_size"
        state["size_multiplier"] = 1.15
        state["portfolio_budget_scale"] = 0.8
        state["last_event_id"] = "evt-1"
        tmpdir = tempfile.mkdtemp(dir=str(Path.cwd()))
        try:
            audit_path = Path(tmpdir) / "decision_audit.jsonl"
            with patch("app.mixins.market_intelligence.Config.MARKET_INTELLIGENCE_DECISION_AUDIT_FILE", str(audit_path)):
                trader._record_decision_audit_event(
                    code="005930",
                    info=info,
                    allowed=False,
                    reason="market_intel_reduce_size",
                    conditions={"risk:news_risk_guard": False},
                    metrics={"news_score": -80.0},
                    quantity=3,
                )
            record = json.loads(audit_path.read_text(encoding="utf-8").strip())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(record["symbol"], "005930")
        self.assertFalse(record["allowed"])
        self.assertEqual(record["action_policy"], "reduce_size")
        self.assertEqual(record["quantity"], 3)
        self.assertEqual(record["market_intel"]["last_event_id"], "evt-1")

    def test_collect_market_replay_scope_state_tracks_release_events(self):
        trader = _Harness()
        records = [
            {
                "ts": "2026-03-25T09:00:00",
                "scope": "market",
                "source": "macro",
                "event_type": "market_risk_mode",
                "payload": {"macro_regime": "risk_off", "portfolio_budget_scale": 0.8, "aggregate_news_risk": -42.0},
            },
            {
                "ts": "2026-03-25T09:01:00",
                "scope": "sector",
                "source": "news",
                "event_type": "sector_block",
                "payload": {"sector": "반도체", "count": 2},
            },
            {
                "ts": "2026-03-25T09:02:00",
                "scope": "theme",
                "source": "theme",
                "event_type": "theme_heat",
                "payload": {"theme": "AI", "theme_score": 77.0},
            },
            {
                "ts": "2026-03-25T09:03:00",
                "scope": "sector",
                "source": "news",
                "event_type": "sector_block_release",
                "payload": {"sector": "반도체"},
            },
        ]

        state = trader._collect_market_replay_scope_state(records)

        self.assertEqual(state["market_mode"], "risk_off")
        self.assertAlmostEqual(state["portfolio_budget_scale"], 0.8, places=6)
        self.assertAlmostEqual(state["aggregate_news_risk"], -42.0, places=6)
        self.assertEqual(state["sector_blocks"], {})
        self.assertEqual(state["hot_themes"], {"AI": 77.0})

    def test_replay_filters_apply_scope_and_allowed(self):
        trader = _Harness()
        event_records = [
            {"scope": "market", "symbol": "KR_MARKET", "source": "macro", "event_type": "market_risk_mode", "summary": "시장"},
            {"scope": "symbol", "symbol": "005930", "source": "news", "event_type": "headline_velocity", "summary": "삼성전자"},
        ]
        audit_records = [
            {"symbol": "005930", "allowed": True, "reason": "buy_signal"},
            {"symbol": "005930", "allowed": False, "reason": "market_intel_reduce_size"},
        ]

        filtered_events = trader._filter_market_replay_event_records(
            event_records,
            {"symbol_filter": "005930", "scope_filter": "symbol", "limit": 20},
        )
        filtered_audits = trader._filter_market_replay_audit_records(
            audit_records,
            {"symbol_filter": "005930", "audit_filter": "blocked", "limit": 20},
        )

        self.assertEqual(len(filtered_events), 1)
        self.assertEqual(filtered_events[0]["event_type"], "headline_velocity")
        self.assertEqual(len(filtered_audits), 1)
        self.assertEqual(filtered_audits[0]["reason"], "market_intel_reduce_size")


if __name__ == "__main__":
    unittest.main()
