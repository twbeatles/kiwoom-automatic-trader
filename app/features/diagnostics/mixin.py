"""Diagnostics table and detail panel behavior for KiwoomProTrader."""

import datetime
from typing import Any, Dict, cast

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTableWidgetItem

from app.mixins._typing import TraderMixinBase
from app.support.ui_text import (
    display_action_policy,
    display_exit_policy,
    display_guard_reason,
    display_market_state,
    display_regime,
    display_source_health,
    display_status,
)
from config import Config


def _dict_or_empty(value: object) -> Dict[str, Any]:
    return cast(Dict[str, Any], value) if isinstance(value, dict) else {}


class DiagnosticsMixin(TraderMixinBase):
    def _diag_touch(self, code: str, **fields: Any):
        if not code:
            return
        diag = self._diagnostics_by_code.get(code, {})
        if not diag:
            diag = {
                "pending_side": "",
                "pending_reason": "",
                "pending_until": None,
                "pending_state": "",
                "pending_remaining": "",
                "sync_status": "",
                "retry_count": 0,
                "last_sync_error": "",
                "last_update": datetime.datetime.now(),
            }
            self._diagnostics_by_code[code] = diag

        for key, value in fields.items():
            if key in {"last_update"} and value is None:
                continue
            diag[key] = value
        diag["last_update"] = fields.get("last_update", datetime.datetime.now())
        self._diagnostics_dirty_codes.add(code)
    def _diag_clear_pending(self, code: str):
        if not code:
            return
        self._diag_touch(
            code,
            pending_side="",
            pending_reason="",
            pending_until=None,
            pending_state="",
            pending_remaining="",
        )
    @staticmethod
    def _diag_fmt_dt(value: Any) -> str:
        if isinstance(value, datetime.datetime):
            return value.strftime("%H:%M:%S")
        return ""
    @staticmethod
    def _diag_age_seconds(value: Any) -> str:
        if isinstance(value, datetime.datetime):
            age = int((datetime.datetime.now() - value).total_seconds())
            return str(max(0, age))
        return ""
    def _refresh_diagnostics(self):
        if not hasattr(self, "diagnostic_table"):
            return

        external_positions = _dict_or_empty(getattr(self, "external_positions", {}))
        codes = list(self.universe.keys())
        codes.extend(code for code in sorted(external_positions.keys()) if code not in self.universe)

        if not self._diagnostics_dirty_codes and self.diagnostic_table.rowCount() == len(codes):
            has_external_clock = any(
                isinstance(info.get("external_updated_at"), datetime.datetime)
                for info in self.universe.values()
            )
            has_external_clock = has_external_clock or any(
                isinstance(_dict_or_empty(info).get("external_updated_at"), datetime.datetime)
                for info in external_positions.values()
            )
            if not has_external_clock and not external_positions:
                return

        self.diagnostic_table.setUpdatesEnabled(False)
        try:
            self.diagnostic_table.setRowCount(len(codes))
            row_to_code: Dict[int, str] = {}
            for row, code in enumerate(codes):
                row_to_code[row] = code
                tracked_getter = getattr(self, "_get_tracked_position_info", None)
                raw_info = tracked_getter(code) if callable(tracked_getter) else self.universe.get(code, {})
                info = _dict_or_empty(raw_info)
                market_intel = _dict_or_empty(info.get("market_intel", {}))
                diag = self._diagnostics_by_code.get(code, {})
                pending = self._pending_order_state.get(code, {})
                if not pending:
                    pending = _dict_or_empty(getattr(self, "_manual_pending_state", {})).get(code, {})
                pending = _dict_or_empty(pending)
                sync_status = str(info.get("status", ""))
                if sync_status == "sync_failed":
                    sync_status = "sync_failed"
                external_updated = info.get("external_updated_at")
                external_status = str(info.get("external_status", "") or "")
                external_error = str(info.get("external_error", "") or "")
                external_age = self._diag_age_seconds(external_updated)
                stale_limit = int(getattr(Config, "EXTERNAL_FLOW_STALE_SEC", 30))
                if external_status == "fresh" and external_age and int(external_age) > stale_limit:
                    external_status = "stale"
                if external_status == "error" and external_error:
                    sync_error = str(diag.get("last_sync_error", "") or "")
                    if sync_error:
                        sync_error = f"{sync_error} | ext:{external_error}"
                    else:
                        sync_error = f"ext:{external_error}"
                else:
                    sync_error = str(diag.get("last_sync_error", ""))
                raw_market_state = str(info.get("market_state", "normal") or "normal")
                raw_guard_reason = str(
                    info.get("last_guard_reason")
                    or self._guard_reason_by_code.get(code, "")
                    or ""
                )
                raw_action_policy = str(market_intel.get("action_policy", "allow") or "allow")
                raw_exit_policy = str(market_intel.get("exit_policy", "none") or "none")
                raw_risk_mode = str(getattr(self, "_global_risk_mode", "normal") or "normal")
                raw_health_mode = str(getattr(self, "_order_health_mode", "normal") or "normal")

                values = [
                    code,
                    str(info.get("name", code)),
                    str(diag.get("pending_side") or pending.get("side") or ""),
                    str(diag.get("pending_reason") or pending.get("reason") or ""),
                    self._diag_fmt_dt(diag.get("pending_until") or pending.get("until")),
                    display_status(sync_status),
                    str(diag.get("retry_count", 0)),
                    sync_error,
                    self._diag_fmt_dt(diag.get("last_update")),
                    display_status(external_status),
                    self._diag_fmt_dt(external_updated),
                    external_age,
                    display_market_state(raw_market_state),
                    display_guard_reason(raw_guard_reason),
                    display_source_health(market_intel.get("source_health", "") or ""),
                    display_action_policy(raw_action_policy),
                    f"{float(market_intel.get('size_multiplier', 1.0) or 1.0):.2f}",
                    display_exit_policy(raw_exit_policy),
                    str(market_intel.get("last_event_id", "") or ""),
                    display_regime(raw_risk_mode),
                    display_regime(raw_health_mode),
                    display_status(diag.get("pending_state") or pending.get("state") or ""),
                    str(diag.get("pending_remaining") or pending.get("remaining_qty") or ""),
                    str(info.get("sync_failed_reason", "") or ""),
                ]

                for col, text in enumerate(values):
                    item = self.diagnostic_table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(str(text))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.diagnostic_table.setItem(row, col, item)
                    elif item.text() != str(text):
                        item.setText(str(text))
                    if col == 9:
                        state = str(text).lower()
                        if state == "error":
                            item.setForeground(QColor("#f85149"))
                        elif state == "stale":
                            item.setForeground(QColor("#d29922"))
                        elif state == "fresh":
                            item.setForeground(QColor("#3fb950"))
                        else:
                            item.setForeground(QColor("#8b949e"))
                    elif col == 12:
                        state = raw_market_state.lower()
                        if state in {"halt", "vi"}:
                            item.setForeground(QColor("#f85149"))
                        elif state == "reopen_cooldown":
                            item.setForeground(QColor("#d29922"))
                        else:
                            item.setForeground(QColor("#8b949e"))
                    elif col == 13:
                        item.setForeground(QColor("#f85149") if raw_guard_reason else QColor("#8b949e"))
                    elif col == 14:
                        item.setForeground(QColor("#8b949e" if not str(text) else "#d29922"))
                    elif col == 15:
                        state = raw_action_policy.lower()
                        if state in {"force_exit", "tighten_exit", "reduce_size", "block_entry"}:
                            item.setForeground(QColor("#f85149"))
                        elif state in {"allow", ""}:
                            item.setForeground(QColor("#8b949e"))
                    elif col == 17:
                        state = raw_exit_policy.lower()
                        if state in {"force_exit", "tighten_exit", "reduce_size"}:
                            item.setForeground(QColor("#f85149"))
                        elif state in {"none", ""}:
                            item.setForeground(QColor("#8b949e"))
                    elif col in {19, 20}:
                        state = raw_risk_mode.lower() if col == 19 else raw_health_mode.lower()
                        if state in {"shock", "degraded"}:
                            item.setForeground(QColor("#f85149"))
                        elif state in {"normal", ""}:
                            item.setForeground(QColor("#8b949e"))
                    elif col == 23:
                        item.setForeground(QColor("#f85149") if str(text) else QColor("#8b949e"))
        finally:
            self.diagnostic_table.setUpdatesEnabled(True)
        self._diagnostic_row_to_code = row_to_code

        self._diagnostics_dirty_codes.clear()
        render_detail = getattr(self, "_render_selected_diagnostic_detail", None)
        if callable(render_detail):
            render_detail()
    def _selected_diagnostic_code(self) -> str:
        table = getattr(self, "diagnostic_table", None)
        if table is None:
            return ""

        row = -1
        getter = getattr(table, "currentRow", None)
        if callable(getter):
            current_row = getter()
            if isinstance(current_row, int):
                row = current_row
        if row < 0:
            selected = getattr(table, "selectedItems", None)
            if callable(selected):
                selected_items = selected()
                if isinstance(selected_items, list) and selected_items:
                    row_fn = getattr(selected_items[0], "row", None)
                    if callable(row_fn):
                        row_value = row_fn()
                        if isinstance(row_value, int):
                            row = row_value
        row_to_code = getattr(self, "_diagnostic_row_to_code", {})
        if isinstance(row_to_code, dict):
            return str(row_to_code.get(row, "") or "")
        return ""
    def _render_selected_diagnostic_detail(self):
        panel = getattr(self, "diag_detail_panel", None)
        if panel is None:
            return
        code = self._selected_diagnostic_code()
        if not code:
            panel.setPlainText("선택된 종목이 없습니다.")
            return

        tracked_getter = getattr(self, "_get_tracked_position_info", None)
        raw_info = tracked_getter(code) if callable(tracked_getter) else self.universe.get(code, {})
        info = _dict_or_empty(raw_info)
        market_intel = _dict_or_empty(info.get("market_intel", {}))
        pending = self._pending_order_state.get(code, {})
        if not pending:
            pending = _dict_or_empty(getattr(self, "_manual_pending_state", {})).get(code, {})
        pending = _dict_or_empty(pending)
        detail = [
            f"코드: {code}",
            f"종목명: {info.get('name', code)}",
            f"상태: {display_status(info.get('status', ''))}",
            f"동기화 실패 사유: {info.get('sync_failed_reason', '')}",
            f"진입 경로: {info.get('entry_origin', '')}",
            f"읽기 전용: {bool(info.get('read_only', False))}",
            f"가용 수량: {info.get('available_qty', info.get('held', ''))}",
            f"시간 청산 가능 여부: {bool(info.get('time_stop_eligible', True))}",
            f"대기 주문 상태: {display_status(pending.get('state', ''))}",
            f"대기 주문 방향: {pending.get('side', '')}",
            f"대기 주문 번호: {pending.get('order_no', '')}",
            f"주문 요청 수량: {pending.get('submitted_qty', '')}",
            f"체결 수량: {pending.get('filled_qty', '')}",
            f"미체결 수량: {pending.get('remaining_qty', '')}",
            f"예상 가격: {pending.get('expected_price', '')}",
            f"최근 주문 갱신: {self._diag_fmt_dt(pending.get('updated_at'))}",
            f"인텔리전스 상태: {display_status(market_intel.get('status', market_intel.get('intel_status', 'idle')))}",
            f"소스 상태: {display_source_health(market_intel.get('source_health', ''))}",
            f"자동매매 정책: {display_action_policy(market_intel.get('action_policy', 'allow'))}",
            f"청산 정책: {display_exit_policy(market_intel.get('exit_policy', 'none'))}",
            f"수량 배수: {market_intel.get('size_multiplier', 1.0)}",
            f"마지막 이벤트 ID: {market_intel.get('last_event_id', '')}",
        ]
        panel.setPlainText("\n".join(detail))
    def _on_diagnostic_selection_changed(self):
        self._render_selected_diagnostic_detail()
    def _on_diagnostic_resync_selected(self):
        code = self._selected_diagnostic_code()
        if not code:
            self.log("[진단] 재동기화 대상 종목이 선택되지 않았습니다.")
            return
        self._sync_position_from_account(code)
        self.log(f"[진단] 선택 종목 재동기화 요청: {code}")
        self._render_selected_diagnostic_detail()
    def _on_diagnostic_release_sync_failed_selected(self):
        code = self._selected_diagnostic_code()
        if not code:
            self.log("[진단] sync_failed 해제 대상 종목이 선택되지 않았습니다.")
            return

        info = _dict_or_empty(self.universe.get(code, {}))
        in_failed = code in getattr(self, "_sync_failed_codes", set())
        if str(info.get("status", "")) != "sync_failed" and not in_failed:
            self.log(f"[진단] {code}는 sync_failed 상태가 아닙니다.")
            return

        # Safety rule: do not flip status directly. Request resync and recover only on success.
        self._sync_position_from_account(code)
        self.log(f"[진단] sync_failed 해제 요청(재동기화 기반): {code}")
        self._render_selected_diagnostic_detail()
