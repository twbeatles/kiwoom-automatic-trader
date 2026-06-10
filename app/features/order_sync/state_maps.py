"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from collections import deque
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class OrderSyncStateMapsMixin(TraderMixinBase):
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
