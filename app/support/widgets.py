"""Custom UI widgets used by KiwoomProTrader."""

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

