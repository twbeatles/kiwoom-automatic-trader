"""Custom UI widgets used by KiwoomProTrader."""

from typing import Any, cast

from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox



class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, e):
        # 마우스 휠로 값 변경 방지 (항상 부모에게 이벤트 전달 -> 스크롤 가능)
        if e is not None:
            e.ignore()

class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, e):
        if e is not None:
            e.ignore()

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, e):
        if e is not None:
            e.ignore()


def update_plain_text_panel(
    panel: object,
    new_text: str,
    preserve_scroll: bool = True,
) -> bool:
    """QPlainTextEdit 패널의 텍스트를 스크롤 위치를 보존하며 안전하게 업데이트합니다.

    - 기존 텍스트와 new_text가 동일하면 불필요한 setPlainText 호출을 방지하여
      마우스 스크롤이 최상단(0)으로 강제 리셋되는 현상을 방지합니다 (False 반환).
    - preserve_scroll이 True인 경우, 기존 수직 스크롤 위치를 기억하여
      텍스트 갱신 후에도 이전 스크롤바 위치를 복원합니다.
    - 텍스트가 갱신되면 True를 반환합니다.
    """
    if panel is None:
        return False

    current_text = None
    to_text = getattr(panel, "toPlainText", None)
    if callable(to_text):
        try:
            current_text = to_text()
        except Exception:
            current_text = None
    elif hasattr(panel, "text") and isinstance(getattr(panel, "text"), str):
        current_text = getattr(panel, "text")

    if current_text is not None and current_text == new_text:
        return False

    scrollbar = None
    sb_getter = getattr(panel, "verticalScrollBar", None)
    if callable(sb_getter):
        try:
            scrollbar = cast(Any, sb_getter)()
        except Exception:
            scrollbar = None

    prev_scroll = 0
    if preserve_scroll and scrollbar is not None:
        val_getter = getattr(scrollbar, "value", None)
        if callable(val_getter):
            try:
                raw_val = cast(Any, val_getter)()
                prev_scroll = int(cast(Any, raw_val))
            except Exception:
                prev_scroll = 0

    set_text = getattr(panel, "setPlainText", None)
    if callable(set_text):
        cast(Any, set_text)(new_text)

    if preserve_scroll and prev_scroll > 0 and scrollbar is not None:
        val_setter = getattr(scrollbar, "setValue", None)
        max_getter = getattr(scrollbar, "maximum", None)
        max_val = prev_scroll
        if callable(max_getter):
            try:
                raw_max = cast(Any, max_getter)()
                max_val = int(cast(Any, raw_max))
            except Exception:
                max_val = prev_scroll
        if callable(val_setter):
            try:
                cast(Any, val_setter)(min(prev_scroll, max_val))
            except Exception:
                pass

    return True


