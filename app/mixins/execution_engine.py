"""Execution engine mixin for KiwoomProTrader."""

import datetime
import time
from collections import deque

from api.models import ExecutionData
from app.support.execution_policy import ExecutionPolicy
from app.support.worker import Worker
from config import Config
from ._typing import TraderMixinBase


class ExecutionEngineMixin(TraderMixinBase):
    def _record_decision_audit_once(
        self,
        code: str,
        info: dict,
        *,
        allowed: bool,
        reason: str,
        conditions: dict | None = None,
        metrics: dict | None = None,
        quantity: int = 0,
    ):
        recorder = getattr(self, "_record_decision_audit_event", None)
        if not callable(recorder):
            return
        state = info.get("market_intel", {}) if isinstance(info.get("market_intel"), dict) else {}
        key = (
            f"{code}:{int(bool(allowed))}:{reason}:{state.get('last_event_id', '')}:"
            f"{int(time.time() // 30)}:{int(quantity or 0)}"
        )
        cache = getattr(self, "_decision_audit_keys", None)
        if not isinstance(cache, dict):
            cache = {}
            self._decision_audit_keys = cache
        if key in cache:
            return
        cache[key] = time.time()
        if len(cache) > 500:
            cutoff = time.time() - 3600
            for old_key in list(cache.keys()):
                if float(cache.get(old_key, 0.0)) < cutoff:
                    cache.pop(old_key, None)
        recorder(
            code=code,
            info=info,
            allowed=allowed,
            reason=reason,
            conditions=conditions,
            metrics=metrics,
            quantity=quantity,
        )

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
        pending_state = getattr(self, "_pending_order_state", {})
        held_count = sum(1 for v in universe.values() if int(v.get("held", 0)) > 0)
        pending_buy = sum(
            1
            for c, state in pending_state.items()
            if self._is_pending_active(state)
            and state.get("side") == "buy"
            and int(universe.get(c, {}).get("held", 0)) == 0
        )
        self._holding_or_pending_count = held_count + pending_buy
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

    @staticmethod
    def _spread_pct(info: dict) -> float:
        ask = float(info.get("ask_price", 0) or 0)
        bid = float(info.get("bid_price", 0) or 0)
        if ask <= 0 or bid <= 0 or (ask + bid) <= 0:
            return 0.0
        mid = (ask + bid) / 2.0
        if mid <= 0:
            return 0.0
        return (ask - bid) / mid * 100.0

    def _average_recent_slippage_bps(self, window_size: int) -> float:
        series = getattr(self, "_recent_slippage_bps", None)
        if series is None:
            return 0.0
        values = list(series)
        if not values:
            return 0.0
        size = max(1, int(window_size))
        subset = values[-size:]
        if not subset:
            return 0.0
        return sum(abs(float(v)) for v in subset) / len(subset)

    def _is_liquidity_stress(self, info: dict) -> bool:
        cfg = getattr(self, "config", None)
        if cfg is None or not bool(getattr(cfg, "use_liquidity_stress_guard", True)):
            return False
        spread_pct = self._spread_pct(info)
        stress_spread = float(getattr(cfg, "stress_spread_pct", getattr(Config, "DEFAULT_STRESS_SPREAD_PCT", 1.0)))
        if spread_pct > stress_spread:
            return True

        avg_value = float(info.get("avg_value_20", 0) or 0)
        min_value = float(getattr(cfg, "min_avg_value", getattr(Config, "DEFAULT_MIN_AVG_VALUE", 1_000_000_000)))
        if min_value < 10_000_000:  # legacy UI scale: 억 단위
            min_value *= 100_000_000
        ratio = float(
            getattr(cfg, "stress_min_value_ratio", getattr(Config, "DEFAULT_STRESS_MIN_VALUE_RATIO", 0.35))
        )
        return avg_value > 0 and avg_value < (min_value * ratio)

    def _resolve_regime_profile(self, code: str) -> tuple[str, float, int]:
        manager = getattr(self, "strategy", None)
        default = ("normal", 1.0, 0)
        if manager is None:
            return default
        fn = getattr(manager, "get_regime_profile", None)
        if not callable(fn):
            return default
        result = fn(code)
        if not (isinstance(result, tuple) and len(result) == 3):
            return default
        regime, scale, _atr_pct = result
        regime_text = str(regime or "normal")
        if regime_text == "extreme":
            return regime_text, float(scale), 2
        if regime_text == "elevated":
            return regime_text, float(scale), 1
        return regime_text, float(scale), 0

    def _can_enter_trade(self, code: str, info: dict, now: datetime.datetime) -> tuple[bool, str]:
        cfg = getattr(self, "config", None)
        if cfg is None:
            return True, ""

        refresh_health = getattr(self, "_update_order_health_mode", None)
        if callable(refresh_health):
            refresh_health(now)
        release_shock = getattr(self, "_maybe_release_global_risk_mode", None)
        if callable(release_shock):
            release_shock(now)

        sync_failed_codes = getattr(self, "_sync_failed_codes", set())
        if str(info.get("status", "")) == "sync_failed" or code in sync_failed_codes:
            return False, "sync_failed"

        if bool(getattr(cfg, "use_shock_guard", True)):
            if str(getattr(self, "_global_risk_mode", "normal")) == "shock":
                until = getattr(self, "_global_risk_until", None)
                if until is None or now < until:
                    return False, "shock_guard"

        if bool(getattr(cfg, "use_vi_guard", True)):
            market_state = str(info.get("market_state", "normal") or "normal")
            if market_state in {"vi", "halt", "reopen_cooldown"}:
                return False, "vi_guard"

        if bool(getattr(cfg, "use_order_health_guard", True)):
            if str(getattr(self, "_order_health_mode", "normal")) == "degraded":
                until = getattr(self, "_order_health_until", None)
                if until is None or now < until:
                    return False, "order_health_guard"

        if self._is_liquidity_stress(info):
            return False, "liquidity_stress_guard"

        if bool(getattr(cfg, "use_slippage_guard", True)):
            max_slippage = float(getattr(cfg, "max_slippage_bps", getattr(Config, "DEFAULT_MAX_SLIPPAGE_BPS", 15.0)))
            window_size = int(
                getattr(cfg, "slippage_window_trades", getattr(Config, "DEFAULT_SLIPPAGE_WINDOW_TRADES", 20))
            )
            avg_slip = self._average_recent_slippage_bps(window_size)
            if avg_slip > max_slippage:
                return False, "slippage_guard"

        return True, ""

    @staticmethod
    def _is_pending_active(pending: dict) -> bool:
        if not isinstance(pending, dict) or not pending:
            return False
        state = str(pending.get("state", "submitted") or "submitted").lower()
        return state in {"submitted", "partial"}

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
        market_state_updater = getattr(self, "_update_market_state_from_execution", None)
        if callable(market_state_updater):
            market_state_updater(code, info, data, now)
        shock_updater = getattr(self, "_update_shock_mode", None)
        market_key_fn = getattr(self, "_market_key_from_info", None)
        index_series_fn = getattr(self, "_get_index_series", None)
        if callable(shock_updater):
            market_key = market_key_fn(info) if callable(market_key_fn) else "KOSPI"
            # Fallback: when official index feed is unavailable, use representative
            # per-market stock price stream for price-based shock detection.
            if callable(index_series_fn):
                series_obj = index_series_fn(market_key)
                if isinstance(series_obj, deque):
                    series = series_obj
                else:
                    series = deque(maxlen=1800)
                rep_map = getattr(self, "_shock_fallback_rep_by_market", None)
                if not isinstance(rep_map, dict):
                    rep_map = {}
                    self._shock_fallback_rep_by_market = rep_map
                rep_code = str(rep_map.get(market_key, "") or "")
                if not rep_code or rep_code not in self.universe:
                    rep_map[market_key] = code
                    rep_code = code
                if code == rep_code:
                    if series and (now.timestamp() - float(series[-1][0])) > 5.0:
                        series.append((now.timestamp(), float(current_price)))
                    elif not series:
                        series.append((now.timestamp(), float(current_price)))
            shock_updater(market_key, now)
        no_buy = now.hour >= Config.NO_ENTRY_HOUR
        held = int(info.get("held", 0))
        target = int(info.get("target", 0))
        buy_price = int(info.get("buy_price", 0))
        status = str(info.get("status", "watch"))

        pending = self._pending_order_state.get(code, {})
        if self._is_pending_active(pending):
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

            defense_getter = getattr(getattr(self, "strategy", None), "get_market_position_defense_policy", None)
            defense = defense_getter(code) if callable(defense_getter) else {}
            exit_policy = str(defense.get("exit_policy", "none") or "none")
            defense_event_id = str(
                defense.get("last_event_id", "") or f"{code}:{exit_policy}:{datetime.date.today().isoformat()}"
            )
            state = info.get("market_intel", {}) if isinstance(info.get("market_intel"), dict) else {}
            market_intel_cfg = getattr(getattr(self, "config", None), "market_intelligence", {})
            defense_cfg = (
                market_intel_cfg.get("position_defense", {})
                if isinstance(market_intel_cfg, dict) and isinstance(market_intel_cfg.get("position_defense"), dict)
                else {}
            )
            if exit_policy == "force_exit" and state.get("last_position_action_event_id", "") != defense_event_id:
                state["last_position_action_event_id"] = defense_event_id
                self._record_decision_audit_once(
                    code,
                    info,
                    allowed=False,
                    reason="market_intel_force_exit",
                    quantity=held,
                )
                self._execute_sell(code, held, current_price, "MARKET_INTEL_FORCE_EXIT")
                return
            if exit_policy == "reduce_size" and state.get("last_position_action_event_id", "") != defense_event_id:
                reduce_ratio = float(defense_cfg.get("reduce_ratio", 0.5) or 0.5)
                reduce_qty = min(held, max(1, int(max(1, held) * reduce_ratio)))
                state["last_position_action_event_id"] = defense_event_id
                self._record_decision_audit_once(
                    code,
                    info,
                    allowed=False,
                    reason="market_intel_reduce_size",
                    quantity=reduce_qty,
                )
                self._execute_sell(code, reduce_qty, current_price, "MARKET_INTEL_REDUCE_SIZE")
                return

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
            if exit_policy in {"tighten_exit", "force_exit"}:
                ts_start *= float(defense_cfg.get("tighten_ts_start_scale", 0.5) or 0.5)
                ts_stop *= float(defense_cfg.get("tighten_ts_stop_scale", 0.5) or 0.5)
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
            if use_time_stop and bool(info.get("time_stop_eligible", True)):
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

            allowed, reason_code = self._can_enter_trade(code, info, now)
            if not allowed:
                info["last_guard_reason"] = reason_code
                guard_map = getattr(self, "_guard_reason_by_code", None)
                if isinstance(guard_map, dict):
                    guard_map[code] = reason_code
                logger = getattr(self, "_log_once", None)
                if callable(logger):
                    logger(
                        f"guard:{code}:{reason_code}",
                        f"[진입차단] {info.get('name', code)} reason={reason_code}",
                    )
                self._record_decision_audit_once(code, info, allowed=False, reason=reason_code)
                return
            info["last_guard_reason"] = ""
            guard_map = getattr(self, "_guard_reason_by_code", None)
            if isinstance(guard_map, dict):
                guard_map[code] = ""

            regime, _regime_scale, holdings_penalty = self._resolve_regime_profile(code)
            max_holdings = int(
                cfg_value(
                    "max_holdings",
                    int(self.spin_max_holdings.value()) if hasattr(self, "spin_max_holdings") else Config.DEFAULT_MAX_HOLDINGS,
                )
            )
            max_holdings = max(1, max_holdings - int(holdings_penalty))
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

                passed, conditions, metrics = self.strategy.evaluate_buy_conditions(code, now.timestamp())
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
                        self._record_decision_audit_once(
                            code,
                            info,
                            allowed=True,
                            reason="buy_signal",
                            conditions=conditions,
                            metrics=metrics,
                            quantity=quantity,
                        )
                        self._execute_buy(code, quantity, current_price)
                else:
                    self._record_decision_audit_once(
                        code,
                        info,
                        allowed=False,
                        reason="strategy_conditions_failed",
                        conditions=conditions,
                        metrics=metrics,
                    )
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
        pending = self._pending_order_state.get(code, {})
        if self._is_pending_active(pending) and pending.get("side") == "buy":
            return
        if info.get("status") in {"buying", "buy_submitted"}:
            return

        if not (self.rest_client and self.current_account):
            self.log(f"BUY failed [{name}]: API/account not ready")
            return

        current_price = int(price) if int(price) > 0 else int(info.get("current", 0) or 0)
        available_cash = getattr(self, "virtual_deposit", int(getattr(self, "deposit", 0) or 0))
        cfg = getattr(self, "config", None)
        policy = str(getattr(cfg, "execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market")))
        use_split = bool(getattr(cfg, "use_split", False)) if cfg is not None else False

        if use_split:
            split_orders = getattr(getattr(self, "strategy", None), "get_split_orders", None)
            planned_orders = split_orders(quantity, current_price, "buy") if callable(split_orders) else []
            child_orders = [
                (max(0, int(qty or 0)), max(1, int(child_price or 0)))
                for qty, child_price in planned_orders
                if int(qty or 0) > 0
            ]
            if len(child_orders) > 1:
                if policy != ExecutionPolicy.LIMIT:
                    self.log(f"BUY blocked [{name}]: split buy requires limit execution policy")
                    return

                required_cash = sum(int(qty) * int(child_price) for qty, child_price in child_orders)
                if required_cash > available_cash:
                    self.log(
                        f"BUY skipped [{name}]: required={required_cash:,} available(V)={available_cash:,} (INSUFFICIENT_CASH)"
                    )
                    seconds = max(1, int(getattr(Config, "ORDER_REJECT_COOLDOWN_SEC", 10)))
                    info["cooldown_until"] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                    info["status"] = "cooldown"
                    self.log(f"BUY cooldown [{name}] {seconds}s (INSUFFICIENT_CASH)")
                    self._dirty_codes.add(code)
                    if not hasattr(self, "_ui_flush_timer"):
                        self.sig_update_table.emit()
                    return

                self._reserve_cash_for_buy(code, required_cash)
                if info.get("held", 0) <= 0:
                    self._holding_or_pending_count += 1

                info["status"] = "buying"
                diag_touch = getattr(self, "_diag_touch", None)
                if callable(diag_touch):
                    diag_touch(code, pending_side="buy", pending_reason="BUY_SPLIT_SUBMITTING", sync_status="buying")
                self._dirty_codes.add(code)

                worker = Worker(self._submit_split_buy_orders, code, child_orders)
                worker.signals.result.connect(
                    lambda rows: self._on_split_buy_result(rows, code, name, child_orders)
                )
                worker.signals.error.connect(lambda e: self._on_split_buy_error(e, code, name))
                self.threadpool.start(worker)
                return

        required_cash = int(quantity) * current_price if current_price > 0 else 0

        if required_cash > available_cash:
            self.log(
                f"BUY skipped [{name}]: required={required_cash:,} available(V)={available_cash:,} (INSUFFICIENT_CASH)"
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

        buy_fn, args = ExecutionPolicy.select_buy(self.rest_client, policy, self.current_account, code, quantity, price)
        worker = Worker(buy_fn, *args)
        worker.signals.result.connect(lambda res: self._on_buy_result(res, code, name, quantity, price))
        worker.signals.error.connect(lambda e: self._on_buy_error(e, code, name))
        self.threadpool.start(worker)

    def _on_split_buy_error(self, e, code, name):
        self.log(f"BUY split error [{name}]: {e}")
        record_failure = getattr(self, "_record_order_failure", None)
        if callable(record_failure):
            record_failure("BUY_SPLIT_ERROR", code=code)
        self._release_reserved_cash(code, reason="BUY_SPLIT_ERROR", refund=True)
        self._clear_pending_order(code)
        if code in self.universe:
            info = self.universe[code]
            seconds = max(1, int(getattr(Config, "ORDER_REJECT_COOLDOWN_SEC", 10)))
            info["cooldown_until"] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            info["status"] = "cooldown"
            self.log(f"BUY cooldown [{name}] {seconds}s (BUY_SPLIT_ERROR)")
            diag_touch = getattr(self, "_diag_touch", None)
            if callable(diag_touch):
                diag_touch(code, sync_status="cooldown")
        self._recompute_holding_or_pending_count()
        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _on_split_buy_result(self, rows, code, name, child_orders: list[tuple[int, int]]):
        normalized_rows = list(rows or [])
        successful: list[dict] = []
        rejected_reserved = 0
        rejected_count = 0

        for row in normalized_rows:
            qty = max(0, int(row.get("quantity", 0) or 0))
            price = max(1, int(row.get("price", 0) or 0))
            if bool(row.get("success", False)):
                successful.append(
                    {
                        "index": max(1, int(row.get("index", 0) or len(successful) + 1)),
                        "submitted_qty": qty,
                        "filled_qty": 0,
                        "remaining_qty": qty,
                        "expected_price": price,
                        "order_no": str(row.get("order_no", "") or ""),
                        "state": "submitted",
                        "reserved_cash": qty * price,
                        "reason": f"BUY_SPLIT#{max(1, int(row.get('index', 0) or len(successful) + 1))}",
                    }
                )
            else:
                rejected_count += 1
                rejected_reserved += qty * price

        if successful:
            success_qty = sum(int(child.get("submitted_qty", 0) or 0) for child in successful)
            success_cash = sum(int(child.get("reserved_cash", 0) or 0) for child in successful)
            weighted_price = int(round(success_cash / success_qty)) if success_qty > 0 else 0
            if code in self.universe:
                self.universe[code]["status"] = "buy_submitted"
                self.universe[code]["cooldown_until"] = None
                self.universe[code]["breakout_hits"] = 0
            self._set_pending_order(
                code,
                "buy",
                "BUY_SPLIT",
                expected_price=weighted_price,
                submitted_qty=success_qty,
                order_no=str(successful[0].get("order_no", "") or ""),
                child_orders=successful,
            )
            if rejected_reserved > 0:
                self._release_reserved_cash_amount(
                    code,
                    rejected_reserved,
                    reason="BUY_SPLIT_PARTIAL_REJECT",
                    refund=True,
                )
            if rejected_count > 0:
                record_failure = getattr(self, "_record_order_failure", None)
                if callable(record_failure):
                    record_failure("BUY_SPLIT_PARTIAL_REJECT", code=code)
            self.log(
                f"BUY split submitted: {name} {success_qty} shares "
                f"({len(successful)} orders, rejected={rejected_count})"
            )
            self._sync_position_from_account(code)
        else:
            message = ""
            if normalized_rows:
                message = str(normalized_rows[0].get("message", "") or "")
            self.log(f"BUY split rejected [{name}]: {message or 'no child order accepted'}")
            record_failure = getattr(self, "_record_order_failure", None)
            if callable(record_failure):
                record_failure("BUY_SPLIT_REJECTED", code=code)
            self._release_reserved_cash(code, reason="BUY_SPLIT_REJECTED", refund=True)
            if code in self.universe:
                info = self.universe[code]
                seconds = max(1, int(getattr(Config, "ORDER_REJECT_COOLDOWN_SEC", 10)))
                info["cooldown_until"] = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                info["status"] = "cooldown"
                self.log(f"BUY cooldown [{name}] {seconds}s (BUY_SPLIT_REJECTED)")
                diag_touch = getattr(self, "_diag_touch", None)
                if callable(diag_touch):
                    diag_touch(code, sync_status="cooldown")
            self._clear_pending_order(code)
            self._recompute_holding_or_pending_count()

        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _on_buy_error(self, e, code, name):
        """Handle buy error."""
        self.log(f"BUY error [{name}]: {e}")
        record_failure = getattr(self, "_record_order_failure", None)
        if callable(record_failure):
            record_failure("BUY_ERROR", code=code)
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
        self._recompute_holding_or_pending_count()
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
            self._set_pending_order(
                code,
                "buy",
                "BUY",
                expected_price=int(price or 0),
                submitted_qty=int(quantity or 0),
                order_no=str(getattr(result, "order_no", "") or ""),
            )
            self.log(f"BUY submitted: {name} {quantity} shares")
            self._sync_position_from_account(code)
        else:
            self.log(f"BUY rejected [{name}]: {result.message}")
            record_failure = getattr(self, "_record_order_failure", None)
            if callable(record_failure):
                record_failure("BUY_REJECTED", code=code)
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
            self._recompute_holding_or_pending_count()

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
        pending = self._pending_order_state.get(code, {})
        if self._is_pending_active(pending) and pending.get("side") == "sell":
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
        record_failure = getattr(self, "_record_order_failure", None)
        if callable(record_failure):
            record_failure("SELL_ERROR", code=code)
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
            self._clear_pending_order(code)

        self._dirty_codes.add(code)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
