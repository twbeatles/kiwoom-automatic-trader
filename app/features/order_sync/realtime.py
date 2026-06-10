"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from collections import deque
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class OrderSyncRealtimeMixin(TraderMixinBase):
    def _on_realtime(self, data: ExecutionData):
        self.sig_execution.emit(data)
    def _on_order_realtime(self, data):
        """WebSocket thread -> main thread bridge."""
        self.sig_order_execution.emit(data)
    def _on_order_execution(self, data):
        """Handle realtime order/execution notifications in main thread."""
        try:
            self._update_order_health_mode()
            code = str(data.get("code") or data.get("stk_cd") or "").strip()
            info = self.universe.get(code, {}) if code else {}
            name = data.get("name") or data.get("stk_nm") or info.get("name", code)

            raw_order_type = str(data.get("order_type") or data.get("ord_tp") or data.get("bs_tp") or "").strip()
            order_type_map = {
                "1": "매수",
                "2": "매도",
                "3": "매수취소",
                "4": "매도취소",
                "5": "매수정정",
                "6": "매도정정",
            }
            order_type = order_type_map.get(raw_order_type, raw_order_type or "주문")

            order_status = str(data.get("order_status") or data.get("ord_st") or data.get("status") or "").strip()
            order_no = str(data.get("order_no") or data.get("ord_no") or data.get("org_ord_no") or "").strip()
            order_qty = self._to_int(data.get("ord_qty", data.get("qty", 0)))
            exec_qty = self._to_int(data.get("exec_qty", data.get("qty", 0)))
            display_qty = exec_qty if exec_qty > 0 else self._to_int(data.get("ord_qty", data.get("qty", 0)))
            price = self._to_int(data.get("exec_price", data.get("price", data.get("ord_prc", 0))))
            status_lower = order_status.lower()
            fill_like = ("체결" in order_status) or ("fill" in status_lower)

            if not order_status:
                order_status = "체결" if exec_qty > 0 else "알림"

            msg = f"{order_type} {order_status} - {name} {display_qty}주"
            if price > 0:
                msg += f" @ {price:,}원"
            self.log(msg)

            side = ""
            lower_type = order_type.lower()
            if "매수" in order_type or "buy" in lower_type:
                side = "buy"
            elif "매도" in order_type or "sell" in lower_type:
                side = "sell"

            if code and code in self._pending_order_state:
                self._update_pending_from_order_event(code, order_no=order_no, order_qty=order_qty)

            if code and exec_qty > 0 and side:
                self._last_exec_event[code] = {
                    "side": side,
                    "qty": exec_qty,
                    "price": price,
                    "timestamp": datetime.datetime.now(),
                }
                self._position_sync_batch.add(code)

            if code and (exec_qty > 0 or fill_like):
                self._sync_position_from_account(code)

            cancelled = ("취소" in order_status) or ("cancel" in status_lower)
            rejected_or_failed = any(token in order_status for token in ["거부", "실패"]) or any(
                token in status_lower for token in ["reject", "fail"]
            )
            cancel_like = cancelled or rejected_or_failed
            if code and cancel_like:
                recorder = getattr(self, "_record_order_lifecycle_event", None)
                if callable(recorder):
                    recorder(
                        {
                            "event": "order_terminal_status",
                            "code": code,
                            "order_no": order_no,
                            "status": order_status,
                            "is_cancel": cancelled,
                            "is_reject_or_fail": rejected_or_failed,
                        }
                    )
                if rejected_or_failed:
                    self._record_order_failure("ORDER_REJECT_OR_FAIL", code=code)
                pending = self._pending_order_state.get(code, {})
                pending_side = str(pending.get("side", ""))
                final_state = "cancelled" if cancelled else "rejected"
                children = self._pending_children(pending)
                if pending_side == "buy" and children:
                    refunded = 0
                    should_clear = False
                    clear_state = final_state
                    for child in children:
                        child_order_no = str(child.get("order_no", "") or "").strip()
                        if order_no and child_order_no and child_order_no != order_no:
                            continue
                        refunded = int(child.get("reserved_cash", 0) or 0)
                        if refunded > 0:
                            self._release_reserved_cash_amount_safe(
                                code,
                                refunded,
                                reason="ORDER_CANCEL_OR_REJECT",
                                refund=True,
                            )
                        break
                    should_clear, clear_state = self._apply_pending_cancel(code, order_no, final_state)
                    if should_clear:
                        self._clear_pending_order(code, final_state=clear_state)
                else:
                    self._mark_pending_state(code, final_state)
                    self._clear_pending_order(code, final_state=final_state)
                    if pending_side == "buy":
                        self._release_reserved_cash_safe(code, reason="ORDER_CANCEL_OR_REJECT", refund=True)
                if code in self.universe:
                    held = int(self.universe[code].get("held", 0))
                    if pending_side == "buy" and self._pending_is_active(self._pending_order_state.get(code, {})):
                        self.universe[code]["status"] = "buy_submitted"
                    elif pending_side == "sell" and self._pending_is_active(self._pending_order_state.get(code, {})):
                        self.universe[code]["status"] = "sell_submitted"
                    else:
                        self.universe[code]["status"] = "holding" if held > 0 else "watch"
                    self._diag_touch_safe(
                        code,
                        sync_status=self.universe[code]["status"],
                        retry_count=0,
                    )
                else:
                    external_positions = getattr(self, "external_positions", {})
                    if isinstance(external_positions, dict) and code in external_positions:
                        held = int(external_positions[code].get("held", 0))
                        if pending_side == "buy" and self._pending_is_active(self._pending_order_state.get(code, {})):
                            external_positions[code]["status"] = "buy_submitted"
                        elif pending_side == "sell" and self._pending_is_active(self._pending_order_state.get(code, {})):
                            external_positions[code]["status"] = "sell_submitted"
                        else:
                            external_positions[code]["status"] = "external_holding" if held > 0 else "watch"
                        self._diag_touch_safe(
                            code,
                            sync_status=external_positions[code]["status"],
                            retry_count=0,
                        )
                self._dirty_codes.add(code)
            if code and code not in self.universe and code in self._manual_pending_map():
                manual_pending = self._manual_pending_map().get(code, {})
                manual_side = str(manual_pending.get("side", ""))
                external_positions = getattr(self, "external_positions", {})
                if cancel_like:
                    if manual_side == "buy":
                        refund = int(manual_pending.get("reserved_cash", 0) or 0)
                        if refund > 0:
                            self._release_reserved_cash_amount_safe(
                                code,
                                refund,
                                reason="MANUAL_EXTERNAL_CANCEL",
                                refund=True,
                            )
                    self._clear_manual_pending_order(code)
                    if isinstance(external_positions, dict) and code in external_positions:
                        external_positions[code]["status"] = "external_holding"
                        self._diag_touch_safe(code, sync_status="external_holding", retry_count=0)
                elif exec_qty > 0 or fill_like:
                    if manual_side == "buy":
                        state_text, remaining_qty, reserved_consumed = self._apply_manual_pending_fill(code, exec_qty)
                        if reserved_consumed > 0:
                            self._consume_reserved_cash_safe(
                                code,
                                amount=reserved_consumed,
                                reason="MANUAL_EXTERNAL_BUY_FILL",
                            )
                        if fill_like and exec_qty <= 0:
                            remaining_reserved = int(manual_pending.get("reserved_cash", 0) or 0)
                            if remaining_reserved > 0:
                                self._release_reserved_cash_amount_safe(
                                    code,
                                    remaining_reserved,
                                    reason="MANUAL_EXTERNAL_BUY_DONE",
                                    refund=False,
                                )
                            self._clear_manual_pending_order(code)
                            if isinstance(external_positions, dict) and code in external_positions:
                                external_positions[code]["status"] = "external_holding"
                                self._diag_touch_safe(code, sync_status="external_holding", retry_count=0)
                        elif state_text == "filled" or remaining_qty <= 0:
                            remaining_reserved = int(manual_pending.get("reserved_cash", 0) or 0)
                            if remaining_reserved > 0:
                                self._release_reserved_cash_amount_safe(
                                    code,
                                    remaining_reserved,
                                    reason="MANUAL_EXTERNAL_BUY_DONE",
                                    refund=False,
                                )
                            self._clear_manual_pending_order(code)
                            if isinstance(external_positions, dict) and code in external_positions:
                                external_positions[code]["status"] = "external_holding"
                                self._diag_touch_safe(code, sync_status="external_holding", retry_count=0)
                    else:
                        self._clear_manual_pending_order(code)
                        if isinstance(external_positions, dict) and code in external_positions:
                            external_positions[code]["status"] = "external_holding"
                            self._diag_touch_safe(code, sync_status="external_holding", retry_count=0)
        except Exception as e:
            self.logger.error(f"주문 체결 처리 오류: {e}")
