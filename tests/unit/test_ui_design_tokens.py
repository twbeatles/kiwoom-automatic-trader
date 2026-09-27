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
                'QFrame#fluentNav',
                'QListWidget#fluentNavList::item:selected',
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


class TestUserVisibleLabels(unittest.TestCase):
    """Rule 19: no emoji icons in user-visible labels (logs excluded)."""

    def test_preset_names_and_help_have_no_emoji(self):
        from config import Config

        for preset in Config.DEFAULT_PRESETS.values():
            self.assertIsNone(
                _EMOJI_RE.search(preset["name"]), f"emoji in preset {preset['name']!r}"
            )
        for section, body in Config.HELP_CONTENT.items():
            self.assertIsNone(
                _EMOJI_RE.search(body), f"emoji in help {section!r}"
            )

    def test_menu_group_button_labels_have_no_emoji(self):
        menu_text = (REPO / "app" / "mixins" / "system_shell.py").read_text(
            encoding="utf-8"
        )
        # single source: menu iterates WORKSPACE_LABELS (no literal copies)
        self.assertIn("enumerate(WORKSPACE_LABELS)", menu_text)
        views_text = (
            REPO / "app" / "features" / "market_intelligence" / "views.py"
        ).read_text(encoding="utf-8")
        for title in ("리플레이 요약", "소스 상태"):
            self.assertIn(title, views_text)
        schedule_text = (REPO / "dialogs" / "schedule.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('QPushButton("저장")', schedule_text)
        favorites_text = (
            REPO / "app" / "features" / "dialogs" / "favorites.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"\u2b50 {name}"', favorites_text)
        for path, content in (
            ("app/mixins/system_shell.py", menu_text),
            ("app/features/market_intelligence/views.py", views_text),
            ("dialogs/schedule.py", schedule_text),
        ):
            for line in content.splitlines():
                if "addAction(" in line or "QGroupBox(" in line or "QPushButton(" in line:
                    self.assertIsNone(
                        _EMOJI_RE.search(line), f"emoji in {path}: {line.strip()}"
                    )


class TestTableStatusColors(unittest.TestCase):
    def test_roles_resolve_per_theme(self):
        for theme in ("dark", "light"):
            for role in theme_engine.TABLE_STATUS_ROLES:
                color = theme_engine.table_status_color(theme, role)
                self.assertRegex(color, r"^#[0-9a-f]{6}$", f"{theme}:{role}")
        self.assertEqual(
            theme_engine.table_status_color("unknown-theme", "error"),
            theme_engine.TABLE_STATUS_COLORS["dark"]["error"],
        )

    def test_status_contrast_passes_on_table_background(self):
        for theme in ("dark", "light"):
            for role, ratio in theme_engine.check_table_status_contrast(
                theme
            ).items():
                self.assertGreaterEqual(ratio, 4.5, f"{theme}:{role}")


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


class TestThemeMode(unittest.TestCase):
    def test_modes_and_defaults(self):
        self.assertEqual(
            theme_engine.DEFAULT_UI_THEME_MODE, "auto"
        )
        self.assertEqual(
            theme_engine.UI_THEME_MODES, ("auto", "dark", "light")
        )
        self.assertEqual(theme_engine.clamp_theme_mode("DARK"), "dark")
        self.assertEqual(theme_engine.clamp_theme_mode("bogus"), "auto")

    def test_resolve_pinned(self):
        self.assertEqual(theme_engine.resolve_theme_name("dark"), "dark")
        self.assertEqual(theme_engine.resolve_theme_name("light"), "light")

    def test_resolve_auto_never_raises(self):
        resolved = theme_engine.resolve_theme_name("auto")
        self.assertIn(resolved, ("dark", "light"))

    def test_log_colors_single_source(self):
        for level in theme_engine.LOG_LEVELS:
            self.assertRegex(
                theme_engine.log_level_color(level), r"^#[0-9a-f]{6}$", level
            )
        self.assertEqual(
            theme_engine.log_level_color("bogus"),
            theme_engine.LOG_LEVEL_COLORS["info"],
        )
        self.assertRegex(theme_engine.log_timestamp_color(), r"^#[0-9a-f]{6}$")

    def test_no_hardcoded_log_hex_in_shell(self):
        text = (REPO / "app" / "mixins" / "system_shell.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_log_level_color(", text)
        for hex_code in ("#f85149", "#d29922", "#3fb950", "#e6edf3", "#8b949e"):
            self.assertNotIn(hex_code, text)

    def test_no_hardcoded_status_hex_in_diagnostics(self):
        text = (
            REPO / "app" / "features" / "diagnostics" / "mixin.py"
        ).read_text(encoding="utf-8")
        self.assertIn("table_status_color(", text)
        for hex_code in ("#8b949e", "#d29922"):
            self.assertNotIn(hex_code, text)


class TestNavigationGuard(unittest.TestCase):
    def _host(self, running=False, current=0, count=5):
        from unittest.mock import MagicMock

        from app.features.ui_build.workspaces import UIBuildWorkspacesMixin

        host = UIBuildWorkspacesMixin.__new__(UIBuildWorkspacesMixin)
        host.is_running = running  # pyright: ignore[reportAttributeAccessIssue]
        tabs = MagicMock()
        tabs.currentIndex.return_value = current
        tabs.count.return_value = count
        host.main_tabs = tabs  # pyright: ignore[reportAttributeAccessIssue]
        return host, tabs

    def test_idle_switch_proceeds_without_dialog(self):
        host, tabs = self._host(running=False, current=0)
        host._goto_workspace(2)
        tabs.setCurrentIndex.assert_called_once_with(2)

    def test_same_tab_proceeds_while_running(self):
        host, tabs = self._host(running=True, current=1)
        host._goto_workspace(1)
        tabs.setCurrentIndex.assert_called_once_with(1)

    def test_running_switch_asks_and_blocks_on_no(self):
        from PyQt6.QtWidgets import QMessageBox

        from unittest.mock import patch

        host, tabs = self._host(running=True, current=0)
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ):
            host._goto_workspace(3)
        tabs.setCurrentIndex.assert_not_called()

    def test_running_switch_proceeds_on_yes(self):
        from PyQt6.QtWidgets import QMessageBox

        from unittest.mock import patch

        host, tabs = self._host(running=True, current=0)
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ):
            host._goto_workspace(3)
        tabs.setCurrentIndex.assert_called_once_with(3)


class TestThemeModeParity(unittest.TestCase):
    def test_config_defaults(self):
        from config import Config

        self.assertEqual(Config.DEFAULT_UI_THEME_MODE, "auto")
        self.assertEqual(Config.UI_THEME_MODES, ("auto", "dark", "light"))

    def test_settings_io_carries_theme_mode(self):
        text = (
            REPO / "app" / "features" / "persistence" / "settings_io.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"theme_mode"', text)
        self.assertIn("ui_theme_mode", text)

    def test_theme_combo_offers_auto(self):
        text = (
            REPO / "app" / "features" / "ui_build" / "settings_tabs.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"auto"', text)


if __name__ == "__main__":
    unittest.main()
