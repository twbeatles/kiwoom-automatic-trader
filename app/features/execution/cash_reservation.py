"""Execution engine mixin for KiwoomProTrader."""

import datetime
import json
import time
from collections import deque
from pathlib import Path

from api.models import ExecutionData
from app.support.execution_policy import ExecutionPolicy
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class ExecutionCashReservationMixin(TraderMixinBase):
    def _reserved_cash_map(self):
        mapping = getattr(self, "_reserved_cash_by_code", None)
        if not isinstance(mapping, dict):
            mapping = {}
            self._reserved_cash_by_code = mapping
        return mapping
    def _reserve_cash_for_buy(self, code: str, amount: int):
        amount = max(0, int(amount or 0))
        if not code or amount <= 0:
            return 0
        mapping = self._reserved_cash_map()
        mapping[code] = int(mapping.get(code, 0)) + amount
        current_v = int(getattr(self, "virtual_deposit", int(getattr(self, "deposit", 0) or 0)) or 0)
        self.virtual_deposit = max(0, current_v - amount)
        return amount
    def _release_reserved_cash(self, code: str, reason: str = "", refund: bool = True) -> int:
        if not code:
            return 0
        mapping = self._reserved_cash_map()
        amount = int(mapping.pop(code, 0) or 0)
        if amount <= 0:
            return 0

        if refund:
            base = int(getattr(self, "virtual_deposit", int(getattr(self, "deposit", 0) or 0)) or 0)
            self.virtual_deposit = max(0, base + amount)

        if reason and hasattr(self, "log"):
            action = "refunded" if refund else "released"
            self.log(f"Reserved cash {action} [{code}]: {amount:,} ({reason})")
        return amount
    def _release_reserved_cash_amount(self, code: str, amount: int, reason: str = "", refund: bool = True) -> int:
        amount = max(0, int(amount or 0))
        if not code or amount <= 0:
            return 0

        mapping = self._reserved_cash_map()
        current = max(0, int(mapping.get(code, 0) or 0))
        released = min(current, amount)
        if released <= 0:
            return 0

        remaining = current - released
        if remaining > 0:
            mapping[code] = remaining
        else:
            mapping.pop(code, None)

        if refund:
            base = int(getattr(self, "virtual_deposit", int(getattr(self, "deposit", 0) or 0)) or 0)
            self.virtual_deposit = max(0, base + released)

        if reason and hasattr(self, "log"):
            action = "refunded" if refund else "released"
            self.log(f"Reserved cash {action} [{code}]: {released:,} ({reason})")
        return released
    def _release_all_reserved_cash(self, reason: str = "STOP_TRADING") -> int:
        mapping = self._reserved_cash_map()
        if not mapping:
            return 0
        total = 0
        for code in list(mapping.keys()):
            total += self._release_reserved_cash(code, reason=reason, refund=True)
        return total
    def _consume_reserved_cash(self, code: str, amount: int, reason: str = "") -> int:
        amount = max(0, int(amount or 0))
        if not code or amount <= 0:
            return 0
        mapping = self._reserved_cash_map()
        current = max(0, int(mapping.get(code, 0) or 0))
        consumed = min(current, amount)
        remaining = current - consumed
        if remaining > 0:
            mapping[code] = remaining
        else:
            mapping.pop(code, None)
        if consumed > 0 and reason and hasattr(self, "log"):
            self.log(f"Reserved cash consumed [{code}]: {consumed:,} ({reason})")
        return consumed
    def _recompute_holding_or_pending_count(self) -> int:
        universe = getattr(self, "universe", {})
        external_positions = getattr(self, "external_positions", {})
        pending_state = getattr(self, "_pending_order_state", {})
        manual_pending_state = getattr(self, "_manual_pending_state", {})
        held_count = sum(1 for v in universe.values() if int(v.get("held", 0)) > 0)
        if isinstance(external_positions, dict):
            held_count += sum(1 for v in external_positions.values() if int(v.get("held", 0)) > 0)
        pending_buy = sum(
            1
            for c, state in pending_state.items()
            if self._is_pending_active(state)
            and state.get("side") == "buy"
            and int(
                (
                    universe.get(c, {})
                    if c in universe
                    else external_positions.get(c, {}) if isinstance(external_positions, dict) else {}
                ).get("held", 0)
            ) == 0
        )
        manual_pending_buy = sum(
            1
            for c, state in manual_pending_state.items()
            if self._is_pending_active(state)
            and state.get("side") == "buy"
            and int(
                (
                    universe.get(c, {})
                    if c in universe
                    else external_positions.get(c, {}) if isinstance(external_positions, dict) else {}
                ).get("held", 0)
            ) == 0
        )
        self._holding_or_pending_count = held_count + pending_buy + manual_pending_buy
        return self._holding_or_pending_count
    def _submit_split_buy_orders(self, code: str, child_orders: list[tuple[int, int]]) -> list[dict]:
        results: list[dict] = []
        account = str(getattr(self, "current_account", "") or "")
        client = getattr(self, "rest_client", None)
        if client is None or not account:
            raise RuntimeError("API/account not ready")

        for index, (quantity, price) in enumerate(child_orders, start=1):
            qty = max(0, int(quantity or 0))
            limit_price = max(1, int(price or 0))
            if qty <= 0:
                continue
            try:
                result = client.buy_limit(account, code, qty, limit_price)
                results.append(
                    {
                        "index": index,
                        "quantity": qty,
                        "price": limit_price,
                        "success": bool(getattr(result, "success", False)),
                        "order_no": str(getattr(result, "order_no", "") or ""),
                        "message": str(getattr(result, "message", "") or ""),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "index": index,
                        "quantity": qty,
                        "price": limit_price,
                        "success": False,
                        "order_no": "",
                        "message": str(exc),
                    }
                )
        return results
