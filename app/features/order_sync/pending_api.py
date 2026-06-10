"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from collections import deque
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class OrderSyncPendingApiMixin(TraderMixinBase):
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
