"""Fluent redesign guards (DESKTOP_UI_DESIGN_RULES): tokens, badges, no-inline-QSS."""

import pathlib
import re
import unittest
from typing import ClassVar

from app.support import design_tokens as tokens
from app.support import theme as theme_engine
from app.support.components import helpers
from app.support.theme import TOKENS, build_stylesheet

REPO = pathlib.Path(__file__).resolve().parents[2]

_EMOJI_RE = re.compile(
    "[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff]"
)


def _mock_widget():
    """Duck-typed widget recording dynamic properties (no QApplication)."""
    from unittest.mock import MagicMock

    widget = MagicMock()
    props: dict = {}
    widget.setProperty.side_effect = (
        lambda name, value: props.__setitem__(name, value) or True
    )
    widget.props = props
    return widget


class TestDesignTokens(unittest.TestCase):
    def test_spacing_scale(self):
        self.assertEqual(
            tokens.SPACING_SCALE, (4, 8, 12, 16, 24, 32)
        )
        self.assertEqual(tokens.PAGE_MARGIN, 24)
        self.assertEqual(tokens.SECTION_GAP, 24)
        self.assertEqual(tokens.CARD_RADIUS, 8)

    def test_semantic_keys_map_to_real_tokens(self):
        for theme, palette in TOKENS.items():
            for key in tokens.SEMANTIC_KEYS:
                concrete = tokens.semantic_color(theme, key)
                self.assertIn(concrete, palette, f"{theme}:{key}")

    def test_is_spacing(self):
        self.assertTrue(tokens.is_spacing(8))
        self.assertFalse(tokens.is_spacing(10))


class TestComponentHelpers(unittest.TestCase):
    def test_mark_secondary(self):
        widget = _mock_widget()
        helpers.mark_secondary(widget)
        self.assertTrue(widget.props.get("secondary"))

    def test_mark_invalid_toggle(self):
        widget = _mock_widget()
        helpers.mark_invalid(widget, True)
        self.assertTrue(widget.props.get("invalid"))
        helpers.mark_invalid(widget, False)
        self.assertFalse(widget.props.get("invalid"))

    def test_connection_badge(self):
        widget = _mock_widget()
        helpers.set_connection_badge(widget, "connected")
        self.assertEqual(widget.props.get("badge"), "connected")

    def test_profit_sign(self):
        widget = _mock_widget()
        helpers.set_profit_sign(widget, 5)
        self.assertEqual(widget.props.get("profit_state"), "up")
        helpers.set_profit_sign(widget, -1)
        self.assertEqual(widget.props.get("profit_state"), "down")
        helpers.set_profit_sign(widget, 0)
        self.assertEqual(widget.props.get("profit_state"), "flat")

    def test_trading_badge(self):
        widget = _mock_widget()
        helpers.set_trading_badge(widget, True)
        self.assertEqual(widget.props.get("badge"), "active")
        helpers.set_trading_badge(widget, False)
        self.assertEqual(widget.props.get("badge"), "off")


class TestThemeFluentRules(unittest.TestCase):
    def test_shared_selectors_present(self):
        for theme in ("dark", "light"):
            qss = build_stylesheet(theme, 1.0)
            for selector in (
                'QLabel[secondary="true"]',
                'QLabel[section="true"]',
                'QLabel[hint="true"]',
                'QLabel[value="true"]',
                'QLabel[tone="warning"]',
                'QLabel[badge="connected"]',
                'QLabel[profit_state="up"]',
                'QPushButton#orderBtn',
                'QFrame[infobar="success"]',
                'QPushButton[secondary_button="true"]',
                'QLineEdit[invalid="true"]',
            ):
                self.assertIn(selector, qss, f"{theme}:{selector}")

    def test_no_gradients_on_flat_surfaces(self):
        for theme in ("dark", "light"):
            qss = build_stylesheet(theme, 1.0)
            self.assertNotIn("qlineargradient", qss, theme)

    def test_no_oversized_radius(self):
        # Cards/dialogs/badges capped at CARD_RADIUS=8; small control
        # chrome (tabs/menus/lists) keeps its own rounding.
        for theme in ("dark", "light"):
            qss = build_stylesheet(theme, 1.0)
            self.assertNotIn("border-radius: 16px", qss, theme)
            self.assertNotIn("border-radius: 14px", qss, theme)

    def test_contrast_still_passes(self):
        for theme in ("dark", "light"):
            for pair, ratio in theme_engine.check_theme_contrast(theme).items():
                self.assertGreaterEqual(ratio, 4.5, f"{theme}:{pair}")


class TestWorkspaceLabels(unittest.TestCase):
    def test_no_emoji_in_workspace_labels(self):
        from app.features.ui_build.workspaces import WORKSPACE_LABELS

        self.assertEqual(len(WORKSPACE_LABELS), 5)
        for label in WORKSPACE_LABELS:
            self.assertIsNone(
                _EMOJI_RE.search(label), f"emoji icon in {label!r}"
            )


class TestNoInlineQss(unittest.TestCase):
    ALLOW: ClassVar = {
        # central theme engine + parent-stylesheet inherit only
        "app/support/theme.py",
        "dialogs/manual_order.py",
    }

    def test_pages_have_no_setstylesheet(self):
        offenders = []
        roots = [
            REPO / "app" / "features",
            REPO / "app" / "mixins",
            REPO / "dialogs",
        ]
        for root in roots:
            for path in sorted(root.rglob("*.py")):
                rel = path.relative_to(REPO).as_posix()
                if rel in self.ALLOW:
                    continue
                text = path.read_text(encoding="utf-8")
                if "setStyleSheet(" in text:
                    offenders.append(rel)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
