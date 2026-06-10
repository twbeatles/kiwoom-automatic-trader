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


class MarketIntelScoringPolicyMixin(TraderMixinBase):
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

        if status in {"error", "stale", "refreshing", "idle", "disabled_by_missing_credentials"}:
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
