"""Order/execution sync mixin for KiwoomProTrader."""

import datetime
from typing import Iterable, Set

from PyQt6.QtCore import QTimer

from api.models import ExecutionData
from app.support.worker import Worker
from config import Config


class OrderSyncMixin:
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
            return int(fn(code, reason=reason, refund=refund) or 0)

        # Fallback for tests that do not include ExecutionEngineMixin.
        mapping = getattr(self, "_reserved_cash_by_code", None)
        if not isinstance(mapping, dict):
            return 0
        amount = int(mapping.pop(code, 0) or 0)
        if amount > 0 and refund and hasattr(self, "virtual_deposit"):
            self.virtual_deposit = max(0, int(getattr(self, "virtual_deposit", 0) or 0) + amount)
        return amount

    def _on_realtime(self, data: ExecutionData):
        self.sig_execution.emit(data)

    def _on_order_realtime(self, data):
        """WebSocket thread -> main thread bridge."""
        self.sig_order_execution.emit(data)

    def _on_order_execution(self, data):
        """Handle realtime order/execution notifications in main thread."""
        try:
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
                pending = self._pending_order_state.get(code, {})
                pending_side = str(pending.get("side", ""))
                self._clear_pending_order(code)
                if pending_side == "buy":
                    self._release_reserved_cash_safe(code, reason="ORDER_CANCEL_OR_REJECT", refund=True)
                if code in self.universe:
                    held = int(self.universe[code].get("held", 0))
                    self.universe[code]["status"] = "holding" if held > 0 else "watch"
                    self._diag_touch_safe(
                        code,
                        sync_status=self.universe[code]["status"],
                        retry_count=0,
                    )
                self._dirty_codes.add(code)
            if code and code not in self.universe and code in self._manual_pending_map():
                if cancel_like or exec_qty > 0 or fill_like:
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

    def _set_pending_order(self, code: str, side: str, reason: str):
        if not code:
            return
        pending_until = datetime.datetime.now() + datetime.timedelta(seconds=5)
        self._pending_order_state[code] = {
            "side": side,
            "reason": reason,
            "until": pending_until,
        }
        self._diag_touch_safe(
            code,
            pending_side=side,
            pending_reason=reason,
            pending_until=pending_until,
        )

    def _clear_pending_order(self, code: str):
        self._pending_order_state.pop(code, None)
        self._diag_clear_pending_safe(code)

    def _set_manual_pending_order(self, code: str, side: str, reason: str):
        if not code:
            return
        pending_until = datetime.datetime.now() + datetime.timedelta(seconds=5)
        self._manual_pending_map()[code] = {
            "side": side,
            "reason": reason,
            "until": pending_until,
        }

    def _clear_manual_pending_order(self, code: str):
        self._manual_pending_map().pop(code, None)

    def _cleanup_manual_pending_state(self, now: datetime.datetime | None = None):
        state = self._manual_pending_map()
        if not state:
            return
        now_dt = now or datetime.datetime.now()
        expired_codes = [
            code for code, pending in state.items() if pending.get("until") and pending.get("until") <= now_dt
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

        for code_item in target_codes:
            info = self.universe.get(code_item)
            if not info:
                continue

            sync_failed_codes = getattr(self, "_sync_failed_codes", set())
            was_sync_failed = code_item in sync_failed_codes
            if was_sync_failed and hasattr(self, "_sync_failed_codes"):
                self._sync_failed_codes.discard(code_item)
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
                # Filled amount is now reflected in real deposit; release reservation without refund.
                self._release_reserved_cash_safe(code_item, reason="BUY_FILLED", refund=False)

            elif delta < 0:
                sell_qty = -delta
                fill_price = self._to_int(exec_event.get("price", 0)) if exec_event.get("side") == "sell" else 0
                if fill_price <= 0:
                    fill_price = int(info.get("current", 0))
                amount = max(0, fill_price * sell_qty)
                profit = (fill_price - prev_buy_price) * sell_qty if prev_buy_price > 0 else 0
                reason = pending.get("reason", "체결동기화") if pending else "체결동기화"

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
                self.strategy.update_market_investment(code_item, amount, is_buy=False)
                self.strategy.update_sector_investment(code_item, amount, is_buy=False)
                if self.sound:
                    self.sound.play_sell() if profit > 0 else self.sound.play_loss()
                if self.telegram:
                    self.telegram.send(f"매도 체결: {info.get('name', code_item)} {sell_qty}주 손익: {profit:+,}원")

            info["held"] = new_held
            info["buy_price"] = new_buy_price
            info["invest_amount"] = new_invest_amount

            if new_held > 0:
                info["status"] = "holding"
                info["cooldown_until"] = None
                if not info.get("buy_time"):
                    info["buy_time"] = now
            else:
                info["status"] = "watch"
                info["buy_time"] = None
                info["max_profit_rate"] = 0
                info["partial_profit_levels"] = set()
                if prev_held > 0 and hasattr(self, "chk_use_cooldown") and self.chk_use_cooldown.isChecked():
                    cooldown_minutes = int(self.spin_cooldown_min.value())
                    info["cooldown_until"] = now + datetime.timedelta(minutes=cooldown_minutes)
                    info["status"] = "cooldown"

            cooldown_until = info.get("cooldown_until")
            if info.get("held", 0) == 0 and cooldown_until and now < cooldown_until:
                info["status"] = "cooldown"

            if pending:
                if delta != 0:
                    self._clear_pending_order(code_item)
                elif now < pending.get("until", now):
                    if pending.get("side") == "buy" and info.get("held", 0) == 0:
                        info["status"] = "buy_submitted"
                    elif pending.get("side") == "sell" and info.get("held", 0) > 0:
                        info["status"] = "sell_submitted"
                else:
                    self._clear_pending_order(code_item)

            if delta != 0:
                self._last_exec_event.pop(code_item, None)

            self._diag_touch_safe(
                code_item,
                sync_status=str(info.get("status", "")),
                retry_count=0,
                last_sync_error="",
            )
            self._dirty_codes.add(code_item)

        held_count = sum(1 for v in self.universe.values() if int(v.get("held", 0)) > 0)
        pending_buy = sum(
            1
            for c, state in self._pending_order_state.items()
            if state.get("side") == "buy" and int(self.universe.get(c, {}).get("held", 0)) == 0
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
                    self._clear_pending_order(code_item)
                if side == "buy":
                    self._release_reserved_cash_safe(code_item, reason="SYNC_FAILED", refund=True)
                info = getattr(self, "universe", {}).get(code_item)
                if info is None:
                    continue
                info["status"] = "sync_failed"
                info["cooldown_until"] = None
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
            universe = getattr(self, "universe", {})
            pending_state = getattr(self, "_pending_order_state", {})
            held_count = sum(1 for v in universe.values() if int(v.get("held", 0)) > 0)
            pending_buy = sum(
                1
                for c, state in pending_state.items()
                if state.get("side") == "buy" and int(universe.get(c, {}).get("held", 0)) == 0
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
