"""P4 theme/a11y: tokenized QSS, 4.5:1 contrast, focus rings, font scaling."""

import re
import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("keyring", MagicMock())

from app.support import theme as theme_engine
from app.support.theme import (
    ACCESSIBLE_CONTROLS,
    DEFAULT_FONT_SCALE,
    FONT_SCALE_MAX,
    FONT_SCALE_MIN,
    apply_accessibility_names,
    apply_theme,
    build_stylesheet,
    check_theme_contrast,
    clamp_font_scale,
    contrast_ratio,
    scaled_sizes,
    set_ui_font_scale,
)
from config import Config


class _StubWidget:
    def __init__(self):
        self.name = None
        self.desc = None

    def setAccessibleName(self, name):
        self.name = name

    def setAccessibleDescription(self, desc):
        self.desc = desc


class _StubHost:
    def __init__(self):
        self.current_theme = "dark"
        self.ui_font_scale = 1.0
        self.stylesheet = None
        self.btn_connect = _StubWidget()
        self.btn_start = _StubWidget()
        self.btn_stop = _StubWidget()

    def setStyleSheet(self, qss):
        self.stylesheet = qss


def _font_sizes(qss):
    # Fonts are emitted in pt for HiDPI correctness; accept legacy px too.
    return [float(v) for v in re.findall(r"font-size:\s*([\d.]+)p[xt]", qss)]


class TestThemeTokens(unittest.TestCase):
    def test_both_themes_build(self):
        dark = build_stylesheet("dark", 1.0)
        light = build_stylesheet("light", 1.0)
        self.assertGreater(len(dark), 2000)
        self.assertGreater(len(light), 2000)
        self.assertIn("QMainWindow", dark)
        self.assertIn("QMainWindow", light)
        self.assertNotEqual(dark, light)

    def test_unknown_theme_falls_back_to_dark(self):
        self.assertEqual(build_stylesheet("nope", 1.0), build_stylesheet("dark", 1.0))

    def test_legacy_shim_paths_still_work(self):
        import dark_theme
        import light_theme

        self.assertEqual(dark_theme.DARK_STYLESHEET, build_stylesheet("dark", 1.0))
        self.assertEqual(light_theme.LIGHT_STYLESHEET, build_stylesheet("light", 1.0))

    def test_no_hardcoded_low_contrast_disabled_colors(self):
        dark = build_stylesheet("dark", 1.0)
        self.assertNotIn("#484f58", dark)

    def test_config_font_scale_defaults(self):
        self.assertEqual(Config.DEFAULT_UI_FONT_SCALE, 1.0)
        self.assertLessEqual(Config.UI_FONT_SCALE_MIN, 1.0)
        self.assertGreaterEqual(Config.UI_FONT_SCALE_MAX, 1.0)


class TestContrast(unittest.TestCase):
    def test_all_text_pairs_meet_aa(self):
        for name in ("dark", "light"):
            with self.subTest(theme=name):
                report = check_theme_contrast(name)
                self.assertTrue(report)
                for pair, ratio in report.items():
                    self.assertGreaterEqual(ratio, 4.5, f"{name}:{pair}={ratio}")

    def test_known_fixes(self):
        self.assertGreaterEqual(
            contrast_ratio(
                theme_engine.DARK_TOKENS["text_disabled"],
                theme_engine.DARK_TOKENS["surface_2"],
            ),
            4.5,
        )
        self.assertGreaterEqual(
            contrast_ratio(
                theme_engine.LIGHT_TOKENS["text_disabled"],
                theme_engine.LIGHT_TOKENS["surface_2"],
            ),
            4.5,
        )


class TestFocusRings(unittest.TestCase):
    def test_focus_ring_present_on_interactive_widgets(self):
        for name in ("dark", "light"):
            qss = build_stylesheet(name, 1.0)
            self.assertIn(":focus", qss)
            self.assertIn("border: 2px solid", qss)
            for selector in (
                "QLineEdit:focus",
                "QPushButton:focus",
                "QTableWidget:focus",
                "QTabBar::tab:focus",
            ):
                self.assertIn(selector, qss, f"{name} missing {selector}")


class TestFontScaling(unittest.TestCase):
    def test_scale_up_grows_all_sizes(self):
        base = _font_sizes(build_stylesheet("dark", 1.0))
        big = _font_sizes(build_stylesheet("dark", 1.25))
        self.assertEqual(len(base), len(big))
        self.assertTrue(all(b >= a for a, b in zip(base, big)))
        self.assertTrue(any(b > a for a, b in zip(base, big)))

    def test_clamp_bounds_and_invalid(self):
        self.assertEqual(clamp_font_scale(99.0), FONT_SCALE_MAX)
        self.assertEqual(clamp_font_scale(0.01), FONT_SCALE_MIN)
        self.assertEqual(clamp_font_scale("bad"), DEFAULT_FONT_SCALE)
        self.assertEqual(clamp_font_scale(None), DEFAULT_FONT_SCALE)
        self.assertEqual(scaled_sizes("dark", 99.0), scaled_sizes("dark", FONT_SCALE_MAX))

    def test_apply_and_set_scale_on_host(self):
        host = _StubHost()
        self.assertEqual(apply_theme(host, "light", 1.2), "light")
        self.assertEqual(host.current_theme, "light")
        self.assertEqual(host.ui_font_scale, 1.2)
        self.assertIsNotNone(host.stylesheet)
        self.assertIn("font-size:", str(host.stylesheet))
        self.assertEqual(set_ui_font_scale(host, 5.0), FONT_SCALE_MAX)
        self.assertEqual(host.current_theme, "light")


class TestAccessibleNames(unittest.TestCase):
    def test_names_applied_to_stub_controls(self):
        host = _StubHost()
        applied = apply_accessibility_names(host)
        self.assertGreaterEqual(applied, 3)
        self.assertEqual(host.btn_connect.name, "API 연결 버튼")
        self.assertTrue(host.btn_start.desc)

    def test_missing_widgets_are_skipped(self):
        host = _StubHost()
        del host.btn_stop
        applied = apply_accessibility_names(host)
        self.assertGreaterEqual(applied, 2)

    def test_control_table_nonempty(self):
        self.assertGreaterEqual(len(ACCESSIBLE_CONTROLS), 8)


if __name__ == "__main__":
    unittest.main()
