"""Execution engine mixin for KiwoomProTrader."""

import datetime

from api.models import ExecutionData
from app.support.execution_policy import ExecutionPolicy
from app.support.worker import Worker
from config import Config


class ExecutionEngineMixin:
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

    def _release_all_reserved_cash(self, reason: str = "STOP_TRADING") -> int:
        mapping = self._reserved_cash_map()
        if not mapping:
            return 0
        total = 0
        for code in list(mapping.keys()):
            total += self._release_reserved_cash(code, reason=reason, refund=True)
        return total

    def _on_execution(self, data: ExecutionData):
        """Handle realtime execution tick and evaluate buy/sell conditions."""
        if not self.is_running:
            return

        cfg = getattr(self, "config", None)

        def cfg_value(key: str, default):
            if cfg is not None and hasattr(cfg, key):
                return getattr(cfg, key)
            return default

        code = data.code
        if code not in self.universe:
            return

        info = self.universe[code]
        current_price = int(data.exec_price or 0)
        if current_price <= 0:
            return

        info["current"] = current_price
        if data.total_volume > 0:
            info["current_volume"] = int(data.total_volume)
        if data.ask_price > 0:
            info["ask_price"] = int(data.ask_price)
        if data.bid_price > 0:
            info["bid_price"] = int(data.bid_price)

        max_len = int(Config.MAX_PRICE_HISTORY)
        trim_threshold = max_len + max(5, int(Config.TABLE_BATCH_LIMIT // 10))
        for key in ("price_history", "minute_prices"):
            series = info.get(key)
            if isinstance(series, list):
                series.append(current_price)
                if len(series) > trim_threshold:
                    del series[:-max_len]

        self._dirty_codes.add(code)

        now = datetime.datetime.now()
        no_buy = now.hour >= Config.NO_ENTRY_HOUR
        held = int(info.get("held", 0))
        target = int(info.get("target", 0))
        buy_price = int(info.get("buy_price", 0))
        status = str(info.get("status", "watch"))

        pending = self._pending_order_state.get(code, {})
        pending_until = pending.get("until")
        if pending_until and pending_until > now:
            return

        sync_failed_codes = getattr(self, "_sync_failed_codes", set())
        if status == "sync_failed" or code in sync_failed_codes:
            return

        if status in {"buying", "selling", "buy_submitted", "sell_submitted"}:
            return

        if held > 0 and buy_price > 0:
            profit_rate = (current_price - buy_price) / buy_price * 100
            if profit_rate > float(info.get("max_profit_rate", 0)):
                info["max_profit_rate"] = profit_rate

            atr_triggered, _ = self.strategy.check_atr_stop_loss(code)
            if atr_triggered:
                self._execute_sell(code, held, current_price, "ATR_STOP")
                return

            loss_limit = float(
                cfg_value(
                    "loss_cut",
                    float(self.spin_loss.value()) if hasattr(self, "spin_loss") else Config.DEFAULT_LOSS_CUT,
                )
            )
            if profit_rate <= -loss_limit:
                self._execute_sell(code, held, current_price, f"STOP_LOSS({profit_rate:.1f}%)")
                return

            partial = self.strategy.calculate_partial_take_profit(code, profit_rate)
            if partial:
                sell_qty = max(1, int(held * partial["sell_ratio"] / 100))
                self._execute_sell(code, sell_qty, current_price, f"PARTIAL_TP_L{partial['level'] + 1}")
                self.strategy.mark_partial_profit_executed(code, partial["level"])
                return

            ts_start = float(
                cfg_value(
                    "ts_start",
                    float(self.spin_ts_start.value()) if hasattr(self, "spin_ts_start") else Config.DEFAULT_TS_START,
                )
            )
            ts_stop = float(
                cfg_value(
                    "ts_stop",
                    float(self.spin_ts_stop.value()) if hasattr(self, "spin_ts_stop") else Config.DEFAULT_TS_STOP,
                )
            )
            max_profit = float(info.get("max_profit_rate", 0))
            if max_profit >= ts_start:
                info["status"] = "trailing"
                drop_from_high = max_profit - profit_rate
                if drop_from_high >= ts_stop:
                    self._execute_sell(code, held, current_price, f"TRAILING_STOP({profit_rate:.1f}%)")
                    return

            use_time_stop = bool(
                cfg_value(
                    "use_time_stop",
                    bool(hasattr(self, "chk_use_time_stop") and self.chk_use_time_stop.isChecked()),
                )
            )
            if use_time_stop:
                buy_time = info.get("buy_time")
                if buy_time:
                    max_minutes = int(
                        cfg_value(
                            "time_stop_min",
                            int(self.spin_time_stop_min.value())
                            if hasattr(self, "spin_time_stop_min")
                            else Config.DEFAULT_MAX_HOLD_MINUTES,
                        )
                    )
                    if now - buy_time >= datetime.timedelta(minutes=max_minutes):
                        self._execute_sell(code, held, current_price, f"TIME_STOP({max_minutes}m)")
                        return

        elif held == 0 and target > 0 and not no_buy:
            # 일일 손실 한도 가드: 타이머 주기 사이 매수 차단
            if getattr(self, "daily_loss_triggered", False):
                return

            max_holdings = int(
                cfg_value(
                    "max_holdings",
                    int(self.spin_max_holdings.value()) if hasattr(self, "spin_max_holdings") else Config.DEFAULT_MAX_HOLDINGS,
                )
            )
            if int(getattr(self, "_holding_or_pending_count", 0)) >= max_holdings:
                return

            cooldown_until = info.get("cooldown_until")
            if cooldown_until and now < cooldown_until:
                return

            if current_price >= target:
                use_breakout_confirm = bool(
                    cfg_value(
                        "use_breakout_confirm",
                        bool(hasattr(self, "chk_use_breakout_confirm") and self.chk_use_breakout_confirm.isChecked()),
                    )
                )
                if use_breakout_confirm:
                    hits = int(info.get("breakout_hits", 0)) + 1
                    info["breakout_hits"] = hits
                    required_hits = int(
                        cfg_value(
                            "breakout_ticks",
                            int(self.spin_breakout_ticks.value())
                            if hasattr(self, "spin_breakout_ticks")
                            else Config.DEFAULT_BREAKOUT_TICKS,
                        )
                    )
                    if hits < required_hits:
                        return

                passed, _, _ = self.strategy.evaluate_buy_conditions(code, now.timestamp())
                if passed:
                    use_dynamic_sizing = bool(
                        cfg_value(
                            "use_dynamic_sizing",
                            bool(hasattr(self, "chk_use_dynamic_sizing") and self.chk_use_dynamic_sizing.isChecked()),
                        )
                    )
                    use_atr_sizing = bool(
                        cfg_value(
                            "use_atr_sizing",
                            bool(hasattr(self, "chk_use_atr_sizing") and self.chk_use_atr_sizing.isChecked()),
                        )
                    )

                    if use_dynamic_sizing:
                        quantity = self.strategy.calculate_dynamic_position_size(code)
                    elif use_atr_sizing:
                        risk_percent = float(
                            cfg_value(
                                "risk_percent",
                                float(self.spin_risk_percent.value())
                                if hasattr(self, "spin_risk_percent")
                                else Config.DEFAULT_RISK_PERCENT,
                            )
                        )
                        quantity = self.strategy.calculate_position_size(code, risk_percent)
                    else:
                        quantity = self.strategy._default_position_size(code)

                    if quantity > 0:
                        self._execute_buy(code, quantity, current_price)
            elif info.get("breakout_hits"):
                info["breakout_hits"] = 0

        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _execute_buy(self, code: str, quantity: int, price: int):
        """Submit buy order asynchronously."""
        info = self.universe.get(code, {})
        name = info.get("name", code)
        now = datetime.datetime.now()

        if quantity <= 0:
            return
        cooldown_until = info.get("cooldown_until")
        if cooldown_until and cooldown_until > now:
            return
        if self._pending_order_state.get(code, {}).get("side") == "buy":
            return
        if info.get("status") in {"buying", "buy_submitted"}:
            return

        if not (self.rest_client and self.current_account):
            self.log(f"BUY failed [{name}]: API/account not ready")
            return

        current_price = int(price) if int(price) > 0 else int(info.get("current", 0) or 0)
        required_cash = int(quantity) * current_price if current_price > 0 else 0
        available_cash = getattr(self, "virtual_deposit", int(getattr(self, "deposit", 0) or 0))

        if required_cash > 0 and available_cash > 0 and required_cash > available_cash:
            self.log(
                f"BUY skipped [{name}]: required={required_cash:,} available(V)={available_cash:,}"
            )
            seconds = max(1, int(getattr(Config, "ORDER_REJECT_COOLDOWN_SEC", 10)))
            info["cooldown_until"] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            info["status"] = "cooldown"
            self.log(f"BUY cooldown [{name}] {seconds}s (INSUFFICIENT_CASH)")
            self._dirty_codes.add(code)
            if not hasattr(self, "_ui_flush_timer"):
                self.sig_update_table.emit()
            return

        # Reserve virtual cash before submit to prevent over-commit.
        self._reserve_cash_for_buy(code, required_cash)

        if info.get("held", 0) <= 0:
            self._holding_or_pending_count += 1

        info["status"] = "buying"
        diag_touch = getattr(self, "_diag_touch", None)
        if callable(diag_touch):
            diag_touch(code, pending_side="buy", pending_reason="SUBMITTING", sync_status="buying")
        self._dirty_codes.add(code)

        cfg = getattr(self, "config", None)
        policy = str(getattr(cfg, "execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market")))
        buy_fn, args = ExecutionPolicy.select_buy(self.rest_client, policy, self.current_account, code, quantity, price)
        worker = Worker(buy_fn, *args)
        worker.signals.result.connect(lambda res: self._on_buy_result(res, code, name, quantity, price))
        worker.signals.error.connect(lambda e: self._on_buy_error(e, code, name))
        self.threadpool.start(worker)

    def _on_buy_error(self, e, code, name):
        """Handle buy error."""
        self.log(f"BUY error [{name}]: {e}")
        self._release_reserved_cash(code, reason="BUY_ERROR", refund=True)
        self._clear_pending_order(code)
        if code in self.universe:
            info = self.universe[code]
            seconds = max(1, int(getattr(Config, "ORDER_REJECT_COOLDOWN_SEC", 10)))
            info["cooldown_until"] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            info["status"] = "cooldown"
            self.log(f"BUY cooldown [{name}] {seconds}s (BUY_ERROR)")
            diag_touch = getattr(self, "_diag_touch", None)
            if callable(diag_touch):
                diag_touch(code, sync_status="cooldown")
        held_count = sum(1 for v in self.universe.values() if int(v.get("held", 0)) > 0)
        pending_buy = sum(
            1
            for c, state in self._pending_order_state.items()
            if state.get("side") == "buy" and int(self.universe.get(c, {}).get("held", 0)) == 0
        )
        self._holding_or_pending_count = held_count + pending_buy
        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _on_buy_result(self, result, code, name, quantity, price):
        """Handle buy result in main thread."""
        if result.success:
            if code in self.universe:
                self.universe[code]["status"] = "buy_submitted"
                self.universe[code]["cooldown_until"] = None
                self.universe[code]["breakout_hits"] = 0
            self._set_pending_order(code, "buy", "BUY")
            self.log(f"BUY submitted: {name} {quantity} shares")
            self._sync_position_from_account(code)
        else:
            self.log(f"BUY rejected [{name}]: {result.message}")
            self._release_reserved_cash(code, reason="BUY_REJECTED", refund=True)
            if code in self.universe:
                info = self.universe[code]
                seconds = max(1, int(getattr(Config, "ORDER_REJECT_COOLDOWN_SEC", 10)))
                info["cooldown_until"] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                info["status"] = "cooldown"
                self.log(f"BUY cooldown [{name}] {seconds}s (BUY_REJECTED)")
                diag_touch = getattr(self, "_diag_touch", None)
                if callable(diag_touch):
                    diag_touch(code, sync_status="cooldown")

            self._clear_pending_order(code)
            held_count = sum(1 for v in self.universe.values() if int(v.get("held", 0)) > 0)
            pending_buy = sum(
                1
                for c, state in self._pending_order_state.items()
                if state.get("side") == "buy" and int(self.universe.get(c, {}).get("held", 0)) == 0
            )
            self._holding_or_pending_count = held_count + pending_buy

        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _execute_sell(self, code: str, quantity: int, price: int, reason: str):
        """Submit sell order asynchronously."""
        info = self.universe.get(code, {})
        name = info.get("name", code)
        buy_price = info.get("buy_price", 0)

        if quantity <= 0:
            self.log(f"SELL quantity invalid [{name}]: {quantity}")
            return
        if self._pending_order_state.get(code, {}).get("side") == "sell":
            return
        if info.get("status") in {"selling", "sell_submitted"}:
            return

        held = int(info.get("held", 0))
        if held > 0 and quantity > held:
            quantity = held

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
        self._clear_pending_order(code)
        if code in self.universe:
            self.universe[code]["status"] = "holding"
        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _on_sell_result(self, result, code, name, quantity, price, buy_price, reason):
        """Handle sell result in main thread."""
        if result.success:
            if code in self.universe:
                self.universe[code]["status"] = "sell_submitted"
            self._set_pending_order(code, "sell", reason)
            self.log(f"SELL submitted: {name} {quantity} shares ({reason})")
            self._sync_position_from_account(code)
        else:
            self.log(f"SELL rejected [{name}]: {result.message}")
            if code in self.universe:
                self.universe[code]["status"] = "holding"
            self._clear_pending_order(code)

        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
