"""KiwoomProTrader mixin module (refactored)."""

import csv
import datetime
import json
import logging
import os
import sys
import time
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import keyring
from PyQt6.QtCore import *
from PyQt6.QtGui import QColor, QFont, QTextCursor, QIcon, QAction, QShortcut, QKeySequence
from PyQt6.QtWidgets import *

from api import KiwoomAuth, KiwoomRESTClient, KiwoomWebSocketClient
from api.models import ExecutionData, OrderType, PriceType, StockQuote
from app.support.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox
from app.support.worker import Worker
from config import Config
from dark_theme import DARK_STYLESHEET
from light_theme import LIGHT_STYLESHEET
from ui_dialogs import (
    HelpDialog,
    ManualOrderDialog,
    PresetDialog,
    ProfileManagerDialog,
    ScheduleDialog,
    StockSearchDialog,
)

class SystemShellMixin:
    def _setup_logging(self):
        Path(Config.LOG_DIR).mkdir(exist_ok=True)
        self.logger = logging.getLogger('KiwoomTrader')
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(Path(Config.LOG_DIR) / f"trader_{datetime.datetime.now():%Y%m%d}.log", encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)

    def _set_auto_start(self, enabled):
        """윈도우 시작 레지스트리 등록/해제"""
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
        except Exception as e:
            self.logger.error(f"자동 실행 설정 오류: {e}")
            QMessageBox.warning(self, "오류", f"레지스트리 설정 실패: {e}")
            self.chk_auto_start.setChecked(not enabled)  # 롤백

    def _create_menu(self):
        menubar = self.menuBar()
        
        # 파일
        file_menu = menubar.addMenu("파일")
        file_menu.addAction("💾 설정 저장", self._save_settings)
        file_menu.addAction("📂 설정 불러오기", self._load_settings)
        file_menu.addSeparator()
        file_menu.addAction("📤 거래내역 내보내기", self._export_csv)
        file_menu.addSeparator()
        file_menu.addAction("종료", self.close)
        
        # 매매 (v4.3 신규)
        trading_menu = menubar.addMenu("매매")
        trading_menu.addAction("🚀 매매 시작", self.start_trading)
        trading_menu.addAction("⏹️ 매매 중지", self.stop_trading)
        trading_menu.addSeparator()
        trading_menu.addAction("🚨 긴급 전체 청산", self._emergency_liquidate)
        trading_menu.addSeparator()
        trading_menu.addAction("📝 수동 주문", self._open_manual_order)
        
        # 도구
        tools_menu = menubar.addMenu("도구")
        tools_menu.addAction("📋 프리셋 관리", self._open_presets)
        tools_menu.addAction("👤 프로필 관리", self._open_profile_manager)
        tools_menu.addSeparator()
        tools_menu.addAction("🔍 종목 검색", self._open_stock_search)
        tools_menu.addAction("⏰ 예약 매매", self._open_schedule)
        tools_menu.addSeparator()
        tools_menu.addAction("🔄 계좌 새로고침", lambda: self._on_account_changed(self.current_account))
        
        # 보기 (v4.3 신규)
        view_menu = menubar.addMenu("보기")
        view_menu.addAction("🌓 테마 전환", self._toggle_theme)
        view_menu.addSeparator()
        view_menu.addAction("🔊 사운드 켜기/끄기", self._toggle_sound)
        
        # 도움말
        help_menu = menubar.addMenu("도움말")
        help_menu.addAction("📚 사용 가이드", lambda: HelpDialog(self).exec())
        help_menu.addAction("⌨️ 단축키 목록", self._show_shortcuts)
        help_menu.addSeparator()
        help_menu.addAction("ℹ️ 버전 정보", lambda: QMessageBox.information(self, "정보", "Kiwoom Pro Algo-Trader v4.3\nREST API 기반 + 확장 기능"))

    def _create_tray(self):
        """시스템 트레이 아이콘 생성"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png")) # 아이콘 파일이 없다면 기본 아이콘 사용될 수 있음
        self.tray_icon.setToolTip("Kiwoom Pro Algo-Trader v4.4")
        
        tray_menu = QMenu()
        
        action_show = QAction("열기", self)
        action_show.triggered.connect(self.showNormal)
        tray_menu.addAction(action_show)
        
        tray_menu.addSeparator()
        
        action_quit = QAction("종료", self)
        action_quit.triggered.connect(self._force_quit) # 강제 종료 메서드 연결
        tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray_icon.show()

    def _force_quit(self):
        """트레이 메뉴에서 '종료' 선택 시 완전히 프로그램 종료"""
        reply = QMessageBox.question(self, "종료 확인", 
                                   "프로그램을 완전히 종료하시겠습니까?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.stop_trading()
            # 리소스 정리
            if self.telegram: self.telegram.stop()
            if self.sound: self.sound.stop()
            self.tray_icon.hide()
            QApplication.quit()

    def _setup_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(1000)

    def _on_timer(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        self.status_time.setText(time_str)
        
        if self.is_running:
            self.status_trading.setText("🚀 매매 중")
            self.status_trading.setObjectName("tradingActive")
            self.status_trading.setStyleSheet("""
                color: #3fb950;
                font-weight: bold;
                padding: 4px 12px;
                background: rgba(63, 185, 80, 0.15);
                border-radius: 10px;
                border: 1px solid rgba(63, 185, 80, 0.3);
            """)
        else:
            self.status_trading.setText("⏸️ 대기 중")
            self.status_trading.setObjectName("tradingOff")
            self.status_trading.setStyleSheet("""
                color: #8b949e;
                font-weight: bold;
                padding: 4px 12px;
                background: rgba(48, 54, 61, 0.5);
                border-radius: 10px;
            """)
        
        # 예약 매매 스케줄 체크 (v4.3)
        if self.schedule.get('enabled', False) and self.is_connected:
            current_time = now.strftime("%H:%M")
            start_time = self.schedule.get('start', '09:00')
            end_time = self.schedule.get('end', '15:19')
            
            # 예약 시작 시간 체크
            if not self.is_running and not self.schedule_started:
                if current_time >= start_time and current_time < end_time:
                    self.log(f"⏰ 예약 매매 시작: {start_time}")
                    self.schedule_started = True
                    self.start_trading()
            
            # 예약 종료 시간 체크
            if self.is_running and self.schedule_started:
                if current_time >= end_time:
                    self.log(f"⏰ 예약 매매 종료: {end_time}")
                    if self.schedule.get('liquidate', True):
                        self._time_liquidate()
                    self.stop_trading()
                    self.schedule_started = False
        
        if not self.is_running:
            return

        # 매매 중 계좌 정보 주기 동기화 (예수금/손익 신선도 유지)
        self._refresh_account_info_async()
        
        # 시간 청산 체크 (15:19) - 중복 방지
        if not self.time_liquidate_executed:
            if now.hour == Config.MARKET_CLOSE_HOUR and now.minute >= Config.MARKET_CLOSE_MINUTE:
                self.time_liquidate_executed = True
                self._time_liquidate()
        
        # 일일 손실 한도 체크
        if self.chk_use_risk.isChecked() and not self.daily_loss_triggered and self.initial_deposit > 0:
            loss_rate = (self.total_realized_profit / self.initial_deposit) * 100
            if loss_rate <= -self.spin_max_loss.value():
                self.daily_loss_triggered = True
                self.log(f"⚠️ 일일 손실 한도 도달 ({loss_rate:.2f}%) - 매매 중지")
                self.stop_trading()
        
        # 지연된 거래 내역 저장
        if self._history_dirty:
            self._save_trade_history()
            self._history_dirty = False

    def _setup_shortcuts(self):
        """키보드 단축키 설정"""
        shortcuts = [
            (Config.SHORTCUTS.get('connect', 'Ctrl+L'), self.connect_api),
            (Config.SHORTCUTS.get('start_trading', 'Ctrl+S'), self.start_trading),
            (Config.SHORTCUTS.get('stop_trading', 'Ctrl+Q'), self.stop_trading),
            (Config.SHORTCUTS.get('emergency_stop', 'Ctrl+Shift+X'), self._emergency_liquidate),
            (Config.SHORTCUTS.get('refresh', 'F5'), lambda: self._on_account_changed(self.current_account)),
            (Config.SHORTCUTS.get('export_csv', 'Ctrl+E'), self._export_csv),
            (Config.SHORTCUTS.get('open_presets', 'Ctrl+P'), self._open_presets),
            (Config.SHORTCUTS.get('toggle_theme', 'Ctrl+T'), self._toggle_theme),
            (Config.SHORTCUTS.get('show_help', 'F1'), lambda: HelpDialog(self).exec()),
            (Config.SHORTCUTS.get('search_stock', 'Ctrl+F'), self._open_stock_search),
            (Config.SHORTCUTS.get('manual_order', 'Ctrl+O'), self._open_manual_order),
        ]
        
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)

    def _toggle_theme(self):
        """다크/라이트 테마 전환"""
        if self.current_theme == 'dark':
            self.current_theme = 'light'
            self.setStyleSheet(LIGHT_STYLESHEET)
            self.log("🌞 라이트 테마 적용")
        else:
            self.current_theme = 'dark'
            self.setStyleSheet(DARK_STYLESHEET)
            self.log("🌙 다크 테마 적용")

    def _toggle_sound(self):
        """사운드 켜기/끄기"""
        if self.sound:
            current = self.sound.enabled
            self.sound.set_enabled(not current)
            self.chk_use_sound.setChecked(not current)
            self.log(f"🔊 사운드 {'켜짐' if not current else '꺼짐'}")

    def _on_sound_changed(self, state):
        """사운드 체크박스 변경 시"""
        if self.sound:
            self.sound.set_enabled(state == Qt.CheckState.Checked.value)

    def _show_shortcuts(self):
        """단축키 목록 표시"""
        shortcuts_text = "\n".join([
            "⌨️ 키보드 단축키",
            "",
            f"  Ctrl+L: API 연결",
            f"  Ctrl+S: 매매 시작",
            f"  Ctrl+Q: 매매 중지",
            f"  Ctrl+Shift+X: 긴급 청산",
            f"  Ctrl+F: 종목 검색",
            f"  Ctrl+O: 수동 주문",
            f"  Ctrl+P: 프리셋 관리",
            f"  Ctrl+E: CSV 내보내기",
            f"  Ctrl+T: 테마 전환",
            f"  F5: 새로고침",
            f"  F1: 도움말",
        ])
        QMessageBox.information(self, "단축키 목록", shortcuts_text)

    def log(self, msg):
        self.sig_log.emit(msg)
        self.logger.info(msg)

    def _append_log(self, msg):
        timestamp = f"[{datetime.datetime.now():%H:%M:%S}]"
        
        # 로그 레벨별 색상 및 배지
        if "❌" in msg or "실패" in msg or "오류" in msg:
            color = "#f85149"  # Red (Error)
            badge_style = "color: #f85149; font-weight: bold;"
            level_mark = "ERR"
        elif "⚠️" in msg or "경고" in msg:
            color = "#d29922"  # Orange (Warning)
            badge_style = "color: #d29922; font-weight: bold;"
            level_mark = "WRN"
        elif "✅" in msg or "성공" in msg or "완료" in msg or "🚀" in msg:
            color = "#3fb950"  # Green (Success)
            badge_style = "color: #3fb950; font-weight: bold;"
            level_mark = "SUC"
        elif "⭐" in msg or "프리셋" in msg:
            color = "#58a6ff"  # Blue (Info/Notice)
            badge_style = "color: #58a6ff; font-weight: bold;"
            level_mark = "INF"
        else:
            color = "#e6edf3"  # Default
            badge_style = "color: #8b949e;"
            level_mark = "INF"
        
        # HTML 포맷팅 (타임스탬프 | 레벨 | 메시지)
        html = f"""
        <div style="margin-bottom: 2px;">
            <span style="color: #8b949e; font-family: monospace;">{timestamp}</span>
            <span style="{badge_style} margin-left: 4px; margin-right: 4px;">[{level_mark}]</span>
            <span style="color: {color};">{msg}</span>
        </div>
        """
        
        self.log_text.append(html)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        # 로그 제한 (줄 수 대신 블록 수로 관리)
        if self.log_text.document().blockCount() > Config.MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(50):  # 한 번에 50줄 삭제
                cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

    def closeEvent(self, event):
        # 트레이 최소화 옵션이 켜져있으면 숨기기만 함
        if hasattr(self, 'chk_minimize_tray') and self.chk_minimize_tray.isChecked():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("Kiwoom Pro Trader", 
                                     "프로그램이 백그라운드에서 실행 중입니다.\n트레이 아이콘을 더블클릭하여 다시 열 수 있습니다.",
                                     QSystemTrayIcon.MessageIcon.Information, 2000)
            return

        # 매매 중일 때 종료 시 확인
        if self.is_running:
            reply = QMessageBox.question(self, "종료 확인", 
                                       "현재 매매가 진행 중입니다.\n강제로 종료하시겠습니까?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        self.stop_trading()
        
        # 리소스 정리
        if self.telegram:
            self.telegram.stop()
        if self.sound:
            self.sound.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            
        # 미저장 데이터 저장
        if self._history_dirty:
            self._save_trade_history()
            
        event.accept()

