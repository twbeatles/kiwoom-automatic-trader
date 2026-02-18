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

class APIAccountMixin:
    def connect_api(self):
        app_key = self.input_app_key.text().strip()
        secret_key = self.input_secret.text().strip()
        
        if not app_key or not secret_key:
            # API 탭(인덱스 8)으로 이동
            tabs = self.centralWidget().findChild(QTabWidget)
            if tabs:
                tabs.setCurrentIndex(8)
            
            # 입력 필드 강조 (빨간 테두리)
            if not app_key:
                self.input_app_key.setStyleSheet("border: 2px solid #ff5555;")
            else:
                self.input_app_key.setStyleSheet("")
                
            if not secret_key:
                self.input_secret.setStyleSheet("border: 2px solid #ff5555;")
            else:
                self.input_secret.setStyleSheet("")
                
            QMessageBox.warning(self, "경고", "API 연동을 위해 App Key와 Secret Key를 입력해주세요.")
            return
        
        # 입력 스타일 초기화
        self.input_app_key.setStyleSheet("")
        self.input_secret.setStyleSheet("")
        
        self.log("🔄 API 연결 시도...")
        self._set_connection_status("● 연결 중...", "connecting")
        
        try:
            auth = KiwoomAuth(app_key, secret_key, self.chk_mock.isChecked())
            result = auth.test_connection()
            if not result.get("success"):
                raise RuntimeError(result.get("message", "인증 실패"))

            self.auth = auth
            self.rest_client = KiwoomRESTClient(self.auth)
            self.ws_client = KiwoomWebSocketClient(self.auth)

            accounts = self.rest_client.get_account_list()
            self.combo_acc.blockSignals(True)
            self.combo_acc.clear()
            self.combo_acc.addItems(accounts if accounts else ["테스트계좌"])
            self.combo_acc.blockSignals(False)

            self.is_connected = True
            self.btn_start.setEnabled(True)
            self._set_connection_status("● 연결됨", "connected")
            self.log("✅ API 연결 성공")

            if self.combo_acc.count() > 0:
                self._on_account_changed(self.combo_acc.currentText())

            # 텔레그램 초기화
            if self.chk_use_telegram.isChecked():
                self.telegram = TelegramNotifier(self.input_tg_token.text(), self.input_tg_chat.text())
                self.telegram.send("🚀 Kiwoom Trader 연결됨")
        except Exception as e:
            self._reset_connection_state()
            self._set_connection_status("● 연결 실패", "disconnected")
            self.log(f"❌ 오류: {e}")

    def _set_connection_status(self, text: str, mode: str):
        self.lbl_status.setText(text)
        if mode == "connected":
            self.lbl_status.setObjectName("statusConnected")
            self.lbl_status.setStyleSheet("""
                color: #3fb950;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                background: rgba(63, 185, 80, 0.15);
                border-radius: 14px;
                border: 1px solid rgba(63, 185, 80, 0.3);
            """)
        elif mode == "connecting":
            self.lbl_status.setObjectName("statusConnecting")
            self.lbl_status.setStyleSheet("color: #ffc107;")
        else:
            self.lbl_status.setObjectName("statusDisconnected")
            self.lbl_status.setStyleSheet("""
                color: #f85149;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                background: rgba(248, 81, 73, 0.15);
                border-radius: 14px;
                border: 1px solid rgba(248, 81, 73, 0.3);
            """)

    def _reset_connection_state(self):
        if self.ws_client:
            try:
                self.ws_client.unsubscribe_all()
                self.ws_client.disconnect()
            except Exception:
                pass
        self.is_connected = False
        self.auth = None
        self.rest_client = None
        self.ws_client = None
        self.current_account = ""
        self.btn_start.setEnabled(False)
        self._account_refresh_pending = False
        self._last_account_refresh_ts = 0.0

    def _on_account_changed(self, account):
        self.current_account = (account or "").strip()
        self._refresh_account_info_async(force=True)

    def _refresh_account_info_async(self, force: bool = False):
        if not (self.rest_client and self.current_account):
            return
        if self._account_refresh_pending:
            return

        now_ts = time.time()
        if not force and now_ts - self._last_account_refresh_ts < 10:
            return

        account = self.current_account
        self._account_refresh_pending = True
        self._last_account_refresh_ts = now_ts

        worker = Worker(self.rest_client.get_account_info, account)
        worker.signals.result.connect(lambda info, acc=account: self._on_account_info_result(acc, info))
        worker.signals.error.connect(lambda e, acc=account: self._on_account_info_error(acc, e))
        self.threadpool.start(worker)

    def _on_account_info_result(self, account: str, info):
        self._account_refresh_pending = False
        if account != self.current_account or not info:
            return

        self.deposit = info.available_amount
        self.initial_deposit = self.initial_deposit or self.deposit
        self.lbl_deposit.setText(f"💰 예수금: {self.deposit:,} 원")

        profit = info.total_profit
        self.lbl_profit.setText(f"📈 손익: {profit:+,} 원")

        if profit > 0:
            self.lbl_profit.setStyleSheet("""
                color: #3fb950;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                background: rgba(63, 185, 80, 0.15);
                border-radius: 10px;
                border: 1px solid rgba(63, 185, 80, 0.2);
            """)
        elif profit < 0:
            self.lbl_profit.setStyleSheet("""
                color: #f85149;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                background: rgba(248, 81, 73, 0.15);
                border-radius: 10px;
                border: 1px solid rgba(248, 81, 73, 0.2);
            """)
        else:
            self.lbl_profit.setStyleSheet("""
                color: #e6edf3;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                background: rgba(139, 148, 158, 0.1);
                border-radius: 10px;
                border: 1px solid rgba(139, 148, 158, 0.2);
            """)

    def _on_account_info_error(self, account: str, error: Exception):
        self._account_refresh_pending = False
        if account != self.current_account:
            return
        self.logger.warning(f"계좌 정보 갱신 실패 [{account}]: {error}")

    def _confirm_live_trading_guard(self) -> bool:
        """실거래 시작 전 보호 확인"""
        if not Config.LIVE_GUARD_ENABLED or self.chk_mock.isChecked():
            return True

        phrase = Config.LIVE_GUARD_PHRASE
        timeout = max(5, int(Config.LIVE_GUARD_TIMEOUT_SEC))

        dialog = QDialog(self)
        dialog.setWindowTitle("실거래 보호 확인")
        dialog.setModal(True)
        dialog.setFixedSize(460, 220)

        layout = QVBoxLayout(dialog)
        msg = QLabel(
            f"실거래 모드로 시작합니다.\n"
            f"{timeout}초 내에 아래 문구를 정확히 입력해야 시작됩니다.\n\n"
            f"입력 문구: {phrase}"
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        input_phrase = QLineEdit()
        input_phrase.setPlaceholderText("문구를 정확히 입력하세요")
        layout.addWidget(input_phrase)

        countdown = QLabel(f"남은 시간: {timeout}초")
        layout.addWidget(countdown)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("취소")
        btn_ok = QPushButton("확인")
        btn_ok.setEnabled(False)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        state = {"remain": timeout}

        def on_text_changed(text: str):
            btn_ok.setEnabled(text.strip() == phrase)

        def on_timeout():
            state["remain"] -= 1
            if state["remain"] <= 0:
                dialog.reject()
                return
            countdown.setText(f"남은 시간: {state['remain']}초")

        timer = QTimer(dialog)
        timer.timeout.connect(on_timeout)
        timer.start(1000)

        input_phrase.textChanged.connect(on_text_changed)
        btn_cancel.clicked.connect(dialog.reject)
        btn_ok.clicked.connect(dialog.accept)

        ok = dialog.exec() == QDialog.DialogCode.Accepted and input_phrase.text().strip() == phrase
        timer.stop()

        if not ok:
            self.log("🛑 실거래 보호 확인 실패 또는 시간 초과로 시작이 차단되었습니다.")
        return ok

