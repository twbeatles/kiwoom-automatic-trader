"""Tests for detail panel scroll position preservation and no-op update on identical text."""

import unittest
from unittest.mock import MagicMock
from app.support.widgets import update_plain_text_panel
from app.features.diagnostics.mixin import DiagnosticsMixin
from app.features.market_intelligence.views import MarketIntelViewsMixin


class _MockScrollBar:
    def __init__(self, value: int = 0, maximum: int = 500):
        self._val = value
        self._max = maximum

    def value(self) -> int:
        return self._val

    def setValue(self, v: int):
        self._val = v

    def maximum(self) -> int:
        return self._max


class _MockPanel:
    def __init__(self, text: str = ""):
        self._text = text
        self.scroll_bar = _MockScrollBar()
        self.set_plain_text_call_count = 0

    def toPlainText(self) -> str:
        return self._text

    def setPlainText(self, text: str):
        self._text = str(text)
        self.set_plain_text_call_count += 1
        # In real Qt QPlainTextEdit, setPlainText resets scroll bar to 0!
        self.scroll_bar.setValue(0)

    def verticalScrollBar(self):
        return self.scroll_bar


class TestUpdatePlainTextPanel(unittest.TestCase):
    def test_none_panel_returns_false(self):
        self.assertFalse(update_plain_text_panel(None, "hello"))

    def test_identical_text_does_not_call_set_plain_text(self):
        panel = _MockPanel("existing text")
        panel.scroll_bar.setValue(120)  # User scrolled down!

        updated = update_plain_text_panel(panel, "existing text", preserve_scroll=True)

        self.assertFalse(updated)
        self.assertEqual(panel.set_plain_text_call_count, 0)
        # Scroll position must remain untouched
        self.assertEqual(panel.scroll_bar.value(), 120)

    def test_new_text_with_preserve_scroll_restores_scroll_value(self):
        panel = _MockPanel("line 1\nline 2")
        panel.scroll_bar.setValue(150)  # User scrolled down!

        updated = update_plain_text_panel(panel, "line 1\nline 2\nline 3", preserve_scroll=True)

        self.assertTrue(updated)
        self.assertEqual(panel.set_plain_text_call_count, 1)
        # Even though setPlainText internally reset it to 0, update_plain_text_panel restored it to 150!
        self.assertEqual(panel.scroll_bar.value(), 150)

    def test_new_text_without_preserve_scroll_keeps_top_position(self):
        panel = _MockPanel("symbol A info")
        panel.scroll_bar.setValue(200)

        # Switching to symbol B: preserve_scroll=False
        updated = update_plain_text_panel(panel, "symbol B info", preserve_scroll=False)

        self.assertTrue(updated)
        self.assertEqual(panel.set_plain_text_call_count, 1)
        # Should stay at 0 (top) for a new symbol
        self.assertEqual(panel.scroll_bar.value(), 0)

    def test_handles_mock_without_to_plain_text_gracefully(self):
        class SimpleMock:
            def __init__(self):
                self.text = ""

            def setPlainText(self, val):
                self.text = val

        panel = SimpleMock()
        self.assertTrue(update_plain_text_panel(panel, "abc"))
        self.assertEqual(panel.text, "abc")
        # Second call with same text should return False
        self.assertFalse(update_plain_text_panel(panel, "abc"))


class TestDiagnosticsDetailPanelPreservation(unittest.TestCase):
    def test_diagnostics_detail_scroll_preserved_across_refreshes(self):
        class DiagnosticsHarness(DiagnosticsMixin):
            def __init__(self):
                self.diagnostic_table = MagicMock()
                self.diagnostic_table.currentRow.return_value = 0
                self._diagnostic_row_to_code = {0: "005930"}
                self.diag_detail_panel = _MockPanel()
                self.universe = {
                    "005930": {
                        "name": "삼성전자",
                        "status": "ready",
                        "held": 10,
                        "time_stop_eligible": True,
                    }
                }
                self._diagnostics_by_code = {}
                self._pending_order_state = {}
                self._manual_pending_state = {}

        harness = DiagnosticsHarness()
        # Initial render (selection)
        harness._render_selected_diagnostic_detail()
        self.assertIn("005930", harness.diag_detail_panel.toPlainText())
        self.assertEqual(harness.diag_detail_panel.set_plain_text_call_count, 1)

        # User scrolls down in the detail panel
        harness.diag_detail_panel.scroll_bar.setValue(80)

        # 100ms periodic timer tick runs _render_selected_diagnostic_detail again
        harness._render_selected_diagnostic_detail()

        # Text is identical -> no setPlainText call, scroll stays at 80!
        self.assertEqual(harness.diag_detail_panel.set_plain_text_call_count, 1)
        self.assertEqual(harness.diag_detail_panel.scroll_bar.value(), 80)

        # Now simulate data update for the same symbol
        harness.universe["005930"]["held"] = 20
        harness._render_selected_diagnostic_detail()

        # Text updated, but scroll restored to 80!
        self.assertEqual(harness.diag_detail_panel.set_plain_text_call_count, 2)
        self.assertEqual(harness.diag_detail_panel.scroll_bar.value(), 80)

        # Now simulate user selecting a different symbol
        harness.universe["000660"] = {"name": "SK하이닉스", "status": "ready"}
        harness._diagnostic_row_to_code[1] = "000660"
        harness.diagnostic_table.currentRow.return_value = 1

        harness._render_selected_diagnostic_detail()
        # Different symbol -> scroll resets to 0 (top)
        self.assertEqual(harness.diag_detail_panel.set_plain_text_call_count, 3)
        self.assertEqual(harness.diag_detail_panel.scroll_bar.value(), 0)
        self.assertIn("SK하이닉스", harness.diag_detail_panel.toPlainText())


class TestMarketIntelDetailPanelPreservation(unittest.TestCase):
    def test_market_intel_detail_scroll_preserved_across_refreshes(self):
        class MarketIntelHarness(MarketIntelViewsMixin):
            def __init__(self):
                self.market_intel_table = MagicMock()
                self.market_intel_table.selectedItems.return_value = [MagicMock(row=lambda: 0)]
                self._market_intel_row_to_code = {0: "005930"}
                self.market_intel_detail_panel = _MockPanel()
                self.universe = {
                    "005930": {
                        "name": "삼성전자",
                        "market_intel": {
                            "status": "fresh",
                            "news_score": 10.0,
                            "dart_risk_level": "normal",
                        },
                    }
                }

            def _market_intel_entity(self, code):
                return self.universe.get(code, {})

            def _ensure_market_intel_state(self, info):
                return info.get("market_intel", {})

        harness = MarketIntelHarness()
        # Initial render
        harness._render_selected_market_intel_detail()
        self.assertIn("삼성전자", harness.market_intel_detail_panel.toPlainText())
        self.assertEqual(harness.market_intel_detail_panel.set_plain_text_call_count, 1)

        # User scrolls down in the detail panel
        harness.market_intel_detail_panel.scroll_bar.setValue(100)

        # 100ms periodic timer tick runs _render_selected_market_intel_detail again
        harness._render_selected_market_intel_detail()

        # Text is identical -> no setPlainText call, scroll stays at 100!
        self.assertEqual(harness.market_intel_detail_panel.set_plain_text_call_count, 1)
        self.assertEqual(harness.market_intel_detail_panel.scroll_bar.value(), 100)


if __name__ == "__main__":
    unittest.main()
