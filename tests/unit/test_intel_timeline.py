import json
import unittest

from app.support.intel_timeline import build_intel_timeline, timeline_row


def _event(ts, symbol="005930", event_type="news_spike", score=10.0, summary="뉴스 급등"):
    return {
        "ts": ts, "scope": "symbol", "symbol": symbol, "source": "news",
        "event_type": event_type, "score": score, "summary": summary,
        "blocking": False, "event_id": f"e-{ts}",
        "payload": {"action_policy": "allow", "exit_policy": "none"},
    }


def _audit(ts, symbol="005930", allowed=True, reason="가드 통과"):
    return {
        "ts": ts, "symbol": symbol, "name": "삼성전자", "allowed": allowed,
        "reason": reason, "quantity": 1, "action_policy": "allow",
        "exit_policy": "none", "market_intel": {"status": "fresh", "last_event_id": "e-1"},
    }


class TestIntelTimeline(unittest.TestCase):
    def test_merge_is_chronological(self):
        events = [_event("2026-09-25T10:00:00"), _event("2026-09-25T09:00:00")]
        audits = [_audit("2026-09-25T09:30:00", allowed=False, reason="차단")]
        entries = build_intel_timeline(events, audits)
        self.assertEqual(len(entries), 3)
        self.assertEqual([e["ts_text"] for e in entries], [
            "2026-09-25T09:00:00", "2026-09-25T09:30:00", "2026-09-25T10:00:00",
        ])
        self.assertEqual([e["kind"] for e in entries], ["event", "audit", "event"])
        row = timeline_row(entries[1])
        self.assertEqual(len(row), 5)
        self.assertEqual(row[1], "감사")
        self.assertIn("차단", row[3])

    def test_limit_keeps_latest(self):
        events = [_event(f"2026-09-25T09:{i:02d}:00") for i in range(10)]
        entries = build_intel_timeline(events, [], limit=3)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[-1]["ts_text"], "2026-09-25T09:09:00")

    def test_empty_and_malformed_safe(self):
        self.assertEqual(build_intel_timeline(None, None), [])
        entries = build_intel_timeline(["not-a-dict", {}], [None], limit=5)
        self.assertEqual(len(entries), 1)

    def test_jsonl_source_shape_preserved(self):
        # Timeline consumes the same parsed-JSONL dicts the replay tables use.
        event_line = json.dumps(_event("2026-09-25T10:00:00"), ensure_ascii=False)
        audit_line = json.dumps(_audit("2026-09-25T10:01:00"), ensure_ascii=False)
        events = [json.loads(event_line)]
        audits = [json.loads(audit_line)]
        entries = build_intel_timeline(events, audits)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["source"]["event_id"], "e-2026-09-25T10:00:00")
        self.assertEqual(entries[1]["source"]["reason"], "가드 통과")

    def test_refresh_intel_timeline_wiring(self):
        from app.features.market_intelligence.views import MarketIntelViewsMixin

        class _Cell:
            def __init__(self, value=""):
                self._value = str(value)

            def setText(self, value):
                self._value = str(value)

        class _Table:
            def __init__(self):
                self.rows = 0
                self.cells = {}

            def setUpdatesEnabled(self, _enabled):
                return None

            def setRowCount(self, rows):
                self.rows = int(rows)

            def item(self, row, col):
                return self.cells.get((row, col))

            def setItem(self, row, col, item):
                self.cells[(row, col)] = item

            def selectedItems(self):
                return []

        class _Panel:
            def __init__(self):
                self.text = ""

            def setPlainText(self, value):
                self.text = str(value)

        class Harness:
            _refresh_intel_timeline = MarketIntelViewsMixin._refresh_intel_timeline
            _render_selected_intel_timeline_detail = MarketIntelViewsMixin._render_selected_intel_timeline_detail

            def __init__(self):
                self.market_replay_timeline_table = _Table()
                self.market_replay_timeline_detail_panel = _Panel()
                self.spin_market_replay_limit = None
                self._market_replay_timeline_entries = []

        harness = Harness()
        harness._refresh_intel_timeline(
            [_event("2026-09-25T10:00:00")], [_audit("2026-09-25T10:01:00")]
        )
        self.assertEqual(harness.market_replay_timeline_table.rows, 2)
        self.assertEqual(len(harness._market_replay_timeline_entries), 2)
        self.assertIn("선택된 타임라인 항목이 없습니다.", harness.market_replay_timeline_detail_panel.text)


if __name__ == "__main__":
    unittest.main()
