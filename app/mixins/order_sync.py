"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from collections import deque
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config
from ._typing import TraderMixinBase


class OrderSyncMixin(TraderMixinBase):
    ACTIVE_PENDING_STATES = {"submitted", "partial"}
    TERMINAL_PENDING_STATES = {"filled", "cancelled", "rejected", "sync_failed"}

    def _manual_pending_map(self):
        mapping = getattr(self, "_manual_pending_state", None)
        if not isinstance(mapping, dict):
            mapping = {}
            self._manual_pending_state = mapping
        return mapping

    def _log_sync_fail_once(self, code: str, message: str):
        cooldown_map = getattr(self, "_log_cooldown_map", None)
        if cooldown_map is None:
            cooldown_map = {}
            self._log_cooldown_map = cooldown_map
        cache_key = f"{code}:sync_failed"
        now_ts = datetime.datetime.now().timestamp()
        last_ts = float(cooldown_map.get(cache_key, 0.0))
        if now_ts - last_ts >= float(getattr(Config, "LOG_DEDUP_SEC", 30)):
            if hasattr(self, "log"):
                self.log(message)
            else:
                self.logger.warning(message)
            cooldown_map[cache_key] = now_ts

    def _diag_touch_safe(self, code: str, **fields):
        fn = getattr(self, "_diag_touch", None)
        if callable(fn):
            fn(code, **fields)

    def _diag_clear_pending_safe(self, code: str):
        fn = getattr(self, "_diag_clear_pending", None)
        if callable(fn):
            fn(code)

    def _release_reserved_cash_safe(self, code: str, reason: str, refund: bool):
        fn = getattr(self, "_release_reserved_cash", None)
        if callable(fn):
            result = fn(code, reason=reason, refund=refund)
            return int(result) if isinstance(result, (int, float, str)) else 0

        # Fallback for tests that do not include ExecutionEngineMixin.
        mapping = getattr(self, "_reserved_cash_by_code", None)
        if not isinstance(mapping, dict):
            return 0
        raw_amount = mapping.pop(code, 0)
        amount = int(raw_amount) if isinstance(raw_amount, (int, float, str)) else 0
        if amount > 0 and refund and hasattr(self, "virtual_deposit"):
            self.virtual_deposit = max(0, int(getattr(self, "virtual_deposit", 0) or 0) + amount)
        return amount

    def _release_reserved_cash_amount_safe(self, code: str, amount: int, reason: str, refund: bool):
        fn = getattr(self, "_release_reserved_cash_amount", None)
        if callable(fn):
            result = fn(code, amount=amount, reason=reason, refund=refund)
            return int(result) if isinstance(result, (int, float, str)) else 0

        mapping = getattr(self, "_reserved_cash_by_code", None)
        if not isinstance(mapping, dict):
            return 0
        current = max(0, int(mapping.get(code, 0) or 0))
        released = min(current, max(0, int(amount or 0)))
        remaining = current - released
        if remaining > 0:
            mapping[code] = remaining
        else:
            mapping.pop(code, None)
        if released > 0 and refund and hasattr(self, "virtual_deposit"):
            self.virtual_deposit = max(0, int(getattr(self, "virtual_deposit", 0) or 0) + released)
        return released

    def _consume_reserved_cash_safe(self, code: str, amount: int, reason: str = "") -> int:
        fn = getattr(self, "_consume_reserved_cash", None)
        if callable(fn):
            result = fn(code, amount=amount, reason=reason)
            return int(result) if isinstance(result, (int, float, str)) else 0

        mapping = getattr(self, "_reserved_cash_by_code", None)
        if not isinstance(mapping, dict):
            return 0
        raw_current = mapping.get(code, 0)
        current = max(0, int(raw_current)) if isinstance(raw_current, (int, float, str)) else 0
        consume = min(current, max(0, int(amount or 0)))
        remain = current - consume
        if remain > 0:
            mapping[code] = remain
        else:
            mapping.pop(code, None)
        return consume

    def _pending_is_active(self, pending: dict) -> bool:
        if not isinstance(pending, dict) or not pending:
            return False
        state = str(pending.get("state", "submitted") or "submitted").lower()
        return state in self.ACTIVE_PENDING_STATES

    @staticmethod
    def _pending_children(pending: dict) -> list[dict]:
        rows = pending.get("child_orders", []) if isinstance(pending, dict) else []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _refresh_pending_order_aggregate(self, code: str) -> tuple[str, int]:
        pending = self._pending_order_state.get(code)
        if not isinstance(pending, dict):
            return "", 0

        children = self._pending_children(pending)
        if not children:
            remaining = max(0, int(pending.get("remaining_qty", 0) or 0))
            state = str(pending.get("state", "submitted") or "submitted").lower()
            pending["updated_at"] = datetime.datetime.now()
            self._diag_touch_safe(
                code,
                pending_state=state,
                pending_remaining=str(remaining),
                pending_side=str(pending.get("side", "")),
                pending_reason=str(pending.get("reason", "")),
                pending_until=pending.get("until"),
            )
            return state, remaining

        total_submitted = 0
        total_filled = 0
        total_remaining = 0
        total_expected = 0
        any_active = False
        any_filled = False
        terminal_states: set[str] = set()
        first_order_no = ""

        for child in children:
            submitted = max(0, int(child.get("submitted_qty", 0) or 0))
            filled = max(0, int(child.get("filled_qty", 0) or 0))
            remaining = max(0, int(child.get("remaining_qty", 0) or 0))
            expected = max(0, int(child.get("expected_price", 0) or 0))
            state = str(child.get("state", "submitted") or "submitted").lower()
            order_no = str(child.get("order_no", "") or "").strip()
            if order_no and not first_order_no:
                first_order_no = order_no
            total_submitted += submitted
            total_filled += filled
            total_remaining += remaining
            total_expected += expected * submitted
            any_active = any_active or state in self.ACTIVE_PENDING_STATES
            any_filled = any_filled or filled > 0
            if state in self.TERMINAL_PENDING_STATES:
                terminal_states.add(state)

        if any_active:
            aggregate_state = "partial" if any_filled else "submitted"
        elif total_remaining <= 0 and any_filled:
            aggregate_state = "filled"
        elif "rejected" in terminal_states:
            aggregate_state = "rejected"
        elif "cancelled" in terminal_states:
            aggregate_state = "cancelled"
        elif "sync_failed" in terminal_states:
            aggregate_state = "sync_failed"
        else:
            aggregate_state = str(pending.get("state", "submitted") or "submitted").lower()

        pending["submitted_qty"] = total_submitted
        pending["filled_qty"] = total_filled
        pending["remaining_qty"] = total_remaining
        pending["state"] = aggregate_state
        pending["expected_price"] = int(round(total_expected / total_submitted)) if total_submitted > 0 else 0
        if first_order_no:
            pending["order_no"] = first_order_no
        pending["updated_at"] = datetime.datetime.now()
        self._diag_touch_safe(
            code,
            pending_state=aggregate_state,
            pending_remaining=str(total_remaining),
            pending_side=str(pending.get("side", "")),
            pending_reason=str(pending.get("reason", "")),
            pending_until=pending.get("until"),
        )
        return aggregate_state, total_remaining

    def _mark_pending_state(self, code: str, state: str):
        pending = self._pending_order_state.get(code)
        if not pending:
            return
        state_text = str(state or "").strip().lower()
        if not state_text:
            return
        pending["state"] = state_text
        for child in self._pending_children(pending):
            if str(child.get("state", "") or "").lower() in self.ACTIVE_PENDING_STATES:
                child["state"] = state_text
                child["updated_at"] = datetime.datetime.now()
        pending["updated_at"] = datetime.datetime.now()
        self._diag_touch_safe(
            code,
            pending_state=state_text,
            pending_remaining=str(int(pending.get("remaining_qty", 0) or 0)),
            pending_side=str(pending.get("side", "")),
            pending_reason=str(pending.get("reason", "")),
            pending_until=pending.get("until"),
        )

    def _update_pending_from_order_event(self, code: str, order_no: str, order_qty: int):
        pending = self._pending_order_state.get(code)
        if not isinstance(pending, dict):
            return

        child_updated = False
        for child in self._pending_children(pending):
            child_order_no = str(child.get("order_no", "") or "").strip()
            if order_no and child_order_no and child_order_no != order_no:
                continue
            if order_no and not child_order_no:
                child["order_no"] = str(order_no).strip()
            if order_qty > 0:
                submitted = int(child.get("submitted_qty", 0) or 0)
                if submitted <= 0:
                    child["submitted_qty"] = int(order_qty)
                    filled = int(child.get("filled_qty", 0) or 0)
                    child["remaining_qty"] = max(0, int(order_qty) - filled)
            child["updated_at"] = datetime.datetime.now()
            child_updated = True
            if order_no:
                break

        if order_no and not str(pending.get("order_no", "")).strip():
            pending["order_no"] = str(order_no).strip()

        if order_qty > 0:
            submitted = int(pending.get("submitted_qty", 0) or 0)
            if submitted <= 0:
                pending["submitted_qty"] = int(order_qty)
                filled = int(pending.get("filled_qty", 0) or 0)
                pending["remaining_qty"] = max(0, int(order_qty) - filled)

        pending["updated_at"] = datetime.datetime.now()
        if child_updated:
            self._refresh_pending_order_aggregate(code)
            return
        self._diag_touch_safe(
            code,
            pending_state=str(pending.get("state", "submitted")),
            pending_remaining=str(int(pending.get("remaining_qty", 0) or 0)),
        )

    def _apply_pending_fill(self, code: str, fill_qty: int) -> tuple[str, int, int]:
        pending = self._pending_order_state.get(code)
        if not isinstance(pending, dict):
            return "", 0, 0
        qty = max(0, int(fill_qty or 0))
        if qty <= 0:
            return str(pending.get("state", "submitted")), int(pending.get("remaining_qty", 0) or 0), 0

        children = self._pending_children(pending)
        if children:
            remaining_fill = qty
            reserved_consumed = 0
            for child in children:
                state = str(child.get("state", "submitted") or "submitted").lower()
                if state not in self.ACTIVE_PENDING_STATES:
                    continue
                child_remaining = max(0, int(child.get("remaining_qty", 0) or 0))
                if child_remaining <= 0:
                    continue
                applied = min(child_remaining, remaining_fill)
                if applied <= 0:
                    continue
                child["filled_qty"] = max(0, int(child.get("filled_qty", 0) or 0)) + applied
                child["remaining_qty"] = max(0, child_remaining - applied)
                expected = max(0, int(child.get("expected_price", 0) or 0))
                child_reserved = max(0, int(child.get("reserved_cash", 0) or 0))
                consume_cash = min(child_reserved, expected * applied) if expected > 0 else 0
                child["reserved_cash"] = max(0, child_reserved - consume_cash)
                reserved_consumed += consume_cash
                child["state"] = "filled" if int(child.get("remaining_qty", 0) or 0) <= 0 else "partial"
                child["updated_at"] = datetime.datetime.now()
                remaining_fill -= applied
                if remaining_fill <= 0:
                    break
            state_text, remaining_qty = self._refresh_pending_order_aggregate(code)
            return state_text, remaining_qty, reserved_consumed

        submitted = max(0, int(pending.get("submitted_qty", 0) or 0))
        filled_before = max(0, int(pending.get("filled_qty", 0) or 0))
        filled_after = filled_before + qty
        pending["filled_qty"] = filled_after

        if submitted > 0:
            remaining = max(0, submitted - filled_after)
        else:
            remaining = 0
        pending["remaining_qty"] = remaining

        if submitted > 0 and remaining > 0:
            pending["state"] = "partial"
        else:
            pending["state"] = "filled"
        pending["updated_at"] = datetime.datetime.now()
        self._diag_touch_safe(
            code,
            pending_state=str(pending.get("state", "")),
            pending_remaining=str(remaining),
        )
        return str(pending.get("state", "")), remaining, 0

    def _apply_pending_cancel(self, code: str, order_no: str, final_state: str) -> tuple[bool, str]:
        pending = self._pending_order_state.get(code)
        if not isinstance(pending, dict):
            return False, ""

        children = self._pending_children(pending)
        if not children:
            return True, final_state

        target_child = None
        order_no_text = str(order_no or "").strip()
        if order_no_text:
            for child in children:
                if str(child.get("order_no", "") or "").strip() == order_no_text:
                    target_child = child
                    break
        if target_child is None:
            if len(children) == 1:
                target_child = children[0]
            else:
                return False, ""

        target_child["state"] = str(final_state or "cancelled").lower()
        target_child["remaining_qty"] = 0
        target_child["reserved_cash"] = 0
        target_child["updated_at"] = datetime.datetime.now()
        aggregate_state, remaining_qty = self._refresh_pending_order_aggregate(code)
        should_clear = remaining_qty <= 0 or aggregate_state not in self.ACTIVE_PENDING_STATES
        clear_state = "filled" if aggregate_state == "filled" else str(final_state or aggregate_state)
        return should_clear, clear_state

    def _record_order_failure(self, reason: str, code: str = ""):
        cfg = getattr(self, "config", None)
        if cfg is None or not bool(getattr(cfg, "use_order_health_guard", True)):
            return

        now_ts = datetime.datetime.now().timestamp()
        events = getattr(self, "_order_fail_events", None)
        if not isinstance(events, deque):
            events = deque(maxlen=500)
            self._order_fail_events = events
        events.append(now_ts)

        window_sec = max(
            1,
            int(getattr(cfg, "order_health_window_sec", getattr(Config, "DEFAULT_ORDER_HEALTH_WINDOW_SEC", 60))),
        )
        while events and (now_ts - float(events[0])) > window_sec:
            events.popleft()

        fail_count_limit = max(
            1,
            int(getattr(cfg, "order_health_fail_count", getattr(Config, "DEFAULT_ORDER_HEALTH_FAIL_COUNT", 5))),
        )
        if len(events) >= fail_count_limit:
            cooldown_sec = max(
                1,
                int(
                    getattr(
                        cfg,
                        "order_health_cooldown_sec",
                        getattr(Config, "DEFAULT_ORDER_HEALTH_COOLDOWN_SEC", 180),
                    )
                ),
            )
            until = datetime.datetime.now() + datetime.timedelta(seconds=cooldown_sec)
            self._order_health_mode = "degraded"
            self._order_health_until = until
            if hasattr(self, "log"):
                self.log(
                    f"[주문건강] degraded 활성화 fail={len(events)}/{fail_count_limit}, "
                    f"cooldown={cooldown_sec}s ({reason}:{code})"
                )

    def _update_order_health_mode(self, now_dt: datetime.datetime | None = None):
        now = now_dt or datetime.datetime.now()
        cfg = getattr(self, "config", None)
        if cfg is None:
            return
        events = getattr(self, "_order_fail_events", None)
        if isinstance(events, deque):
            window_sec = max(
                1,
                int(getattr(cfg, "order_health_window_sec", getattr(Config, "DEFAULT_ORDER_HEALTH_WINDOW_SEC", 60))),
            )
            now_ts = now.timestamp()
            while events and (now_ts - float(events[0])) > window_sec:
                events.popleft()

        if str(getattr(self, "_order_health_mode", "normal")) != "degraded":
            return
        until = getattr(self, "_order_health_until", None)
        if isinstance(until, datetime.datetime) and now >= until:
            self._order_health_mode = "normal"
            self._order_health_until = None
            if hasattr(self, "log"):
                self.log("[주문건강] degraded -> normal 자동복구")

    def _record_slippage_bps(self, expected_price: int, fill_price: int, code: str = ""):
        expected = float(expected_price or 0)
        fill = float(fill_price or 0)
        if expected <= 0 or fill <= 0:
            return
        slippage = abs((fill - expected) / expected) * 10000.0
        series = getattr(self, "_recent_slippage_bps", None)
        if not isinstance(series, deque):
            series = deque(maxlen=300)
            self._recent_slippage_bps = series
        series.append(slippage)
        if code and code in getattr(self, "universe", {}):
            self.universe[code]["last_slippage_bps"] = float(slippage)

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

            cancel_like = any(token in order_status for token in ["취소", "거부", "실패"]) or any(
                token in status_lower for token in ["cancel", "reject", "fail"]
            )
            if code and cancel_like:
                self._record_order_failure("ORDER_CANCEL_REJECT", code=code)
                pending = self._pending_order_state.get(code, {})
                pending_side = str(pending.get("side", ""))
                cancelled = ("취소" in order_status) or ("cancel" in status_lower)
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
                self._dirty_codes.add(code)
            if code and code not in self.universe and code in self._manual_pending_map():
                manual_pending = self._manual_pending_map().get(code, {})
                manual_side = str(manual_pending.get("side", ""))
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
                    else:
                        self._clear_manual_pending_order(code)
        except Exception as e:
            self.logger.error(f"주문 체결 처리 오류: {e}")

    @staticmethod
    def _to_int(value, default=0) -> int:
        """Safely convert common payload values to int."""
        try:
            if value is None:
                return default
            text = str(value).strip().replace(",", "")
            if text == "":
                return default
            return int(float(text))
        except (ValueError, TypeError):
            return default

    def _set_pending_order(
        self,
        code: str,
        side: str,
        reason: str,
        expected_price: int = 0,
        submitted_qty: int = 0,
        order_no: str = "",
        child_orders: list[dict] | None = None,
    ):
        if not code:
            return
        pending_until = datetime.datetime.now() + datetime.timedelta(seconds=5)
        submit_qty = max(0, int(submitted_qty or 0))
        children = [dict(row) for row in (child_orders or []) if isinstance(row, dict)]
        self._pending_order_state[code] = {
            "side": side,
            "reason": reason,
            "until": pending_until,
            "state": "submitted",
            "order_no": str(order_no or ""),
            "submitted_qty": submit_qty,
            "filled_qty": 0,
            "remaining_qty": submit_qty,
            "expected_price": int(expected_price or 0),
            "child_orders": children,
            "updated_at": datetime.datetime.now(),
        }
        self._refresh_pending_order_aggregate(code)
        self._diag_touch_safe(
            code,
            pending_side=side,
            pending_reason=reason,
            pending_until=pending_until,
        )

    def _clear_pending_order(self, code: str, final_state: str = ""):
        if final_state and code in self._pending_order_state:
            self._mark_pending_state(code, final_state)
        self._pending_order_state.pop(code, None)
        self._diag_clear_pending_safe(code)

    def _set_manual_pending_order(
        self,
        code: str,
        side: str,
        reason: str,
        expected_price: int = 0,
        submitted_qty: int = 0,
        order_no: str = "",
        reserved_cash: int = 0,
    ):
        if not code:
            return
        has_live_order = bool(order_no) or int(submitted_qty or 0) > 0 or int(reserved_cash or 0) > 0
        pending_until = None if has_live_order else datetime.datetime.now() + datetime.timedelta(seconds=5)
        self._manual_pending_map()[code] = {
            "side": side,
            "reason": reason,
            "until": pending_until,
            "state": "submitted",
            "submitted_qty": max(0, int(submitted_qty or 0)),
            "filled_qty": 0,
            "remaining_qty": max(0, int(submitted_qty or 0)),
            "expected_price": max(0, int(expected_price or 0)),
            "order_no": str(order_no or ""),
            "reserved_cash": max(0, int(reserved_cash or 0)),
            "updated_at": datetime.datetime.now(),
        }

    def _clear_manual_pending_order(self, code: str):
        self._manual_pending_map().pop(code, None)

    def _apply_manual_pending_fill(self, code: str, fill_qty: int) -> tuple[str, int, int]:
        pending = self._manual_pending_map().get(code)
        if not isinstance(pending, dict):
            return "", 0, 0
        qty = max(0, int(fill_qty or 0))
        if qty <= 0:
            remaining = max(0, int(pending.get("remaining_qty", 0) or 0))
            return str(pending.get("state", "submitted") or "submitted"), remaining, 0

        remaining_before = max(0, int(pending.get("remaining_qty", 0) or 0))
        applied = min(remaining_before if remaining_before > 0 else qty, qty)
        pending["filled_qty"] = max(0, int(pending.get("filled_qty", 0) or 0)) + applied
        pending["remaining_qty"] = max(0, remaining_before - applied)
        expected = max(0, int(pending.get("expected_price", 0) or 0))
        reserved_before = max(0, int(pending.get("reserved_cash", 0) or 0))
        reserved_consumed = min(reserved_before, expected * applied) if expected > 0 else 0
        pending["reserved_cash"] = max(0, reserved_before - reserved_consumed)
        pending["state"] = "filled" if int(pending.get("remaining_qty", 0) or 0) <= 0 else "partial"
        pending["updated_at"] = datetime.datetime.now()
        return str(pending.get("state", "")), int(pending.get("remaining_qty", 0) or 0), reserved_consumed

    def _cleanup_manual_pending_state(self, now: datetime.datetime | None = None):
        state = self._manual_pending_map()
        if not state:
            return
        now_dt = now or datetime.datetime.now()
        expired_codes = [
            code
            for code, pending in state.items()
            if pending.get("until")
            and pending.get("until") <= now_dt
            and int(pending.get("reserved_cash", 0) or 0) <= 0
            and str(pending.get("state", "submitted") or "submitted").lower() not in self.ACTIVE_PENDING_STATES
        ]
        for code in expired_codes:
            state.pop(code, None)

    def _sync_position_from_account(self, code: str):
        """Sync positions from account API with debounce/batch."""
        if code and code in self.universe:
            self._position_sync_batch.add(code)

        if not (self.rest_client and self.current_account):
            return

        if code:
            if self._position_sync_scheduled:
                return
            self._position_sync_scheduled = True
            delay_ms = max(0, int(Config.POSITION_SYNC_DEBOUNCE_MS))
            QTimer.singleShot(delay_ms, lambda: self._sync_position_from_account(""))
            return

        self._position_sync_scheduled = False
        if "__batch__" in self._position_sync_pending:
            return
        if not self._position_sync_batch:
            return

        request_codes = set(self._position_sync_batch)
        self._position_sync_batch.clear()
        self._position_sync_pending.add("__batch__")

        worker = Worker(self.rest_client.get_positions, self.current_account)
        worker.signals.result.connect(
            lambda positions, codes=request_codes: self._on_position_sync_result(codes, positions)
        )
        worker.signals.error.connect(lambda e, codes=request_codes: self._on_position_sync_error(codes, e))
        self.threadpool.start(worker)

    def _on_position_sync_result(self, code: Iterable[str], positions):
        if positions is None:
            self._on_position_sync_error(code, RuntimeError("계좌 포지션 조회 결과가 비어 있습니다."))
            return

        self._position_sync_pending.discard("__batch__")
        self._position_sync_retry_count = 0

        if isinstance(code, str):
            target_codes: Set[str] = {code} if code else set()
        else:
            target_codes = {c for c in code if c}

        if not target_codes:
            return

        positions_by_code = {getattr(pos, "code", ""): pos for pos in positions or []}
        now = datetime.datetime.now()
        self._update_order_health_mode(now)

        for code_item in target_codes:
            info = self.universe.get(code_item)
            if not info:
                continue

            sync_failed_codes = getattr(self, "_sync_failed_codes", set())
            was_sync_failed = code_item in sync_failed_codes
            if was_sync_failed and hasattr(self, "_sync_failed_codes"):
                self._sync_failed_codes.discard(code_item)
                info["sync_failed_reason"] = ""
                if hasattr(self, "log"):
                    self.log(f"[복구] {info.get('name', code_item)} 포지션 동기화가 정상 복구되었습니다.")

            prev_held = int(info.get("held", 0))
            prev_buy_price = int(info.get("buy_price", 0))
            pending = self._pending_order_state.get(code_item)
            matched = positions_by_code.get(code_item)

            if matched:
                new_held = max(0, int(getattr(matched, "quantity", 0)))
                new_buy_price = int(getattr(matched, "buy_price", 0))
                new_invest_amount = int(getattr(matched, "buy_amount", 0))
            else:
                new_held = 0
                new_buy_price = 0
                new_invest_amount = 0

            delta = new_held - prev_held
            exec_event = self._last_exec_event.get(code_item, {})

            if delta > 0:
                buy_qty = delta
                fill_price = self._to_int(exec_event.get("price", 0)) if exec_event.get("side") == "buy" else 0
                if fill_price <= 0:
                    fill_price = new_buy_price or int(info.get("current", 0))
                expected_price = self._to_int(pending.get("expected_price", 0)) if pending else 0
                if expected_price <= 0:
                    expected_price = int(info.get("current", 0) or fill_price)
                self._record_slippage_bps(expected_price, fill_price, code_item)
                amount = max(0, fill_price * buy_qty)

                self._add_trade(
                    {
                        "code": code_item,
                        "name": info.get("name", code_item),
                        "type": "매수",
                        "price": fill_price,
                        "quantity": buy_qty,
                        "amount": amount,
                        "profit": 0,
                        "reason": "체결동기화",
                    }
                )
                self.strategy.update_market_investment(code_item, amount, is_buy=True)
                self.strategy.update_sector_investment(code_item, amount, is_buy=True)
                if self.sound:
                    self.sound.play_buy()
                # Keep remaining reservation for partial fills; only consume filled portion.
                pending_state, remaining_qty, reserved_consumed = self._apply_pending_fill(code_item, buy_qty)
                reserve_amount = reserved_consumed if reserved_consumed > 0 else max(0, expected_price * buy_qty)
                self._consume_reserved_cash_safe(code_item, amount=reserve_amount, reason="BUY_FILLED_PARTIAL")
                if pending_state == "filled" or remaining_qty <= 0:
                    self._release_reserved_cash_safe(code_item, reason="BUY_FILLED_DONE", refund=False)
                    self._clear_pending_order(code_item, final_state="filled")

            elif delta < 0:
                sell_qty = -delta
                fill_price = self._to_int(exec_event.get("price", 0)) if exec_event.get("side") == "sell" else 0
                if fill_price <= 0:
                    fill_price = int(info.get("current", 0))
                expected_price = self._to_int(pending.get("expected_price", 0)) if pending else 0
                if expected_price <= 0:
                    expected_price = int(info.get("current", 0) or fill_price)
                self._record_slippage_bps(expected_price, fill_price, code_item)
                amount = max(0, fill_price * sell_qty)
                profit = (fill_price - prev_buy_price) * sell_qty if prev_buy_price > 0 else 0
                reason = pending.get("reason", "체결동기화") if pending else "체결동기화"
                prev_invest_amount = int(info.get("invest_amount", 0) or 0)
                if prev_held > 0:
                    unit_cost = prev_invest_amount / prev_held if prev_invest_amount > 0 else float(prev_buy_price)
                    cost_decrease = max(0, int(round(unit_cost * sell_qty)))
                else:
                    cost_decrease = max(0, int(prev_buy_price * sell_qty))

                self._add_trade(
                    {
                        "code": code_item,
                        "name": info.get("name", code_item),
                        "type": "매도",
                        "price": fill_price,
                        "quantity": sell_qty,
                        "amount": amount,
                        "profit": profit,
                        "reason": reason,
                    }
                )
                self.strategy.update_consecutive_results(profit > 0)
                self.strategy.update_market_investment(code_item, amount, is_buy=False, cost_amount=cost_decrease)
                self.strategy.update_sector_investment(code_item, amount, is_buy=False, cost_amount=cost_decrease)
                if self.sound:
                    self.sound.play_sell() if profit > 0 else self.sound.play_loss()
                if self.telegram:
                    self.telegram.send(f"매도 체결: {info.get('name', code_item)} {sell_qty}주 손익: {profit:+,}원")
                pending_state, remaining_qty, _ = self._apply_pending_fill(code_item, sell_qty)
                if pending_state == "filled" or remaining_qty <= 0:
                    self._clear_pending_order(code_item, final_state="filled")

            info["held"] = new_held
            info["buy_price"] = new_buy_price
            info["invest_amount"] = new_invest_amount

            if new_held > 0:
                info["status"] = "holding"
                info["cooldown_until"] = None
                if not info.get("buy_time"):
                    info["buy_time"] = now
                if delta > 0 and prev_held <= 0:
                    info["entry_origin"] = "session_new"
                    info["time_stop_eligible"] = True
            else:
                info["status"] = "watch"
                info["buy_time"] = None
                info["max_profit_rate"] = 0
                info["partial_profit_levels"] = set()
                info["entry_origin"] = "watch"
                info["time_stop_eligible"] = True
                if prev_held > 0 and hasattr(self, "chk_use_cooldown") and self.chk_use_cooldown.isChecked():
                    cooldown_minutes = int(self.spin_cooldown_min.value())
                    info["cooldown_until"] = now + datetime.timedelta(minutes=cooldown_minutes)
                    info["status"] = "cooldown"

            cooldown_until = info.get("cooldown_until")
            if info.get("held", 0) == 0 and cooldown_until and now < cooldown_until:
                info["status"] = "cooldown"

            pending = self._pending_order_state.get(code_item)
            if self._pending_is_active(pending):
                if pending.get("side") == "buy" and info.get("held", 0) == 0:
                    info["status"] = "buy_submitted"
                elif pending.get("side") == "sell" and info.get("held", 0) > 0:
                    info["status"] = "sell_submitted"

            if delta != 0:
                self._last_exec_event.pop(code_item, None)

            self._diag_touch_safe(
                code_item,
                sync_status=str(info.get("status", "")),
                retry_count=0,
                last_sync_error="",
            )
            self._dirty_codes.add(code_item)

        recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
        if callable(recompute_count):
            recompute_count()
        else:
            held_count = sum(1 for v in self.universe.values() if int(v.get("held", 0)) > 0)
            pending_buy = sum(
                1
                for c, state in self._pending_order_state.items()
                if self._pending_is_active(state)
                and state.get("side") == "buy"
                and int(self.universe.get(c, {}).get("held", 0)) == 0
            )
            self._holding_or_pending_count = held_count + pending_buy

        if self._position_sync_batch and not self._position_sync_scheduled:
            self._position_sync_scheduled = True
            delay_ms = max(0, int(Config.POSITION_SYNC_DEBOUNCE_MS))
            QTimer.singleShot(delay_ms, lambda: self._sync_position_from_account(""))

        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _on_position_sync_error(self, code: Iterable[str], error: Exception):
        if isinstance(code, str):
            failed_codes: Set[str] = {code} if code else set()
        else:
            failed_codes = {c for c in code if c}

        self._position_sync_pending.discard("__batch__")
        if isinstance(code, str):
            if code:
                self._position_sync_batch.add(code)
        else:
            self._position_sync_batch.update(c for c in code if c)
        self._position_sync_retry_count = int(getattr(self, "_position_sync_retry_count", 0)) + 1
        max_retries = max(1, int(getattr(Config, "POSITION_SYNC_MAX_RETRIES", 5)))

        for code_item in failed_codes:
            info = getattr(self, "universe", {}).get(code_item, {})
            self._diag_touch_safe(
                code_item,
                sync_status=str(info.get("status", "")),
                retry_count=self._position_sync_retry_count,
                last_sync_error=str(error),
            )

        if self._position_sync_retry_count > max_retries:
            dropped_codes = set(self._position_sync_batch) or failed_codes
            dropped = len(dropped_codes)
            for code_item in dropped_codes:
                pending = getattr(self, "_pending_order_state", {}).get(code_item, {})
                side = str(pending.get("side", ""))
                if hasattr(self, "_pending_order_state"):
                    self._mark_pending_state(code_item, "sync_failed")
                    self._clear_pending_order(code_item, final_state="sync_failed")
                if side == "buy":
                    self._release_reserved_cash_safe(code_item, reason="SYNC_FAILED", refund=True)
                info = getattr(self, "universe", {}).get(code_item)
                if info is None:
                    continue
                info["status"] = "sync_failed"
                info["cooldown_until"] = None
                info["sync_failed_reason"] = str(error)
                if hasattr(self, "_sync_failed_codes"):
                    self._sync_failed_codes.add(code_item)
                if hasattr(self, "_dirty_codes"):
                    self._dirty_codes.add(code_item)
                self._diag_touch_safe(
                    code_item,
                    sync_status="sync_failed",
                    retry_count=0,
                    last_sync_error=str(error),
                )
                self._log_sync_fail_once(
                    code_item,
                    f"[안전차단] {info.get('name', code_item)} 포지션 동기화 실패 누적으로 자동주문을 차단했습니다.",
                )

            self._position_sync_batch.clear()
            self._position_sync_scheduled = False
            self._position_sync_retry_count = 0
            self.logger.warning(f"포지션동기화 재시도 초과로 배치를 폐기합니다. ({dropped}건: {error})")
            recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
            if callable(recompute_count):
                recompute_count()
            else:
                universe = getattr(self, "universe", {})
                pending_state = getattr(self, "_pending_order_state", {})
                held_count = sum(1 for v in universe.values() if int(v.get("held", 0)) > 0)
                pending_buy = sum(
                    1
                    for c, state in pending_state.items()
                    if self._pending_is_active(state)
                    and state.get("side") == "buy"
                    and int(universe.get(c, {}).get("held", 0)) == 0
                )
                self._holding_or_pending_count = held_count + pending_buy
            if hasattr(self, "sig_update_table") and not hasattr(self, "_ui_flush_timer"):
                self.sig_update_table.emit()
            return

        backoff_cap_ms = max(
            int(getattr(Config, "POSITION_SYNC_DEBOUNCE_MS", 200)),
            int(getattr(Config, "POSITION_SYNC_BACKOFF_MAX_MS", 5000)),
        )
        delay_ms = min(
            int(Config.POSITION_SYNC_DEBOUNCE_MS) * (2 ** (self._position_sync_retry_count - 1)),
            backoff_cap_ms,
        )
        self.logger.warning(
            f"포지션동기화 실패({self._position_sync_retry_count}/{max_retries}), {delay_ms}ms 후 재시도: {error}"
        )
        if self._position_sync_batch and not self._position_sync_scheduled:
            self._position_sync_scheduled = True
            QTimer.singleShot(delay_ms, lambda: self._sync_position_from_account(""))
