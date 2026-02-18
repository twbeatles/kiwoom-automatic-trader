"""Custom UI widgets used by KiwoomProTrader."""

from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox


class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        # 마우스 휠로 값 변경 방지 (항상 부모에게 이벤트 전달 -> 스크롤 가능)
        event.ignore()

class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

