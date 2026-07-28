"""Persistence/settings mixin for KiwoomProTrader."""

import copy
import csv
import datetime
import json
import os
from pathlib import Path

try:
    import keyring
    KEYRING_AVAILABLE = True
except ModuleNotFoundError:
    KEYRING_AVAILABLE = False

    class _NoopKeyring:
        @staticmethod
        def set_password(service_name, username, password):
            return None

        @staticmethod
        def get_password(service_name, username):
            return None

        @staticmethod
        def delete_password(service_name, username):
            return None

    keyring = _NoopKeyring()
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from app.support.ui_text import combo_value, set_combo_value
from app.support.worker import Worker
from config import Config
from dark_theme import DARK_STYLESHEET
from light_theme import LIGHT_STYLESHEET
from app.mixins._typing import TraderMixinBase


class PersistenceTradeHistoryMixin(TraderMixinBase):
    def _add_trade(self, record: dict):
        """거래 기록 추가."""
        record["timestamp"] = datetime.datetime.now().isoformat()
        self.trade_history.append(record)
        self._history_dirty = True
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if hasattr(self, "history_table") and record["timestamp"].startswith(today):
            self.history_table.insertRow(0)
            time_str = record["timestamp"].split("T")[-1][:8]
            items = [
                time_str,
                record.get("name", record.get("code", "")),
                record.get("type", ""),
                f"{record.get('price', 0):,}",
                str(record.get("quantity", 0)),
                f"{record.get('amount', 0):,}",
                f"{record.get('profit', 0):+,}",
                record.get("reason", ""),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6:
                    item.setForeground(QColor("#e63946" if record.get("profit", 0) > 0 else "#4361ee"))
                self.history_table.setItem(0, col, item)
        else:
            self._refresh_history_table()

        if record.get("type") == "매수":
            self.trade_count += 1
        if record.get("profit", 0) > 0:
            self.win_count += 1
        self.total_realized_profit += record.get("profit", 0)
        if record.get("type") == "매도":
            self.daily_realized_profit = int(getattr(self, "daily_realized_profit", 0) or 0) + int(
                record.get("profit", 0) or 0
            )
            # 매도 체결 누적 직후 일일 손실 한도를 즉시 평가하여 다음 timer tick 전 진입을 차단.
            check_fn = getattr(self, "_check_daily_loss_limit", None)
            if callable(check_fn):
                check_fn()
    def _refresh_history_table(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_history = [r for r in self.trade_history if r.get("timestamp", "").startswith(today)]

        self.history_table.setUpdatesEnabled(False)
        try:
            self.history_table.setRowCount(len(today_history))
            for row, record in enumerate(reversed(today_history)):
                timestamp = record.get("timestamp", "")
                time_str = timestamp.split("T")[-1][:8] if "T" in timestamp else timestamp
                items = [
                    time_str,
                    record.get("name", record.get("code", "")),
                    record.get("type", ""),
                    f"{record.get('price', 0):,}",
                    str(record.get("quantity", 0)),
                    f"{record.get('amount', 0):,}",
                    f"{record.get('profit', 0):+,}",
                    record.get("reason", ""),
                ]
                for col, text in enumerate(items):
                    text_str = str(text)
                    item = self.history_table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(text_str)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.history_table.setItem(row, col, item)
                    elif item.text() != text_str:
                        item.setText(text_str)
                    if col == 6:
                        item.setForeground(QColor("#e63946" if record.get("profit", 0) > 0 else "#4361ee"))
        finally:
            self.history_table.setUpdatesEnabled(True)
        if hasattr(self, "stats_labels"):
            self._update_stats()
    def _export_csv(self):
        if not self.trade_history:
            QMessageBox.information(self, "알림", "내보낼 내역이 없습니다.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "CSV 저장",
            f"trades_{datetime.datetime.now():%Y%m%d}.csv",
            "CSV (*.csv)",
        )
        if filename:
            with open(filename, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["시간", "코드", "종목", "구분", "가격", "수량", "금액", "손익", "사유"])
                for record in self.trade_history:
                    writer.writerow(
                        [
                            record.get("timestamp"),
                            record.get("code"),
                            record.get("name"),
                            record.get("type"),
                            record.get("price"),
                            record.get("quantity"),
                            record.get("amount"),
                            record.get("profit"),
                            record.get("reason"),
                        ]
                    )
            self.log(f"📤 CSV 저장: {filename}")
    def _clear_today_history(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        count = sum(1 for r in self.trade_history if r.get("timestamp", "").startswith(today))
        if count == 0:
            return
        if QMessageBox.question(self, "확인", f"오늘 기록 {count}건 삭제?") == QMessageBox.StandardButton.Yes:
            self.trade_history = [r for r in self.trade_history if not r.get("timestamp", "").startswith(today)]
            self._save_trade_history()
            self._refresh_history_table()
    def _update_stats(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_trades = [r for r in self.trade_history if r.get("timestamp", "").startswith(today)]
        sells = [r for r in today_trades if r.get("type") == "매도"]

        wins = sum(1 for r in sells if r.get("profit", 0) > 0)
        total_profit = sum(r.get("profit", 0) for r in sells)
        profits = [r.get("profit", 0) for r in sells]

        self.stats_labels["trades"].setText(str(len(today_trades)))
        self.stats_labels["wins"].setText(f"{wins}/{len(sells)}")
        self.stats_labels["winrate"].setText(f"{wins / len(sells) * 100:.1f}%" if sells else "-")
        self.stats_labels["profit"].setText(f"{total_profit:+,} 원")
        self.stats_labels["max_profit"].setText(f"{max(profits):+,}" if profits else "-")
        self.stats_labels["max_loss"].setText(f"{min(profits):+,}" if profits else "-")
    def _load_trade_history(self):
        """거래 내역 로드."""
        try:
            if os.path.exists(Config.TRADE_HISTORY_FILE):
                with open(Config.TRADE_HISTORY_FILE, "r", encoding="utf-8") as file:
                    self.trade_history = json.load(file)
        except json.JSONDecodeError as exc:
            self.logger.warning(f"거래 내역 파싱 실패: {exc}")
            self.trade_history = []
        except OSError as exc:
            self.logger.warning(f"거래 내역 로드 실패: {exc}")
    def _save_trade_history(self):
        """거래 내역 저장 (single-writer 비동기)."""
        history_snapshot = list(self.trade_history)

        if not hasattr(self, "threadpool"):
            # 테스트/동기 환경 대응
            self._save_trade_history_sync(history_snapshot)
            return

        self._history_save_pending_snapshot = history_snapshot
        if bool(getattr(self, "_history_save_inflight", False)):
            return
        self._start_next_trade_history_save()
    def _start_next_trade_history_save(self):
        if bool(getattr(self, "_history_save_inflight", False)):
            return

        snapshot = getattr(self, "_history_save_pending_snapshot", None)
        if snapshot is None:
            return
        self._history_save_pending_snapshot = None
        self._history_save_inflight = True

        worker = Worker(self._save_trade_history_worker, list(snapshot))
        worker.signals.result.connect(lambda _res=None: self._on_trade_history_save_done(success=True, error=None))
        worker.signals.error.connect(lambda err: self._on_trade_history_save_done(success=False, error=err))
        self.threadpool.start(worker)
    def _save_trade_history_worker(self, history: list):
        """실제 파일 IO 수행 워커"""
        self._atomic_write_json(Config.TRADE_HISTORY_FILE, history)
    def _on_trade_history_save_done(self, success: bool, error=None):
        self._history_save_inflight = False
        if not success:
            self._history_dirty = True
            if error is not None:
                self.logger.error(f"거래 내역 저장 실패: {error}")
            # Keep latest pending snapshot queued for next timer/flush cycle.
            return

        if getattr(self, "_history_save_pending_snapshot", None) is not None:
            self._start_next_trade_history_save()
            return
        self._history_dirty = False
    def _save_trade_history_sync(self, history_snapshot=None):
        """동기 거래 내역 저장 (테스트용)"""
        try:
            payload = list(self.trade_history) if history_snapshot is None else list(history_snapshot)
            self._atomic_write_json(Config.TRADE_HISTORY_FILE, payload)
            self._history_dirty = False
            self._history_save_pending_snapshot = None
            self._history_save_inflight = False
        except OSError as exc:
            self.logger.error(f"거래 내역 동기 저장 실패: {exc}")
            self._history_dirty = True
    def _flush_trade_history_on_exit(self):
        if (
            not bool(getattr(self, "_history_dirty", False))
            and getattr(self, "_history_save_pending_snapshot", None) is None
            and not bool(getattr(self, "_history_save_inflight", False))
        ):
            return

        cfg = getattr(self, "config", None)
        flush_sync = bool(
            getattr(
                cfg,
                "sync_history_flush_on_exit",
                getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True),
            )
        )
        latest_snapshot = list(self.trade_history)
        if flush_sync:
            self._save_trade_history_sync(latest_snapshot)
            return

        self._save_trade_history()
        # Exit path hardening: if async save may still be inflight, force sync flush with latest snapshot.
        if bool(getattr(self, "_history_save_inflight", False)) or getattr(self, "_history_save_pending_snapshot", None) is not None:
            self._save_trade_history_sync(latest_snapshot)
