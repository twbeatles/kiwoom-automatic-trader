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


class TradingSessionPositionsMixin(TraderMixinBase):
    def _rollover_daily_metrics(self, now: Optional[datetime.datetime] = None, reset_baseline: bool = False):
        now_dt = now or datetime.datetime.now()
        today = now_dt.date()
        current_day = getattr(self, "_trading_day", None)
        if current_day != today:
            self._trading_day = today
            self.daily_realized_profit = 0
            self.daily_initial_deposit = 0
            self.daily_loss_triggered = False

        if reset_baseline and int(getattr(self, "daily_initial_deposit", 0) or 0) <= 0:
            cfg = getattr(self, "config", None)
            basis = str(getattr(cfg, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")))
            if basis == "total_equity":
                baseline = int(getattr(self, "total_equity", 0) or 0) or int(getattr(self, "deposit", 0) or 0)
            else:
                baseline = int(getattr(self, "deposit", 0) or 0)
            if baseline <= 0:
                baseline = int(getattr(self, "initial_deposit", 0) or 0)
            if baseline > 0:
                self.daily_initial_deposit = baseline
    def _strategy_primary_id(self) -> str:
        cfg = getattr(self, "config", None)
        pack = getattr(cfg, "strategy_pack", {}) if cfg is not None else {}
        if isinstance(pack, dict):
            return str(pack.get("primary_strategy", "volatility_breakout"))
        return "volatility_breakout"
    def _external_data_enabled(self) -> bool:
        cfg = getattr(self, "config", None)
        flags = getattr(cfg, "feature_flags", {}) if cfg is not None else {}
        if not isinstance(flags, dict):
            flags = {}
        return bool(flags.get("enable_external_data", True))
    def _log_once(self, key: str, message: str):
        cooldown_map = getattr(self, "_log_cooldown_map", None)
        if cooldown_map is None:
            cooldown_map = {}
            self._log_cooldown_map = cooldown_map
        now_ts = time.time()
        last_ts = float(cooldown_map.get(key, 0.0))
        if now_ts - last_ts >= float(getattr(Config, "LOG_DEDUP_SEC", 30)):
            self.log(message)
            cooldown_map[key] = now_ts
    @staticmethod
    def _calc_spread_pct(info: Dict[str, Any]) -> float:
        ask = float(info.get("ask_price", 0) or 0)
        bid = float(info.get("bid_price", 0) or 0)
        if ask <= 0 or bid <= 0 or (ask + bid) <= 0:
            return 0.0
        mid = (ask + bid) / 2.0
        if mid <= 0:
            return 0.0
        return (ask - bid) / mid * 100.0
    @staticmethod
    def _series_return_pct(series: Deque[Tuple[float, float]], lookback_sec: int, now_ts: float) -> float:
        if not series:
            return 0.0
        latest_ts, latest_val = series[-1]
        if latest_val <= 0:
            return 0.0
        cutoff_ts = now_ts - float(lookback_sec)
        ref_val = 0.0
        for ts, value in reversed(series):
            if ts <= cutoff_ts:
                ref_val = float(value)
                break
        if ref_val <= 0:
            first_val = float(series[0][1]) if series else 0.0
            ref_val = first_val if first_val > 0 and (latest_ts - float(series[0][0])) >= lookback_sec else 0.0
        if ref_val <= 0:
            return 0.0
        return (latest_val / ref_val - 1.0) * 100.0
    @staticmethod
    def _code_return_pct(series: Deque[Tuple[float, int]], lookback_sec: int, now_ts: float) -> float:
        if not series:
            return 0.0
        latest_ts, latest_val = series[-1]
        latest_price = float(latest_val or 0)
        if latest_price <= 0:
            return 0.0
        cutoff_ts = now_ts - float(lookback_sec)
        ref_price = 0.0
        for ts, value in reversed(series):
            if ts <= cutoff_ts:
                ref_price = float(value or 0)
                break
        if ref_price <= 0:
            first_price = float(series[0][1]) if series else 0.0
            ref_price = first_price if first_price > 0 and (latest_ts - float(series[0][0])) >= lookback_sec else 0.0
        if ref_price <= 0:
            return 0.0
        return (latest_price / ref_price - 1.0) * 100.0
    def _get_index_series(self, market_key: str) -> Deque[Tuple[float, float]]:
        mapping = getattr(self, "_index_ticks_by_market", None)
        if not isinstance(mapping, dict):
            mapping = {}
            self._index_ticks_by_market = mapping
        key = str(market_key or "KOSPI").upper()
        series = mapping.get(key)
        if not isinstance(series, deque):
            series = deque(maxlen=1800)
            mapping[key] = series
        return series
    def _market_key_from_index_code(self, index_code: str) -> str:
        text = str(index_code or "").upper()
        if any(token in text for token in ("KQ", "KOSDAQ", "101", "001KQ")):
            return "KOSDAQ"
        return "KOSPI"
    def _market_key_from_info(self, info: Dict[str, Any]) -> str:
        market_type = str(info.get("market_type", "") or "").upper()
        if "KOSDAQ" in market_type:
            return "KOSDAQ"
        return "KOSPI"
    def _external_positions_map(self) -> Dict[str, Dict[str, Any]]:
        mapping = getattr(self, "external_positions", None)
        if not isinstance(mapping, dict):
            mapping = {}
            self.external_positions = mapping
        return mapping
    def _tracked_position_kind(self, code: str) -> str:
        if code in getattr(self, "universe", {}):
            return "universe"
        if code in self._external_positions_map():
            return "external"
        return ""
    def _get_tracked_position_info(self, code: str) -> Dict[str, Any]:
        if code in getattr(self, "universe", {}):
            return self.universe.get(code, {})
        return self._external_positions_map().get(code, {})
    def _tracked_position_codes(self, include_external: bool = True) -> List[str]:
        codes = list(getattr(self, "universe", {}).keys())
        if not include_external:
            return codes
        external_codes = [
            code for code in sorted(self._external_positions_map().keys()) if code not in getattr(self, "universe", {})
        ]
        return codes + external_codes
    def _manual_pending_entries(self) -> Dict[str, Dict[str, Any]]:
        getter = getattr(self, "_manual_pending_map", None)
        if callable(getter):
            mapping = getter()
            if isinstance(mapping, dict):
                return mapping
        mapping = getattr(self, "_manual_pending_state", None)
        if not isinstance(mapping, dict):
            mapping = {}
            self._manual_pending_state = mapping
        return mapping
    @staticmethod
    def _pending_active_fallback(pending: Dict[str, Any]) -> bool:
        if not isinstance(pending, dict) or not pending:
            return False
        return str(pending.get("state", "submitted") or "submitted").lower() in {"submitted", "partial"}
    def _pending_is_active_safe(self, pending: Dict[str, Any]) -> bool:
        checker = getattr(self, "_pending_is_active", None)
        if callable(checker):
            return bool(checker(pending))
        return self._pending_active_fallback(pending)
    def _pending_children_safe(self, pending: Dict[str, Any]) -> List[Dict[str, Any]]:
        getter = getattr(self, "_pending_children", None)
        if callable(getter):
            rows = getter(pending)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        rows = pending.get("child_orders", []) if isinstance(pending, dict) else []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]
    def _resolve_external_position_metadata(
        self,
        code: str,
        *,
        name: str = "",
        current_price: int = 0,
        existing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        current_info = existing if isinstance(existing, dict) else {}
        resolved_name = str(name or current_info.get("name") or code)
        resolved_current = max(0, int(current_price or 0))
        if resolved_current <= 0:
            resolved_current = max(0, int(current_info.get("current", 0) or 0))
        resolved_market_type = str(current_info.get("market_type", "") or "").strip()
        resolved_sector = str(current_info.get("sector", "") or "").strip()

        needs_quote = (
            not resolved_market_type
            or not resolved_sector
            or resolved_sector == "기타"
            or resolved_current <= 0
            or resolved_name == code
        )
        quote_getter = getattr(getattr(self, "rest_client", None), "get_stock_quote", None)
        if needs_quote and callable(quote_getter):
            try:
                quote = quote_getter(code)
            except Exception:
                quote = None
            if quote:
                quote_name = str(getattr(quote, "name", "") or "").strip()
                quote_market_type = str(getattr(quote, "market_type", "") or "").strip()
                quote_sector = str(getattr(quote, "sector", "") or "").strip()
                quote_current = max(0, int(getattr(quote, "current_price", 0) or 0))
                if quote_name:
                    resolved_name = quote_name
                if quote_current > 0:
                    resolved_current = quote_current
                if quote_market_type:
                    resolved_market_type = quote_market_type
                if quote_sector:
                    resolved_sector = quote_sector

        if not resolved_market_type:
            resolved_market_type = "unknown"
        if not resolved_sector:
            resolved_sector = "기타"
        return {
            "name": resolved_name,
            "current": resolved_current,
            "market_type": resolved_market_type,
            "sector": resolved_sector,
        }
    def _sync_external_positions_from_account_positions(
        self,
        positions: List[Any],
        *,
        rebuild_strategy: bool = False,
        now_dt: Optional[datetime.datetime] = None,
    ) -> List[str]:
        now = now_dt or datetime.datetime.now()
        mapping = self._external_positions_map()
        universe = getattr(self, "universe", {})
        universe_codes = set(universe.keys())
        manual_pending_map = self._manual_pending_entries()
        next_external: Dict[str, Any] = {}

        for position in positions or []:
            code = str(getattr(position, "code", "") or "").strip()
            if not code or code in universe_codes:
                continue
            held = max(0, int(getattr(position, "quantity", 0) or 0))
            if held <= 0:
                continue
            next_external[code] = position

        removed_codes = [code for code in list(mapping.keys()) if code not in next_external]
        for code in removed_codes:
            prev_info = mapping.pop(code, None)
            prev_amount = int(prev_info.get("invest_amount", 0) or 0) if isinstance(prev_info, dict) else 0
            if not rebuild_strategy and prev_amount > 0 and hasattr(self, "strategy"):
                self.strategy.update_market_investment(code, prev_amount, is_buy=False, cost_amount=prev_amount)
                self.strategy.update_sector_investment(code, prev_amount, is_buy=False, cost_amount=prev_amount)
            if hasattr(self, "_diagnostics_dirty_codes") and isinstance(self._diagnostics_dirty_codes, set):
                self._diagnostics_dirty_codes.add(code)

        for code, position in next_external.items():
            previous = mapping.get(code, {})
            previous_amount = int(previous.get("invest_amount", 0) or 0) if isinstance(previous, dict) else 0
            buy_price = max(0, int(getattr(position, "buy_price", 0) or 0))
            invest_amount = max(0, int(getattr(position, "buy_amount", 0) or 0))
            available_qty = max(
                0,
                int(getattr(position, "available_qty", getattr(position, "quantity", 0)) or 0),
            )
            metadata = self._resolve_external_position_metadata(
                code,
                name=str(getattr(position, "name", "") or ""),
                current_price=max(0, int(getattr(position, "current_price", 0) or 0)),
                existing=previous,
            )
            pending = getattr(self, "_pending_order_state", {}).get(code, {})
            if not pending:
                pending = manual_pending_map.get(code, {})
            status = "external_holding"
            if self._pending_is_active_safe(pending):
                side = str(pending.get("side", "") or "").lower()
                if side == "sell":
                    status = "sell_submitted"
                elif side == "buy":
                    status = "buy_submitted"

            partial_levels = previous.get("partial_profit_levels", set()) if isinstance(previous, dict) else set()
            if not isinstance(partial_levels, set):
                partial_levels = set(partial_levels or [])
            info = {
                "code": code,
                "name": metadata["name"],
                "held": max(0, int(getattr(position, "quantity", 0) or 0)),
                "available_qty": available_qty,
                "buy_price": buy_price,
                "invest_amount": invest_amount,
                "current": metadata["current"],
                "market_type": metadata["market_type"],
                "sector": metadata["sector"],
                "status": status,
                "read_only": True,
                "entry_origin": "external_account",
                "time_stop_eligible": False,
                "buy_time": previous.get("buy_time") or now,
                "max_profit_rate": float(previous.get("max_profit_rate", 0.0) or 0.0),
                "partial_profit_levels": partial_levels,
                "external_updated_at": previous.get("external_updated_at"),
                "external_status": previous.get("external_status", "idle"),
                "external_error": previous.get("external_error", ""),
                "market_state": previous.get("market_state", "normal"),
                "market_state_until": previous.get("market_state_until"),
                "last_guard_reason": previous.get("last_guard_reason", ""),
                "sync_failed_reason": "",
            }
            mapping[code] = info

            if hasattr(self, "strategy") and invest_amount > 0:
                if rebuild_strategy:
                    self.strategy.update_market_investment(code, invest_amount, is_buy=True)
                    self.strategy.update_sector_investment(code, invest_amount, is_buy=True)
                elif invest_amount > previous_amount:
                    delta = invest_amount - previous_amount
                    self.strategy.update_market_investment(code, delta, is_buy=True)
                    self.strategy.update_sector_investment(code, delta, is_buy=True)
                elif invest_amount < previous_amount:
                    delta = previous_amount - invest_amount
                    self.strategy.update_market_investment(code, delta, is_buy=False, cost_amount=delta)
                    self.strategy.update_sector_investment(code, delta, is_buy=False, cost_amount=delta)

            diag_touch = getattr(self, "_diag_touch", None)
            if callable(diag_touch):
                diag_touch(code, sync_status=status, retry_count=0, last_sync_error="")
            if hasattr(self, "_diagnostics_dirty_codes") and isinstance(self._diagnostics_dirty_codes, set):
                self._diagnostics_dirty_codes.add(code)

        return sorted(next_external.keys())
    def _apply_account_position_snapshot(
        self,
        codes: List[str],
        positions: List[Any],
        *,
        reset_tracking: bool = False,
        rebuild_strategy: bool = False,
        log_external: bool = False,
    ) -> None:
        if reset_tracking and hasattr(self, "strategy"):
            self.strategy.reset_tracking()

        positions_by_code = {str(getattr(pos, "code", "") or "").strip(): pos for pos in positions or []}
        now = datetime.datetime.now()

        for code in codes:
            info = self.universe.get(code, {})
            matched = positions_by_code.get(code)
            held = max(0, int(getattr(matched, "quantity", 0) or 0)) if matched else 0
            buy_price = max(0, int(getattr(matched, "buy_price", 0) or 0)) if matched else 0
            invest_amount = max(0, int(getattr(matched, "buy_amount", 0) or 0)) if matched else 0
            available_qty = max(
                0,
                int(getattr(matched, "available_qty", getattr(matched, "quantity", 0)) or 0),
            ) if matched else 0

            info["held"] = held
            info["available_qty"] = available_qty
            info["buy_price"] = buy_price
            info["invest_amount"] = invest_amount

            pending = getattr(self, "_pending_order_state", {}).get(code, {})
            if held > 0:
                info["status"] = "holding"
                if self._pending_is_active_safe(pending):
                    side = str(pending.get("side", "") or "").lower()
                    if side == "sell":
                        info["status"] = "sell_submitted"
                    elif side == "buy":
                        info["status"] = "buy_submitted"
                info["buy_time"] = info.get("buy_time") or now
                info["cooldown_until"] = None
                info["entry_origin"] = str(info.get("entry_origin") or "session_inbound")
                info["time_stop_eligible"] = bool(info.get("time_stop_eligible", False))
                info["sync_failed_reason"] = ""
                if rebuild_strategy and hasattr(self, "strategy") and invest_amount > 0:
                    self.strategy.update_market_investment(code, invest_amount, is_buy=True)
                    self.strategy.update_sector_investment(code, invest_amount, is_buy=True)
            else:
                info["status"] = "watch"
                if self._pending_is_active_safe(pending) and str(pending.get("side", "") or "").lower() == "buy":
                    info["status"] = "buy_submitted"
                info["buy_time"] = None
                info["max_profit_rate"] = 0
                info["partial_profit_levels"] = set()
                info["entry_origin"] = "watch"
                info["time_stop_eligible"] = True
                info["sync_failed_reason"] = ""

            if hasattr(self, "_sync_failed_codes"):
                self._sync_failed_codes.discard(code)
            diag_touch = getattr(self, "_diag_touch", None)
            if callable(diag_touch):
                diag_touch(code, sync_status=str(info.get("status", "")), retry_count=0, last_sync_error="")

        external_codes = self._sync_external_positions_from_account_positions(
            positions,
            rebuild_strategy=rebuild_strategy,
            now_dt=now,
        )
        if log_external and external_codes:
            preview = ", ".join(external_codes[:5])
            suffix = " ..." if len(external_codes) > 5 else ""
            self.log(f"External holdings tracked in read-only mode: {preview}{suffix}")

        recompute_count = getattr(self, "_recompute_holding_or_pending_count", None)
        if callable(recompute_count):
            recompute_count()
        else:
            external_positions = self._external_positions_map()
            manual_pending_state = getattr(self, "_manual_pending_state", {})
            held_count = sum(1 for v in self.universe.values() if int(v.get("held", 0)) > 0)
            held_count += sum(1 for v in external_positions.values() if int(v.get("held", 0)) > 0)
            pending_buy = sum(
                1
                for c, state in getattr(self, "_pending_order_state", {}).items()
                if self._pending_is_active_safe(state)
                and state.get("side") == "buy"
                and int(self._get_tracked_position_info(c).get("held", 0)) == 0
            )
            manual_pending_buy = sum(
                1
                for c, state in manual_pending_state.items()
                if self._pending_is_active_safe(state)
                and state.get("side") == "buy"
                and int(self._get_tracked_position_info(c).get("held", 0)) == 0
            )
            self._holding_or_pending_count = held_count + pending_buy + manual_pending_buy
        self._dirty_codes.update(codes)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    def _set_trading_stopped_state(self):
        self.is_running = False
        self._trading_start_inflight = False
        self._scheduled_start_requested = False
        if hasattr(self, "btn_start"):
            self.btn_start.setEnabled(True)
        if hasattr(self, "btn_stop"):
            self.btn_stop.setEnabled(False)
        if hasattr(self, "btn_emergency"):
            self.btn_emergency.setEnabled(False)
        self.schedule_started = False
        self._position_sync_pending.clear()
        if hasattr(self, "_position_sync_batch"):
            self._position_sync_batch.clear()
        if hasattr(self, "_position_sync_scheduled"):
            self._position_sync_scheduled = False
        if hasattr(self, "_position_sync_retry_count"):
            self._position_sync_retry_count = 0
        self._last_time_strategy_phase = None
        self._stop_external_refresh_loop()
        stop_market_intel = getattr(self, "_stop_market_intelligence_loop", None)
        if callable(stop_market_intel):
            stop_market_intel()
        self._stop_index_feed()
        self._global_risk_mode = "normal"
        self._global_risk_until = None
        self._order_health_mode = "normal"
        self._order_health_until = None
        if hasattr(self, "_guard_reason_by_code") and isinstance(self._guard_reason_by_code, dict):
            self._guard_reason_by_code.clear()
    def _disconnect_realtime_clients(self):
        try:
            if self.ws_client:
                self.ws_client.unsubscribe_all()
                self.ws_client.disconnect()
        except Exception as exc:
            self.log(f"WebSocket 종료 중 오류: {exc}")
