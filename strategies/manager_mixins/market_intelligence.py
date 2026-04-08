import datetime
import time
from typing import Any, Dict, Optional, Tuple

from config import Config


class StrategyManagerMarketIntelMixin:
    def get_market_intel_snapshot(self, code: str, now_ts: Optional[float] = None) -> Dict[str, Any]:
        info = self.trader.universe.get(code, {})
        state = info.get("market_intel", {}) if isinstance(info.get("market_intel"), dict) else {}
        cfg = getattr(self.config, "market_intelligence", getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {}))
        if not isinstance(cfg, dict):
            cfg = getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {})
        flags = getattr(self.config, "feature_flags", {}) if self.config is not None else {}
        if not isinstance(flags, dict):
            flags = {}
        enabled = bool(flags.get("enable_external_data", True) and cfg.get("enabled", True))
        reference_now_ts = float(now_ts) if now_ts is not None else time.time()
        if reference_now_ts < 1_000_000_000:
            reference_now_ts = time.time()
        updated_at = state.get("intel_updated_at")
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.datetime.fromisoformat(updated_at)
            except ValueError:
                updated_at = None
        age_sec = -1.0
        if isinstance(updated_at, datetime.datetime):
            age_sec = max(0.0, reference_now_ts - updated_at.timestamp())
        stale_sec = float(getattr(Config, "MARKET_INTEL_STALE_SEC", 180))
        status = str(state.get("status", state.get("intel_status", "idle")) or "idle")
        fresh = enabled and age_sec >= 0.0 and age_sec <= stale_sec and status == "fresh"
        if not enabled:
            status = "disabled"
        elif status == "fresh" and age_sec > stale_sec:
            status = "stale"
        block_until = state.get("dart_block_until")
        if isinstance(block_until, str):
            try:
                block_until = datetime.datetime.fromisoformat(block_until)
            except ValueError:
                block_until = None
        return {
            "enabled": enabled,
            "config": cfg,
            "info": info,
            "state": state,
            "status": status,
            "fresh": fresh,
            "age_sec": age_sec,
            "news_score": float(state.get("news_score", 0.0) or 0.0),
            "theme_score": float(state.get("theme_score", 0.0) or 0.0),
            "headline_velocity": int(state.get("headline_velocity", 0) or 0),
            "relevance_score": float(state.get("relevance_score", 0.0) or 0.0),
            "dart_risk_level": str(state.get("dart_risk_level", "normal") or "normal"),
            "macro_regime": str(state.get("macro_regime", "neutral") or "neutral"),
            "action_policy": str(state.get("action_policy", "allow") or "allow"),
            "exit_policy": str(state.get("exit_policy", "none") or "none"),
            "size_multiplier": float(state.get("size_multiplier", 1.0) or 1.0),
            "portfolio_budget_scale": float(state.get("portfolio_budget_scale", 1.0) or 1.0),
            "last_event_id": str(state.get("last_event_id", "") or ""),
            "event_type": str(state.get("event_type", "") or ""),
            "event_severity": str(state.get("event_severity", "low") or "low"),
            "source_health": str(state.get("source_health", "") or ""),
            "market_risk_mode": str(getattr(self.trader, "_market_risk_mode", "neutral") or "neutral"),
            "aggregate_news_risk": float(getattr(self.trader, "_aggregate_news_risk", 0.0) or 0.0),
            "block_until": block_until,
        }

    def get_market_position_defense_policy(self, code: str, now_ts: Optional[float] = None) -> Dict[str, Any]:
        snapshot = self.get_market_intel_snapshot(code, now_ts=now_ts)
        return {
            "action_policy": str(snapshot.get("action_policy", "allow") or "allow"),
            "exit_policy": str(snapshot.get("exit_policy", "none") or "none"),
            "last_event_id": str(snapshot.get("last_event_id", "") or ""),
            "event_type": str(snapshot.get("event_type", "") or ""),
            "event_severity": str(snapshot.get("event_severity", "low") or "low"),
        }

    def check_market_news_risk_guard(self, code: str, now_ts: Optional[float] = None) -> Tuple[bool, float]:
        snapshot = self.get_market_intel_snapshot(code, now_ts=now_ts)
        threshold = float(snapshot["config"].get("scoring", {}).get("news_block_threshold", -60))
        if not snapshot["enabled"]:
            return True, float(snapshot["news_score"])
        return float(snapshot["news_score"]) > threshold, float(snapshot["news_score"])

    def check_market_disclosure_event_guard(self, code: str, now_ts: Optional[float] = None) -> Tuple[bool, str]:
        snapshot = self.get_market_intel_snapshot(code, now_ts=now_ts)
        if not snapshot["enabled"]:
            return True, str(snapshot["dart_risk_level"])
        block_until = snapshot.get("block_until")
        active_block = isinstance(block_until, datetime.datetime) and datetime.datetime.now() < block_until
        passed = str(snapshot["dart_risk_level"]) != "high" and not active_block
        return passed, str(snapshot["dart_risk_level"])

    def check_market_macro_regime_guard(self, code: str, now_ts: Optional[float] = None) -> Tuple[bool, str]:
        snapshot = self.get_market_intel_snapshot(code, now_ts=now_ts)
        threshold = float(snapshot["config"].get("scoring", {}).get("macro_block_threshold", -40))
        if not snapshot["enabled"]:
            return True, str(snapshot["macro_regime"])
        passed = not (
            str(snapshot["macro_regime"]) == "risk_off" and float(snapshot["news_score"]) <= threshold
        )
        return passed, str(snapshot["macro_regime"])

    def check_market_theme_heat_filter(self, code: str, now_ts: Optional[float] = None) -> Tuple[bool, float]:
        snapshot = self.get_market_intel_snapshot(code, now_ts=now_ts)
        threshold = float(snapshot["config"].get("scoring", {}).get("theme_heat_threshold", 60))
        if not snapshot["enabled"]:
            return True, float(snapshot["theme_score"])
        return float(snapshot["theme_score"]) >= threshold, float(snapshot["theme_score"])

    def check_market_intel_fresh_guard(self, code: str, now_ts: Optional[float] = None) -> Tuple[bool, float]:
        snapshot = self.get_market_intel_snapshot(code, now_ts=now_ts)
        if not snapshot["enabled"]:
            return True, float(snapshot["age_sec"])
        request_refresh = getattr(self.trader, "_request_market_intelligence_refresh_batch", None)
        if not snapshot["fresh"] and callable(request_refresh):
            request_refresh([code], reason="intel_fresh_guard", force=False)
        return bool(snapshot["fresh"]), float(snapshot["age_sec"])
