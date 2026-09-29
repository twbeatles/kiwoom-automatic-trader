"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from collections import deque
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class OrderSyncPositionSyncMixin(TraderMixinBase):
    def _sync_position_from_account(self, code: str):
        """Sync positions from account API with debounce/batch."""
        external_positions = getattr(self, "external_positions", {})
        manual_pending = self._manual_pending_map()
        if code and (
            code in self.universe
            or (isinstance(external_positions, dict) and code in external_positions)
            or code in manual_pending
        ):
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
        sync_external_positions = getattr(self, "_sync_external_positions_from_account_positions", None)
        if callable(sync_external_positions):
            sync_external_positions(list(positions or []), rebuild_strategy=False, now_dt=now)

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
                new_available_qty = max(0, int(getattr(matched, "available_qty", new_held)))
                new_buy_price = int(getattr(matched, "buy_price", 0))
                new_invest_amount = int(getattr(matched, "buy_amount", 0))
            else:
                new_held = 0
                new_available_qty = 0
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
            info["available_qty"] = new_available_qty
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

            self._note_pending_empty_sync(code_item, matched, delta)
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
            external_positions = getattr(self, "external_positions", {})
            manual_pending_state = getattr(self, "_manual_pending_state", {})
            held_count = sum(1 for v in self.universe.values() if int(v.get("held", 0)) > 0)
            if isinstance(external_positions, dict):
                held_count += sum(1 for v in external_positions.values() if int(v.get("held", 0)) > 0)
            pending_buy = sum(
                1
                for c, state in self._pending_order_state.items()
                if self._pending_is_active(state)
                and state.get("side") == "buy"
                and int(
                    (
                        self.universe.get(c, {})
                        if c in self.universe
                        else external_positions.get(c, {}) if isinstance(external_positions, dict) else {}
                    ).get("held", 0)
                ) == 0
            )
            manual_pending_buy = sum(
                1
                for c, state in manual_pending_state.items()
                if self._pending_is_active(state)
                and state.get("side") == "buy"
                and int(
                    (
                        self.universe.get(c, {})
                        if c in self.universe
                        else external_positions.get(c, {}) if isinstance(external_positions, dict) else {}
                    ).get("held", 0)
                ) == 0
            )
            self._holding_or_pending_count = held_count + pending_buy + manual_pending_buy

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
                manual_pending = self._manual_pending_map().get(code_item, {})
                if hasattr(self, "_pending_order_state"):
                    self._mark_pending_state(code_item, "sync_failed")
                    self._clear_pending_order(code_item, final_state="sync_failed")
                if side == "buy":
                    self._release_reserved_cash_safe(code_item, reason="SYNC_FAILED", refund=True)
                manual_side = str(manual_pending.get("side", ""))
                if manual_side == "buy":
                    refund_amount = int(manual_pending.get("reserved_cash", 0) or 0)
                    if refund_amount > 0:
                        self._release_reserved_cash_amount_safe(
                            code_item,
                            refund_amount,
                            reason="MANUAL_SYNC_FAILED",
                            refund=True,
                        )
                if manual_pending:
                    self._clear_manual_pending_order(code_item)
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
                external_positions = getattr(self, "external_positions", {})
                pending_state = getattr(self, "_pending_order_state", {})
                manual_pending_state = getattr(self, "_manual_pending_state", {})
                held_count = sum(1 for v in universe.values() if int(v.get("held", 0)) > 0)
                if isinstance(external_positions, dict):
                    held_count += sum(1 for v in external_positions.values() if int(v.get("held", 0)) > 0)
                pending_buy = sum(
                    1
                    for c, state in pending_state.items()
                    if self._pending_is_active(state)
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
                    if self._pending_is_active(state)
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
    # =====================================================================
    # ISSUE-001: 성공-빈 동기화 vs 활성 pending 정합 조정
    # =====================================================================
    def _note_pending_empty_sync(self, code: str, matched, delta: int) -> None:
        """성공한 동기화에서 포지션도 없고 변동도 없는데 pending이 살아있으면 계수."""
        pending_state = getattr(self, "_pending_order_state", {})
        pending = pending_state.get(code) if isinstance(pending_state, dict) else None
        order_no = ""
        if isinstance(pending, dict):
            order_no = str(pending.get("order_no", "") or "").strip()
        if (
            matched is None
            and int(delta or 0) == 0
            and self._pending_is_active(pending)
            and order_no
        ):
            counts = self._pending_empty_sync_counts()
            counts[code] = int(counts.get(code, 0) or 0) + 1
            threshold = max(1, int(getattr(Config, "PENDING_RECONCILE_EMPTY_SYNCS", 3)))
            if int(counts.get(code, 0) or 0) >= threshold:
                self._schedule_pending_reconcile(code)
        else:
            self._reset_pending_empty_sync(code)
    def _schedule_pending_reconcile(self, code: str) -> None:
        """미체결 조회(ka10075)로 브로커 측 주문 실재를 재확인한다."""
        if not bool(getattr(self, "is_running", False)):
            return
        inflight = getattr(self, "_pending_reconcile_inflight", None)
        if not isinstance(inflight, set):
            inflight = set()
            self._pending_reconcile_inflight = inflight
        if code in inflight:
            return
        rest_client = getattr(self, "rest_client", None)
        account = str(getattr(self, "current_account", "") or "")
        get_orders = getattr(rest_client, "get_open_orders", None)
        if not callable(get_orders) or not account:
            return
        if not bool(getattr(rest_client, "supports_open_orders", False)):
            return
        pending_state = getattr(self, "_pending_order_state", {})
        pending = pending_state.get(code) if isinstance(pending_state, dict) else None
        order_no = ""
        if isinstance(pending, dict):
            order_no = str(pending.get("order_no", "") or "").strip()
        if not order_no:
            return
        threadpool = getattr(self, "threadpool", None)
        starter = getattr(threadpool, "start", None)
        if not callable(starter):
            return
        inflight.add(code)
        worker = Worker(get_orders, account)
        worker.signals.result.connect(
            lambda orders, c=code, o=order_no: self._on_pending_reconcile_result(c, o, orders)
        )
        worker.signals.error.connect(lambda err, c=code: self._on_pending_reconcile_error(c, err))
        starter(worker)
    def _on_pending_reconcile_result(self, code: str, expected_order_no: str, orders) -> None:
        inflight = getattr(self, "_pending_reconcile_inflight", None)
        if isinstance(inflight, set):
            inflight.discard(code)
        pending_state = getattr(self, "_pending_order_state", {})
        pending = pending_state.get(code) if isinstance(pending_state, dict) else None
        if not self._pending_is_active(pending) or not isinstance(pending, dict):
            self._reset_pending_empty_sync(code)
            return
        if str(pending.get("order_no", "") or "").strip() != str(expected_order_no or "").strip():
            return
        rows = [o for o in (orders or []) if o is not None] if isinstance(orders, (list, tuple)) else []
        still_open = any(
            str(getattr(o, "order_no", "") or "").strip() == str(expected_order_no or "").strip()
            and str(getattr(o, "code", "") or "").strip() == str(code or "").strip()
            for o in rows
        )
        if still_open:
            self._reset_pending_empty_sync(code)
            return
        if rows:
            self._release_stale_pending(code, "RECONCILED_NOT_OPEN")
        else:
            self._isolate_stale_pending(code, "미체결 조회에서 주문 미확인(연속 빈 동기화)")
    def _on_pending_reconcile_error(self, code: str, error: Exception) -> None:
        inflight = getattr(self, "_pending_reconcile_inflight", None)
        if isinstance(inflight, set):
            inflight.discard(code)
        if hasattr(self, "logger"):
            self.logger.warning(f"미체결 재조회 실패 [{code}]: {error}")
    def _release_stale_pending(self, code: str, reason: str) -> None:
        """브로커에 없는 주문으로 확정 -> pending 해제 + 매수 예약현금 환불."""
        pending_state = getattr(self, "_pending_order_state", {})
        pending = pending_state.get(code) if isinstance(pending_state, dict) else None
        side = ""
        if isinstance(pending, dict):
            side = str(pending.get("side", "") or "").lower()
        universe = getattr(self, "universe", {})
        info = universe.get(code) if isinstance(universe, dict) else None
        name = str(info.get("name", code) or code) if isinstance(info, dict) else code
        if side == "buy":
            self._release_reserved_cash_safe(code, reason=f"STALE_PENDING_{reason}", refund=True)
        self._clear_pending_order(code)
        self._reset_pending_empty_sync(code)
        if isinstance(info, dict):
            info["status"] = "holding" if int(info.get("held", 0) or 0) > 0 else "watch"
            dirty = getattr(self, "_dirty_codes", None)
            if isinstance(dirty, set):
                dirty.add(code)
        recompute = getattr(self, "_recompute_holding_or_pending_count", None)
        if callable(recompute):
            recompute()
        if hasattr(self, "log"):
            self.log(f"[주문조정] {name} 미체결 주문 미확인으로 pending 해제했습니다. (예약현금 환불)")
        if hasattr(self, "sig_update_table") and not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    def _isolate_stale_pending(self, code: str, reason_text: str) -> None:
        """소멸 확정 불가 -> sync_failed 격리(fail-closed, 매수 예약현금 환불)."""
        pending_state = getattr(self, "_pending_order_state", {})
        pending = pending_state.get(code) if isinstance(pending_state, dict) else None
        side = ""
        if isinstance(pending, dict):
            side = str(pending.get("side", "") or "").lower()
        if side == "buy":
            self._release_reserved_cash_safe(code, reason="STALE_PENDING_SYNC_FAILED", refund=True)
        self._mark_pending_state(code, "sync_failed")
        self._clear_pending_order(code, final_state="sync_failed")
        self._reset_pending_empty_sync(code)
        universe = getattr(self, "universe", {})
        info = universe.get(code) if isinstance(universe, dict) else None
        name = code
        if isinstance(info, dict):
            name = str(info.get("name", code) or code)
            info["status"] = "sync_failed"
            info["cooldown_until"] = None
            info["sync_failed_reason"] = str(reason_text or "")
            dirty = getattr(self, "_dirty_codes", None)
            if isinstance(dirty, set):
                dirty.add(code)
        failed_codes = getattr(self, "_sync_failed_codes", None)
        if isinstance(failed_codes, set):
            failed_codes.add(code)
        self._diag_touch_safe(code, sync_status="sync_failed", retry_count=0, last_sync_error=str(reason_text or ""))
        self._log_sync_fail_once(code, f"[안전차단] {name} 주문 상태 불일치로 자동주문을 차단했습니다. ({reason_text})")
        recompute = getattr(self, "_recompute_holding_or_pending_count", None)
        if callable(recompute):
            recompute()
        if hasattr(self, "sig_update_table") and not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    # =====================================================================
    # Phase-2: 지정가 미체결 자동취소 (STALE_LIMIT_ORDER_CANCEL_SEC, 0이면 비활성)
    # =====================================================================
    def _sweep_stale_limit_orders(self, now=None) -> int:
        """타임아웃 초과 지정가 미체결에 취소 요청. 확정은 WS 이벤트가 처리."""
        timeout_sec = max(0, int(getattr(Config, "STALE_LIMIT_ORDER_CANCEL_SEC", 0)))
        if timeout_sec <= 0 or not bool(getattr(self, "is_running", False)):
            return 0
        now_dt = now or datetime.datetime.now()
        rest_client = getattr(self, "rest_client", None)
        account = str(getattr(self, "current_account", "") or "")
        cancel_fn = getattr(rest_client, "cancel_order", None)
        if not callable(cancel_fn) or not account:
            return 0
        threadpool = getattr(self, "threadpool", None)
        starter = getattr(threadpool, "start", None)
        if not callable(starter):
            return 0
        pending_state = getattr(self, "_pending_order_state", {})
        if not isinstance(pending_state, dict):
            return 0
        requested = 0
        for code, pending in list(pending_state.items()):
            if not isinstance(pending, dict) or not self._pending_is_active(pending):
                continue
            updated = pending.get("updated_at")
            if not isinstance(updated, datetime.datetime):
                continue
            if (now_dt - updated).total_seconds() < timeout_sec:
                continue
            last_cancel = pending.get("cancel_requested_at")
            if isinstance(last_cancel, datetime.datetime) and (
                now_dt - last_cancel
            ).total_seconds() < timeout_sec:
                continue
            targets = []
            children = self._pending_children(pending)
            if children:
                for child in children:
                    child_no = str(child.get("order_no", "") or "").strip()
                    remaining = max(0, int(child.get("remaining_qty", 0) or 0))
                    if child_no and remaining > 0:
                        targets.append((child_no, remaining))
            else:
                order_no = str(pending.get("order_no", "") or "").strip()
                remaining = max(0, int(pending.get("remaining_qty", 0) or 0))
                if order_no and remaining > 0:
                    targets.append((order_no, remaining))
            if not targets:
                continue
            pending["cancel_requested_at"] = now_dt
            for order_no, qty in targets:
                worker = Worker(cancel_fn, account, order_no, code, qty)
                worker.signals.result.connect(
                    lambda res, c=code: self._on_stale_cancel_result(c, res)
                )
                worker.signals.error.connect(
                    lambda err, c=code: self._on_stale_cancel_error(c, err)
                )
                starter(worker)
                requested += 1
        return requested
    def _on_stale_cancel_result(self, code: str, result) -> None:
        ok = bool(getattr(result, "success", False))
        detail = "" if ok else str(getattr(result, "message", "") or "")
        if hasattr(self, "log"):
            self.log(f"[자동취소] {code} 미체결 취소 {'요청됨' if ok else f'실패({detail})'}")
    def _on_stale_cancel_error(self, code: str, error: Exception) -> None:
        if hasattr(self, "log"):
            self.log(f"[자동취소] {code} 취소 요청 오류: {error}")
