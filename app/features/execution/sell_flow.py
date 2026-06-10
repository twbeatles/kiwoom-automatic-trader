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


class ExecutionSellFlowMixin(TraderMixinBase):
    def _execute_sell(self, code: str, quantity: int, price: int, reason: str):
        """Submit sell order asynchronously."""
        tracked_getter = getattr(self, "_get_tracked_position_info", None)
        raw_info = tracked_getter(code) if callable(tracked_getter) else self.universe.get(code, {})
        info = raw_info if isinstance(raw_info, dict) else {}
        external_positions = getattr(self, "external_positions", {})
        is_external = code not in self.universe and isinstance(external_positions, dict) and code in external_positions
        name = info.get("name", code)
        buy_price = info.get("buy_price", 0)

        if quantity <= 0:
            self.log(f"SELL quantity invalid [{name}]: {quantity}")
            return
        pending = self._pending_order_state.get(code, {})
        if self._is_pending_active(pending) and pending.get("side") == "sell":
            return
        if info.get("status") in {"selling", "sell_submitted"}:
            return

        held = int(info.get("held", 0))
        if held > 0 and quantity > held:
            quantity = held

        if self._is_signal_only_mode():
            self._record_signal_only_order(
                side="sell",
                code=code,
                quantity=quantity,
                price=price,
                reason=reason,
                payload={"held": held},
            )
            return

        if not (self.rest_client and self.current_account):
            self.log(f"SELL failed [{name}]: API/account not ready")
            return

        info["status"] = "selling"
        diag_touch = getattr(self, "_diag_touch", None)
        if callable(diag_touch):
            diag_touch(code, pending_side="sell", pending_reason=reason, sync_status="selling")
        self._dirty_codes.add(code)

        cfg = getattr(self, "config", None)
        policy = str(getattr(cfg, "execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market")))
        sell_fn, args = ExecutionPolicy.select_sell(self.rest_client, policy, self.current_account, code, quantity, price)
        worker = Worker(sell_fn, *args)
        worker.signals.result.connect(
            lambda res: self._on_sell_result(res, code, name, quantity, price, buy_price, reason)
        )
        worker.signals.error.connect(lambda e: self._on_sell_error(e, code, name))
        self.threadpool.start(worker)
    def _on_sell_error(self, e, code, name):
        """Handle sell error."""
        self.log(f"SELL error [{name}]: {e}")
        record_failure = getattr(self, "_record_order_failure", None)
        if callable(record_failure):
            record_failure("SELL_ERROR", code=code)
        self._clear_pending_order(code)
        if code in self.universe:
            self.universe[code]["status"] = "holding"
        else:
            external_positions = getattr(self, "external_positions", {})
            if isinstance(external_positions, dict) and code in external_positions:
                external_positions[code]["status"] = "external_holding"
        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    def _on_sell_result(self, result, code, name, quantity, price, buy_price, reason):
        """Handle sell result in main thread."""
        external_positions = getattr(self, "external_positions", {})
        if result.success:
            if code in self.universe:
                self.universe[code]["status"] = "sell_submitted"
            elif isinstance(external_positions, dict) and code in external_positions:
                external_positions[code]["status"] = "sell_submitted"
            self._set_pending_order(
                code,
                "sell",
                reason,
                expected_price=int(price or 0),
                submitted_qty=int(quantity or 0),
                order_no=str(getattr(result, "order_no", "") or ""),
            )
            self.log(f"SELL submitted: {name} {quantity} shares ({reason})")
            self._sync_position_from_account(code)
        else:
            self.log(f"SELL rejected [{name}]: {result.message}")
            record_failure = getattr(self, "_record_order_failure", None)
            if callable(record_failure):
                record_failure("SELL_REJECTED", code=code)
            if code in self.universe:
                self.universe[code]["status"] = "holding"
            elif isinstance(external_positions, dict) and code in external_positions:
                external_positions[code]["status"] = "external_holding"
            self._clear_pending_order(code)

        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
