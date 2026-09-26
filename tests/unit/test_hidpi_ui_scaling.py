"""HiDPI UI scaling: display recommendations, pt fonts, density paddings."""

import re
import sys
import unittest
from typing import Any
from unittest.mock import MagicMock

sys.modules.setdefault("keyring", MagicMock())

from app.support.theme import (
    apply_theme,
    build_stylesheet,
    current_ui_settings,
    layout_scale,
    px_to_pt,
    set_ui_density,
    set_ui_font_scale,
)
from app.support.ui_scale import (
    clamp_density,
    configure_high_dpi_scaling,
    next_scale_step,
    recommended_density,
    recommended_font_scale,
)
from config import Config


def _font_size_units(qss):
    return re.findall(r"font-size:\s*[\d.]+(p[xt])", qss)


def _menu_item_top_padding(qss):
    match = re.search(r"QMenu::item\s*\{\s*padding:\s*(\d+)px", qss)
    assert match is not None, "QMenu::item padding missing"
    return int(match.group(1))


class _StubHost:
    def __init__(self):
        self.current_theme = "dark"
        self.ui_font_scale = 1.0
        self.ui_density = "compact"
        self.stylesheet = None

    def setStyleSheet(self, qss):
        self.stylesheet = qss


class TestDisplayRecommendations(unittest.TestCase):
    def test_standard_display_keeps_scale_1(self):
        self.assertEqual(recommended_font_scale(None, None), 1.0)
        self.assertEqual(recommended_font_scale(1.0, 96), 1.0)
        self.assertEqual(recommended_font_scale("bad", "bad"), 1.0)

    def test_high_ratio_displays_keep_scale_1(self):
        # pt fonts already follow the OS scale; an app multiplier on top
        # double-scales HiDPI text, so every bucket stays at 1.0.
        self.assertEqual(recommended_font_scale(1.25, None), 1.0)
        self.assertEqual(recommended_font_scale(1.5, 144), 1.0)
        self.assertEqual(recommended_font_scale(2.0, 192), 1.0)
        self.assertEqual(recommended_font_scale(None, 200), 1.0)

    def test_density_recommendation(self):
        self.assertEqual(recommended_density(1.0, 96), "compact")
        self.assertEqual(recommended_density(1.25, 120), "compact")
        self.assertEqual(recommended_density(1.5, 144), "comfortable")
        self.assertEqual(recommended_density(2.0, 192), "comfortable")

    def test_clamp_density(self):
        self.assertEqual(clamp_density("COMFORTABLE"), "comfortable")
        self.assertEqual(clamp_density("compact"), "compact")
        self.assertEqual(clamp_density("roomy"), "compact")
        self.assertEqual(clamp_density(None), "compact")

    def test_scale_steps(self):
        self.assertEqual(next_scale_step(1.0, 1), 1.15)
        self.assertEqual(next_scale_step(1.0, -1), 0.85)
        self.assertEqual(next_scale_step(1.5, 1), 1.5)
        self.assertEqual(next_scale_step(0.85, -1), 0.85)
        self.assertEqual(next_scale_step("bad", 1), 1.15)

    def test_configure_high_dpi_never_raises(self):
        self.assertIn(
            configure_high_dpi_scaling(),
            ("passthrough", "legacy", "unavailable"),
        )

    def test_hidpi_defaults_keep_font_scale(self):
        # Regression: first-run HiDPI must not lift ui_font_scale
        # (pt fonts already follow the OS scale); density may relax.
        from app.features.ui_build.layout import UIBuildLayoutMixin

        class _FakeScreen:
            def devicePixelRatio(self):
                return 1.5

            def logicalDotsPerInchX(self):
                return 144.0

        class _Stub(UIBuildLayoutMixin):
            ui_font_scale = 1.0
            ui_density = "compact"

            def screen(self) -> Any:
                return _FakeScreen()

        stub = _Stub()
        stub._apply_hidpi_defaults()
        self.assertEqual(stub.ui_font_scale, 1.0)
        self.assertEqual(stub.ui_density, "comfortable")


