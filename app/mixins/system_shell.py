"""System shell/logging/tray mixin for KiwoomProTrader."""

import datetime
import logging
import os
import sys
import winreg
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from config import Config
from app.support.theme import apply_theme
from app.support.theme import set_ui_font_scale as _set_ui_font_scale
from app.support.theme import set_ui_density as _set_ui_density
from app.support.ui_scale import next_scale_step as _next_scale_step
from ui_dialogs import HelpDialog
from ._typing import TraderMixinBase


class SystemShellMixin(TraderMixinBase):
    def _setup_logging(self):
        Path(Config.LOG_DIR).mkdir(exist_ok=True)
        self.logger = logging.getLogger("KiwoomTrader")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        log_file = Path(Config.LOG_DIR) / f"trader_{datetime.datetime.now():%Y%m%d}.log"
        existing_paths = {
            Path(getattr(handler, "baseFilename"))
            for handler in self.logger.handlers
            if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None)
        }
        if log_file not in existing_paths:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(file_handler)

    def _set_auto_start(self, enabled):
        """윈도우 시작 레지스트리 등록/해제."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "KiwoomProTrader"
        try:
            exe_path = f'"{os.path.abspath(sys.argv[0])}"'
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                self.logger.info("자동 실행 등록 완료")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    self.logger.info("자동 실행 해제 완료")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as exc:
            self.logger.error(f"자동 실행 설정 오류: {exc}")
            QMessageBox.warning(self, "오류", f"레지스트리 설정 실패: {exc}")
            self.chk_auto_start.setChecked(not enabled)

    def _create_menu(self):
        menubar = self.menuBar()
        assert menubar is not None

        file_menu = menubar.addMenu("파일")
        assert file_menu is not None
        file_menu.addAction("설정 저장", self._save_settings)
        file_menu.addAction("설정 불러오기", self._load_settings)
        file_menu.addSeparator()
        file_menu.addAction("거래내역 내보내기", self._export_csv)
        file_menu.addSeparator()
        file_menu.addAction("종료", self.close)

        trading_menu = menubar.addMenu("매매")
        assert trading_menu is not None
        trading_menu.addAction("매매 시작", self.start_trading)
        trading_menu.addAction("매매 중지", self.stop_trading)
        trading_menu.addSeparator()
        trading_menu.addAction("긴급 전체 청산", self._emergency_liquidate)
        trading_menu.addSeparator()
        trading_menu.addAction("수동 주문", self._open_manual_order)

        tools_menu = menubar.addMenu("도구")
        assert tools_menu is not None
        tools_menu.addAction("프리셋 관리", self._open_presets)
        tools_menu.addAction("프로필 관리", self._open_profile_manager)
        tools_menu.addSeparator()
        tools_menu.addAction("종목 검색", self._open_stock_search)
        tools_menu.addAction("예약 매매", self._open_schedule)
        tools_menu.addSeparator()
        tools_menu.addAction("계좌 새로고침", lambda: self._on_account_changed(self.current_account))
        tools_menu.addAction("민감정보/토큰 삭제", self._clear_stored_secrets)

        view_menu = menubar.addMenu("보기")
        assert view_menu is not None
        view_menu.addAction("테마 전환", self._toggle_theme)
        view_menu.addSeparator()
        view_menu.addAction("사운드 켜기/끄기", self._toggle_sound)
        view_menu.addSeparator()
        ui_scale_menu = view_menu.addMenu("UI 크기")
        assert ui_scale_menu is not None
        self._ui_scale_actions = {}
        for _step in (1.0, 1.15, 1.3, 1.5):
            _action = ui_scale_menu.addAction(
                f"글자 {int(round(_step * 100))}%",
                lambda _checked=False, _s=_step: self._set_ui_scale_step(_s),
            )
            assert _action is not None
            _action.setCheckable(True)
            self._ui_scale_actions[_step] = _action
        self._density_action = view_menu.addAction(
            "여유 있는 밀도", self._toggle_ui_density
        )
        assert self._density_action is not None
        self._density_action.setCheckable(True)
        self._density_action.setToolTip("메뉴/버튼 간격을 넓혀 고배율에서 고르기 쉽게 합니다.")
        self._refresh_ui_scale_menu()
        view_menu.addSeparator()
        workspace_menu = view_menu.addMenu("워크스페이스 이동")
        assert workspace_menu is not None
        for _ws_index, _ws_label in enumerate(("⚡ 매매", "📊 종목 탐색", "💼 포트폴리오", "🧠 인텔리전스", "⚙ 시스템")):
            workspace_menu.addAction(_ws_label, lambda _checked=False, _i=_ws_index: self._goto_workspace(_i))
        view_menu.addAction("주문 티켓 표시/숨기기", self._toggle_order_ticket)

        help_menu = menubar.addMenu("도움말")
        assert help_menu is not None
        help_menu.addAction("사용 가이드", lambda: HelpDialog(self).exec())
        help_menu.addAction("단축키 목록", self._show_shortcuts)
        help_menu.addSeparator()
        help_menu.addAction(
            "버전 정보",
            lambda: QMessageBox.information(
                self,
                "정보",
                "키움 자동매매 도우미 v4.5\nKiwoom Pro Algo-Trader\nREST API 기반 + 초보자 친화 UI 개편",
            ),
        )

    def _create_tray(self):
        """시스템 트레이 아이콘 생성."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))
        self.tray_icon.setToolTip("키움 자동매매 도우미 v4.5")

        tray_menu = QMenu()
        action_show = QAction("열기", self)
        action_show.triggered.connect(self.showNormal)
        tray_menu.addAction(action_show)
        tray_menu.addSeparator()
        action_quit = QAction("종료", self)
        action_quit.triggered.connect(self._force_quit)
        tray_menu.addAction(action_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(
            lambda reason: self.showNormal()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        self.tray_icon.show()

    def _force_quit(self):
        """트레이 메뉴에서 완전 종료."""
        reply = QMessageBox.question(
            self,
            "종료 확인",
            "프로그램을 완전히 종료하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._force_quit_requested = True
            self.close()

    def _setup_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(1000)

    def _on_timer(self):
        now = datetime.datetime.now()
        if hasattr(self, "_rollover_daily_metrics"):
            self._rollover_daily_metrics(now=now, reset_baseline=False)
        self.status_time.setText(now.strftime("%H:%M:%S"))

        badge_mode = "running" if self.is_running else "idle"
        if badge_mode != self._last_status_badge:
            self._last_status_badge = badge_mode
            if self.is_running:
                self.status_trading.setText("자동매매 실행중")
                self.status_trading.setObjectName("tradingActive")
                self.status_trading.setStyleSheet(
                    """
                    color: #3fb950;
                    font-weight: bold;
                    padding: 4px 12px;
                    background: rgba(63, 185, 80, 0.15);
                    border-radius: 10px;
                    border: 1px solid rgba(63, 185, 80, 0.3);
                    """
                )
            else:
                self.status_trading.setText("자동매매 대기중")
                self.status_trading.setObjectName("tradingOff")
                self.status_trading.setStyleSheet(
                    """
                    color: #8b949e;
                    font-weight: bold;
                    padding: 4px 12px;
                    background: rgba(48, 54, 61, 0.5);
                    border-radius: 10px;
                    """
                )

        if self.schedule.get("enabled", False) and self.is_connected:
            current_time = now.strftime("%H:%M")
            start_time = self.schedule.get("start", "09:00")
            end_time = self.schedule.get("end", "15:19")

            start_inflight = bool(getattr(self, "_trading_start_inflight", False))
            if not self.is_running and not self.schedule_started and not start_inflight:
                if start_time <= current_time < end_time:
                    self.log(f"예약 매매 시작: {start_time}")
                    self.start_trading(from_schedule=True)

            if self.is_running and self.schedule_started:
                if current_time >= end_time:
                    self.log(f"예약 매매 종료: {end_time}")
                    if self.schedule.get("liquidate", True):
                        self._time_liquidate()
                    self.stop_trading()
                    self.schedule_started = False

        if not self.is_running:
            return

        cleanup_manual_pending = getattr(self, "_cleanup_manual_pending_state", None)
        if callable(cleanup_manual_pending):
            cleanup_manual_pending(now)

        self._refresh_account_info_async()
        recalc_time_targets = getattr(self, "_maybe_recalculate_time_strategy_targets", None)
        if callable(recalc_time_targets):
            recalc_time_targets(now)

        if not self.time_liquidate_executed:
            if now.hour == Config.MARKET_CLOSE_HOUR and now.minute >= Config.MARKET_CLOSE_MINUTE:
                self.time_liquidate_executed = True
                self._time_liquidate()

        cfg = getattr(self, "config", None)
        loss_basis = str(getattr(cfg, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")))
        if loss_basis == "total_equity":
            basis_amount = int(getattr(self, "total_equity", 0) or 0) or int(getattr(self, "deposit", 0) or 0)
        else:
            basis_amount = int(getattr(self, "deposit", 0) or 0)
        if int(getattr(self, "daily_initial_deposit", 0) or 0) <= 0 and basis_amount > 0:
            self.daily_initial_deposit = basis_amount

        self._check_daily_loss_limit()

        if self._history_dirty:
            self._save_trade_history()

    def _check_daily_loss_limit(self):
        """일일 손실 한도 평가. 타이머뿐 아니라 매도 체결 누적 직후에도 호출되어
        한도 도달 시 즉시 매매를 중지한다(다음 timer tick 전 진입 차단)."""
        if bool(getattr(self, "daily_loss_triggered", False)):
            return
        if not self.is_running:
            return
        cfg = getattr(self, "config", None)
        use_risk_chk = getattr(self, "chk_use_risk", None)
        if use_risk_chk is None or not use_risk_chk.isChecked():
            return
        if int(getattr(self, "daily_initial_deposit", 0) or 0) <= 0:
            return
        loss_rate = (self.daily_realized_profit / self.daily_initial_deposit) * 100
        max_loss_spin = getattr(self, "spin_max_loss", None)
        max_loss = float(getattr(cfg, "max_daily_loss", max_loss_spin.value() if max_loss_spin else 0))
        if loss_rate <= -max_loss:
            self.daily_loss_triggered = True
            loss_basis = str(getattr(cfg, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")))
            self.log(
                f"일일 손실 한도 도달 ({loss_rate:.2f}%, 손익 {self.daily_realized_profit:+,}원, 기준={loss_basis}) - 매매 중지"
            )
            self.stop_trading()

    def _setup_shortcuts(self):
        """키보드 단축키 설정."""
        shortcuts = [
            (Config.SHORTCUTS.get("connect", "Ctrl+L"), self.connect_api),
            (Config.SHORTCUTS.get("start_trading", "Ctrl+S"), self.start_trading),
            (Config.SHORTCUTS.get("stop_trading", "Ctrl+Q"), self.stop_trading),
            (Config.SHORTCUTS.get("emergency_stop", "Ctrl+Shift+X"), self._emergency_liquidate),
            (Config.SHORTCUTS.get("refresh", "F5"), lambda: self._on_account_changed(self.current_account)),
            (Config.SHORTCUTS.get("export_csv", "Ctrl+E"), self._export_csv),
            (Config.SHORTCUTS.get("open_profile_manager", "Ctrl+P"), self._open_profile_manager),
            (Config.SHORTCUTS.get("open_presets", "Ctrl+Shift+P"), self._open_presets),
            (Config.SHORTCUTS.get("toggle_theme", "Ctrl+T"), self._toggle_theme),
            (Config.SHORTCUTS.get("show_help", "F1"), lambda: HelpDialog(self).exec()),
            (Config.SHORTCUTS.get("search_stock", "Ctrl+F"), self._open_stock_search),
            (Config.SHORTCUTS.get("manual_order", "Ctrl+O"), self._open_manual_order),
            (Config.SHORTCUTS.get("ui_zoom_in", "Ctrl+="), self._zoom_ui_in),
            (Config.SHORTCUTS.get("ui_zoom_out", "Ctrl+-"), self._zoom_ui_out),
        ]

        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)

    def set_ui_density(self, density):
        """UI 밀도 변경 후 현재 테마 재적용 (compact/comfortable)."""
        applied = _set_ui_density(self, density)
        combo = getattr(self, "combo_ui_density", None)
        if combo is not None:
            try:
                combo.blockSignals(True)
                combo.setCurrentText(applied)
            finally:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass
        self._refresh_ui_scale_menu()
        self.log(f"UI 밀도 '{applied}' 적용")
        return applied

    def _set_ui_scale_step(self, scale):
        """보기 메뉴/단축키에서 고른 배율로 UI 글자 크기 변경."""
        clamped = self.set_ui_font_scale(scale)
        spin = getattr(self, "spin_ui_font_scale", None)
        if spin is not None:
            try:
                spin.blockSignals(True)
                spin.setValue(float(clamped))
            finally:
                try:
                    spin.blockSignals(False)
                except Exception:
                    pass
        self._refresh_ui_scale_menu()
        return clamped

    def _toggle_ui_density(self):
        """빽빽/여유 밀도 전환."""
        current = str(getattr(self, "ui_density", "compact"))
        self.set_ui_density("compact" if current == "comfortable" else "comfortable")

    def _zoom_ui_in(self):
        """UI 한 단계 확대 (Ctrl+=)."""
        self._set_ui_scale_step(
            _next_scale_step(getattr(self, "ui_font_scale", 1.0), 1)
        )

    def _zoom_ui_out(self):
        """UI 한 단계 축소 (Ctrl+-)."""
        self._set_ui_scale_step(
            _next_scale_step(getattr(self, "ui_font_scale", 1.0), -1)
        )

    def _on_density_changed(self, density):
        """UI 밀도 콤보박스 변경 처리."""
        self.set_ui_density(density)

    def _refresh_ui_scale_menu(self):
        """보기 메뉴의 UI 크기 체크 상태를 현재 값과 동기화."""
        try:
            current = float(getattr(self, "ui_font_scale", 1.0) or 1.0)
        except (TypeError, ValueError):
            current = 1.0
        actions = getattr(self, "_ui_scale_actions", None)
        if isinstance(actions, dict):
            for step, action in actions.items():
                try:
                    action.setChecked(abs(float(step) - current) < 1e-9)
                except Exception:
                    continue
        density_action = getattr(self, "_density_action", None)
        if density_action is not None:
            try:
                density_action.setChecked(
                    str(getattr(self, "ui_density", "compact")) == "comfortable"
                )
            except Exception:
                pass

    def set_ui_font_scale(self, scale):
        """UI 폰트 스케일 변경 후 현재 테마 재적용 (0.85~1.5)."""
        clamped = _set_ui_font_scale(self, scale)
        self._refresh_ui_scale_menu()
        self.log(f"UI 글자 크기 x{clamped:.2f} 적용")
        return clamped

    def _toggle_theme(self):
        """다크/라이트 테마 전환."""
        new_theme = "light" if getattr(self, "current_theme", "dark") == "dark" else "dark"
        apply_theme(self, new_theme)
        if self.current_theme == "light":
            self.log("라이트 테마 적용")
        else:
            self.log("다크 테마 적용")

    def _on_theme_combo_changed(self, theme):
        """테마 콤보박스 변경 처리."""
        if theme in ("dark", "light") and theme != getattr(self, "current_theme", "dark"):
            apply_theme(self, theme)
            self.log(f"{'다크' if theme == 'dark' else '라이트'} 테마 적용")

    def _on_font_scale_changed(self, scale):
        """UI 글자 크기 스핀박스 변경 처리."""
        self.set_ui_font_scale(scale)

    def _toggle_sound(self):
        """사운드 켜기/끄기."""
        if self.sound:
            current = self.sound.enabled
            self.sound.set_enabled(not current)
            self.chk_use_sound.setChecked(not current)
            self.log(f"사운드 {'켜짐' if not current else '꺼짐'}")

    def _on_sound_changed(self, state):
        """사운드 체크박스 변경 처리."""
        if self.sound:
            self.sound.set_enabled(state == Qt.CheckState.Checked.value)

    def _show_shortcuts(self):
        """단축키 목록 표시."""
        shortcuts_text = "\n".join(
            [
                "주요 키보드 단축키",
                "",
                "  Ctrl+L: API 연결",
                "  Ctrl+S: 매매 시작",
                "  Ctrl+Q: 매매 중지",
                "  Ctrl+Shift+X: 긴급 청산",
                "  Ctrl+F: 종목 검색",
                "  Ctrl+O: 수동 주문",
                "  Ctrl+P: 프로필 관리",
                "  Ctrl+Shift+P: 프리셋 관리",
                "  Ctrl+E: CSV 내보내기",
                "  Ctrl+T: 테마 전환",
                "  Ctrl+= / Ctrl+-: UI 글자 확대 / 축소",
                "  F5: 새로고침",
                "  F1: 도움말",
            ]
        )
        QMessageBox.information(self, "단축키 목록", shortcuts_text)

    def log(self, msg):
        self.sig_log.emit(msg)
        self.logger.info(msg)

    def _append_log(self, msg):
        timestamp = f"[{datetime.datetime.now():%H:%M:%S}]"

        if "실패" in msg or "오류" in msg:
            color = "#f85149"
            badge_style = "color: #f85149; font-weight: bold;"
            level_mark = "ERR"
        elif "경고" in msg or "손실" in msg:
            color = "#d29922"
            badge_style = "color: #d29922; font-weight: bold;"
            level_mark = "WRN"
        elif "성공" in msg or "완료" in msg or "시작" in msg:
            color = "#3fb950"
            badge_style = "color: #3fb950; font-weight: bold;"
            level_mark = "SUC"
        else:
            color = "#e6edf3"
            badge_style = "color: #8b949e;"
            level_mark = "INF"

        html = f"""
        <div style="margin-bottom: 2px;">
            <span style="color: #8b949e; font-family: monospace;">{timestamp}</span>
            <span style="{badge_style} margin-left: 4px; margin-right: 4px;">[{level_mark}]</span>
            <span style="color: {color};">{msg}</span>
        </div>
        """

        self.log_text.append(html)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        if self.log_text.document().blockCount() > Config.MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(50):
                cursor.movePosition(
                    QTextCursor.MoveOperation.Down,
                    QTextCursor.MoveMode.KeepAnchor,
                )
            cursor.removeSelectedText()

    def closeEvent(self, a0):
        if a0 is None:
            return
        event = a0
        force_quit = getattr(self, "_force_quit_requested", False)
        if getattr(self, "_shutdown_in_progress", False):
            event.accept()
            return

        if not force_quit and hasattr(self, "chk_minimize_tray") and self.chk_minimize_tray.isChecked():
            event.ignore()
            self.hide()
            if hasattr(self, "tray_icon"):
                self.tray_icon.showMessage(
                    "Kiwoom Pro Trader",
                    "프로그램이 백그라운드에서 실행 중입니다.\n트레이 아이콘을 더블클릭하면 다시 열립니다.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
            return

        if not force_quit and self.is_running:
            reply = QMessageBox.question(
                self,
                "종료 확인",
                "현재 매매가 진행 중입니다.\n강제로 종료하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        self._shutdown_in_progress = True
        try:
            self.stop_trading()

            if self.telegram:
                self.telegram.stop()
            if self.sound:
                self.sound.stop()
            if hasattr(self, "tray_icon"):
                self.tray_icon.hide()

            has_pending_history_save = bool(
                getattr(self, "_history_save_inflight", False)
                or getattr(self, "_history_save_pending_snapshot", None) is not None
            )
            if self._history_dirty or has_pending_history_save:
                if hasattr(self, "_flush_trade_history_on_exit"):
                    self._flush_trade_history_on_exit()
                else:
                    cfg = getattr(self, "config", None)
                    flush_sync = bool(
                        getattr(
                            cfg,
                            "sync_history_flush_on_exit",
                            getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True),
                        )
                    )
                    if flush_sync and hasattr(self, "_save_trade_history_sync"):
                        self._save_trade_history_sync()
                    else:
                        self._save_trade_history()

            event.accept()
        finally:
            self._force_quit_requested = False
