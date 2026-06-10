"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from collections import deque
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class OrderSyncPendingStateMixin(TraderMixinBase):
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