class TestThemeHidpiOutput(unittest.TestCase):
    def test_fonts_use_pt_not_px(self):
        for theme in ("dark", "light"):
            units = _font_size_units(build_stylesheet(theme, 1.0))
            self.assertTrue(units)
            self.assertTrue(all(u == "pt" for u in units), theme)

    def test_px_to_pt_conversion(self):
        self.assertAlmostEqual(px_to_pt(14), 10.5)
        self.assertAlmostEqual(px_to_pt(96), 72.0)
        self.assertGreaterEqual(px_to_pt(0), 6.5)
        self.assertAlmostEqual(px_to_pt("bad"), 10.5)

    def test_comfortable_is_roomier_than_compact(self):
        for theme in ("dark", "light"):
            compact = _menu_item_top_padding(build_stylesheet(theme, 1.0, "compact"))
            comfortable = _menu_item_top_padding(
                build_stylesheet(theme, 1.0, "comfortable")
            )
            self.assertGreater(comfortable, compact, theme)

    def test_font_scale_grows_menu_padding(self):
        base = _menu_item_top_padding(build_stylesheet("dark", 1.0, "compact"))
        big = _menu_item_top_padding(build_stylesheet("dark", 1.3, "compact"))
        self.assertGreater(big, base)

    def test_menu_has_minimum_width(self):
        for theme in ("dark", "light"):
            qss = build_stylesheet(theme, 1.0)
            self.assertIn("min-width:", qss)

    def test_layout_scale_combines_font_and_density(self):
        self.assertAlmostEqual(layout_scale(1.0, "compact"), 1.0)
        self.assertGreater(
            layout_scale(1.0, "comfortable"), layout_scale(1.0, "compact")
        )
        self.assertGreater(
            layout_scale(1.3, "compact"), layout_scale(1.0, "compact")
        )


class TestDensityRoundTrip(unittest.TestCase):
    def test_apply_theme_records_density(self):
        host = _StubHost()
        self.assertEqual(apply_theme(host, "dark", 1.0, "comfortable"), "dark")
        self.assertEqual(host.ui_density, "comfortable")
        self.assertIn("font-size:", str(host.stylesheet))

    def test_set_density_preserves_scale(self):
        host = _StubHost()
        apply_theme(host, "dark", 1.15, "compact")
        self.assertEqual(set_ui_density(host, "comfortable"), "comfortable")
        self.assertEqual(host.ui_font_scale, 1.15)
        self.assertEqual(
            _menu_item_top_padding(str(host.stylesheet)),
            _menu_item_top_padding(build_stylesheet("dark", 1.15, "comfortable")),
        )

    def test_set_scale_preserves_density(self):
        host = _StubHost()
        apply_theme(host, "dark", 1.0, "comfortable")
        set_ui_font_scale(host, 1.3)
        self.assertEqual(host.ui_density, "comfortable")
        self.assertEqual(host.ui_font_scale, 1.3)

    def test_unknown_density_falls_back_to_compact(self):
        host = _StubHost()
        self.assertEqual(set_ui_density(host, "roomy"), "compact")
        theme, scale, density = current_ui_settings(host)
        self.assertEqual((theme, scale, density), ("dark", 1.0, "compact"))

    def test_host_without_density_attr_defaults_compact(self):
        host = _StubHost()
        del host.ui_density
        theme, scale, density = current_ui_settings(host)
        self.assertEqual(density, "compact")
        apply_theme(host)
        self.assertEqual(host.ui_density, "compact")


class TestHidpiConfigDefaults(unittest.TestCase):
    def test_density_defaults(self):
        self.assertEqual(Config.DEFAULT_UI_DENSITY, "compact")
        self.assertIn("compact", Config.UI_DENSITIES)
        self.assertIn("comfortable", Config.UI_DENSITIES)

    def test_zoom_shortcuts_registered(self):
        self.assertEqual(Config.SHORTCUTS.get("ui_zoom_in"), "Ctrl+=")
        self.assertEqual(Config.SHORTCUTS.get("ui_zoom_out"), "Ctrl+-")


if __name__ == "__main__":
    unittest.main()
