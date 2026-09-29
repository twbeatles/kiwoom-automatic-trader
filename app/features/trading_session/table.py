"""Trading session lifecycle mixin for KiwoomProTrader."""

from collections import deque
import datetime
import time
from typing import Any, Deque, Dict, List, Literal, Optional, Tuple, overload

from PyQt6.QtCore import QCoreApplication, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem

from app.support.worker import Worker
from config import Config
from app.support.theme import table_status_color
from app.mixins._typing import TraderMixinBase


BackgroundUniversePayload = Tuple[List[str], Dict[str, Dict[str, Any]], List[str]]


class TradingSessionTableMixin(TraderMixinBase):
    def _update_row(self, row, code):
        if row < 0:
            return
        info = self.universe.get(code, {})
        profit_rate = 0.0
        if info.get("held", 0) > 0 and info.get("buy_price", 0) > 0:
            profit_rate = (info["current"] - info["buy_price"]) / info["buy_price"] * 100

        data = [
            info.get("name", code),
            f"{info.get('current', 0):,}",
            f"{info.get('target', 0):,}",
            info.get("status", ""),
            str(info.get("held", 0)),
            f"{info.get('buy_price', 0):,}",
            f"{profit_rate:.2f}%",
            f"{info.get('max_profit_rate', 0):.2f}%",
            f"{info.get('invest_amount', 0):,}",
        ]
        _theme = str(getattr(self, "current_theme", "dark") or "dark")
        for col, text in enumerate(data):
            text_str = str(text)
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem(text_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
            elif item.text() != text_str:
                item.setText(text_str)

            if col == 6:
                if profit_rate > 0:
                    item.setForeground(QColor(table_status_color(_theme, "profit_up")))
                elif profit_rate < 0:
                    item.setForeground(QColor(table_status_color(_theme, "profit_down")))
    def _refresh_table(self):
        if not self.universe or not self._dirty_codes:
            return

        if "__all__" in self._dirty_codes:
            codes_to_update = list(self.universe.keys())
            self._dirty_codes.clear()
        else:
            codes_to_update = []
            limit = max(1, int(Config.TABLE_BATCH_LIMIT))
            while self._dirty_codes and len(codes_to_update) < limit:
                code = self._dirty_codes.pop()
                if code in self.universe:
                    codes_to_update.append(code)

        if not codes_to_update:
            return

        if len(self._code_to_row) != len(self.universe):
            self.table.setRowCount(len(self.universe))
            self._code_to_row = {code: idx for idx, code in enumerate(self.universe.keys())}

        self.table.setUpdatesEnabled(False)
        try:
            for code in codes_to_update:
                row = self._code_to_row.get(code)
                if row is None:
                    self._code_to_row = {c: idx for idx, c in enumerate(self.universe.keys())}
                    row = self._code_to_row.get(code)
                if row is not None:
                    self._update_row(row, code)
        finally:
            self.table.setUpdatesEnabled(True)
    def _emergency_liquidate(self):
        """긴급 전체 청산."""
        if not self.is_connected:
            self.log("API 연결 필요")
            return

        holding_targets = self._collect_liquidation_targets()
        holding_count = len(holding_targets)
        if holding_count == 0:
            QMessageBox.information(self, "알림", "청산할 보유 종목이 없습니다.")
            return

        confirm = QMessageBox.warning(
            self,
            "긴급 청산 확인",
            f"보유 중인 {holding_count}개 종목을 모두 시장가로 청산합니다.\n\n"
            "이 작업은 되돌릴 수 없습니다.\n정말 실행하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            live_guard_required = getattr(self, "_manual_order_live_guard_required", None)
            if callable(live_guard_required) and bool(live_guard_required()):
                confirm_guard = getattr(self, "_confirm_live_trading_guard", None)
                if callable(confirm_guard) and not bool(confirm_guard()):
                    return
            self._set_trading_stopped_state()
            submitted = [False]

            def _proceed(_result=None):
                if submitted[0]:
                    return
                submitted[0] = True
                self._submit_emergency_sells()

            starter = getattr(self, "_cleanup_active_orders_async", None)
            if callable(starter):
                try:
                    if bool(starter("emergency_liquidate", on_done=_proceed)):
                        return
                except Exception as exc:
                    self.log(f"긴급청산 정리 비동기 실행 실패, 동기 경로로 계속: {exc}")
            if not submitted[0]:
                self._cleanup_active_orders("emergency_liquidate")
                _proceed()
    def _submit_emergency_sells(self):
        """긴급청산 매도 제출. 결과는 매도 콜백에서 집계 보고한다."""
        if getattr(self, "_emergency_sells_token", None) is not None:
            return
        self._emergency_sells_token = True
        try:
            holding_targets = self._collect_liquidation_targets()
            batch = {}
            for code, info in holding_targets:
                held = int(info.get("held", 0) or 0)
                if held > 0:
                    batch[code] = {
                        "name": str(info.get("name", code) or code),
                        "qty": held,
                        "settled": False,
                        "ok": False,
                        "detail": "",
                    }
            self._liquidation_batch = batch
            liquidated_count = 0
            for code, info in holding_targets:
                held = int(info.get("held", 0) or 0)
                if held > 0:
                    name = info.get("name", code)
                    current = info.get("current", 0)
                    self.log(f"  - {name} {held}주 청산 중...")
                    self._execute_sell(code, held, current, "긴급청산")
                    liquidated_count += 1

            if getattr(self, "sound", None):
                self.sound.play_warning()
            if getattr(self, "telegram", None):
                self.telegram.send(f"긴급 전체 청산 시작: {liquidated_count}개 종목")

            self.log(f"긴급 청산 요청 {liquidated_count}건 제출 (결과 집계 중)")
            if liquidated_count == 0:
                self._liquidation_batch = {}
                return
            try:
                from PyQt6.QtCore import QTimer as _QTimer

                _QTimer.singleShot(30000, self._sweep_liquidation_batch)
            except Exception:
                pass
        finally:
            self._emergency_sells_token = None
    def _sweep_liquidation_batch(self):
        """장시간 미결착 긴급청산 항목을 타임아웃으로 마감."""
        batch = getattr(self, "_liquidation_batch", None)
        if not isinstance(batch, dict) or not batch:
            return
        pending = [c for c, v in batch.items() if isinstance(v, dict) and not v.get("settled")]
        if not pending:
            return
        for code in pending:
            self._note_liquidation_settlement(code, False, "결과 미확인(타임아웃)")
