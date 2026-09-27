"""Fluent navigation rail guards (DESKTOP_UI_DESIGN_RULES §9/§27.1).

QTabWidget 전체-앱 내비게이션(규칙 금지 패턴) 대신 좌측 FluentNavRail이
워크스페이스를 조종한다. Qt 위젯이 필요하므로 오프스크린 QApplication에서
실행한다 (헤드리스 결정성 보장, 타 테스트에 영향 없음).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import (
    QApplication,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QWidget,
)

from app.features.ui_build.workspaces import WORKSPACE_LABELS, UIBuildWorkspacesMixin
from app.support.components.fluent_nav import (
    NAV_ACTION_ORDER_TICKET,
    NAV_ACTION_THEME,
    FluentNavRail,
)

_EMOJI_RE = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff]")


_QAPP = None


def _ensure_qapp():
    """Create (and keep alive) the offscreen QApplication for widget tests."""
    global _QAPP
    if QApplication.instance() is None:
        _QAPP = QApplication([])
    return QApplication.instance()


def _host(running=False):
    """Real QTabWidget + real rail on a mixin host (no full window)."""
    _ensure_qapp()
    host = UIBuildWorkspacesMixin.__new__(UIBuildWorkspacesMixin)
    host.is_running = running  # pyright: ignore[reportAttributeAccessIssue]
    tabs = QTabWidget()
    for label in WORKSPACE_LABELS:
        tabs.addTab(QWidget(), label)
    host.main_tabs = tabs  # pyright: ignore[reportAttributeAccessIssue]
    host.fluent_nav = host._create_fluent_nav()  # pyright: ignore[reportAttributeAccessIssue]
    return host


def _top_list(rail) -> QListWidget:
    lst = rail.findChild(QListWidget, "fluentNavList")
    assert lst is not None
    return lst


class TestFluentNavRail(unittest.TestCase):
    def test_labels_come_from_single_source_without_emoji(self):
        _ensure_qapp()
        rail = FluentNavRail(list(WORKSPACE_LABELS))
        self.assertEqual(rail.labels(), list(WORKSPACE_LABELS))
        for label in rail.labels():
            self.assertIsNone(_EMOJI_RE.search(label), f"emoji in {label!r}")

    def test_bottom_actions_have_no_emoji(self):
        _ensure_qapp()
        rail = FluentNavRail(list(WORKSPACE_LABELS))
        buttons = rail.findChildren(QPushButton)
        self.assertEqual(len(buttons), 2)
        for button in buttons:
            self.assertIsNone(_EMOJI_RE.search(button.text()))

    def test_set_current_does_not_reemit(self):
        _ensure_qapp()
        rail = FluentNavRail(list(WORKSPACE_LABELS))
        spy = MagicMock()
        rail.requested.connect(spy)
        rail.set_current(3)
        self.assertEqual(rail.current(), 3)
        spy.assert_not_called()

    def test_action_buttons_emit_keys(self):
        _ensure_qapp()
        rail = FluentNavRail(list(WORKSPACE_LABELS))
        seen = []
        rail.action_triggered.connect(seen.append)
        buttons = rail.findChildren(QPushButton)
        buttons[0].click()
        buttons[1].click()
        self.assertEqual(seen, [NAV_ACTION_ORDER_TICKET, NAV_ACTION_THEME])


class TestWorkspaceRailWiring(unittest.TestCase):
    def test_tab_bar_hidden_as_page_stack(self):
        host = _host()
        tabs = host.main_tabs
        host._hide_workspace_tab_bar(tabs)
        bar = tabs.tabBar()
        assert bar is not None
        self.assertTrue(bar.isHidden())

    def test_click_navigates_idle_and_syncs(self):
        host = _host(running=False)
        lst = _top_list(host.fluent_nav)
        lst.itemClicked.emit(lst.item(2))
        self.assertEqual(host.main_tabs.currentIndex(), 2)
        self.assertEqual(host.fluent_nav.current(), 2)

    def test_goto_workspace_syncs_rail(self):
        host = _host(running=False)
        host._goto_workspace(4)
        self.assertEqual(host.main_tabs.currentIndex(), 4)
        self.assertEqual(host.fluent_nav.current(), 4)

    def test_tabs_changed_syncs_rail(self):
        host = _host(running=False)
        host.main_tabs.setCurrentIndex(1)
        host._sync_fluent_nav(1)
        self.assertEqual(host.fluent_nav.current(), 1)

    def test_running_block_keeps_tab_and_resyncs_rail(self):
        host = _host(running=True)
        lst = _top_list(host.fluent_nav)
        # 실제 마우스 클릭처럼 레일 선택이 먼저 바뀌었다고 가정
        lst.setCurrentRow(3)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            lst.itemClicked.emit(lst.item(3))
        self.assertEqual(host.main_tabs.currentIndex(), 0)
        self.assertEqual(host.fluent_nav.current(), 0)

    def test_running_allow_moves_both(self):
        host = _host(running=True)
        lst = _top_list(host.fluent_nav)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            lst.itemClicked.emit(lst.item(1))
        self.assertEqual(host.main_tabs.currentIndex(), 1)
        self.assertEqual(host.fluent_nav.current(), 1)

    def test_bottom_actions_dispatch_to_view_handlers(self):
        host = _host(running=False)
        host._toggle_order_ticket = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]
        host._toggle_theme = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]
        host._on_fluent_nav_action(NAV_ACTION_ORDER_TICKET)
        host._on_fluent_nav_action(NAV_ACTION_THEME)
        host._toggle_order_ticket.assert_called_once_with()
        host._toggle_theme.assert_called_once_with()

    def test_sync_without_rail_is_noop(self):
        _ensure_qapp()
        host = UIBuildWorkspacesMixin.__new__(UIBuildWorkspacesMixin)
        host._sync_fluent_nav(2)
        host._sync_fluent_nav("bogus")


class TestFluentNavQss(unittest.TestCase):
    def test_rail_selectors_present_in_both_themes(self):
        from app.support.theme import build_stylesheet

        for theme in ("dark", "light"):
            qss = build_stylesheet(theme, 1.0)
            for selector in (
                "QFrame#fluentNav",
                "QListWidget#fluentNavList",
                "QListWidget#fluentNavList::item:selected",
            ):
                self.assertIn(selector, qss, f"{theme}:{selector}")


if __name__ == "__main__":
    unittest.main()
