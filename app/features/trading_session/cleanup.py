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


class TradingSessionCleanupMixin(TraderMixinBase):
    def _collect_liquidation_targets(self) -> List[Tuple[str, Dict[str, Any]]]:
        targets: List[Tuple[str, Dict[str, Any]]] = []
        for code, info in getattr(self, "universe", {}).items():
            if int(info.get("held", 0) or 0) > 0:
                targets.append((code, info))
        for code, info in self._external_positions_map().items():
            if int(info.get("held", 0) or 0) > 0:
                targets.append((code, info))
        return targets
    def _force_account_position_sync(self, reason: str = "") -> bool:
        rest_client = getattr(self, "rest_client", None)
        current_account = str(getattr(self, "current_account", "") or "")
        if not (rest_client and current_account):
            return False
        try:
            positions = rest_client.get_positions(current_account)
        except Exception as exc:
            self._log_once(f"force_sync_error:{reason}", f"[account-sync] refresh failed ({reason}): {exc}")
            return False
        if positions is None:
            return False
        self._apply_account_position_snapshot(
            list(getattr(self, "universe", {}).keys()),
            positions,
            reset_tracking=False,
            rebuild_strategy=False,
            log_external=False,
        )
        return True
    def _collect_active_order_cleanup_targets(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        live_targets: List[Dict[str, Any]] = []
        placeholders: List[Dict[str, Any]] = []

        for code, pending in list(getattr(self, "_pending_order_state", {}).items()):
            if not self._pending_is_active_safe(pending):
                continue
            side = str(pending.get("side", "") or "").lower()
            children = self._pending_children_safe(pending)
            if children:
                for index, child in enumerate(children, start=1):
                    remaining_qty = max(0, int(child.get("remaining_qty", 0) or 0))
                    if remaining_qty <= 0:
                        continue
                    target = {
                        "source": "pending_child",
                        "code": code,
                        "side": side,
                        "order_no": str(child.get("order_no", "") or "").strip(),
                        "quantity": remaining_qty,
                        "child_index": index,
                    }
                    if target["order_no"]:
                        live_targets.append(target)
                    else:
                        placeholders.append(target)
                continue

            remaining_qty = max(0, int(pending.get("remaining_qty", 0) or 0))
            if remaining_qty <= 0:
                continue
            target = {
                "source": "pending",
                "code": code,
                "side": side,
                "order_no": str(pending.get("order_no", "") or "").strip(),
                "quantity": remaining_qty,
            }
            if target["order_no"]:
                live_targets.append(target)
            else:
                placeholders.append(target)

        for code, pending in list(self._manual_pending_entries().items()):
            if not isinstance(pending, dict):
                continue
            side = str(pending.get("side", "") or "").lower()
            remaining_qty = max(0, int(pending.get("remaining_qty", 0) or 0))
            reserved_cash = max(0, int(pending.get("reserved_cash", 0) or 0))
            order_no = str(pending.get("order_no", "") or "").strip()
            if order_no and remaining_qty > 0:
                live_targets.append(
                    {
                        "source": "manual",
                        "code": code,
                        "side": side,
                        "order_no": order_no,
                        "quantity": remaining_qty,
                    }
                )
            elif remaining_qty > 0 or reserved_cash > 0 or self._pending_is_active_safe(pending):
                placeholders.append(
                    {
                        "source": "manual",
                        "code": code,
                        "side": side,
                        "order_no": order_no,
                        "quantity": remaining_qty,
                    }
                )

        return live_targets, placeholders
    def _cleanup_target_is_active(self, target: Dict[str, Any]) -> bool:
        source = str(target.get("source", "") or "")
        code = str(target.get("code", "") or "")
        order_no = str(target.get("order_no", "") or "").strip()
        if source == "manual":
            pending = self._manual_pending_entries().get(code)
            if not isinstance(pending, dict) or not self._pending_is_active_safe(pending):
                return False
            if order_no and str(pending.get("order_no", "") or "").strip() not in {"", order_no}:
                return False
            return max(0, int(pending.get("remaining_qty", 0) or 0)) > 0

        pending = getattr(self, "_pending_order_state", {}).get(code)
        if not isinstance(pending, dict) or not self._pending_is_active_safe(pending):
            return False
        if source == "pending_child":
            child_index = max(1, int(target.get("child_index", 0) or 0)) - 1
            children = self._pending_children_safe(pending)
            if child_index >= len(children):
                return False
            child = children[child_index]
            child_order_no = str(child.get("order_no", "") or "").strip()
            if order_no and child_order_no not in {"", order_no}:
                return False
            state = str(child.get("state", "submitted") or "submitted").lower()
            active_states = set(getattr(self, "ACTIVE_PENDING_STATES", {"submitted", "partial"}))
            return state in active_states and max(0, int(child.get("remaining_qty", 0) or 0)) > 0

        pending_order_no = str(pending.get("order_no", "") or "").strip()
        if order_no and pending_order_no not in {"", order_no}:
            return False
        return max(0, int(pending.get("remaining_qty", 0) or 0)) > 0
    def _force_finalize_cleanup_target(self, target: Dict[str, Any], final_state: str, reason: str = ""):
        source = str(target.get("source", "") or "")
        code = str(target.get("code", "") or "")
        side = str(target.get("side", "") or "").lower()
        order_no = str(target.get("order_no", "") or "").strip()
        reason_text = reason or final_state
        now = datetime.datetime.now()

        if source == "manual":
            pending = self._manual_pending_entries().get(code, {})
            if side == "buy":
                refund_amount = max(0, int(pending.get("reserved_cash", 0) or 0))
                if refund_amount > 0:
                    self._release_reserved_cash_amount_safe(
                        code,
                        refund_amount,
                        reason=f"MANUAL_CLEANUP_{reason_text}",
                        refund=True,
                    )
            self._clear_manual_pending_order(code)
        elif source == "pending_child":
            pending = getattr(self, "_pending_order_state", {}).get(code, {})
            children = self._pending_children_safe(pending)
            child_index = max(1, int(target.get("child_index", 0) or 0)) - 1
            if child_index < len(children):
                child = children[child_index]
                child_order_no = str(child.get("order_no", "") or "").strip()
                if order_no and child_order_no not in {"", order_no}:
                    child = None
                if child is not None:
                    refund_amount = max(0, int(child.get("reserved_cash", 0) or 0)) if side == "buy" else 0
                    if refund_amount > 0:
                        self._release_reserved_cash_amount_safe(
                            code,
                            refund_amount,
                            reason=f"PENDING_CHILD_CLEANUP_{reason_text}",
                            refund=True,
                        )
                    child["state"] = final_state
                    child["remaining_qty"] = 0
                    child["reserved_cash"] = 0
                    child["updated_at"] = now
                    aggregate_state, remaining_qty = self._refresh_pending_order_aggregate(code)
                    active_states = set(getattr(self, "ACTIVE_PENDING_STATES", {"submitted", "partial"}))
                    if remaining_qty <= 0 or aggregate_state not in active_states:
                        clear_state = "filled" if aggregate_state == "filled" else final_state
                        self._clear_pending_order(code, final_state=clear_state)
        else:
            if side == "buy":
                self._release_reserved_cash_safe(
                    code,
                    reason=f"PENDING_CLEANUP_{reason_text}",
                    refund=True,
                )
            self._mark_pending_state(code, final_state)
            self._clear_pending_order(code, final_state=final_state)

        info = self._get_tracked_position_info(code)
        if info:
            pending = getattr(self, "_pending_order_state", {}).get(code, {})
            kind = self._tracked_position_kind(code)
            if self._pending_is_active_safe(pending):
                side_text = str(pending.get("side", "") or "").lower()
                if side_text == "sell":
                    info["status"] = "sell_submitted"
                elif side_text == "buy":
                    info["status"] = "buy_submitted"
            elif int(info.get("held", 0) or 0) > 0:
                info["status"] = "external_holding" if kind == "external" else "holding"
            elif kind == "universe":
                info["status"] = "watch"

            diag_touch = getattr(self, "_diag_touch", None)
            if callable(diag_touch):
                diag_touch(code, sync_status=str(info.get("status", "")), retry_count=0, last_sync_error="")
            if kind == "universe":
                dirty_codes = getattr(self, "_dirty_codes", None)
                if isinstance(dirty_codes, set):
                    dirty_codes.add(code)
            elif hasattr(self, "_diagnostics_dirty_codes") and isinstance(self._diagnostics_dirty_codes, set):
                self._diagnostics_dirty_codes.add(code)
    def _mark_cleanup_target_failed(self, target: Dict[str, Any], reason: str = ""):
        source = str(target.get("source", "") or "")
        code = str(target.get("code", "") or "")
        now = datetime.datetime.now()
        if not code:
            return

        if source == "manual":
            pending = self._manual_pending_entries().get(code)
            if isinstance(pending, dict):
                pending["state"] = "sync_failed"
                pending["updated_at"] = now
            return

        if source == "pending_child":
            pending = getattr(self, "_pending_order_state", {}).get(code, {})
            if not isinstance(pending, dict):
                return
            children = self._pending_children_safe(pending)
            child_index = max(1, int(target.get("child_index", 0) or 0)) - 1
            if child_index < len(children):
                child = children[child_index]
                child["state"] = "sync_failed"
                child["updated_at"] = now
                refresher = getattr(self, "_refresh_pending_order_aggregate", None)
                if callable(refresher):
                    refresher(code)
                else:
                    pending["state"] = "sync_failed"
                    pending["updated_at"] = now
            return

        marker = getattr(self, "_mark_pending_state", None)
        if callable(marker):
            marker(code, "sync_failed")
        else:
            pending = getattr(self, "_pending_order_state", {}).get(code)
            if isinstance(pending, dict):
                pending["state"] = "sync_failed"
                pending["updated_at"] = now

        if hasattr(self, "log"):
            self.log(f"[order-cleanup] cancel unresolved ({reason}) {code}: state=sync_failed")
    def _cleanup_active_orders(self, reason: str, timeout_sec: float = 8.0) -> Dict[str, Any]:
        live_targets, placeholders = self._collect_active_order_cleanup_targets()
        if not live_targets and not placeholders:
            self._force_account_position_sync(reason=f"{reason}_noop")
            return {"live_targets": [], "placeholders": [], "unresolved_codes": []}

        if hasattr(self, "log"):
            self.log(
                f"[order-cleanup] {reason}: live={len(live_targets)} placeholder={len(placeholders)}"
            )

        client = getattr(self, "rest_client", None)
        account = str(getattr(self, "current_account", "") or "")
        for target in live_targets:
            order_no = str(target.get("order_no", "") or "").strip()
            quantity = max(0, int(target.get("quantity", 0) or 0))
            success = False
            message = ""
            if client is not None and account and order_no and quantity > 0:
                try:
                    result = client.cancel_order(account, order_no, target["code"], quantity)
                    success = bool(getattr(result, "success", False))
                    message = str(getattr(result, "message", "") or "")
                except Exception as exc:
                    message = str(exc)
            else:
                message = "API/account not ready"
            target["cancel_success"] = success
            target["cancel_message"] = message
            if not success and hasattr(self, "log"):
                self.log(
                    f"[order-cleanup] cancel request failed ({reason}) {target['code']} {order_no}: {message}"
                )

        unresolved = list(live_targets)
        deadline = time.monotonic() + max(0.1, float(timeout_sec or 0.0))
        while unresolved and time.monotonic() < deadline:
            self._force_account_position_sync(reason=f"{reason}_poll")
            unresolved = [target for target in live_targets if self._cleanup_target_is_active(target)]
            if not unresolved:
                break
            app = QCoreApplication.instance()
            if app is not None:
                app.processEvents()
            time.sleep(0.2)

        self._force_account_position_sync(reason=f"{reason}_final")
        unresolved = [target for target in live_targets if self._cleanup_target_is_active(target)]

        for target in placeholders:
            self._force_finalize_cleanup_target(target, final_state="cancelled", reason=reason)

        for target in live_targets:
            if not self._cleanup_target_is_active(target):
                continue
            if bool(target.get("cancel_success")):
                self._force_finalize_cleanup_target(target, final_state="cancelled", reason=reason)
            else:
                self._mark_cleanup_target_failed(target, reason=reason)

        unresolved_codes = sorted({str(target.get("code", "") or "") for target in unresolved if target.get("code")})
        if unresolved_codes and hasattr(self, "log"):
            preview = ", ".join(unresolved_codes[:5])
            suffix = " ..." if len(unresolved_codes) > 5 else ""
            self.log(f"[order-cleanup] unresolved before local finalization ({reason}): {preview}{suffix}")

        self._force_account_position_sync(reason=f"{reason}_post_finalize")
        recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
        if callable(recompute_count):
            recompute_count()
        if not hasattr(self, "_ui_flush_timer"):
            signal = getattr(self, "sig_update_table", None)
            emit = getattr(signal, "emit", None)
            if callable(emit):
                emit()
        return {
            "live_targets": live_targets,
            "placeholders": placeholders,
            "unresolved_codes": unresolved_codes,
        }
    def _cleanup_cancel_requests_worker(self, live_targets: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
        client = getattr(self, "rest_client", None)
        account = str(getattr(self, "current_account", "") or "")
        rows: List[Dict[str, Any]] = []
        for raw_target in live_targets:
            target = dict(raw_target)
            order_no = str(target.get("order_no", "") or "").strip()
            quantity = max(0, int(target.get("quantity", 0) or 0))
            success = False
            message = ""
            if client is not None and account and order_no and quantity > 0:
                try:
                    result = client.cancel_order(account, order_no, target["code"], quantity)
                    success = bool(getattr(result, "success", False))
                    message = str(getattr(result, "message", "") or "")
                except Exception as exc:
                    message = str(exc)
            else:
                message = "API/account not ready"
            target["cancel_success"] = success
            target["cancel_message"] = message
            target["cleanup_reason"] = reason
            rows.append(target)
        return rows
    def _finalize_order_cleanup_requests(
        self,
        reason: str,
        live_targets: List[Dict[str, Any]],
        placeholders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        for target in placeholders:
            self._force_finalize_cleanup_target(target, final_state="cancelled", reason=reason)

        for target in live_targets:
            if bool(target.get("cancel_success")):
                self._force_finalize_cleanup_target(target, final_state="cancelled", reason=reason)
            else:
                if hasattr(self, "log"):
                    self.log(
                        f"[order-cleanup] cancel request failed ({reason}) "
                        f"{target.get('code')} {target.get('order_no')}: {target.get('cancel_message', '')}"
                    )
                self._mark_cleanup_target_failed(target, reason=reason)

        self._force_account_position_sync(reason=f"{reason}_async_finalize")
        recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
        if callable(recompute_count):
            recompute_count()
        if not hasattr(self, "_ui_flush_timer"):
            signal = getattr(self, "sig_update_table", None)
            emit = getattr(signal, "emit", None)
            if callable(emit):
                emit()
        unresolved_codes = sorted(
            {
                str(target.get("code", "") or "")
                for target in live_targets
                if target.get("code") and not bool(target.get("cancel_success"))
            }
        )
        return {
            "live_targets": live_targets,
            "placeholders": placeholders,
            "unresolved_codes": unresolved_codes,
        }
    def _cleanup_active_orders_async(self, reason: str, on_done=None) -> bool:
        threadpool = getattr(self, "threadpool", None)
        starter = getattr(threadpool, "start", None)
        if not callable(starter):
            return False

        live_targets, placeholders = self._collect_active_order_cleanup_targets()
        if not live_targets and not placeholders:
            self._force_account_position_sync(reason=f"{reason}_noop")
            if callable(on_done):
                on_done({"live_targets": [], "placeholders": [], "unresolved_codes": []})
            return False

        if hasattr(self, "log"):
            self.log(f"[order-cleanup] {reason} async: live={len(live_targets)} placeholder={len(placeholders)}")
        self._order_cleanup_inflight = True
        if hasattr(self, "btn_start"):
            self.btn_start.setEnabled(False)

        worker = Worker(self._cleanup_cancel_requests_worker, [dict(row) for row in live_targets], reason)

        def finish(rows):
            self._order_cleanup_inflight = False
            result = self._finalize_order_cleanup_requests(reason, list(rows or []), placeholders)
            if not getattr(self, "is_running", False) and hasattr(self, "btn_start"):
                self.btn_start.setEnabled(True)
            if callable(on_done):
                on_done(result)

        def fail(exc):
            self._order_cleanup_inflight = False
            if hasattr(self, "log"):
                self.log(f"[order-cleanup] async failed ({reason}): {exc}")
            result = self._cleanup_active_orders(reason, timeout_sec=0.1)
            if not getattr(self, "is_running", False) and hasattr(self, "btn_start"):
                self.btn_start.setEnabled(True)
            if callable(on_done):
                on_done(result)

        worker.signals.result.connect(finish)
        worker.signals.error.connect(fail)
        starter(worker)
        return True
    def _cancel_pending_orders_before_stop(self) -> Dict[str, Any]:
        return self._cleanup_active_orders("stop_trading", timeout_sec=0.1)
