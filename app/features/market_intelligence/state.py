"""Market intelligence mixin for KiwoomProTrader."""

from __future__ import annotations

import copy
import datetime
import hashlib
import html
import json
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.support.ui_text import (
    AI_PROVIDER_CHOICES,
    REPLAY_AUDIT_CHOICES,
    REPLAY_SCOPE_CHOICES,
    combo_value,
    display_action_policy,
    display_allowed,
    display_event_severity,
    display_event_type,
    display_exit_policy,
    display_market_state,
    display_news_sentiment,
    display_regime,
    display_replay_scope,
    display_source_health,
    display_source_name,
    display_status,
    display_yes_no,
    populate_combo,
    set_combo_value,
)
from app.support.widgets import NoScrollComboBox, NoScrollSpinBox
from config import Config
from data.providers import AIProvider, DartProvider, MacroProvider, NaverTrendProvider, NewsProvider
from app.mixins._typing import TraderMixinBase


class MarketIntelStateMixin(TraderMixinBase):
    MARKET_INTEL_SOURCE_NAMES = ("news", "dart", "datalab", "macro", "ai")
    @staticmethod
    def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = MarketIntelStateMixin._deep_merge_dict(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    def _market_intelligence_config(self) -> Dict[str, Any]:
        default_cfg = copy.deepcopy(getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {}))
        cfg = getattr(getattr(self, "config", None), "market_intelligence", {}) or {}
        if not isinstance(cfg, dict):
            return default_cfg
        return self._deep_merge_dict(default_cfg, cfg)
    def _market_intelligence_enabled(self) -> bool:
        flags = getattr(getattr(self, "config", None), "feature_flags", {}) or {}
        return bool(flags.get("enable_external_data", True) and self._market_intelligence_config().get("enabled", True))
    def _market_intelligence_provider_enabled(self, provider_name: str) -> bool:
        if not self._market_intelligence_enabled():
            return False
        providers = self._market_intelligence_config().get("providers", {})
        return bool(providers.get(provider_name, False))
    def _market_api_credentials(self) -> Dict[str, str]:
        def _text(name: str) -> str:
            widget = getattr(self, name, None)
            return str(widget.text()).strip() if widget is not None else ""

        return {
            "naver_client_id": _text("input_naver_client_id"),
            "naver_client_secret": _text("input_naver_client_secret"),
            "dart_api_key": _text("input_dart_api_key"),
            "fred_api_key": _text("input_fred_api_key"),
            "ai_api_key": _text("input_ai_api_key"),
        }
    def _default_market_intel_state(self) -> Dict[str, Any]:
        return copy.deepcopy(getattr(Config, "DEFAULT_MARKET_INTEL_STATE", {}))
    def _ensure_market_intel_state(self, info: Dict[str, Any]) -> Dict[str, Any]:
        state = info.get("market_intel")
        if not isinstance(state, dict):
            state = self._default_market_intel_state()
        else:
            state = self._deep_merge_dict(self._default_market_intel_state(), state)
        info["market_intel"] = state
        return state
    def _ensure_market_intel_sources(self) -> Dict[str, Dict[str, Any]]:
        state = getattr(self, "_market_intel_sources", None)
        if isinstance(state, dict):
            return state
        state = {
            source: {"status": "idle", "updated_at": None, "error": ""}
            for source in self.MARKET_INTEL_SOURCE_NAMES
        }
        self._market_intel_sources = state
        return state
    def _set_market_intel_source_status(self, source: str, status: str, error: str = ""):
        sources = self._ensure_market_intel_sources()
        if source not in sources:
            sources[source] = {"status": "idle", "updated_at": None, "error": ""}
        sources[source]["status"] = str(status or "idle")
        sources[source]["error"] = str(error or "")
        sources[source]["updated_at"] = datetime.datetime.now()
        label = getattr(self, f"lbl_market_source_{source}", None)
        if label is not None:
            text = f"{display_source_name(source)}: {display_status(sources[source]['status'])}"
            if error:
                text = f"{text} ({error})"
            label.setText(text)
    @staticmethod
    def _clean_text(value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    @staticmethod
    def _normalize_link(value: Any) -> str:
        link = str(value or "").strip()
        if not link:
            return ""
        return link.split("?", 1)[0].rstrip("/")
    @staticmethod
    def _market_intel_policy_rank(policy: str) -> int:
        order = {
            "allow": 0,
            "watch_only": 1,
            "block_entry": 2,
            "reduce_size": 3,
            "tighten_exit": 4,
            "force_exit": 5,
        }
        return int(order.get(str(policy or "allow"), 0))
    @staticmethod
    def _market_intel_policy_from_rank(rank: int) -> str:
        reverse = {
            0: "allow",
            1: "watch_only",
            2: "block_entry",
            3: "reduce_size",
            4: "tighten_exit",
            5: "force_exit",
        }
        return str(reverse.get(int(rank), "allow"))
    @staticmethod
    def _combine_source_statuses(statuses: List[str]) -> str:
        normalized = [str(status or "idle") for status in statuses if str(status or "").strip()]
        if not normalized:
            return "idle"
        has_success = any(status in {"fresh", "ok_with_data", "ok_empty"} for status in normalized)
        has_data = any(status in {"fresh", "ok_with_data"} for status in normalized)
        has_empty = any(status == "ok_empty" for status in normalized)
        has_error = any(status == "error" for status in normalized)
        has_partial = any(status == "partial" for status in normalized)
        has_missing_credentials = any(status == "disabled_by_missing_credentials" for status in normalized)
        if has_partial or (has_error and has_success):
            return "partial"
        if has_error:
            return "error"
        if has_missing_credentials:
            return "disabled_by_missing_credentials"
        if has_data:
            return "ok_with_data"
        if has_empty:
            return "ok_empty"
        if all(status == "disabled" for status in normalized):
            return "disabled"
        if any(status == "disabled" for status in normalized):
            return "disabled"
        return normalized[-1]
    def _market_intel_entities(self) -> Dict[str, Dict[str, Any]]:
        combined: Dict[str, Dict[str, Any]] = {str(code): info for code, info in getattr(self, "universe", {}).items()}
        active = getattr(self, "_active_market_candidates", None)
        if isinstance(active, dict):
            for code, info in active.items():
                if code not in combined and isinstance(info, dict):
                    combined[str(code)] = info
        return combined
    def _market_intel_entity(self, code: str) -> Dict[str, Any]:
        if code in getattr(self, "universe", {}):
            return self.universe[code]
        active = getattr(self, "_active_market_candidates", {})
        if isinstance(active, dict) and code in active:
            return active[code]
        candidate = getattr(self, "_candidate_universe", {})
        if isinstance(candidate, dict) and code in candidate:
            return candidate[code]
        return {}
    def _is_candidate_entity(self, code: str) -> bool:
        return code not in getattr(self, "universe", {})
    def _symbol_aliases(self, info: Dict[str, Any], code: str) -> List[str]:
        raw = [str(info.get("name", code) or code), str(code or "")]
        extra = info.get("aliases", [])
        if isinstance(extra, list):
            raw.extend(str(item or "") for item in extra)
        aliases: List[str] = []
        seen = set()
        for item in raw:
            text = self._clean_text(item)
            if not text:
                continue
            variants = {
                text,
                text.replace("주식회사", "").strip(),
                text.replace(" ", ""),
                text.replace("(우)", "").strip(),
            }
            for variant in variants:
                normalized = self._clean_text(variant)
                key = normalized.lower()
                if len(normalized) < 2 or key in seen:
                    continue
                seen.add(key)
                aliases.append(normalized)
        return aliases[:4]
    def _news_queries_for_symbol(self, info: Dict[str, Any], code: str) -> List[str]:
        aliases = [alias for alias in self._symbol_aliases(info, code) if not alias.isdigit()]
        return aliases[:2] or [str(info.get("name", code) or code)]
    def _build_market_intel_event_id(self, *parts: Any) -> str:
        payload = "|".join(str(part or "") for part in parts)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    def _published_bucket(self, published_at: Any) -> str:
        if isinstance(published_at, datetime.datetime):
            dt = published_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            ts = int(dt.timestamp() // 300) * 300
            return datetime.datetime.fromtimestamp(ts, tz=dt.tzinfo).isoformat()
        return ""
    def _news_relevance_score(self, info: Dict[str, Any], code: str, title: str, description: str) -> float:
        combined = f"{title} {description}".lower()
        aliases = self._symbol_aliases(info, code)
        if not aliases:
            return 0.0
        matched = 0
        for alias in aliases:
            alias_norm = alias.lower()
            if alias_norm and alias_norm in combined:
                matched += 1
        if matched <= 0:
            return 0.0
        return min(1.0, 0.35 + matched * 0.25)
    def _classify_disclosure_event(self, title: str) -> str:
        lowered = str(title or "").lower()
        for event_type in ("funding", "governance", "halt", "earnings", "contract", "correction"):
            keywords = getattr(Config, "MARKET_INTELLIGENCE_EVENT_KEYWORDS", {}).get(event_type, set())
            if any(str(keyword).lower() in lowered for keyword in keywords):
                return event_type
        return "general"
    @staticmethod
    def _severity_from_policy(policy: str) -> str:
        rank = MarketIntelStateMixin._market_intel_policy_rank(policy)
        if rank >= 5:
            return "critical"
        if rank >= 4:
            return "high"
        if rank >= 3:
            return "medium"
        return "low"
    def _determine_symbol_status(self, source_meta: Dict[str, Dict[str, Any]]) -> str:
        cfg = self._market_intelligence_config()
        policy = cfg.get("source_policy", {}) if isinstance(cfg.get("source_policy"), dict) else {}
        core_sources = list(policy.get("core_sources", ["news", "dart"]))
        fail_on_core_error = bool(policy.get("fail_on_core_error", True))
        configured_sources = [
            source
            for source in ("news", "dart", "datalab", "macro")
            if self._market_intelligence_provider_enabled(source)
        ]
        if not configured_sources:
            return "disabled"
        any_success = False
        any_error = False
        core_error = False
        for source in configured_sources:
            status = str(source_meta.get(source, {}).get("status", "idle") or "idle")
            if status in {"ok_with_data", "ok_empty", "fresh"}:
                any_success = True
            elif status == "partial":
                any_success = True
                any_error = True
                if source in core_sources:
                    core_error = True
            elif status == "stale":
                any_success = True
            elif status in {"error", "disabled_by_missing_credentials"}:
                any_error = True
                if source in core_sources:
                    core_error = True
        if fail_on_core_error and core_error:
            return "error"
        if any_error:
            return "partial"
        if any_success:
            return "fresh"
        return "idle"
    def _sync_source_meta(self, state: Dict[str, Any], source_meta: Dict[str, Dict[str, Any]]):
        sources = state.get("sources", {})
        if not isinstance(sources, dict):
            sources = {}
        now_dt = datetime.datetime.now()
        for source in self.MARKET_INTEL_SOURCE_NAMES:
            current = sources.get(source, {}) if isinstance(sources.get(source), dict) else {}
            row = source_meta.get(source, {}) if isinstance(source_meta.get(source), dict) else {}
            current.update(
                {
                    "status": str(row.get("status", current.get("status", "idle")) or "idle"),
                    "updated_at": row.get("updated_at", current.get("updated_at", now_dt)),
                    "error": str(row.get("error", current.get("error", "")) or ""),
                }
            )
            if "count" in row:
                current["count"] = int(row.get("count", 0) or 0)
            if "value" in row:
                current["value"] = float(row.get("value", 0.0) or 0.0)
            if "summary" in row:
                current["summary"] = str(row.get("summary", "") or "")
            sources[source] = current
        state["sources"] = sources
        summaries = []
        for source in ("news", "dart", "datalab", "macro"):
            row = sources.get(source, {})
            summaries.append(f"{source}:{row.get('status', 'idle')}")
        state["source_health"] = ", ".join(summaries)
