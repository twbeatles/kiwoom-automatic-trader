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
                    item.setForeground(QColor("#e63946"))
                elif profit_rate < 0:
                    item.setForeground(QColor("#4361ee"))
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
            self._set_trading_stopped_state()
            self._cleanup_active_orders("emergency_liquidate")
            holding_targets = self._collect_liquidation_targets()
            self.log("긴급 전체 청산 시작")
            liquidated_count = 0
            for code, info in holding_targets:
                held = info.get("held", 0)
                if held > 0:
                    name = info.get("name", code)
                    current = info.get("current", 0)
                    self.log(f"  - {name} {held}주 청산 중...")
                    self._execute_sell(code, held, current, "긴급청산")
                    liquidated_count += 1

            if self.sound:
                self.sound.play_warning()
            if self.telegram:
                self.telegram.send(f"긴급 전체 청산: {liquidated_count}개 종목")

            self.log(f"긴급 청산 완료: {liquidated_count}개 종목")
