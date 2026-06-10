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


class ExecutionGuardsMixin(TraderMixinBase):
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
    def _market_intelligence_entry_guard(self, code: str, info: dict, now: datetime.datetime) -> tuple[bool, str]:
        cfg = getattr(self, "config", None)
        flags = getattr(cfg, "feature_flags", {}) if cfg is not None else {}
        if not isinstance(flags, dict):
            flags = {}
        intel_cfg = getattr(cfg, "market_intelligence", {}) if cfg is not None else {}
        if not isinstance(intel_cfg, dict):
            intel_cfg = getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {})
        enabled = bool(flags.get("enable_external_data", True) and intel_cfg.get("enabled", True))
        if not enabled:
            return True, ""
        policy = intel_cfg.get("source_policy", {}) if isinstance(intel_cfg.get("source_policy"), dict) else {}
        strict_entry_guard = bool(policy.get("strict_entry_guard", False))

        def allow_relaxed(reason: str) -> tuple[bool, str]:
            if strict_entry_guard:
                return False, reason
            info["last_guard_warning"] = reason
            logger = getattr(self, "_log_once", None)
            if callable(logger):
                logger(
                    f"market_intel_relaxed:{code}:{reason}",
                    f"[market-intel] relaxed entry guard allowed {code}: {reason}",
                )
            return True, ""

        state = info.get("market_intel", {}) if isinstance(info.get("market_intel"), dict) else {}
        if not state:
            request_refresh = getattr(self, "_request_market_intelligence_refresh_batch", None)
            if not callable(request_refresh):
                return True, ""
            if callable(request_refresh):
                request_refresh([code], reason="entry_guard_missing", force=False)
            return allow_relaxed("market_intel_fresh_guard")

        status = str(state.get("status", state.get("intel_status", "idle")) or "idle").lower()
        if status == "disabled":
            return True, ""

        action_policy = str(state.get("action_policy", "allow") or "allow").lower()
        if action_policy in {"block_entry", "force_exit"}:
            return False, "market_intel_action_guard"

        if str(state.get("dart_risk_level", "normal") or "normal").lower() == "high":
            return False, "market_intel_dart_guard"

        allow_partial = bool(policy.get("allow_partial_for_entry", False))
        if status == "partial" and not allow_partial:
            return allow_relaxed("market_intel_source_guard")
        if status in {"error", "stale", "refreshing", "idle", "disabled_by_missing_credentials"}:
            if status in {"idle", "stale"}:
                request_refresh = getattr(self, "_request_market_intelligence_refresh_batch", None)
                if callable(request_refresh):
                    request_refresh([code], reason=f"entry_guard_{status}", force=False)
            reason = "market_intel_fresh_guard" if status in {"idle", "stale", "refreshing"} else "market_intel_source_guard"
            return allow_relaxed(reason)

        updated_at = state.get("intel_updated_at", state.get("updated_at"))
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.datetime.fromisoformat(updated_at)
            except ValueError:
                updated_at = None
        stale_sec = float(getattr(Config, "MARKET_INTEL_STALE_SEC", 180))
        if not isinstance(updated_at, datetime.datetime) or (now.timestamp() - updated_at.timestamp()) > stale_sec:
            request_refresh = getattr(self, "_request_market_intelligence_refresh_batch", None)
            if callable(request_refresh):
                request_refresh([code], reason="entry_guard_stale_ts", force=False)
            return allow_relaxed("market_intel_fresh_guard")

        return True, ""
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

        market_intel_ok, market_intel_reason = self._market_intelligence_entry_guard(code, info, now)
        if not market_intel_ok:
            return False, market_intel_reason

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
