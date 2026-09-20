"""Preset/profile/schedule dialogs (SRP: open-apply-log only)."""

from PyQt6.QtWidgets import QDialog

from app.mixins._typing import TraderMixinBase
from ui_dialogs import PresetDialog, ProfileManagerDialog, ScheduleDialog


class PresetProfilesMixin(TraderMixinBase):
    """Preset/profile/schedule dialogs (SRP: open-apply-log only)."""

    def _open_presets(self):
        current = {"k": self.spin_k.value(), "ts_start": self.spin_ts_start.value(),
                   "ts_stop": self.spin_ts_stop.value(), "loss": self.spin_loss.value(),
                   "betting": self.spin_betting.value()}
        dialog = PresetDialog(self, current)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_preset:
            p = dialog.selected_preset
            self.spin_k.setValue(p.get("k", 0.5))
            self.spin_ts_start.setValue(p.get("ts_start", 3.0))
            self.spin_ts_stop.setValue(p.get("ts_stop", 1.5))
            self.spin_loss.setValue(p.get("loss", 2.0))
            self.spin_betting.setValue(p.get("betting", 10.0))
            self.log(f"📋 프리셋 적용: {p.get('name', 'Unknown')}")

    def _open_profile_manager(self):
        """프로필 관리 다이얼로그 열기"""
        current_settings = self._get_current_settings()
        dialog = ProfileManagerDialog(self, self.profile_manager, current_settings)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_settings:
            self._apply_settings(dialog.selected_settings)
            self.log(f"👤 프로필 적용됨")

    def _open_schedule(self):
        """예약 매매 다이얼로그 열기"""
        dialog = ScheduleDialog(self, self.schedule)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.schedule = dialog.schedule
            if self.schedule.get('enabled'):
                self.log(f"⏰ 예약 매매 설정: {self.schedule['start']} ~ {self.schedule['end']}")
            else:
                self.log("⏰ 예약 매매 비활성화")
