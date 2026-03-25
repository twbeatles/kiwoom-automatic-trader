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
from ._typing import TraderMixinBase


class MarketIntelligenceMixin(TraderMixinBase):
    MARKET_INTEL_SOURCE_NAMES = ("news", "dart", "datalab", "macro", "ai")

    @staticmethod
    def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = MarketIntelligenceMixin._deep_merge_dict(result[key], value)
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
        if has_partial or (has_error and has_success):
            return "partial"
        if has_error:
            return "error"
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
        rank = MarketIntelligenceMixin._market_intel_policy_rank(policy)
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
            elif status == "error":
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

    def _bind_market_intelligence_signals(self):
        for name in (
            "chk_market_intel_enabled",
            "chk_market_news",
            "chk_market_dart",
            "chk_market_datalab",
            "chk_market_macro",
            "chk_market_ai_enabled",
            "spin_market_news_refresh",
            "spin_market_macro_refresh",
            "spin_market_news_block",
            "spin_market_news_boost",
            "spin_market_ai_daily_calls",
            "spin_market_ai_symbol_calls",
            "spin_market_ai_budget",
            "combo_market_ai_provider",
            "input_market_ai_model",
        ):
            control = getattr(self, name, None)
            if control is None:
                continue
            for signal_name in ("toggled", "valueChanged", "currentTextChanged", "textChanged"):
                signal = getattr(control, signal_name, None)
                if signal is not None:
                    signal.connect(self._update_market_intelligence_config_from_ui)
                    break

    def _update_market_intelligence_config_from_ui(self, *_args):
        cfg = self._market_intelligence_config()
        cfg["enabled"] = bool(getattr(self, "chk_market_intel_enabled", None) and self.chk_market_intel_enabled.isChecked())
        cfg["providers"]["news"] = bool(getattr(self, "chk_market_news", None) and self.chk_market_news.isChecked())
        cfg["providers"]["dart"] = bool(getattr(self, "chk_market_dart", None) and self.chk_market_dart.isChecked())
        cfg["providers"]["datalab"] = bool(getattr(self, "chk_market_datalab", None) and self.chk_market_datalab.isChecked())
        cfg["providers"]["macro"] = bool(getattr(self, "chk_market_macro", None) and self.chk_market_macro.isChecked())
        if hasattr(self, "spin_market_news_refresh"):
            refresh = int(self.spin_market_news_refresh.value())
            cfg["refresh_sec"]["news"] = refresh
            cfg["refresh_sec"]["dart"] = refresh
            cfg["refresh_sec"]["datalab"] = refresh
        if hasattr(self, "spin_market_macro_refresh"):
            cfg["refresh_sec"]["macro"] = int(self.spin_market_macro_refresh.value())
        if hasattr(self, "spin_market_news_block"):
            cfg["scoring"]["news_block_threshold"] = -abs(int(self.spin_market_news_block.value()))
        if hasattr(self, "spin_market_news_boost"):
            cfg["scoring"]["news_boost_threshold"] = abs(int(self.spin_market_news_boost.value()))
        if hasattr(self, "chk_market_ai_enabled"):
            cfg["ai"]["enabled"] = bool(self.chk_market_ai_enabled.isChecked())
        if hasattr(self, "combo_market_ai_provider"):
            cfg["ai"]["provider"] = combo_value(self.combo_market_ai_provider, "gemini").lower()
        if hasattr(self, "input_market_ai_model"):
            cfg["ai"]["model"] = str(self.input_market_ai_model.text() or cfg["ai"].get("model", "gemini-2.5-flash-lite"))
        if hasattr(self, "spin_market_ai_daily_calls"):
            cfg["ai"]["max_calls_per_day"] = int(self.spin_market_ai_daily_calls.value())
        if hasattr(self, "spin_market_ai_symbol_calls"):
            cfg["ai"]["max_calls_per_symbol"] = int(self.spin_market_ai_symbol_calls.value())
        if hasattr(self, "spin_market_ai_budget"):
            cfg["ai"]["daily_budget_krw"] = int(self.spin_market_ai_budget.value())
        if hasattr(self, "config"):
            self.config.market_intelligence = cfg

    def _score_news_items(self, info: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
        seen = set()
        unique_items: List[Dict[str, Any]] = []
        positive_hits = 0
        negative_hits = 0
        relevance_total = 0.0
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        velocity = 0
        code = str(info.get("code", "") or info.get("stock_code", "") or "")
        if not code:
            for candidate_code, candidate_info in self._market_intel_entities().items():
                if candidate_info is info:
                    code = candidate_code
                    break
        min_relevance = float(
            self._market_intelligence_config().get("scoring", {}).get("min_relevance_score", 0.4)
        )
        for raw in items:
            if not isinstance(raw, dict):
                continue
            title = self._clean_text(raw.get("title"))
            description = self._clean_text(raw.get("description"))
            if not title:
                continue
            published_at = raw.get("published_at")
            event_id = self._build_market_intel_event_id(
                title.lower(),
                self._normalize_link(raw.get("origin_link") or raw.get("link")),
                self._published_bucket(published_at),
            )
            if event_id in seen:
                continue
            seen.add(event_id)
            relevance_score = self._news_relevance_score(info, code, title, description)
            if relevance_score <= 0:
                continue
            item = dict(raw)
            item["title"] = title
            item["description"] = description
            item["event_id"] = event_id
            item["relevance_score"] = relevance_score
            unique_items.append(item)
            relevance_total += relevance_score
            lowered = title.lower()
            if any(keyword.lower() in lowered for keyword in getattr(Config, "MARKET_INTELLIGENCE_POSITIVE_KEYWORDS", set())):
                positive_hits += max(1, int(round(relevance_score * 2)))
            if any(keyword.lower() in lowered for keyword in getattr(Config, "MARKET_INTELLIGENCE_NEGATIVE_KEYWORDS", set())):
                negative_hits += max(1, int(round(relevance_score * 2)))
            if isinstance(published_at, datetime.datetime):
                published = published_at.astimezone(now.tzinfo) if published_at.tzinfo else published_at.replace(tzinfo=now.tzinfo)
                if relevance_score >= min_relevance and (now - published) <= datetime.timedelta(minutes=5):
                    velocity += 1
        score = max(-100, min(100, positive_hits * 20 - negative_hits * 25))
        sentiment = "neutral"
        if score >= 20:
            sentiment = "bullish"
        elif score <= -20:
            sentiment = "bearish"
        relevance = (relevance_total / len(unique_items)) if unique_items else 0.0
        return {
            "headlines": unique_items[:10],
            "score": float(score),
            "sentiment": sentiment,
            "headline_velocity": velocity,
            "relevance_score": float(relevance),
        }

    def _score_dart_events(self, disclosures: List[Dict[str, Any]]) -> Dict[str, Any]:
        normalized: List[Dict[str, Any]] = []
        risk_level = "normal"
        score = 0.0
        high_risk = False
        event_type = "general"
        severity = "low"
        latest_event_id = ""
        for row in disclosures:
            if not isinstance(row, dict):
                continue
            title = self._clean_text(row.get("report_nm") or row.get("report_name") or row.get("rpt_nm"))
            if not title:
                continue
            lowered = title.lower()
            row_event_type = self._classify_disclosure_event(title)
            receipt_no = str(row.get("rcept_no", "") or row.get("rcp_no", "") or "")
            event_id = self._build_market_intel_event_id(receipt_no or title, row.get("rcept_dt", "") or row.get("filing_date", ""))
            tags: List[str] = []
            for keyword in getattr(Config, "MARKET_INTELLIGENCE_HIGH_RISK_KEYWORDS", set()):
                if keyword.lower() in lowered:
                    tags.append(keyword)
            if tags:
                high_risk = True
                risk_level = "high"
                score = min(score, -80.0)
                event_type = row_event_type
                severity = "critical"
            elif row_event_type == "earnings":
                score = min(0.0, score)
                event_type = row_event_type
                severity = "medium"
            normalized.append(
                {
                    "title": title,
                    "receipt_no": receipt_no,
                    "date": str(row.get("rcept_dt", "") or row.get("filing_date", "") or ""),
                    "tags": tags,
                    "event_type": row_event_type,
                    "event_id": event_id,
                }
            )
            if event_id:
                latest_event_id = event_id
        return {
            "events": normalized[:10],
            "risk_level": risk_level,
            "score": score,
            "blocking": high_risk,
            "event_type": event_type,
            "severity": severity,
            "latest_event_id": latest_event_id,
        }

    def _derive_macro_regime(self, values: Dict[str, float]) -> Dict[str, Any]:
        vix = float(values.get("VIXCLS", 0.0) or 0.0)
        yield_10y = float(values.get("DGS10", 0.0) or 0.0)
        if vix >= 25.0 or yield_10y >= 4.5:
            return {"regime": "risk_off", "score": -60.0, "summary": f"VIX={vix:.1f}, 10Y={yield_10y:.2f}"}
        if 0 < vix <= 18.0 and 0 < yield_10y <= 4.0:
            return {"regime": "risk_on", "score": 20.0, "summary": f"VIX={vix:.1f}, 10Y={yield_10y:.2f}"}
        return {"regime": "neutral", "score": 0.0, "summary": f"VIX={vix:.1f}, 10Y={yield_10y:.2f}"}

    def _calculate_theme_score(
        self, info: Dict[str, Any], news_titles: List[str], trend_ratio: float, ranking_overlap: float = 0.0
    ) -> Dict[str, Any]:
        weights = self._market_intelligence_config().get("scoring", {}).get("weights", {})
        keyword_counts: Dict[str, int] = {}
        for title in news_titles:
            for token in re.findall(r"[A-Za-z0-9가-힣]{2,}", title):
                keyword_counts[token] = keyword_counts.get(token, 0) + 1
        top_keywords = [token for token, _count in sorted(keyword_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
        keyword_score = min(100.0, float(sum(keyword_counts.get(token, 0) for token in top_keywords) * 10))
        trend_score = max(0.0, min(100.0, float(trend_ratio)))
        overlap_score = max(0.0, min(100.0, float(ranking_overlap)))
        total = (
            keyword_score * float(weights.get("keyword_frequency", 50)) / 100.0
            + trend_score * float(weights.get("datalab_change", 30)) / 100.0
            + overlap_score * float(weights.get("ranking_intersection", 20)) / 100.0
        )
        return {"score": min(100.0, total), "keywords": top_keywords}

    def _ranking_intersection_score(self, code: str) -> float:
        def _contains_code(table_name: str, code_col: int) -> bool:
            table = getattr(self, table_name, None)
            if table is None:
                return False
            try:
                for row in range(table.rowCount()):
                    item = table.item(row, code_col)
                    if item is not None and str(item.text()).strip() == code:
                        return True
            except Exception:
                return False
            return False

        in_condition = _contains_code("condition_table", 0)
        in_ranking = _contains_code("ranking_table", 1)
        if in_condition and in_ranking:
            return 100.0
        if in_condition or in_ranking:
            return 50.0
        return 0.0

    def _refresh_candidate_universe_state(self):
        cfg = self._market_intelligence_config().get("candidate_universe", {})
        if not bool(cfg.get("enabled", True)):
            self._candidate_universe = {}
            self._active_market_candidates = {}
            return
        now_ts = time.time()
        max_candidates = max(1, int(cfg.get("max_candidates", 20)))
        ttl_sec = max(60, int(cfg.get("active_ttl_sec", 900)))
        dual_required = bool(cfg.get("promotion_requires_dual_source", True))
        promotion_news = float(cfg.get("promotion_news_score", 70))
        promotion_theme = float(cfg.get("promotion_theme_score", 70))
        pool = copy.deepcopy(getattr(self, "_candidate_universe", {}))

        def _upsert_from_table(table_name: str, code_col: int, name_col: int, source_name: str):
            table = getattr(self, table_name, None)
            if table is None:
                return
            for row in range(table.rowCount()):
                code_item = table.item(row, code_col)
                name_item = table.item(row, name_col)
                code = str(code_item.text()).strip() if code_item is not None else ""
                if not code or code in self.universe:
                    continue
                entry = pool.get(code, {})
                if not isinstance(entry, dict):
                    entry = {}
                source_hits = set(entry.get("source_hits", []) or [])
                source_hits.add(source_name)
                entry.update(
                    {
                        "code": code,
                        "name": str(name_item.text()).strip() if name_item is not None else code,
                        "source_hits": sorted(source_hits),
                        "last_seen_ts": now_ts,
                        "is_candidate": True,
                    }
                )
                self._ensure_market_intel_state(entry)
                pool[code] = entry

        _upsert_from_table("condition_table", 0, 1, "condition")
        _upsert_from_table("ranking_table", 1, 2, "ranking")

        active: Dict[str, Dict[str, Any]] = {}
        for code, entry in list(pool.items()):
            if code in self.universe:
                pool.pop(code, None)
                continue
            state = self._ensure_market_intel_state(entry)
            source_hits = set(entry.get("source_hits", []) or [])
            strong_signal = (
                float(state.get("news_score", 0.0) or 0.0) >= promotion_news
                or float(state.get("theme_score", 0.0) or 0.0) >= promotion_theme
            )
            within_ttl = (now_ts - float(entry.get("last_seen_ts", now_ts))) <= ttl_sec
            should_activate = (len(source_hits) >= 2 if dual_required else bool(source_hits)) or strong_signal
            if should_activate and within_ttl:
                active[code] = entry
            elif not within_ttl and not strong_signal:
                pool.pop(code, None)
        ordered = sorted(
            active.items(),
            key=lambda kv: (
                -len(set(kv[1].get("source_hits", []) or [])),
                -float(self._ensure_market_intel_state(kv[1]).get("theme_score", 0.0) or 0.0),
                -float(self._ensure_market_intel_state(kv[1]).get("news_score", 0.0) or 0.0),
                kv[0],
            ),
        )[:max_candidates]
        self._candidate_universe = pool
        self._active_market_candidates = {code: info for code, info in ordered}
        self._candidate_last_refresh_ts = now_ts

    def _update_global_market_intel_state(self):
        entities = self._market_intel_entities()
        news_scores: List[float] = []
        theme_heat_map: Dict[str, float] = {}
        sector_negative_counts: Dict[str, int] = {}
        macro_modes: List[str] = []
        for code, info in entities.items():
            state = self._ensure_market_intel_state(info)
            news_scores.append(float(state.get("news_score", 0.0) or 0.0))
            macro_modes.append(str(state.get("macro_regime", "neutral") or "neutral"))
            for keyword in list(state.get("theme_keywords", []) or [])[:5]:
                theme_heat_map[keyword] = max(theme_heat_map.get(keyword, 0.0), float(state.get("theme_score", 0.0) or 0.0))
            sector = str(info.get("sector", "") or "").strip()
            if sector and float(state.get("news_score", 0.0) or 0.0) <= float(
                self._market_intelligence_config().get("scoring", {}).get("news_block_threshold", -60)
            ):
                sector_negative_counts[sector] = sector_negative_counts.get(sector, 0) + 1
        aggregate_news = sum(news_scores) / len(news_scores) if news_scores else 0.0
        budget_cfg = self._market_intelligence_config().get("portfolio_budget", {})
        budget_scale = 1.0
        market_risk_mode = "neutral"
        if any(mode == "risk_off" for mode in macro_modes):
            market_risk_mode = "risk_off"
            budget_scale = min(budget_scale, float(budget_cfg.get("risk_off_scale", 0.7)))
        elif macro_modes and all(mode == "risk_on" for mode in macro_modes):
            market_risk_mode = "risk_on"
        if aggregate_news <= float(budget_cfg.get("aggregate_negative_news_threshold", -80)):
            budget_scale = min(budget_scale, float(budget_cfg.get("aggregate_negative_scale", 0.85)))
        self._market_risk_mode = market_risk_mode
        self._portfolio_budget_scale = max(0.1, float(budget_scale))
        self._aggregate_news_risk = float(aggregate_news)
        self._theme_heat_map = theme_heat_map
        self._sector_blocks = {
            sector: {"reason": "aggregate_negative_news", "count": count}
            for sector, count in sector_negative_counts.items()
            if count >= 2
        }
        event_cache = getattr(self, "_market_scope_event_cache", None)
        if not isinstance(event_cache, dict):
            event_cache = {"market_mode": "", "budget_scale": 1.0, "sector_blocks": {}, "theme_heat": {}}
            self._market_scope_event_cache = event_cache
        prev_market_mode = str(event_cache.get("market_mode", "") or "")
        prev_budget_scale = float(event_cache.get("budget_scale", 1.0) or 1.0)
        prev_sector_blocks = dict(event_cache.get("sector_blocks", {}) or {})
        prev_theme_heat = dict(event_cache.get("theme_heat", {}) or {})
        if market_risk_mode != prev_market_mode or abs(prev_budget_scale - self._portfolio_budget_scale) >= 0.01:
            market_event_id = self._build_market_intel_event_id(
                "market",
                market_risk_mode,
                f"{self._portfolio_budget_scale:.2f}",
                int(round(self._aggregate_news_risk)),
            )
            self._record_market_intel_event(
                scope="market",
                symbol="KR_MARKET",
                source="macro",
                event_type="market_risk_mode",
                score=float(self._aggregate_news_risk),
                tags=[market_risk_mode],
                summary=f"시장 리스크 모드 {market_risk_mode}, 포트폴리오 예산 스케일 {self._portfolio_budget_scale:.2f}",
                blocking=False,
                event_id=market_event_id,
                payload={
                    "macro_regime": market_risk_mode if market_risk_mode in {"risk_on", "risk_off"} else "neutral",
                    "portfolio_budget_scale": self._portfolio_budget_scale,
                    "aggregate_news_risk": self._aggregate_news_risk,
                    "action_policy": "allow",
                    "event_severity": "high" if market_risk_mode == "risk_off" else "low",
                },
            )
        for sector, meta in self._sector_blocks.items():
            prev_count = int(prev_sector_blocks.get(sector, 0) or 0)
            current_count = int(meta.get("count", 0) or 0)
            if current_count == prev_count:
                continue
            sector_event_id = self._build_market_intel_event_id("sector", sector, current_count)
            self._record_market_intel_event(
                scope="sector",
                symbol="",
                source="news",
                event_type="sector_block",
                score=-80.0,
                tags=[sector],
                summary=f"{sector} 섹터 경계 강화 ({current_count}건)",
                blocking=True,
                event_id=sector_event_id,
                payload={
                    "sector": sector,
                    "count": current_count,
                    "action_policy": "block_entry",
                    "event_severity": "high",
                    "portfolio_budget_scale": self._portfolio_budget_scale,
                },
            )
        for sector in set(prev_sector_blocks) - set(self._sector_blocks):
            sector_event_id = self._build_market_intel_event_id("sector", sector, "released")
            self._record_market_intel_event(
                scope="sector",
                symbol="",
                source="news",
                event_type="sector_block_release",
                score=0.0,
                tags=[sector],
                summary=f"{sector} 섹터 경계 해제",
                blocking=False,
                event_id=sector_event_id,
                payload={
                    "sector": sector,
                    "count": 0,
                    "action_policy": "allow",
                    "event_severity": "low",
                },
            )
        theme_threshold = float(self._market_intelligence_config().get("scoring", {}).get("theme_heat_threshold", 60))
        hot_themes = {theme: score for theme, score in theme_heat_map.items() if float(score or 0.0) >= theme_threshold}
        for theme, score in hot_themes.items():
            previous_score = float(prev_theme_heat.get(theme, 0.0) or 0.0)
            if previous_score >= theme_threshold:
                continue
            theme_event_id = self._build_market_intel_event_id("theme", theme, int(round(score)))
            self._record_market_intel_event(
                scope="theme",
                symbol="",
                source="theme",
                event_type="theme_heat",
                score=float(score),
                tags=[theme],
                summary=f"{theme} 테마 과열 감지 ({score:.0f})",
                blocking=False,
                event_id=theme_event_id,
                payload={
                    "theme": theme,
                    "theme_score": float(score),
                    "action_policy": "allow",
                    "event_severity": "medium",
                },
            )
        for theme in set(prev_theme_heat) - set(hot_themes):
            theme_event_id = self._build_market_intel_event_id("theme", theme, "released")
            self._record_market_intel_event(
                scope="theme",
                symbol="",
                source="theme",
                event_type="theme_cooldown",
                score=0.0,
                tags=[theme],
                summary=f"{theme} 테마 과열 해제",
                blocking=False,
                event_id=theme_event_id,
                payload={
                    "theme": theme,
                    "theme_score": 0.0,
                    "action_policy": "allow",
                    "event_severity": "low",
                },
            )
        event_cache["market_mode"] = market_risk_mode
        event_cache["budget_scale"] = self._portfolio_budget_scale
        event_cache["sector_blocks"] = {sector: int(meta.get("count", 0) or 0) for sector, meta in self._sector_blocks.items()}
        event_cache["theme_heat"] = hot_themes

    def _resolve_market_intel_policy(self, code: str, info: Dict[str, Any]) -> Dict[str, Any]:
        state = self._ensure_market_intel_state(info)
        cfg = self._market_intelligence_config()
        scoring = cfg.get("scoring", {}) if isinstance(cfg.get("scoring"), dict) else {}
        soft_cfg = cfg.get("soft_scale", {}) if isinstance(cfg.get("soft_scale"), dict) else {}
        defense_cfg = cfg.get("position_defense", {}) if isinstance(cfg.get("position_defense"), dict) else {}
        ai_cfg = cfg.get("ai", {}) if isinstance(cfg.get("ai"), dict) else {}

        policy = "allow"
        size_multiplier = float(soft_cfg.get("base_multiplier", 1.0) or 1.0)
        exit_policy = "none"
        reason = "baseline"
        status = str(state.get("status", state.get("intel_status", "idle")) or "idle")
        news_score = float(state.get("news_score", 0.0) or 0.0)
        theme_score = float(state.get("theme_score", 0.0) or 0.0)
        macro_regime = str(state.get("macro_regime", "neutral") or "neutral")
        dart_risk = str(state.get("dart_risk_level", "normal") or "normal")
        block_until = state.get("dart_block_until")
        dart_blocking = isinstance(block_until, datetime.datetime) and datetime.datetime.now() < block_until

        if status in {"error", "stale"}:
            policy = "block_entry"
            reason = "source_unhealthy"
        elif status == "partial" and not bool(cfg.get("source_policy", {}).get("allow_partial_for_entry", False)):
            policy = "block_entry"
            reason = "partial_source"

        if dart_risk == "high" or dart_blocking:
            policy = "force_exit" if bool(defense_cfg.get("allow_force_exit_on_high_risk_dart", True)) else "reduce_size"
            exit_policy = policy if policy != "block_entry" else "reduce_size"
            reason = "high_risk_disclosure"
        elif news_score <= float(scoring.get("news_block_threshold", -60)):
            policy = "reduce_size"
            exit_policy = "reduce_size"
            reason = "negative_news"
        elif macro_regime == "risk_off" and news_score <= float(scoring.get("macro_block_threshold", -40)):
            policy = "tighten_exit"
            exit_policy = "tighten_exit"
            reason = "macro_news_combo"

        if policy == "allow" and bool(soft_cfg.get("enabled", True)):
            if news_score >= float(scoring.get("news_boost_threshold", 60)):
                size_multiplier *= float(soft_cfg.get("positive_news_multiplier", 1.15))
            if theme_score >= float(scoring.get("theme_heat_threshold", 60)):
                size_multiplier *= float(soft_cfg.get("theme_heat_multiplier", 1.10))
            if macro_regime == "risk_on":
                size_multiplier *= float(soft_cfg.get("risk_on_multiplier", 1.05))
            size_multiplier = min(float(soft_cfg.get("max_multiplier", 1.25)), max(1.0, size_multiplier))
        else:
            size_multiplier = 1.0

        ai_summary = state.get("ai_summary", {}) if isinstance(state.get("ai_summary"), dict) else {}
        ai_action = str(ai_summary.get("action_hint", "") or "").strip()
        ai_conf = float(ai_summary.get("confidence", 0.0) or 0.0)
        if bool(ai_cfg.get("apply_to_policy", True)) and ai_action and ai_conf >= float(ai_cfg.get("min_confidence_for_policy", 0.8)):
            if ai_action == "force_exit" and policy != "force_exit":
                ai_action = "tighten_exit"
            if ai_action in {"allow", "watch_only", "block_entry", "reduce_size", "tighten_exit", "force_exit"}:
                combined_rank = max(self._market_intel_policy_rank(policy), self._market_intel_policy_rank(ai_action))
                policy = self._market_intel_policy_from_rank(combined_rank)
                if policy in {"reduce_size", "tighten_exit", "force_exit"}:
                    exit_policy = policy
                if policy != "allow":
                    size_multiplier = 1.0

        portfolio_budget_scale = float(getattr(self, "_portfolio_budget_scale", 1.0) or 1.0)
        severity = self._severity_from_policy(policy)
        return {
            "action_policy": policy,
            "size_multiplier": max(0.1, float(size_multiplier)),
            "exit_policy": exit_policy,
            "event_severity": severity,
            "portfolio_budget_scale": max(0.1, portfolio_budget_scale),
            "reason": reason,
            "event_type": str(state.get("event_type", "") or ""),
        }

    def _build_briefing_summary(self, code: str, info: Dict[str, Any]) -> str:
        state = self._ensure_market_intel_state(info)
        name = str(info.get("name", code) or code)
        lines = [
            f"{name}: 뉴스 점수 {float(state.get('news_score', 0.0) or 0.0):+.0f}, 뉴스 심리 {state.get('news_sentiment', 'neutral')}.",
            f"공시 리스크는 {state.get('dart_risk_level', 'normal')}, 매크로 레짐은 {state.get('macro_regime', 'neutral')}입니다.",
            f"테마 점수는 {float(state.get('theme_score', 0.0) or 0.0):.0f}, 정책은 {state.get('action_policy', 'allow')}입니다.",
        ]
        return " ".join(lines)

    def _ai_usage_bucket(self) -> Dict[str, Any]:
        today = datetime.date.today().isoformat()
        usage = getattr(self, "_market_ai_usage", None)
        if not isinstance(usage, dict) or usage.get("day") != today:
            usage = {"day": today, "count": 0, "cost_krw": 0, "by_symbol": {}}
            self._market_ai_usage = usage
        return usage

    def _consume_ai_budget(self, code: str, estimated_cost_krw: int = 100) -> bool:
        usage = self._ai_usage_bucket()
        ai_cfg = self._market_intelligence_config().get("ai", {})
        if int(usage.get("count", 0)) >= int(ai_cfg.get("max_calls_per_day", 30)):
            return False
        if int(usage.get("cost_krw", 0)) + int(estimated_cost_krw) > int(ai_cfg.get("daily_budget_krw", 1000)):
            return False
        by_symbol = usage.setdefault("by_symbol", {})
        if int(by_symbol.get(code, 0)) >= int(ai_cfg.get("max_calls_per_symbol", 3)):
            return False
        usage["count"] = int(usage.get("count", 0)) + 1
        usage["cost_krw"] = int(usage.get("cost_krw", 0)) + int(estimated_cost_krw)
        by_symbol[code] = int(by_symbol.get(code, 0)) + 1
        return True

    def _rules_based_ai_fallback(self, code: str, info: Dict[str, Any], reason: str = "", error: str = "") -> Dict[str, Any]:
        state = self._ensure_market_intel_state(info)
        policy = self._resolve_market_intel_policy(code, info)
        news_score = float(state.get("news_score", 0.0) or 0.0)
        stance = "bullish" if news_score >= 60 else "bearish" if news_score <= -60 else "neutral"
        summary = self._build_briefing_summary(code, info)
        if error:
            summary = f"{summary} (AI fallback: {error})"
        return {
            "summary": summary,
            "stance": stance,
            "risk_tags": [str(state.get("dart_risk_level", "normal"))] if str(state.get("dart_risk_level", "normal")) != "normal" else [],
            "confidence": 0.35,
            "action_hint": str(policy.get("action_policy", "watch_only") or "watch_only"),
            "reason": reason,
            "source": "rules",
        }

    def _maybe_run_ai_summary(self, code: str, info: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
        state = self._ensure_market_intel_state(info)
        ai_cfg = self._market_intelligence_config().get("ai", {})
        if not bool(ai_cfg.get("enabled", False)):
            summary = self._rules_based_ai_fallback(code, info, reason=reason)
            state["ai_summary"] = summary
            return summary
        if not self._consume_ai_budget(code):
            summary = self._rules_based_ai_fallback(code, info, reason=reason, error="budget_exceeded")
            state["ai_summary"] = summary
            return summary
        provider = AIProvider(provider=str(ai_cfg.get("provider", "gemini")), api_key=self._market_api_credentials().get("ai_api_key", ""))
        prompt = (
            f"종목: {info.get('name', code)} ({code})\n"
            f"뉴스 점수: {state.get('news_score', 0)}\n"
            f"공시 리스크: {state.get('dart_risk_level', 'normal')}\n"
            f"테마 점수: {state.get('theme_score', 0)}\n"
            f"매크로 레짐: {state.get('macro_regime', 'neutral')}\n"
            f"헤드라인: {[item.get('title', '') for item in state.get('news_headlines', [])[:5]]}\n"
            f"공시: {[item.get('title', '') for item in state.get('dart_events', [])[:5]]}\n"
            f"사유: {reason}\n"
        )
        try:
            summary = provider.summarize_event(prompt, str(ai_cfg.get("model", "gemini-2.5-flash-lite")))
            if not isinstance(summary, dict):
                raise RuntimeError("invalid_ai_payload")
            normalized = {
                "summary": str(summary.get("summary", "") or self._build_briefing_summary(code, info)),
                "stance": str(summary.get("stance", "neutral") or "neutral"),
                "risk_tags": list(summary.get("risk_tags", []) or []),
                "confidence": float(summary.get("confidence", 0.5) or 0.5),
                "action_hint": str(summary.get("action_hint", "watch_only") or "watch_only"),
                "reason": reason,
                "source": str(ai_cfg.get("provider", "gemini")),
            }
            state["ai_summary"] = normalized
            self._set_market_intel_source_status("ai", "fresh")
            state.setdefault("sources", {}).setdefault("ai", {})
            state["sources"]["ai"].update({"status": "ok_with_data", "updated_at": datetime.datetime.now(), "error": ""})
            return normalized
        except Exception as exc:
            self._set_market_intel_source_status("ai", "error", error=str(exc))
            summary = self._rules_based_ai_fallback(code, info, reason=reason, error=str(exc))
            state["ai_summary"] = summary
            state.setdefault("sources", {}).setdefault("ai", {})
            state["sources"]["ai"].update({"status": "error", "updated_at": datetime.datetime.now(), "error": str(exc)})
            return summary

    def _record_market_intel_event(
        self,
        *,
        scope: str,
        symbol: str,
        source: str,
        event_type: str,
        score: float,
        tags: List[str],
        summary: str,
        blocking: bool,
        event_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        raw_ref: str = "",
    ):
        legacy_raw_ref = str(raw_ref or "")
        if not legacy_raw_ref and isinstance(payload, dict) and payload:
            try:
                legacy_raw_ref = json.dumps(payload, ensure_ascii=False)
            except Exception:
                legacy_raw_ref = ""
        record = {
            "schema_version": 2,
            "ts": datetime.datetime.now().isoformat(),
            "event_id": str(event_id or self._build_market_intel_event_id(scope, symbol, source, event_type, summary)),
            "scope": str(scope or "symbol"),
            "symbol": str(symbol or ""),
            "source": str(source or ""),
            "event_type": str(event_type or ""),
            "score": float(score or 0.0),
            "tags": list(tags or []),
            "summary": str(summary or ""),
            "blocking": bool(blocking),
            "payload": payload if isinstance(payload, dict) else {},
            "raw_ref": legacy_raw_ref,
        }
        path = Path(getattr(Config, "MARKET_INTELLIGENCE_EVENTS_FILE", "data/market_intelligence_events.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._schedule_market_replay_refresh()

    def _record_decision_audit_event(
        self,
        *,
        code: str,
        info: Dict[str, Any],
        allowed: bool,
        reason: str,
        conditions: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        quantity: int = 0,
    ):
        path = Path(getattr(Config, "MARKET_INTELLIGENCE_DECISION_AUDIT_FILE", "data/decision_audit.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        state = self._ensure_market_intel_state(info)
        record = {
            "ts": datetime.datetime.now().isoformat(),
            "symbol": str(code or ""),
            "name": str(info.get("name", code) or code),
            "allowed": bool(allowed),
            "reason": str(reason or ""),
            "quantity": int(quantity or 0),
            "action_policy": str(state.get("action_policy", "allow") or "allow"),
            "exit_policy": str(state.get("exit_policy", "none") or "none"),
            "size_multiplier": float(state.get("size_multiplier", 1.0) or 1.0),
            "portfolio_budget_scale": float(state.get("portfolio_budget_scale", 1.0) or 1.0),
            "market_intel": {
                "status": str(state.get("status", state.get("intel_status", "idle")) or "idle"),
                "news_score": float(state.get("news_score", 0.0) or 0.0),
                "theme_score": float(state.get("theme_score", 0.0) or 0.0),
                "macro_regime": str(state.get("macro_regime", "neutral") or "neutral"),
                "dart_risk_level": str(state.get("dart_risk_level", "normal") or "normal"),
                "last_event_id": str(state.get("last_event_id", "") or ""),
            },
            "conditions": dict(conditions or {}),
            "metrics": dict(metrics or {}),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._schedule_market_replay_refresh()

    def _maybe_emit_market_intel_alert(
        self,
        code: str,
        info: Dict[str, Any],
        *,
        source: str,
        event_type: str,
        score: float,
        summary: str,
        blocking: bool,
        tags: Optional[List[str]] = None,
        event_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        raw_ref: str = "",
    ):
        dedup = getattr(self, "_market_intel_alert_ts", None)
        if not isinstance(dedup, dict):
            dedup = {}
            self._market_intel_alert_ts = dedup
        key = f"{code}:{source}:{event_type}"
        now_ts = time.time()
        cooldown = int(getattr(Config, "MARKET_INTEL_ALERT_DEDUP_SEC", 600))
        if (now_ts - float(dedup.get(key, 0.0))) < cooldown:
            return
        dedup[key] = now_ts
        state = self._ensure_market_intel_state(info)
        state["last_alert"] = summary
        self._record_market_intel_event(
            scope="symbol",
            symbol=code,
            source=source,
            event_type=event_type,
            score=score,
            tags=list(tags or []),
            summary=summary,
            blocking=blocking,
            event_id=event_id,
            payload=payload,
            raw_ref=raw_ref,
        )
        channels = self._market_intelligence_config().get("alert_channels", {})
        if channels.get("ui", True):
            self.log(f"[시장인텔리전스] {summary}")
        if channels.get("telegram", True) and getattr(self, "telegram", None):
            self.telegram.send(summary)
        if blocking and getattr(self, "sound", None):
            self.sound.play_warning()

    def _build_news_provider(self) -> NewsProvider:
        creds = self._market_api_credentials()
        return NewsProvider(creds.get("naver_client_id", ""), creds.get("naver_client_secret", ""))

    def _build_dart_provider(self) -> DartProvider:
        creds = self._market_api_credentials()
        return DartProvider(creds.get("dart_api_key", ""), cache_dir=getattr(Config, "DATA_DIR", "data"))

    def _build_macro_provider(self) -> MacroProvider:
        creds = self._market_api_credentials()
        return MacroProvider(creds.get("fred_api_key", ""))

    def _build_trend_provider(self) -> NaverTrendProvider:
        creds = self._market_api_credentials()
        return NaverTrendProvider(creds.get("naver_client_id", ""), creds.get("naver_client_secret", ""))

    def _apply_market_intelligence_payload(self, code: str, row: Dict[str, Any], macro_values: Dict[str, float]):
        info = self._market_intel_entity(code)
        if not info:
            return
        state = self._ensure_market_intel_state(info)
        now_dt = datetime.datetime.now()
        news = self._score_news_items(info, row.get("news", []))
        dart = self._score_dart_events(row.get("dart", []))
        trend_ratio = float(row.get("trend_ratio", 0.0) or 0.0)
        ranking_overlap = self._ranking_intersection_score(code)
        theme = self._calculate_theme_score(
            info,
            [item.get("title", "") for item in news["headlines"]],
            trend_ratio,
            ranking_overlap=ranking_overlap,
        )
        macro = self._derive_macro_regime(macro_values)
        session_block_until = datetime.datetime.combine(now_dt.date(), datetime.time(15, 30))
        source_meta = row.get("source_meta", {}) if isinstance(row.get("source_meta"), dict) else {}
        self._sync_source_meta(state, source_meta)
        symbol_status = self._determine_symbol_status(source_meta)
        velocity_threshold = int(self._market_intelligence_config().get("scoring", {}).get("headline_velocity_threshold", 5))
        theme_threshold = float(self._market_intelligence_config().get("scoring", {}).get("theme_heat_threshold", 60))
        latest_event_id = str(dart.get("latest_event_id", "") or (news["headlines"][0].get("event_id", "") if news["headlines"] else ""))
        effective_event_type = str(dart.get("event_type", "") or "")
        if not effective_event_type and int(news.get("headline_velocity", 0) or 0) >= velocity_threshold:
            effective_event_type = "headline_velocity"
        elif not effective_event_type and float(theme.get("score", 0.0) or 0.0) >= theme_threshold:
            effective_event_type = "theme_heat"
        event_ids = [
            str(item.get("event_id", "") or "")
            for item in list(news.get("headlines", []) or []) + list(dart.get("events", []) or [])
            if str(item.get("event_id", "") or "")
        ]
        seen_event_ids = list(dict.fromkeys(list(state.get("seen_event_ids", []) or []) + event_ids))[-200:]
        state.update(
            {
                "status": symbol_status,
                "updated_at": now_dt,
                "news_score": news["score"],
                "news_sentiment": news["sentiment"],
                "news_headlines": news["headlines"],
                "headline_velocity": news["headline_velocity"],
                "relevance_score": news["relevance_score"],
                "dart_events": dart["events"],
                "dart_risk_level": dart["risk_level"],
                "dart_block_until": session_block_until if bool(dart.get("blocking", False)) else None,
                "event_type": effective_event_type,
                "event_severity": str(dart.get("severity", "low") or "low"),
                "theme_score": theme["score"],
                "theme_keywords": theme["keywords"],
                "macro_regime": macro["regime"],
                "source_health": str(state.get("source_health", "") or ""),
                "intel_updated_at": now_dt,
                "intel_status": symbol_status,
                "intel_error": "" if symbol_status not in {"error", "partial"} else state.get("source_health", ""),
                "last_event_id": latest_event_id,
                "seen_event_ids": seen_event_ids,
            }
        )
        policy = self._resolve_market_intel_policy(code, info)
        state.update(policy)
        info["external_updated_at"] = now_dt
        info["external_status"] = symbol_status
        info["external_error"] = str(state.get("intel_error", "") or "")
        state["briefing_summary"] = self._build_briefing_summary(code, info)
        if bool(self._market_intelligence_config().get("ai", {}).get("enabled", False)):
            triggers = [
                abs(float(state.get("news_score", 0.0) or 0.0))
                >= float(self._market_intelligence_config().get("ai", {}).get("min_score_to_call", 60)),
                bool(dart.get("blocking", False)),
                int(state.get("headline_velocity", 0) or 0)
                >= int(self._market_intelligence_config().get("scoring", {}).get("headline_velocity_threshold", 5)),
            ]
            if any(triggers):
                self._maybe_run_ai_summary(code, info, reason="event_trigger")
                state.update(self._resolve_market_intel_policy(code, info))
        else:
            state["ai_summary"] = self._rules_based_ai_fallback(code, info, reason="disabled")
        if dart.get("blocking", False):
            self._maybe_emit_market_intel_alert(
                code,
                info,
                source="dart",
                event_type="high_risk_disclosure",
                score=float(dart.get("score", -80.0) or -80.0),
                summary=f"{info.get('name', code)} 고위험 공시 감지 - 신규 진입 차단",
                blocking=True,
                tags=[tag for event in dart["events"] for tag in event.get("tags", [])],
                event_id=str(state.get("last_event_id", "") or ""),
                payload={
                    "dart_risk_level": state.get("dart_risk_level", "normal"),
                    "event_type": state.get("event_type", ""),
                    "action_policy": state.get("action_policy", "allow"),
                    "exit_policy": state.get("exit_policy", "none"),
                },
            )
        if int(state.get("headline_velocity", 0) or 0) >= velocity_threshold:
            self._maybe_emit_market_intel_alert(
                code,
                info,
                source="news",
                event_type="headline_velocity",
                score=float(state.get("news_score", 0.0) or 0.0),
                summary=f"{info.get('name', code)} 헤드라인 급증 감지 ({state.get('headline_velocity', 0)}건/5분)",
                blocking=False,
                tags=list(state.get("theme_keywords", []) or []),
                event_id=str(news["headlines"][0].get("event_id", "") if news["headlines"] else ""),
                payload={
                    "news_score": state.get("news_score", 0.0),
                    "headline_velocity": state.get("headline_velocity", 0),
                    "action_policy": state.get("action_policy", "allow"),
                },
            )
        if float(state.get("theme_score", 0.0) or 0.0) >= theme_threshold:
            self._maybe_emit_market_intel_alert(
                code,
                info,
                source="theme",
                event_type="theme_heat",
                score=float(state.get("theme_score", 0.0) or 0.0),
                summary=f"{info.get('name', code)} 테마 과열 감지 (점수 {state.get('theme_score', 0.0):.0f})",
                blocking=False,
                tags=list(state.get("theme_keywords", []) or []),
                event_id=str(state.get("last_event_id", "") or self._build_market_intel_event_id(code, "theme", now_dt.isoformat())),
                payload={
                    "theme_score": state.get("theme_score", 0.0),
                    "theme_keywords": state.get("theme_keywords", []),
                    "action_policy": state.get("action_policy", "allow"),
                },
            )
        self._market_intel_dirty_codes.add(code)

    def _fetch_market_intelligence_worker(self, codes: List[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"codes": {}, "source_statuses": {}, "macro_values": {}}
        if not self._market_intelligence_enabled():
            for source in ("news", "dart", "datalab", "macro"):
                payload["source_statuses"][source] = {"status": "disabled", "error": "market_intelligence_disabled"}
            return payload
        source_buckets = {
            source: {"statuses": [], "errors": []}
            for source in ("news", "dart", "datalab", "macro")
        }

        def _track_source(source_name: str, status: str, error: str = ""):
            bucket = source_buckets.setdefault(source_name, {"statuses": [], "errors": []})
            bucket["statuses"].append(str(status or "idle"))
            if error:
                bucket["errors"].append(str(error))

        macro_values: Dict[str, float] = {}
        macro_status = "disabled"
        macro_error = "provider_disabled"
        if self._market_intelligence_provider_enabled("macro"):
            provider = self._build_macro_provider()
            if provider.available():
                cache = getattr(self, "_market_macro_cache", None)
                now_ts = time.time()
                macro_refresh_sec = int(
                    self._market_intelligence_config().get("refresh_sec", {}).get(
                        "macro", getattr(Config, "MARKET_INTEL_MACRO_REFRESH_SEC", 300)
                    )
                )
                if (
                    isinstance(cache, dict)
                    and isinstance(cache.get("values"), dict)
                    and cache.get("values")
                    and (now_ts - float(cache.get("ts", 0.0))) < max(30, macro_refresh_sec)
                ):
                    macro_values = dict(cache.get("values", {}))
                    macro_status = "fresh"
                    macro_error = ""
                else:
                    macro_values = provider.latest_values(list(self._market_intelligence_config().get("macro_series", [])))
                    self._market_macro_cache = {"values": dict(macro_values), "ts": now_ts}
                    macro_status = str(getattr(provider, "last_status", "idle") or "idle")
                    macro_error = str(getattr(provider, "last_error", "") or "")
            else:
                macro_status = "disabled"
                macro_error = "api_key_missing"
        else:
            macro_status = "disabled"
            macro_error = "provider_disabled"
        _track_source("macro", macro_status, macro_error)
        payload["macro_values"] = macro_values

        news_provider = self._build_news_provider()
        dart_provider = self._build_dart_provider()
        trend_provider = self._build_trend_provider()

        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=30)).strftime("%Y%m%d")
        end_date = today.strftime("%Y%m%d")
        for code in codes:
            info = self._market_intel_entity(code)
            news_enabled = self._market_intelligence_provider_enabled("news")
            dart_enabled = self._market_intelligence_provider_enabled("dart")
            datalab_enabled = self._market_intelligence_provider_enabled("datalab")
            news_available = bool(news_enabled and news_provider.available())
            dart_available = bool(dart_enabled and dart_provider.available())
            datalab_available = bool(datalab_enabled and trend_provider.available())
            row = {
                "news": [],
                "dart": [],
                "trend_ratio": 0.0,
                "source_meta": {
                    "news": {
                        "status": "idle" if news_available else "disabled",
                        "error": "" if news_available else ("provider_disabled" if not news_enabled else "api_key_missing"),
                        "updated_at": datetime.datetime.now(),
                        "count": 0,
                    },
                    "dart": {
                        "status": "idle" if dart_available else "disabled",
                        "error": "" if dart_available else ("provider_disabled" if not dart_enabled else "api_key_missing"),
                        "updated_at": datetime.datetime.now(),
                        "count": 0,
                    },
                    "datalab": {
                        "status": "idle" if datalab_available else "disabled",
                        "error": "" if datalab_available else ("provider_disabled" if not datalab_enabled else "api_key_missing"),
                        "updated_at": datetime.datetime.now(),
                        "value": 0.0,
                    },
                    "macro": {
                        "status": macro_status,
                        "error": macro_error,
                        "updated_at": datetime.datetime.now(),
                        "summary": self._derive_macro_regime(macro_values).get("summary", "") if macro_values else "",
                    },
                },
            }
            if news_available:
                merged_news: List[Dict[str, Any]] = []
                seen_ids = set()
                query_statuses: List[str] = []
                query_errors: List[str] = []
                for query in self._news_queries_for_symbol(info, code):
                    try:
                        items = news_provider.search(query, display=10, sort="date")
                    except Exception:
                        items = []
                    current_status = str(getattr(news_provider, "last_status", "idle") or "idle")
                    current_error = str(getattr(news_provider, "last_error", "") or "")
                    query_statuses.append(current_status)
                    if current_error:
                        query_errors.append(current_error)
                    _track_source("news", current_status, current_error)
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        item_id = self._build_market_intel_event_id(
                            self._clean_text(item.get("title")),
                            self._normalize_link(item.get("origin_link") or item.get("link")),
                            self._published_bucket(item.get("published_at")),
                        )
                        if item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)
                        merged_news.append(item)
                news_status = self._combine_source_statuses(query_statuses)
                row["news"] = merged_news
                row["source_meta"]["news"] = {
                    "status": news_status,
                    "error": " | ".join(dict.fromkeys([error for error in query_errors if error])),
                    "updated_at": datetime.datetime.now(),
                    "count": len(merged_news),
                }
            elif not news_enabled:
                _track_source("news", "disabled", "provider_disabled")
            else:
                _track_source("news", "disabled", "api_key_missing")
            if dart_available:
                try:
                    disclosures = dart_provider.get_recent_disclosures(code, start_date=start_date, end_date=end_date, page_count=10)
                except Exception:
                    disclosures = []
                cursor = str(getattr(self, "_market_dart_cursor_by_code", {}).get(code, "") or "")
                fresh_disclosures = []
                max_cursor = cursor
                for item in disclosures:
                    receipt_no = str(item.get("rcept_no", "") or item.get("rcp_no", "") or "")
                    if receipt_no and receipt_no > max_cursor:
                        max_cursor = receipt_no
                    if not cursor or (receipt_no and receipt_no > cursor):
                        fresh_disclosures.append(item)
                row["dart"] = fresh_disclosures if fresh_disclosures else disclosures[:3]
                getattr(self, "_market_dart_cursor_by_code", {})[code] = max_cursor
                dart_status = str(getattr(dart_provider, "last_status", "idle") or "idle")
                dart_error = str(getattr(dart_provider, "last_error", "") or "")
                _track_source("dart", dart_status, dart_error)
                row["source_meta"]["dart"] = {
                    "status": dart_status,
                    "error": dart_error,
                    "updated_at": datetime.datetime.now(),
                    "count": len(row["dart"]),
                }
            elif not dart_enabled:
                _track_source("dart", "disabled", "provider_disabled")
            else:
                _track_source("dart", "disabled", "api_key_missing")
            if datalab_available:
                ratios = trend_provider.latest_ratios(self._news_queries_for_symbol(info, code))
                best_ratio = 0.0
                for query in self._news_queries_for_symbol(info, code):
                    best_ratio = max(best_ratio, float(ratios.get(query, 0.0) or 0.0))
                row["trend_ratio"] = best_ratio
                datalab_status = str(getattr(trend_provider, "last_status", "idle") or "idle")
                datalab_error = str(getattr(trend_provider, "last_error", "") or "")
                _track_source("datalab", datalab_status, datalab_error)
                row["source_meta"]["datalab"] = {
                    "status": datalab_status,
                    "error": datalab_error,
                    "updated_at": datetime.datetime.now(),
                    "value": best_ratio,
                }
            elif not datalab_enabled:
                _track_source("datalab", "disabled", "provider_disabled")
            else:
                _track_source("datalab", "disabled", "api_key_missing")
            payload["codes"][code] = row
        for source_name, bucket in source_buckets.items():
            status = self._combine_source_statuses(list(bucket.get("statuses", [])))
            errors = [str(error) for error in bucket.get("errors", []) if str(error or "").strip()]
            payload["source_statuses"][source_name] = {
                "status": status,
                "error": " | ".join(dict.fromkeys(errors)),
            }
        return payload

    def _on_market_intelligence_result(self, requested_codes: List[str], payload: Dict[str, Any]):
        source_statuses = payload.get("source_statuses", {}) if isinstance(payload, dict) else {}
        for source, row in source_statuses.items():
            if isinstance(row, dict):
                self._set_market_intel_source_status(source, str(row.get("status", "idle") or "idle"), str(row.get("error", "") or ""))
        macro_values = payload.get("macro_values", {}) if isinstance(payload, dict) else {}
        for code in requested_codes:
            row = payload.get("codes", {}).get(code, {}) if isinstance(payload, dict) else {}
            self._apply_market_intelligence_payload(code, row if isinstance(row, dict) else {}, macro_values if isinstance(macro_values, dict) else {})
        self._refresh_candidate_universe_state()
        self._update_global_market_intel_state()
        self._last_market_intel_fetch_ts = time.time()
        self._refresh_market_intelligence_table()

    def _on_market_intelligence_error(self, requested_codes: List[str], error: Exception):
        for code in requested_codes:
            info = self._market_intel_entity(code)
            if not info:
                continue
            state = self._ensure_market_intel_state(info)
            state["status"] = "error"
            state["intel_status"] = "error"
            state["intel_error"] = str(error)
            info["external_status"] = "error"
            info["external_error"] = str(error)
            self._market_intel_dirty_codes.add(code)
        for source in ("news", "dart", "datalab", "macro"):
            self._set_market_intel_source_status(source, "error", error=str(error))
        self._refresh_market_intelligence_table()

    def _request_market_intelligence_refresh_batch(self, codes: List[str], reason: str = "periodic", force: bool = False) -> bool:
        if not codes:
            return False
        if not self._market_intelligence_enabled():
            for source in ("news", "dart", "datalab", "macro"):
                self._set_market_intel_source_status(source, "disabled", error="market_intelligence_disabled")
            for code in codes:
                info = self._market_intel_entity(code)
                if not info:
                    continue
                state = self._ensure_market_intel_state(info)
                state["status"] = "disabled"
                state["intel_status"] = "disabled"
                state["intel_error"] = "market_intelligence_disabled"
                info["external_status"] = "disabled"
                info["external_error"] = "market_intelligence_disabled"
            return False
        now_ts = time.time()
        min_interval = max(1, int(self._market_intelligence_config().get("refresh_sec", {}).get("news", getattr(Config, "MARKET_INTEL_REFRESH_SEC", 60))))
        if not force and (now_ts - float(getattr(self, "_last_market_intel_fetch_ts", 0.0))) < min_interval:
            return False
        selected = [code for code in codes if code in self.universe]
        active_candidates = getattr(self, "_active_market_candidates", {})
        if isinstance(active_candidates, dict):
            selected.extend(code for code in codes if code in active_candidates and code not in selected)
        if not selected:
            return False
        if hasattr(self, "threadpool"):
            from app.support.worker import Worker

            worker = Worker(self._fetch_market_intelligence_worker, selected)
            worker.signals.result.connect(lambda payload, requested=selected: self._on_market_intelligence_result(requested, payload))
            worker.signals.error.connect(lambda error, requested=selected: self._on_market_intelligence_error(requested, error))
            self.threadpool.start(worker)
        else:
            try:
                payload = self._fetch_market_intelligence_worker(selected)
                self._on_market_intelligence_result(selected, payload)
            except Exception as exc:
                self._on_market_intelligence_error(selected, exc)
        return True

    def _start_market_intelligence_loop(self, codes: List[str]):
        if not hasattr(self, "_market_intel_timer") or self._market_intel_timer is None:
            try:
                self._market_intel_timer = QTimer(self)
            except TypeError:
                self._market_intel_timer = QTimer()
            self._market_intel_timer.timeout.connect(self._on_market_intelligence_timer)
        refresh_sec = int(self._market_intelligence_config().get("refresh_sec", {}).get("news", getattr(Config, "MARKET_INTEL_REFRESH_SEC", 60)))
        self._market_intel_timer.setInterval(max(1, refresh_sec) * 1000)
        self._refresh_candidate_universe_state()
        combined_codes = list(dict.fromkeys(list(codes) + list(getattr(self, "_active_market_candidates", {}).keys())))
        if combined_codes:
            self._request_market_intelligence_refresh_batch(combined_codes, reason="startup", force=True)
            if not self._market_intel_timer.isActive():
                self._market_intel_timer.start()

    def _stop_market_intelligence_loop(self):
        timer = getattr(self, "_market_intel_timer", None)
        if timer is not None:
            timer.stop()

    def _on_market_intelligence_timer(self):
        if not getattr(self, "is_running", False):
            return
        self._refresh_candidate_universe_state()
        combined_codes = list(
            dict.fromkeys(list(self.universe.keys()) + list(getattr(self, "_active_market_candidates", {}).keys()))
        )
        self._request_market_intelligence_refresh_batch(combined_codes, reason="periodic", force=True)
        self._maybe_publish_market_briefing(force=False)

    def _maybe_publish_market_briefing(self, force: bool = False):
        if not getattr(self, "is_running", False):
            return
        briefing_time = str(self._market_intelligence_config().get("briefing_time", getattr(Config, "MARKET_INTEL_BRIEFING_TIME", "08:50")) or "08:50")
        now = datetime.datetime.now()
        today = now.date().isoformat()
        if not force and now.strftime("%H:%M") != briefing_time:
            return
        if not force and getattr(self, "_market_briefing_sent_day", "") == today:
            return
        lines = []
        for code, info in self._market_intel_entities().items():
            state = self._ensure_market_intel_state(info)
            if int(info.get("held", 0) or 0) > 0 or float(state.get("news_score", 0.0) or 0.0) != 0.0:
                lines.append(state.get("briefing_summary") or self._build_briefing_summary(code, info))
        if not lines:
            return
        message = "[장전 브리핑]\n" + "\n".join(lines[:10])
        self._market_briefing_sent_day = today
        if self._market_intelligence_config().get("alert_channels", {}).get("ui", True):
            self.log(message)
        if self._market_intelligence_config().get("alert_channels", {}).get("telegram", True) and getattr(self, "telegram", None):
            self.telegram.send(message)

    def _refresh_market_intelligence_table(self):
        table = getattr(self, "market_intel_table", None)
        if table is None:
            return
        entities = self._market_intel_entities()
        codes = list(entities.keys())
        stale_sec = int(getattr(Config, "MARKET_INTEL_STALE_SEC", 180))
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(codes))
            self._market_intel_row_to_code = {}
            for row, code in enumerate(codes):
                info = entities.get(code, {})
                state = self._ensure_market_intel_state(info)
                updated_at = state.get("updated_at") or state.get("intel_updated_at")
                status = str(state.get("status", state.get("intel_status", "idle")) or "idle")
                if status == "fresh" and isinstance(updated_at, datetime.datetime):
                    age = max(0, int((datetime.datetime.now() - updated_at).total_seconds()))
                    if age > stale_sec:
                        status = "stale"
                values = [
                    f"{info.get('name', code)}{' (후보)' if self._is_candidate_entity(code) else ''}",
                    display_status(status),
                    f"{float(state.get('news_score', 0.0) or 0.0):+.0f}",
                    display_regime(state.get("dart_risk_level", "normal") or "normal"),
                    f"{float(state.get('theme_score', 0.0) or 0.0):.0f}",
                    display_regime(state.get("macro_regime", "neutral") or "neutral"),
                    display_source_health(state.get("source_health", "") or ""),
                    display_action_policy(state.get("action_policy", "allow") or "allow"),
                    f"{float(state.get('size_multiplier', 1.0) or 1.0):.2f}",
                    display_exit_policy(state.get("exit_policy", "none") or "none"),
                    str(state.get("last_event_id", "") or ""),
                    updated_at.strftime("%H:%M:%S") if isinstance(updated_at, datetime.datetime) else "",
                    str(state.get("last_alert", "") or ""),
                ]
                for col, value in enumerate(values):
                    item = table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(str(value))
                        table.setItem(row, col, item)
                    else:
                        item.setText(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._market_intel_row_to_code[row] = code
        finally:
            table.setUpdatesEnabled(True)
        self._market_intel_dirty_codes = set()
        self._render_selected_market_intel_detail()

    def _selected_market_intel_code(self) -> str:
        table = getattr(self, "market_intel_table", None)
        if table is None:
            return ""
        selected = table.selectedItems()
        if not selected:
            return ""
        return str(getattr(self, "_market_intel_row_to_code", {}).get(selected[0].row(), "") or "")

    def _render_selected_market_intel_detail(self):
        panel = getattr(self, "market_intel_detail_panel", None)
        if panel is None:
            return
        code = self._selected_market_intel_code()
        if not code:
            panel.setPlainText("선택된 종목이 없습니다.")
            return
        info = self._market_intel_entity(code)
        state = self._ensure_market_intel_state(info)
        ai_summary = state.get("ai_summary", {}) if isinstance(state.get("ai_summary"), dict) else {}
        headlines = [f"- {item.get('title', '')}" for item in state.get("news_headlines", [])[:5]]
        disclosures = [f"- {item.get('title', '')}" for item in state.get("dart_events", [])[:5]]
        sources = state.get("sources", {}) if isinstance(state.get("sources"), dict) else {}
        detail = [
            f"종목: {info.get('name', code)} ({code})",
            f"인텔리전스 상태: {display_status(state.get('status', state.get('intel_status', 'idle')))}",
            f"뉴스 점수: {state.get('news_score', 0.0):+.0f}",
            f"뉴스 톤: {display_news_sentiment(state.get('news_sentiment', 'neutral'))}",
            f"헤드라인 증가 속도: {state.get('headline_velocity', 0)}",
            f"관련도 점수: {state.get('relevance_score', 0.0):.2f}",
            f"공시 위험도: {display_regime(state.get('dart_risk_level', 'normal'))}",
            f"이벤트 유형: {display_event_type(state.get('event_type', ''))}",
            f"이벤트 심각도: {display_event_severity(state.get('event_severity', 'low'))}",
            f"테마 점수: {state.get('theme_score', 0.0):.0f}",
            f"테마 키워드: {', '.join(state.get('theme_keywords', []) or [])}",
            f"매크로 상태: {display_regime(state.get('macro_regime', 'neutral'))}",
            f"소스 상태: {display_source_health(state.get('source_health', ''))}",
            f"자동매매 정책: {display_action_policy(state.get('action_policy', 'allow'))}",
            f"수량 배수: {state.get('size_multiplier', 1.0):.2f}",
            f"청산 정책: {display_exit_policy(state.get('exit_policy', 'none'))}",
            f"포트폴리오 예산 배수: {state.get('portfolio_budget_scale', 1.0):.2f}",
            f"마지막 이벤트 ID: {state.get('last_event_id', '')}",
            f"브리핑 요약: {state.get('briefing_summary', '')}",
            f"AI 요약: {ai_summary.get('summary', '') if isinstance(ai_summary, dict) else ''}",
            "소스 상태:",
            *[
                f"- {display_source_name(source)}: {display_status(row.get('status', 'idle'))} ({row.get('error', '')})"
                for source, row in sources.items()
            ],
            "헤드라인:",
            *headlines,
            "공시:",
            *disclosures,
        ]
        panel.setPlainText("\n".join(detail))

    def _on_market_intel_selection_changed(self):
        self._render_selected_market_intel_detail()

    def _on_market_intel_refresh_selected(self):
        code = self._selected_market_intel_code()
        if not code:
            self.log("[시장인텔리전스] 새로고침 대상 종목이 선택되지 않았습니다.")
            return
        self.log(f"[시장인텔리전스] 선택 종목 새로고침: {code}")
        self._request_market_intelligence_refresh_batch([code], reason="manual_selected", force=True)

    def _on_market_intel_refresh_all(self):
        codes = list(dict.fromkeys(list(self.universe.keys()) + list(getattr(self, "_active_market_candidates", {}).keys())))
        if not codes:
            self.log("[시장인텔리전스] 새로고침 대상 종목이 없습니다.")
            return
        self.log(f"[시장인텔리전스] 전체 새로고침: {len(codes)}개 종목")
        self._request_market_intelligence_refresh_batch(codes, reason="manual_all", force=True)

    @staticmethod
    def _market_replay_payload(record: Dict[str, Any]) -> Dict[str, Any]:
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        if isinstance(payload, dict):
            return payload
        raw_ref = record.get("raw_ref", "") if isinstance(record, dict) else ""
        if isinstance(raw_ref, dict):
            return raw_ref
        if isinstance(raw_ref, str) and raw_ref:
            try:
                parsed = json.loads(raw_ref)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    @staticmethod
    def _market_replay_parse_ts(value: Any) -> Optional[datetime.datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.datetime.fromisoformat(text)
        except ValueError:
            return None

    def _read_jsonl_tail_records(self, path_value: Any, limit: int = 200) -> List[Dict[str, Any]]:
        path = Path(str(path_value or "")).expanduser()
        if not path.exists():
            return []
        tail = deque(maxlen=max(1, int(limit)))
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = str(line or "").strip()
                    if text:
                        tail.append(text)
        except Exception:
            return []
        records: List[Dict[str, Any]] = []
        for text in tail:
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records

    def _collect_market_replay_scope_state(self, event_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        market_mode = "unknown"
        portfolio_budget_scale = 1.0
        aggregate_news_risk = 0.0
        sector_blocks: Dict[str, int] = {}
        hot_themes: Dict[str, float] = {}
        latest_event_ts = ""
        for record in event_records:
            scope = str(record.get("scope", "symbol") or "symbol")
            event_type = str(record.get("event_type", "") or "")
            payload = self._market_replay_payload(record)
            latest_event_ts = str(record.get("ts", latest_event_ts) or latest_event_ts)
            if scope == "market":
                mode = str(payload.get("macro_regime", "") or "")
                if mode:
                    market_mode = mode
                portfolio_budget_scale = float(payload.get("portfolio_budget_scale", portfolio_budget_scale) or portfolio_budget_scale)
                aggregate_news_risk = float(payload.get("aggregate_news_risk", aggregate_news_risk) or aggregate_news_risk)
            elif scope == "sector":
                sector = str(payload.get("sector", "") or record.get("symbol", "") or "").strip()
                if not sector:
                    continue
                if event_type == "sector_block":
                    sector_blocks[sector] = int(payload.get("count", sector_blocks.get(sector, 0)) or sector_blocks.get(sector, 0))
                elif event_type == "sector_block_release":
                    sector_blocks.pop(sector, None)
            elif scope == "theme":
                theme = str(payload.get("theme", "") or record.get("symbol", "") or "").strip()
                if not theme:
                    continue
                if event_type == "theme_heat":
                    hot_themes[theme] = float(payload.get("theme_score", record.get("score", 0.0)) or 0.0)
                elif event_type == "theme_cooldown":
                    hot_themes.pop(theme, None)
        return {
            "market_mode": market_mode,
            "portfolio_budget_scale": portfolio_budget_scale,
            "aggregate_news_risk": aggregate_news_risk,
            "sector_blocks": sector_blocks,
            "hot_themes": hot_themes,
            "latest_event_ts": latest_event_ts,
        }

    def _market_replay_filters(self) -> Dict[str, Any]:
        symbol_filter = str(getattr(getattr(self, "input_market_replay_symbol_filter", None), "text", lambda: "")()).strip().lower()
        scope_filter = combo_value(getattr(self, "combo_market_replay_scope", None), "all").strip().lower()
        audit_filter = combo_value(getattr(self, "combo_market_replay_allowed", None), "all").strip().lower()
        limit = int(getattr(getattr(self, "spin_market_replay_limit", None), "value", lambda: 100)() or 100)
        return {
            "symbol_filter": symbol_filter,
            "scope_filter": scope_filter,
            "audit_filter": audit_filter,
            "limit": max(20, limit),
        }

    def _filter_market_replay_event_records(self, records: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        symbol_filter = str(filters.get("symbol_filter", "") or "")
        scope_filter = str(filters.get("scope_filter", "all") or "all")
        limit = int(filters.get("limit", 100) or 100)
        filtered: List[Dict[str, Any]] = []
        for record in reversed(records):
            scope = str(record.get("scope", "symbol") or "symbol").lower()
            payload = self._market_replay_payload(record)
            haystack = " ".join(
                [
                    str(record.get("symbol", "") or ""),
                    str(record.get("source", "") or ""),
                    str(record.get("event_type", "") or ""),
                    str(record.get("summary", "") or ""),
                    str(payload.get("sector", "") or ""),
                    str(payload.get("theme", "") or ""),
                    str(payload.get("action_policy", "") or ""),
                    str(payload.get("exit_policy", "") or ""),
                ]
            ).lower()
            if scope_filter != "all" and scope != scope_filter:
                continue
            if symbol_filter and symbol_filter not in haystack:
                continue
            filtered.append(record)
            if len(filtered) >= limit:
                break
        return filtered

    def _filter_market_replay_audit_records(self, records: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        symbol_filter = str(filters.get("symbol_filter", "") or "")
        audit_filter = str(filters.get("audit_filter", "all") or "all")
        limit = int(filters.get("limit", 100) or 100)
        filtered: List[Dict[str, Any]] = []
        for record in reversed(records):
            allowed = bool(record.get("allowed", False))
            haystack = " ".join(
                [
                    str(record.get("symbol", "") or ""),
                    str(record.get("name", "") or ""),
                    str(record.get("reason", "") or ""),
                    str(record.get("action_policy", "") or ""),
                    str(record.get("exit_policy", "") or ""),
                    str(record.get("market_intel", {}).get("last_event_id", "") if isinstance(record.get("market_intel"), dict) else ""),
                ]
            ).lower()
            if audit_filter == "allowed" and not allowed:
                continue
            if audit_filter == "blocked" and allowed:
                continue
            if symbol_filter and symbol_filter not in haystack:
                continue
            filtered.append(record)
            if len(filtered) >= limit:
                break
        return filtered

    def _build_market_replay_summary(
        self,
        event_records: List[Dict[str, Any]],
        audit_records: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> str:
        scope_state = self._collect_market_replay_scope_state(event_records)
        scope_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}
        for record in event_records:
            scope = str(record.get("scope", "symbol") or "symbol")
            source = str(record.get("source", "") or "unknown")
            scope_counts[scope] = scope_counts.get(scope, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
        allowed_count = sum(1 for record in audit_records if bool(record.get("allowed", False)))
        blocked_count = len(audit_records) - allowed_count
        reason_counts: Dict[str, int] = {}
        for record in audit_records:
            reason = str(record.get("reason", "") or "")
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        top_reasons = ", ".join(
            f"{reason}({count})" for reason, count in sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        ) or "-"
        sector_text = ", ".join(
            f"{sector}({count})" for sector, count in sorted(scope_state.get("sector_blocks", {}).items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        ) or "-"
        theme_text = ", ".join(
            f"{theme}({score:.0f})" for theme, score in sorted(scope_state.get("hot_themes", {}).items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        ) or "-"
        audit_label = {"all": "전체", "allowed": "허용만", "blocked": "차단만"}.get(
            str(filters.get("audit_filter", "all") or "all"),
            str(filters.get("audit_filter", "all") or "all"),
        )
        return "\n".join(
            [
                f"이벤트 로그: {getattr(Config, 'MARKET_INTELLIGENCE_EVENTS_FILE', 'data/market_intelligence_events.jsonl')}",
                f"감사 로그: {getattr(Config, 'MARKET_INTELLIGENCE_DECISION_AUDIT_FILE', 'data/decision_audit.jsonl')}",
                f"필터: 검색='{filters.get('symbol_filter', '')}', 범위={display_replay_scope(filters.get('scope_filter', 'all'))}, 감사={audit_label}, 개수={filters.get('limit', 100)}",
                f"최근 이벤트 {len(event_records)}건, 최근 감사 {len(audit_records)}건",
                f"범위 분포: {', '.join(f'{display_replay_scope(scope)}={count}' for scope, count in sorted(scope_counts.items())) or '-'}",
                f"소스 분포: {', '.join(f'{display_source_name(source)}={count}' for source, count in sorted(source_counts.items())) or '-'}",
                f"시장 리스크: 상태={display_regime(scope_state.get('market_mode', 'unknown'))}, 예산 배수={float(scope_state.get('portfolio_budget_scale', 1.0)):.2f}, 누적 뉴스 위험={float(scope_state.get('aggregate_news_risk', 0.0)):+.1f}",
                f"활성 섹터 차단: {sector_text}",
                f"활성 테마 과열: {theme_text}",
                f"감사 집계: 허용={allowed_count}, 차단={blocked_count}",
                f"상위 사유: {top_reasons}",
            ]
        )

    def _schedule_market_replay_refresh(self, force: bool = False):
        if force:
            self._market_replay_refresh_scheduled = False
            self._refresh_market_replay_dashboard()
            return
        if getattr(self, "_market_replay_refresh_scheduled", False):
            return
        self._market_replay_refresh_scheduled = True
        QTimer.singleShot(300, self._run_scheduled_market_replay_refresh)

    def _run_scheduled_market_replay_refresh(self):
        self._market_replay_refresh_scheduled = False
        self._refresh_market_replay_dashboard()

    def _refresh_market_replay_dashboard(self):
        summary_panel = getattr(self, "market_replay_summary_panel", None)
        event_table = getattr(self, "market_replay_event_table", None)
        audit_table = getattr(self, "market_replay_audit_table", None)
        if summary_panel is None or event_table is None or audit_table is None:
            return
        filters = self._market_replay_filters()
        scan_limit = max(300, int(filters.get("limit", 100)) * 5)
        raw_event_records = self._read_jsonl_tail_records(getattr(Config, "MARKET_INTELLIGENCE_EVENTS_FILE", ""), limit=scan_limit)
        raw_audit_records = self._read_jsonl_tail_records(getattr(Config, "MARKET_INTELLIGENCE_DECISION_AUDIT_FILE", ""), limit=scan_limit)
        event_records = self._filter_market_replay_event_records(raw_event_records, filters)
        audit_records = self._filter_market_replay_audit_records(raw_audit_records, filters)
        self._market_replay_event_records = event_records
        self._market_replay_audit_records = audit_records
        self._market_replay_event_row_to_index = {}
        self._market_replay_audit_row_to_index = {}
        summary_panel.setPlainText(self._build_market_replay_summary(raw_event_records, raw_audit_records, filters))

        event_table.setUpdatesEnabled(False)
        try:
            event_table.setRowCount(len(event_records))
            for row, record in enumerate(event_records):
                payload = self._market_replay_payload(record)
                values = [
                    str(record.get("ts", "") or ""),
                    display_replay_scope(record.get("scope", "symbol") or "symbol"),
                    str(record.get("symbol", "") or payload.get("sector", "") or payload.get("theme", "") or ""),
                    display_source_name(record.get("source", "") or ""),
                    display_event_type(record.get("event_type", "") or ""),
                    f"{float(record.get('score', 0.0) or 0.0):+.1f}",
                    display_action_policy(payload.get("action_policy", "") or ""),
                    display_exit_policy(payload.get("exit_policy", "") or ""),
                    display_yes_no(bool(record.get("blocking", False)), "예", ""),
                    str(record.get("summary", "") or ""),
                ]
                for col, value in enumerate(values):
                    item = event_table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(str(value))
                        event_table.setItem(row, col, item)
                    else:
                        item.setText(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col < 9 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._market_replay_event_row_to_index[row] = row
        finally:
            event_table.setUpdatesEnabled(True)

        audit_table.setUpdatesEnabled(False)
        try:
            audit_table.setRowCount(len(audit_records))
            for row, record in enumerate(audit_records):
                market_intel = record.get("market_intel", {}) if isinstance(record.get("market_intel"), dict) else {}
                values = [
                    str(record.get("ts", "") or ""),
                    str(record.get("symbol", "") or ""),
                    display_allowed(bool(record.get("allowed", False))),
                    str(record.get("reason", "") or ""),
                    str(record.get("quantity", 0) or 0),
                    display_action_policy(record.get("action_policy", "") or ""),
                    display_exit_policy(record.get("exit_policy", "") or ""),
                    display_status(market_intel.get("status", "") or ""),
                    str(market_intel.get("last_event_id", "") or ""),
                ]
                for col, value in enumerate(values):
                    item = audit_table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(str(value))
                        audit_table.setItem(row, col, item)
                    else:
                        item.setText(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col != 3 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._market_replay_audit_row_to_index[row] = row
        finally:
            audit_table.setUpdatesEnabled(True)

        self._render_selected_market_replay_event_detail()
        self._render_selected_market_replay_audit_detail()

    def _selected_market_replay_event_record(self) -> Dict[str, Any]:
        table = getattr(self, "market_replay_event_table", None)
        if table is None:
            return {}
        selected = table.selectedItems()
        if not selected:
            return {}
        record_index = getattr(self, "_market_replay_event_row_to_index", {}).get(selected[0].row(), -1)
        records = getattr(self, "_market_replay_event_records", [])
        if not isinstance(records, list) or not (0 <= int(record_index) < len(records)):
            return {}
        return records[int(record_index)]

    def _selected_market_replay_audit_record(self) -> Dict[str, Any]:
        table = getattr(self, "market_replay_audit_table", None)
        if table is None:
            return {}
        selected = table.selectedItems()
        if not selected:
            return {}
        record_index = getattr(self, "_market_replay_audit_row_to_index", {}).get(selected[0].row(), -1)
        records = getattr(self, "_market_replay_audit_records", [])
        if not isinstance(records, list) or not (0 <= int(record_index) < len(records)):
            return {}
        return records[int(record_index)]

    def _render_selected_market_replay_event_detail(self):
        panel = getattr(self, "market_replay_event_detail_panel", None)
        if panel is None:
            return
        record = self._selected_market_replay_event_record()
        if not record:
            panel.setPlainText("선택된 이벤트가 없습니다.")
            return
        payload = self._market_replay_payload(record)
        detail = [
            f"시각: {record.get('ts', '')}",
            f"범위: {display_replay_scope(record.get('scope', 'symbol'))}",
            f"대상: {record.get('symbol', '')}",
            f"소스: {display_source_name(record.get('source', ''))}",
            f"이벤트 유형: {display_event_type(record.get('event_type', ''))}",
            f"점수: {float(record.get('score', 0.0) or 0.0):+.1f}",
            f"차단 여부: {display_yes_no(bool(record.get('blocking', False)))}",
            f"이벤트 ID: {record.get('event_id', '')}",
            f"요약: {record.get('summary', '')}",
            "원본 payload:",
            json.dumps(payload, ensure_ascii=False, indent=2) if payload else "{}",
        ]
        panel.setPlainText("\n".join(detail))

    def _render_selected_market_replay_audit_detail(self):
        panel = getattr(self, "market_replay_audit_detail_panel", None)
        if panel is None:
            return
        record = self._selected_market_replay_audit_record()
        if not record:
            panel.setPlainText("선택된 감사 로그가 없습니다.")
            return
        detail = [
            f"시각: {record.get('ts', '')}",
            f"종목코드: {record.get('symbol', '')}",
            f"종목명: {record.get('name', '')}",
            f"허용 여부: {display_allowed(bool(record.get('allowed', False)))}",
            f"사유: {record.get('reason', '')}",
            f"수량: {record.get('quantity', 0)}",
            f"자동매매 정책: {display_action_policy(record.get('action_policy', ''))}",
            f"청산 정책: {display_exit_policy(record.get('exit_policy', ''))}",
            "원본 snapshot:",
            json.dumps(record, ensure_ascii=False, indent=2),
        ]
        panel.setPlainText("\n".join(detail))

    def _on_market_replay_event_selection_changed(self):
        self._render_selected_market_replay_event_detail()

    def _on_market_replay_audit_selection_changed(self):
        self._render_selected_market_replay_audit_detail()

    def _on_market_replay_refresh(self):
        self._schedule_market_replay_refresh(force=True)

    def _create_market_replay_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_row = QHBoxLayout()
        btn_refresh = QPushButton("로그 새로고침")
        btn_refresh.clicked.connect(self._on_market_replay_refresh)
        control_row.addWidget(btn_refresh)

        self.input_market_replay_symbol_filter = QLineEdit()
        self.input_market_replay_symbol_filter.setPlaceholderText("종목코드, 업종, 테마, 사유로 검색")
        self.input_market_replay_symbol_filter.textChanged.connect(self._on_market_replay_refresh)
        control_row.addWidget(self.input_market_replay_symbol_filter)

        self.combo_market_replay_scope = NoScrollComboBox()
        populate_combo(self.combo_market_replay_scope, REPLAY_SCOPE_CHOICES, "all")
        self.combo_market_replay_scope.currentTextChanged.connect(self._on_market_replay_refresh)
        control_row.addWidget(QLabel("범위"))
        control_row.addWidget(self.combo_market_replay_scope)

        self.combo_market_replay_allowed = NoScrollComboBox()
        populate_combo(self.combo_market_replay_allowed, REPLAY_AUDIT_CHOICES, "all")
        self.combo_market_replay_allowed.currentTextChanged.connect(self._on_market_replay_refresh)
        control_row.addWidget(QLabel("감사"))
        control_row.addWidget(self.combo_market_replay_allowed)

        self.spin_market_replay_limit = NoScrollSpinBox()
        self.spin_market_replay_limit.setRange(20, 500)
        self.spin_market_replay_limit.setValue(100)
        self.spin_market_replay_limit.valueChanged.connect(self._on_market_replay_refresh)
        control_row.addWidget(QLabel("표시 개수"))
        control_row.addWidget(self.spin_market_replay_limit)
        control_row.addStretch()
        layout.addLayout(control_row)

        summary_group = QGroupBox("📼 리플레이 요약")
        summary_layout = QVBoxLayout(summary_group)
        self.market_replay_summary_panel = QPlainTextEdit()
        self.market_replay_summary_panel.setReadOnly(True)
        self.market_replay_summary_panel.setMaximumHeight(220)
        self.market_replay_summary_panel.setPlainText("로그를 불러오는 중입니다.")
        summary_layout.addWidget(self.market_replay_summary_panel)
        layout.addWidget(summary_group)

        body_layout = QGridLayout()

        event_group = QGroupBox("이벤트 로그")
        event_layout = QVBoxLayout(event_group)
        self.market_replay_event_table = QTableWidget()
        event_cols = ["시각", "범위", "대상", "소스", "유형", "점수", "정책", "청산", "차단", "요약"]
        self.market_replay_event_table.setColumnCount(len(event_cols))
        self.market_replay_event_table.setHorizontalHeaderLabels(event_cols)
        self.market_replay_event_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.market_replay_event_table.itemSelectionChanged.connect(self._on_market_replay_event_selection_changed)
        event_header = self.market_replay_event_table.horizontalHeader()
        if event_header is not None:
            from PyQt6.QtWidgets import QHeaderView

            event_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        event_layout.addWidget(self.market_replay_event_table)
        self.market_replay_event_detail_panel = QPlainTextEdit()
        self.market_replay_event_detail_panel.setReadOnly(True)
        self.market_replay_event_detail_panel.setMaximumHeight(220)
        self.market_replay_event_detail_panel.setPlainText("선택된 이벤트가 없습니다.")
        event_layout.addWidget(self.market_replay_event_detail_panel)
        body_layout.addWidget(event_group, 0, 0)

        audit_group = QGroupBox("결정 감사")
        audit_layout = QVBoxLayout(audit_group)
        self.market_replay_audit_table = QTableWidget()
        audit_cols = ["시각", "종목", "허용 여부", "사유", "수량", "정책", "청산", "상태", "마지막 이벤트"]
        self.market_replay_audit_table.setColumnCount(len(audit_cols))
        self.market_replay_audit_table.setHorizontalHeaderLabels(audit_cols)
        self.market_replay_audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.market_replay_audit_table.itemSelectionChanged.connect(self._on_market_replay_audit_selection_changed)
        audit_header = self.market_replay_audit_table.horizontalHeader()
        if audit_header is not None:
            from PyQt6.QtWidgets import QHeaderView

            audit_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        audit_layout.addWidget(self.market_replay_audit_table)
        self.market_replay_audit_detail_panel = QPlainTextEdit()
        self.market_replay_audit_detail_panel.setReadOnly(True)
        self.market_replay_audit_detail_panel.setMaximumHeight(220)
        self.market_replay_audit_detail_panel.setPlainText("선택된 감사 로그가 없습니다.")
        audit_layout.addWidget(self.market_replay_audit_detail_panel)
        body_layout.addWidget(audit_group, 0, 1)

        layout.addLayout(body_layout)
        self._schedule_market_replay_refresh(force=True)
        return widget

    def _create_market_intelligence_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        source_group = QGroupBox("📡 소스 상태")
        source_layout = QGridLayout(source_group)
        for idx, source in enumerate(self.MARKET_INTEL_SOURCE_NAMES):
            label = QLabel(f"{display_source_name(source)}: {display_status('idle')}")
            setattr(self, f"lbl_market_source_{source}", label)
            source_layout.addWidget(label, idx // 3, idx % 3)
        layout.addWidget(source_group)

        control_row = QHBoxLayout()
        btn_refresh_selected = QPushButton("선택 종목 새로고침")
        btn_refresh_selected.clicked.connect(self._on_market_intel_refresh_selected)
        control_row.addWidget(btn_refresh_selected)
        btn_refresh_all = QPushButton("전체 새로고침")
        btn_refresh_all.clicked.connect(self._on_market_intel_refresh_all)
        control_row.addWidget(btn_refresh_all)
        control_row.addStretch()
        layout.addLayout(control_row)

        self.market_intel_table = QTableWidget()
        cols = [
            "종목명",
            "인텔리전스 상태",
            "뉴스 점수",
            "공시 위험도",
            "테마 점수",
            "매크로 상태",
            "소스 상태",
            "자동매매 정책",
            "수량 배수",
            "청산 정책",
            "마지막 이벤트 ID",
            "최근 갱신",
            "최근 알림",
        ]
        self.market_intel_table.setColumnCount(len(cols))
        self.market_intel_table.setHorizontalHeaderLabels(cols)
        header = self.market_intel_table.horizontalHeader()
        if header is not None:
            from PyQt6.QtWidgets import QHeaderView

            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.market_intel_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.market_intel_table.itemSelectionChanged.connect(self._on_market_intel_selection_changed)
        layout.addWidget(self.market_intel_table)

        self.market_intel_detail_panel = QPlainTextEdit()
        self.market_intel_detail_panel.setReadOnly(True)
        self.market_intel_detail_panel.setMaximumHeight(220)
        self.market_intel_detail_panel.setPlainText("선택된 종목이 없습니다.")
        layout.addWidget(self.market_intel_detail_panel)

        return widget

    def _create_market_intelligence_settings_tab(self):
        from PyQt6.QtWidgets import QCheckBox

        cfg = self._market_intelligence_config()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        body = QVBoxLayout(content)

        intro = QLabel(
            "시장 인텔리전스는 뉴스, 공시, 검색량, 매크로 데이터를 읽어 자동매매를 보조합니다. "
            "초보자는 먼저 '기본 사용'과 '점수/차단 기준'만 확인해도 충분합니다."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b949e;")
        body.addWidget(intro)

        basic_group = QGroupBox("기본 사용")
        basic_form = QFormLayout(basic_group)
        self.chk_market_intel_enabled = QCheckBox("시장 인텔리전스 사용")
        self.chk_market_intel_enabled.setChecked(bool(cfg.get("enabled", True)))
        basic_form.addRow("", self.chk_market_intel_enabled)
        body.addWidget(basic_group)

        source_group = QGroupBox("데이터 소스")
        source_form = QFormLayout(source_group)
        self.chk_market_news = QCheckBox("NAVER 뉴스 사용")
        self.chk_market_news.setChecked(bool(cfg.get("providers", {}).get("news", True)))
        self.chk_market_dart = QCheckBox("OpenDART 공시 사용")
        self.chk_market_dart.setChecked(bool(cfg.get("providers", {}).get("dart", True)))
        self.chk_market_datalab = QCheckBox("NAVER 데이터랩 사용")
        self.chk_market_datalab.setChecked(bool(cfg.get("providers", {}).get("datalab", True)))
        self.chk_market_macro = QCheckBox("FRED 매크로 데이터 사용")
        self.chk_market_macro.setChecked(bool(cfg.get("providers", {}).get("macro", True)))
        provider_row = QHBoxLayout()
        provider_row.addWidget(self.chk_market_news)
        provider_row.addWidget(self.chk_market_dart)
        provider_row.addWidget(self.chk_market_datalab)
        provider_row.addWidget(self.chk_market_macro)
        source_form.addRow("사용 소스:", provider_row)

        self.input_naver_client_id = QLineEdit()
        self.input_naver_client_id.setPlaceholderText("NAVER Client ID")
        source_form.addRow("NAVER Client ID:", self.input_naver_client_id)
        self.input_naver_client_secret = QLineEdit()
        self.input_naver_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_naver_client_secret.setPlaceholderText("NAVER Client Secret")
        source_form.addRow("NAVER Client Secret:", self.input_naver_client_secret)

        self.input_dart_api_key = QLineEdit()
        self.input_dart_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_dart_api_key.setPlaceholderText("OPEN_DART_API_KEY")
        source_form.addRow("DART API Key:", self.input_dart_api_key)

        self.input_fred_api_key = QLineEdit()
        self.input_fred_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_fred_api_key.setPlaceholderText("FRED_API_KEY")
        source_form.addRow("FRED API Key:", self.input_fred_api_key)
        body.addWidget(source_group)

        refresh_group = QGroupBox("갱신 주기")
        refresh_form = QFormLayout(refresh_group)
        self.spin_market_news_refresh = NoScrollSpinBox()
        self.spin_market_news_refresh.setRange(10, 600)
        self.spin_market_news_refresh.setValue(int(cfg.get("refresh_sec", {}).get("news", 60)))
        refresh_form.addRow("뉴스/공시 갱신(초):", self.spin_market_news_refresh)
        self.spin_market_macro_refresh = NoScrollSpinBox()
        self.spin_market_macro_refresh.setRange(30, 1800)
        self.spin_market_macro_refresh.setValue(int(cfg.get("refresh_sec", {}).get("macro", 300)))
        refresh_form.addRow("매크로 갱신(초):", self.spin_market_macro_refresh)
        body.addWidget(refresh_group)

        scoring_group = QGroupBox("점수/차단 기준")
        scoring_form = QFormLayout(scoring_group)
        self.spin_market_news_block = NoScrollSpinBox()
        self.spin_market_news_block.setRange(10, 100)
        self.spin_market_news_block.setValue(abs(int(cfg.get("scoring", {}).get("news_block_threshold", -60))))
        scoring_form.addRow("신규 진입 차단 점수:", self.spin_market_news_block)
        self.spin_market_news_boost = NoScrollSpinBox()
        self.spin_market_news_boost.setRange(10, 100)
        self.spin_market_news_boost.setValue(abs(int(cfg.get("scoring", {}).get("news_boost_threshold", 60))))
        scoring_form.addRow("우선순위 강화 점수:", self.spin_market_news_boost)
        body.addWidget(scoring_group)

        ai_group = QGroupBox("AI 요약")
        ai_form = QFormLayout(ai_group)
        self.chk_market_ai_enabled = QCheckBox("AI 요약 사용")
        self.chk_market_ai_enabled.setChecked(bool(cfg.get("ai", {}).get("enabled", False)))
        ai_form.addRow("", self.chk_market_ai_enabled)
        self.combo_market_ai_provider = NoScrollComboBox()
        populate_combo(self.combo_market_ai_provider, AI_PROVIDER_CHOICES, str(cfg.get("ai", {}).get("provider", "gemini")))
        ai_form.addRow("AI 제공사:", self.combo_market_ai_provider)
        self.input_market_ai_model = QLineEdit(str(cfg.get("ai", {}).get("model", "gemini-2.5-flash-lite")))
        self.input_market_ai_model.setPlaceholderText("예: gemini-2.5-flash-lite")
        ai_form.addRow("모델 이름:", self.input_market_ai_model)
        self.input_ai_api_key = QLineEdit()
        self.input_ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_ai_api_key.setPlaceholderText("AI_API_KEY")
        ai_form.addRow("AI API Key:", self.input_ai_api_key)

        self.spin_market_ai_daily_calls = NoScrollSpinBox()
        self.spin_market_ai_daily_calls.setRange(1, 500)
        self.spin_market_ai_daily_calls.setValue(int(cfg.get("ai", {}).get("max_calls_per_day", 30)))
        ai_form.addRow("하루 최대 호출 수:", self.spin_market_ai_daily_calls)
        self.spin_market_ai_symbol_calls = NoScrollSpinBox()
        self.spin_market_ai_symbol_calls.setRange(1, 50)
        self.spin_market_ai_symbol_calls.setValue(int(cfg.get("ai", {}).get("max_calls_per_symbol", 3)))
        ai_form.addRow("종목당 최대 호출 수:", self.spin_market_ai_symbol_calls)
        self.spin_market_ai_budget = NoScrollSpinBox()
        self.spin_market_ai_budget.setRange(100, 100000)
        self.spin_market_ai_budget.setValue(int(cfg.get("ai", {}).get("daily_budget_krw", 1000)))
        ai_form.addRow("하루 예산(원):", self.spin_market_ai_budget)
        body.addWidget(ai_group)

        note_group = QGroupBox("설명/주의사항")
        note_layout = QVBoxLayout(note_group)
        note = QLabel(
            "1. 악재 뉴스나 공시는 신규 진입을 막거나 기존 포지션 청산 정책을 강화할 수 있습니다.\n"
            "2. AI 요약은 보조 수단입니다. 결정론적 규칙이 항상 우선합니다.\n"
            "3. 실거래 전에는 API 키와 로그 저장 위치를 반드시 점검하세요."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #d29922;")
        note_layout.addWidget(note)
        body.addWidget(note_group)

        body.addStretch()
        return widget
