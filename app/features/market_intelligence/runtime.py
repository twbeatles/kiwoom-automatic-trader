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


class MarketIntelRuntimeMixin(TraderMixinBase):
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
                macro_status = "disabled_by_missing_credentials"
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
                        "status": "idle" if news_available else ("disabled" if not news_enabled else "disabled_by_missing_credentials"),
                        "error": "" if news_available else ("provider_disabled" if not news_enabled else "api_key_missing"),
                        "updated_at": datetime.datetime.now(),
                        "count": 0,
                    },
                    "dart": {
                        "status": "idle" if dart_available else ("disabled" if not dart_enabled else "disabled_by_missing_credentials"),
                        "error": "" if dart_available else ("provider_disabled" if not dart_enabled else "api_key_missing"),
                        "updated_at": datetime.datetime.now(),
                        "count": 0,
                    },
                    "datalab": {
                        "status": "idle" if datalab_available else ("disabled" if not datalab_enabled else "disabled_by_missing_credentials"),
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
                _track_source("news", "disabled_by_missing_credentials", "api_key_missing")
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
                _track_source("dart", "disabled_by_missing_credentials", "api_key_missing")
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
                _track_source("datalab", "disabled_by_missing_credentials", "api_key_missing")
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
        now_dt = datetime.datetime.now()
        for code in selected:
            info = self._market_intel_entity(code)
            if not info:
                continue
            state = self._ensure_market_intel_state(info)
            state["status"] = "refreshing"
            state["intel_status"] = "refreshing"
            state["intel_error"] = str(reason or "refreshing")
            state["updated_at"] = now_dt
            info["external_status"] = "refreshing"
            info["external_error"] = str(reason or "refreshing")
            self._market_intel_dirty_codes.add(code)
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
