from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import QCheckBox, QDialog, QFormLayout, QHBoxLayout, QPushButton, QTimeEdit, QVBoxLayout


class ScheduleDialog(QDialog):
    """예약 매매 설정"""

    def __init__(self, parent=None, current_schedule=None):
        super().__init__(parent)
        self.schedule = current_schedule or {}
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("⏰ 예약 매매 설정")
        self.setFixedSize(350, 250)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.chk_enabled = QCheckBox("예약 매매 활성화")
        self.chk_enabled.setChecked(self.schedule.get("enabled", False))
        form.addRow("", self.chk_enabled)

        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm")
        start = self.schedule.get("start", "09:00")
        self.time_start.setTime(QTime.fromString(start, "HH:mm"))
        form.addRow("시작 시간:", self.time_start)

        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat("HH:mm")
        end = self.schedule.get("end", "15:19")
        self.time_end.setTime(QTime.fromString(end, "HH:mm"))
        form.addRow("종료 시간:", self.time_end)

        self.chk_liquidate = QCheckBox("종료 시 자동 청산")
        self.chk_liquidate.setChecked(self.schedule.get("liquidate", True))
        form.addRow("", self.chk_liquidate)

        layout.addLayout(form)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        btn_close = QPushButton("취소")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _save(self):
        self.schedule = {
            "enabled": self.chk_enabled.isChecked(),
            "start": self.time_start.time().toString("HH:mm"),
            "end": self.time_end.time().toString("HH:mm"),
            "liquidate": self.chk_liquidate.isChecked(),
        }
        self.accept()
