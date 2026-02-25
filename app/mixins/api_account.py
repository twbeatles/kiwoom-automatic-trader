"""API/account connection and refresh mixin for KiwoomProTrader."""

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from api import KiwoomAuth, KiwoomRESTClient, KiwoomWebSocketClient
from app.support.worker import Worker
from config import Config
from telegram_notifier import TelegramNotifier


class APIAccountMixin:
    def connect_api(self):
        if getattr(self, "_connect_inflight", False):
            self.log("API 연결이 이미 진행 중입니다.")
            return

        app_key = self.input_app_key.text().strip()
        secret_key = self.input_secret.text().strip()
        is_mock = self.chk_mock.isChecked()

        if not app_key or not secret_key:
            tabs = self.centralWidget().findChild(QTabWidget)
            if tabs:
                tabs.setCurrentIndex(8)

            self.input_app_key.setStyleSheet("border: 2px solid #ff5555;" if not app_key else "")
            self.input_secret.setStyleSheet("border: 2px solid #ff5555;" if not secret_key else "")
            QMessageBox.warning(self, "경고", "API 연동을 위해 App Key와 Secret Key를 입력해주세요.")
            return

        self.input_app_key.setStyleSheet("")
        self.input_secret.setStyleSheet("")
        self.btn_start.setEnabled(False)
        self._connect_inflight = True
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("API 연결 중...")
        self.log("API 연결 시도...")
        self._set_connection_status("API 연결 중...", "connecting")

        worker = Worker(self._connect_api_worker, app_key, secret_key, is_mock)
        worker.signals.result.connect(self._on_connect_api_success)
        worker.signals.error.connect(self._on_connect_api_failure)
        self.threadpool.start(worker)

    def _connect_api_worker(self, app_key: str, secret_key: str, is_mock: bool):
        auth = KiwoomAuth(app_key, secret_key, is_mock)
        result = auth.test_connection()
        if not result.get("success"):
            raise RuntimeError(result.get("message", "인증 실패"))

        rest_client = KiwoomRESTClient(auth)
        ws_client = KiwoomWebSocketClient(auth)
        accounts = rest_client.get_account_list()
        if not accounts:
            raise RuntimeError("계좌 목록이 비어 있습니다. 계좌 권한/연결 상태를 확인해주세요.")
        return {
            "auth": auth,
            "rest_client": rest_client,
            "ws_client": ws_client,
            "accounts": accounts,
        }

    def _finalize_connect_ui(self):
        self._connect_inflight = False
        if hasattr(self, "btn_connect"):
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("API 연결")

    def _on_connect_api_success(self, payload):
        try:
            self.auth = payload["auth"]
            self.rest_client = payload["rest_client"]
            self.ws_client = payload["ws_client"]

            self.combo_acc.blockSignals(True)
            self.combo_acc.clear()
            self.combo_acc.addItems(payload["accounts"])
            self.combo_acc.blockSignals(False)

            self.is_connected = True
            self.btn_start.setEnabled(True)
            self._set_connection_status("API 연결됨", "connected")
            self.log("API 연결 성공")

            if self.combo_acc.count() > 0:
                self._on_account_changed(self.combo_acc.currentText())

            if self.chk_use_telegram.isChecked():
                self.telegram = TelegramNotifier(self.input_tg_token.text(), self.input_tg_chat.text())
                self.telegram.send("Kiwoom Trader 연결됨")
        except Exception as exc:
            self._reset_connection_state()
            self._set_connection_status("API 연결 실패", "disconnected")
            self.log(f"API 연결 후처리 실패: {exc}")
            QMessageBox.warning(self, "연결 실패", f"연결 후처리 중 오류가 발생했습니다.\n{exc}")
        finally:
            self._finalize_connect_ui()

    def _on_connect_api_failure(self, error):
        self._reset_connection_state()
        self._set_connection_status("API 연결 실패", "disconnected")
        message = str(error)
        lower_message = message.lower()

        if any(token in lower_message for token in ("401", "403", "invalid", "unauthorized", "forbidden", "auth")):
            user_guide = "인증에 실패했습니다. App Key/Secret Key를 다시 확인해주세요."
        elif any(token in lower_message for token in ("계좌 목록", "accounts", "empty account")):
            user_guide = "계좌 목록을 가져오지 못했습니다. API 계좌 권한/상품 신청 상태를 확인해주세요."
        elif any(token in lower_message for token in ("timeout", "network", "connection", "dns", "timed out")):
            user_guide = "네트워크 연결에 실패했습니다. 인터넷/방화벽 상태를 확인해주세요."
        else:
            user_guide = "API 연결 중 오류가 발생했습니다. 로그를 확인하고 다시 시도해주세요."

        self.log(f"API 연결 실패: {message}")
        QMessageBox.warning(self, "연결 실패", f"{user_guide}\n\n원인: {message}")
        self._finalize_connect_ui()

    def _set_connection_status(self, text: str, mode: str):
        self.lbl_status.setText(text)
        if mode == self._last_connection_mode:
            return

        self._last_connection_mode = mode
        if mode == "connected":
            self.lbl_status.setObjectName("statusConnected")
            self.lbl_status.setStyleSheet(
                """
                color: #3fb950;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                background: rgba(63, 185, 80, 0.15);
                border-radius: 14px;
                border: 1px solid rgba(63, 185, 80, 0.3);
                """
            )
        elif mode == "connecting":
            self.lbl_status.setObjectName("statusConnecting")
            self.lbl_status.setStyleSheet("color: #ffc107;")
        else:
            self.lbl_status.setObjectName("statusDisconnected")
            self.lbl_status.setStyleSheet(
                """
                color: #f85149;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                background: rgba(248, 81, 73, 0.15);
                border-radius: 14px;
                border: 1px solid rgba(248, 81, 73, 0.3);
                """
            )

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
        self._connect_inflight = False
        self._last_connection_mode = None
        self._last_profit_sign = None
        if hasattr(self, "_reserved_cash_by_code"):
            self._reserved_cash_by_code.clear()
        if hasattr(self, "_diagnostics_by_code"):
            self._diagnostics_by_code.clear()
        if hasattr(self, "_diagnostics_dirty_codes"):
            self._diagnostics_dirty_codes.clear()
        if hasattr(self, "btn_connect"):
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("API 연결")

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
        worker.signals.error.connect(lambda error, acc=account: self._on_account_info_error(acc, error))
        self.threadpool.start(worker)

    def _on_account_info_result(self, account: str, info):
        self._account_refresh_pending = False
        if account != self.current_account or not info:
            return

        available_amount = int(getattr(info, "available_amount", 0) or getattr(info, "deposit", 0) or 0)
        total_eval_amount = int(getattr(info, "total_eval_amount", 0) or 0)
        computed_equity = available_amount + max(0, total_eval_amount)
        if computed_equity <= 0:
            computed_equity = available_amount

        self.deposit = available_amount
        self.total_equity = max(0, int(computed_equity))
        self.initial_deposit = self.initial_deposit or self.total_equity or self.deposit

        # Virtual deposit is always real deposit minus active reserved cash.
        reserved_map = getattr(self, "_reserved_cash_by_code", {})
        reserved_total = 0
        if isinstance(reserved_map, dict):
            reserved_total = sum(max(0, int(v or 0)) for v in reserved_map.values())
        self.virtual_deposit = max(0, int(self.deposit) - int(reserved_total))

        # 일일 기준 예수금이 비어 있으면 즉시 확보 (start_trading 시점 정합성 보장)
        if int(getattr(self, "daily_initial_deposit", 0) or 0) <= 0:
            cfg = getattr(self, "config", None)
            basis = str(getattr(cfg, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")))
            basis_amount = self.total_equity if basis == "total_equity" else int(self.deposit)
            if basis_amount <= 0:
                basis_amount = int(self.deposit)
            self.daily_initial_deposit = basis_amount
            
        self.lbl_deposit.setText(
            f"예수금(V) {self.virtual_deposit:,} 원 / (실) {self.deposit:,} 원 / 총자산 {self.total_equity:,} 원"
        )

        profit = info.total_profit
        self.lbl_profit.setText(f"손익: {profit:+,} 원")
        sign = 1 if profit > 0 else (-1 if profit < 0 else 0)
        if sign == self._last_profit_sign:
            return

        self._last_profit_sign = sign
        if sign > 0:
            self.lbl_profit.setStyleSheet(
                """
                color: #3fb950;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                background: rgba(63, 185, 80, 0.15);
                border-radius: 10px;
                border: 1px solid rgba(63, 185, 80, 0.2);
                """
            )
        elif sign < 0:
            self.lbl_profit.setStyleSheet(
                """
                color: #f85149;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                background: rgba(248, 81, 73, 0.15);
                border-radius: 10px;
                border: 1px solid rgba(248, 81, 73, 0.2);
                """
            )
        else:
            self.lbl_profit.setStyleSheet(
                """
                color: #e6edf3;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                background: rgba(139, 148, 158, 0.1);
                border-radius: 10px;
                border: 1px solid rgba(139, 148, 158, 0.2);
                """
            )

    def _on_account_info_error(self, account: str, error: Exception):
        self._account_refresh_pending = False
        if account != self.current_account:
            return
        self.logger.warning(f"계좌 정보 갱신 실패 [{account}]: {error}")

    def _confirm_live_trading_guard(self) -> bool:
        """실거래 시작 전 보호 확인."""
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
            self.log("실거래 보호 확인 실패 또는 시간 초과로 시작이 차단되었습니다.")
        return ok
