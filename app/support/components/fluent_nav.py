"""PyQt6-native Fluent-style navigation rail (no qfluentwidgets dependency).

DESKTOP_UI_DESIGN_RULES Strict KTrain Profile (§9/§27.1)은 좌측 Fluent
Navigation을 요구하지만, 본 프로젝트는 PyQt6 고정 + qfluentwidgets 미도입
결정(동일 import namespace 충돌, 규칙 §4)을 유지한다. 이 레일은 금지 패턴인
"QTabWidget 전체-앱 내비게이션"을 대체하는 동등 UX다: 상단 워크스페이스 목록
+ 하단 빠른 동작, QTabWidget(탭바 숨김)과 양방향 동기화.

스타일은 중앙 테마 엔진(app.support.theme)의 QSS 토큰으로만 입힌다.
이 파일에서 setStyleSheet()를 호출하지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QListWidget, QPushButton, QVBoxLayout, QWidget

NAV_ACTION_ORDER_TICKET = "order_ticket"
NAV_ACTION_THEME = "theme"

_RAIL_WIDTH = 192


class FluentNavRail(QFrame):
    """좌측 워크스페이스 내비게이션 레일.

    상단 목록 클릭/Enter는 ``requested(index)`` 를, 하단 버튼은
    ``action_triggered(key)`` 를 방출한다. 프로그램적 선택 변경은
    시그널을 방출하지 않아 탭-레일 동기화 루프가 생기지 않는다.
    """

    requested = pyqtSignal(int)
    action_triggered = pyqtSignal(str)

    def __init__(self, labels: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fluentNav")
        self.setAccessibleName("워크스페이스 탐색")
        self.setFixedWidth(_RAIL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._top = QListWidget(self)
        self._top.setObjectName("fluentNavList")
        self._top.setAccessibleName("워크스페이스 목록")
        self._top.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._top.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for label in labels:
            self._top.addItem(str(label))
        if self._top.count() > 0:
            self._top.setCurrentRow(0)
        self._top.itemClicked.connect(self._on_top_item_activated)
        self._top.itemActivated.connect(self._on_top_item_activated)
        layout.addWidget(self._top, 1)

        layout.addStretch(0)

        self._ticket_btn = QPushButton("주문 티켓", self)
        self._ticket_btn.setObjectName("fluentNavAction")
        self._ticket_btn.setProperty("secondary_button", True)
        self._ticket_btn.setToolTip("주문 티켓 표시/숨기기")
        self._ticket_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ticket_btn.clicked.connect(
            lambda _checked=False: self.action_triggered.emit(NAV_ACTION_ORDER_TICKET)
        )
        layout.addWidget(self._ticket_btn)

        self._theme_btn = QPushButton("테마 전환", self)
        self._theme_btn.setObjectName("fluentNavAction")
        self._theme_btn.setProperty("secondary_button", True)
        self._theme_btn.setToolTip("다크/라이트 테마 전환")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(
            lambda _checked=False: self.action_triggered.emit(NAV_ACTION_THEME)
        )
        layout.addWidget(self._theme_btn)

    def _on_top_item_activated(self, item) -> None:
        row = self._top.row(item)
        if 0 <= row < self._top.count():
            self.requested.emit(row)

    def set_current(self, index: int) -> None:
        """탭 동기화용 선택 반영 (시그널 방출 없음)."""
        try:
            target = int(index)
        except (TypeError, ValueError):
            return
        if 0 <= target < self._top.count() and target != self._top.currentRow():
            self._top.blockSignals(True)
            try:
                self._top.setCurrentRow(target)
            finally:
                self._top.blockSignals(False)

    def current(self) -> int:
        return self._top.currentRow()

    def labels(self) -> list:
        names = []
        for i in range(self._top.count()):
            item = self._top.item(i)
            if item is not None:
                names.append(item.text())
        return names
