"""Market intelligence mixin for KiwoomProTrader."""

from __future__ import annotations

import copy
import datetime
import html
import json
import re
import time
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
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
            merged = self._default_market_intel_state()
            merged.update(state)
            state = merged
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
            text = f"{source.upper()}: {sources[source]['status']}"
            if error:
                text = f"{text} ({error})"
            label.setText(text)

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

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
            cfg["ai"]["provider"] = str(self.combo_market_ai_provider.currentText() or "gemini").lower()
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
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        velocity = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            title = self._clean_text(raw.get("title"))
            if not title:
                continue
            lowered = title.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            item = dict(raw)
            item["title"] = title
            unique_items.append(item)
            if any(keyword.lower() in lowered for keyword in getattr(Config, "MARKET_INTELLIGENCE_POSITIVE_KEYWORDS", set())):
                positive_hits += 1
            if any(keyword.lower() in lowered for keyword in getattr(Config, "MARKET_INTELLIGENCE_NEGATIVE_KEYWORDS", set())):
                negative_hits += 1
            published_at = item.get("published_at")
            if isinstance(published_at, datetime.datetime):
                published = published_at.astimezone(now.tzinfo) if published_at.tzinfo else published_at.replace(tzinfo=now.tzinfo)
                if (now - published) <= datetime.timedelta(minutes=5):
                    velocity += 1
        score = max(-100, min(100, positive_hits * 20 - negative_hits * 25))
        sentiment = "neutral"
        if score >= 20:
            sentiment = "bullish"
        elif score <= -20:
            sentiment = "bearish"
        return {
            "headlines": unique_items[:10],
            "score": float(score),
            "sentiment": sentiment,
            "headline_velocity": velocity,
        }

    def _score_dart_events(self, disclosures: List[Dict[str, Any]]) -> Dict[str, Any]:
        normalized: List[Dict[str, Any]] = []
        risk_level = "normal"
        score = 0.0
        high_risk = False
        for row in disclosures:
            if not isinstance(row, dict):
                continue
            title = self._clean_text(row.get("report_nm") or row.get("report_name") or row.get("rpt_nm"))
            if not title:
                continue
            lowered = title.lower()
            tags: List[str] = []
            for keyword in getattr(Config, "MARKET_INTELLIGENCE_HIGH_RISK_KEYWORDS", set()):
                if keyword.lower() in lowered:
                    tags.append(keyword)
            if tags:
                high_risk = True
                risk_level = "high"
                score = min(score, -80.0)
            normalized.append(
                {
                    "title": title,
                    "receipt_no": str(row.get("rcept_no", "") or row.get("rcp_no", "") or ""),
                    "date": str(row.get("rcept_dt", "") or row.get("filing_date", "") or ""),
                    "tags": tags,
                }
            )
        return {"events": normalized[:10], "risk_level": risk_level, "score": score, "blocking": high_risk}

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

    def _build_briefing_summary(self, code: str, info: Dict[str, Any]) -> str:
        state = self._ensure_market_intel_state(info)
        name = str(info.get("name", code) or code)
        lines = [
            f"{name}: 뉴스 점수 {float(state.get('news_score', 0.0) or 0.0):+.0f}, 뉴스 심리 {state.get('news_sentiment', 'neutral')}.",
            f"공시 리스크는 {state.get('dart_risk_level', 'normal')}, 매크로 레짐은 {state.get('macro_regime', 'neutral')}입니다.",
            f"테마 점수는 {float(state.get('theme_score', 0.0) or 0.0):.0f}입니다.",
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
        news_score = float(state.get("news_score", 0.0) or 0.0)
        dart_risk = str(state.get("dart_risk_level", "normal") or "normal")
        stance = "neutral"
        action_hint = "watch_only"
        if dart_risk == "high" or news_score <= -60:
            stance = "bearish"
            action_hint = "block_entry"
        elif news_score >= 60:
            stance = "bullish"
            action_hint = "allow"
        summary = self._build_briefing_summary(code, info)
        if error:
            summary = f"{summary} (AI fallback: {error})"
        return {
            "summary": summary,
            "stance": stance,
            "risk_tags": [dart_risk] if dart_risk != "normal" else [],
            "confidence": 0.35,
            "action_hint": action_hint,
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
            return normalized
        except Exception as exc:
            self._set_market_intel_source_status("ai", "error", error=str(exc))
            summary = self._rules_based_ai_fallback(code, info, reason=reason, error=str(exc))
            state["ai_summary"] = summary
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
        raw_ref: str = "",
    ):
        record = {
            "ts": datetime.datetime.now().isoformat(),
            "scope": str(scope or "symbol"),
            "symbol": str(symbol or ""),
            "source": str(source or ""),
            "event_type": str(event_type or ""),
            "score": float(score or 0.0),
            "tags": list(tags or []),
            "summary": str(summary or ""),
            "blocking": bool(blocking),
            "raw_ref": str(raw_ref or ""),
        }
        path = Path(getattr(Config, "MARKET_INTELLIGENCE_EVENTS_FILE", "data/market_intelligence_events.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

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
        info = self.universe.get(code)
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
        state.update(
            {
                "news_score": news["score"],
                "news_sentiment": news["sentiment"],
                "news_headlines": news["headlines"],
                "headline_velocity": news["headline_velocity"],
                "dart_events": dart["events"],
                "dart_risk_level": dart["risk_level"],
                "dart_block_until": session_block_until if bool(dart.get("blocking", False)) else None,
                "theme_score": theme["score"],
                "theme_keywords": theme["keywords"],
                "macro_regime": macro["regime"],
                "intel_updated_at": now_dt,
                "intel_status": "fresh",
                "intel_error": "",
            }
        )
        info["external_updated_at"] = now_dt
        info["external_status"] = "fresh"
        info["external_error"] = ""
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
            )
        velocity_threshold = int(self._market_intelligence_config().get("scoring", {}).get("headline_velocity_threshold", 5))
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
            )
        theme_threshold = float(self._market_intelligence_config().get("scoring", {}).get("theme_heat_threshold", 60))
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
            )
        self._market_intel_dirty_codes.add(code)

    def _fetch_market_intelligence_worker(self, codes: List[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"codes": {}, "source_statuses": {}, "macro_values": {}}
        if not self._market_intelligence_enabled():
            for source in ("news", "dart", "datalab", "macro"):
                payload["source_statuses"][source] = {"status": "disabled", "error": "market_intelligence_disabled"}
            return payload

        macro_values: Dict[str, float] = {}
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
                    payload["source_statuses"]["macro"] = {"status": "fresh", "error": ""}
                else:
                    macro_values = provider.latest_values(list(self._market_intelligence_config().get("macro_series", [])))
                    self._market_macro_cache = {"values": dict(macro_values), "ts": now_ts}
                    payload["source_statuses"]["macro"] = {
                        "status": "fresh" if macro_values else "error",
                        "error": "" if macro_values else "empty_response",
                    }
            else:
                payload["source_statuses"]["macro"] = {"status": "disabled", "error": "api_key_missing"}
        else:
            payload["source_statuses"]["macro"] = {"status": "disabled", "error": "provider_disabled"}
        payload["macro_values"] = macro_values

        news_provider = self._build_news_provider()
        dart_provider = self._build_dart_provider()
        trend_provider = self._build_trend_provider()
        for source_name, provider, enabled in (
            ("news", news_provider, self._market_intelligence_provider_enabled("news")),
            ("dart", dart_provider, self._market_intelligence_provider_enabled("dart")),
            ("datalab", trend_provider, self._market_intelligence_provider_enabled("datalab")),
        ):
            if not enabled:
                payload["source_statuses"][source_name] = {"status": "disabled", "error": "provider_disabled"}
            elif not provider.available():
                payload["source_statuses"][source_name] = {"status": "disabled", "error": "api_key_missing"}
            else:
                payload["source_statuses"][source_name] = {"status": "fresh", "error": ""}

        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=30)).strftime("%Y%m%d")
        end_date = today.strftime("%Y%m%d")
        for code in codes:
            info = self.universe.get(code, {})
            name = str(info.get("name", code) or code)
            row = {"news": [], "dart": [], "trend_ratio": 0.0}
            if self._market_intelligence_provider_enabled("news") and news_provider.available():
                try:
                    row["news"] = news_provider.search(name, display=10, sort="date")
                except Exception as exc:
                    payload["source_statuses"]["news"] = {"status": "error", "error": str(exc)}
            if self._market_intelligence_provider_enabled("dart") and dart_provider.available():
                try:
                    row["dart"] = dart_provider.get_recent_disclosures(code, start_date=start_date, end_date=end_date, page_count=10)
                except Exception as exc:
                    payload["source_statuses"]["dart"] = {"status": "error", "error": str(exc)}
            if self._market_intelligence_provider_enabled("datalab") and trend_provider.available():
                try:
                    row["trend_ratio"] = float(trend_provider.latest_ratios([name]).get(name, 0.0) or 0.0)
                except Exception as exc:
                    payload["source_statuses"]["datalab"] = {"status": "error", "error": str(exc)}
            payload["codes"][code] = row
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
        self._last_market_intel_fetch_ts = time.time()
        self._refresh_market_intelligence_table()

    def _on_market_intelligence_error(self, requested_codes: List[str], error: Exception):
        for code in requested_codes:
            info = self.universe.get(code)
            if not info:
                continue
            state = self._ensure_market_intel_state(info)
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
                info = self.universe.get(code)
                if not info:
                    continue
                state = self._ensure_market_intel_state(info)
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
        if codes:
            self._request_market_intelligence_refresh_batch(codes, reason="startup", force=True)
            if not self._market_intel_timer.isActive():
                self._market_intel_timer.start()

    def _stop_market_intelligence_loop(self):
        timer = getattr(self, "_market_intel_timer", None)
        if timer is not None:
            timer.stop()

    def _on_market_intelligence_timer(self):
        if not getattr(self, "is_running", False):
            return
        self._request_market_intelligence_refresh_batch(list(self.universe.keys()), reason="periodic", force=True)
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
        for code, info in self.universe.items():
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
        codes = list(self.universe.keys())
        stale_sec = int(getattr(Config, "MARKET_INTEL_STALE_SEC", 180))
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(codes))
            self._market_intel_row_to_code = {}
            for row, code in enumerate(codes):
                info = self.universe.get(code, {})
                state = self._ensure_market_intel_state(info)
                updated_at = state.get("intel_updated_at")
                status = str(state.get("intel_status", "idle") or "idle")
                if status == "fresh" and isinstance(updated_at, datetime.datetime):
                    age = max(0, int((datetime.datetime.now() - updated_at).total_seconds()))
                    if age > stale_sec:
                        status = "stale"
                values = [
                    str(info.get("name", code) or code),
                    status,
                    f"{float(state.get('news_score', 0.0) or 0.0):+.0f}",
                    str(state.get("dart_risk_level", "normal") or "normal"),
                    f"{float(state.get('theme_score', 0.0) or 0.0):.0f}",
                    str(state.get("macro_regime", "neutral") or "neutral"),
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
        info = self.universe.get(code, {})
        state = self._ensure_market_intel_state(info)
        ai_summary = state.get("ai_summary", {}) if isinstance(state.get("ai_summary"), dict) else {}
        headlines = [f"- {item.get('title', '')}" for item in state.get("news_headlines", [])[:5]]
        disclosures = [f"- {item.get('title', '')}" for item in state.get("dart_events", [])[:5]]
        detail = [
            f"종목: {info.get('name', code)} ({code})",
            f"intel status: {state.get('intel_status', 'idle')}",
            f"news score: {state.get('news_score', 0.0):+.0f}",
            f"news sentiment: {state.get('news_sentiment', 'neutral')}",
            f"headline velocity: {state.get('headline_velocity', 0)}",
            f"dart risk: {state.get('dart_risk_level', 'normal')}",
            f"theme score: {state.get('theme_score', 0.0):.0f}",
            f"theme keywords: {', '.join(state.get('theme_keywords', []) or [])}",
            f"macro regime: {state.get('macro_regime', 'neutral')}",
            f"briefing: {state.get('briefing_summary', '')}",
            f"ai summary: {ai_summary.get('summary', '') if isinstance(ai_summary, dict) else ''}",
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
        codes = list(self.universe.keys())
        if not codes:
            self.log("[시장인텔리전스] 새로고침 대상 종목이 없습니다.")
            return
        self.log(f"[시장인텔리전스] 전체 새로고침: {len(codes)}개 종목")
        self._request_market_intelligence_refresh_batch(codes, reason="manual_all", force=True)

    def _create_market_intelligence_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        source_group = QGroupBox("📡 소스 상태")
        source_layout = QGridLayout(source_group)
        for idx, source in enumerate(self.MARKET_INTEL_SOURCE_NAMES):
            label = QLabel(f"{source.upper()}: idle")
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
        cols = ["종목명", "intel status", "news score", "dart risk", "theme score", "macro regime", "last update", "last alert"]
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

    def _create_market_intelligence_api_group(self):
        from PyQt6.QtWidgets import QCheckBox

        group = QGroupBox("🧠 시장 인텔리전스 API")
        form = QFormLayout(group)

        self.chk_market_intel_enabled = QCheckBox("시장 인텔리전스 사용")
        self.chk_market_intel_enabled.setChecked(bool(self._market_intelligence_config().get("enabled", True)))
        form.addRow("", self.chk_market_intel_enabled)

        self.chk_market_news = QCheckBox("NAVER 뉴스")
        self.chk_market_news.setChecked(bool(self._market_intelligence_config().get("providers", {}).get("news", True)))
        self.chk_market_dart = QCheckBox("OpenDART")
        self.chk_market_dart.setChecked(bool(self._market_intelligence_config().get("providers", {}).get("dart", True)))
        self.chk_market_datalab = QCheckBox("NAVER Datalab")
        self.chk_market_datalab.setChecked(bool(self._market_intelligence_config().get("providers", {}).get("datalab", True)))
        self.chk_market_macro = QCheckBox("FRED Macro")
        self.chk_market_macro.setChecked(bool(self._market_intelligence_config().get("providers", {}).get("macro", True)))
        provider_row = QHBoxLayout()
        provider_row.addWidget(self.chk_market_news)
        provider_row.addWidget(self.chk_market_dart)
        provider_row.addWidget(self.chk_market_datalab)
        provider_row.addWidget(self.chk_market_macro)
        form.addRow("소스:", provider_row)

        self.input_naver_client_id = QLineEdit()
        self.input_naver_client_id.setPlaceholderText("NAVER Client ID")
        form.addRow("NAVER Client ID:", self.input_naver_client_id)
        self.input_naver_client_secret = QLineEdit()
        self.input_naver_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_naver_client_secret.setPlaceholderText("NAVER Client Secret")
        form.addRow("NAVER Client Secret:", self.input_naver_client_secret)

        self.input_dart_api_key = QLineEdit()
        self.input_dart_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_dart_api_key.setPlaceholderText("OPEN_DART_API_KEY")
        form.addRow("DART API Key:", self.input_dart_api_key)

        self.input_fred_api_key = QLineEdit()
        self.input_fred_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_fred_api_key.setPlaceholderText("FRED_API_KEY")
        form.addRow("FRED API Key:", self.input_fred_api_key)

        self.chk_market_ai_enabled = QCheckBox("AI 요약 사용")
        self.chk_market_ai_enabled.setChecked(bool(self._market_intelligence_config().get("ai", {}).get("enabled", False)))
        form.addRow("", self.chk_market_ai_enabled)
        self.combo_market_ai_provider = NoScrollComboBox()
        self.combo_market_ai_provider.addItems(["gemini", "openai"])
        self.combo_market_ai_provider.setCurrentText(str(self._market_intelligence_config().get("ai", {}).get("provider", "gemini")))
        form.addRow("AI Provider:", self.combo_market_ai_provider)
        self.input_market_ai_model = QLineEdit(str(self._market_intelligence_config().get("ai", {}).get("model", "gemini-2.5-flash-lite")))
        form.addRow("AI Model:", self.input_market_ai_model)
        self.input_ai_api_key = QLineEdit()
        self.input_ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_ai_api_key.setPlaceholderText("AI_API_KEY")
        form.addRow("AI API Key:", self.input_ai_api_key)

        self.spin_market_news_refresh = NoScrollSpinBox()
        self.spin_market_news_refresh.setRange(10, 600)
        self.spin_market_news_refresh.setValue(int(self._market_intelligence_config().get("refresh_sec", {}).get("news", 60)))
        form.addRow("뉴스 갱신(초):", self.spin_market_news_refresh)
        self.spin_market_macro_refresh = NoScrollSpinBox()
        self.spin_market_macro_refresh.setRange(30, 1800)
        self.spin_market_macro_refresh.setValue(int(self._market_intelligence_config().get("refresh_sec", {}).get("macro", 300)))
        form.addRow("매크로 갱신(초):", self.spin_market_macro_refresh)

        self.spin_market_news_block = NoScrollSpinBox()
        self.spin_market_news_block.setRange(10, 100)
        self.spin_market_news_block.setValue(abs(int(self._market_intelligence_config().get("scoring", {}).get("news_block_threshold", -60))))
        form.addRow("차단 임계치:", self.spin_market_news_block)
        self.spin_market_news_boost = NoScrollSpinBox()
        self.spin_market_news_boost.setRange(10, 100)
        self.spin_market_news_boost.setValue(abs(int(self._market_intelligence_config().get("scoring", {}).get("news_boost_threshold", 60))))
        form.addRow("강화 임계치:", self.spin_market_news_boost)

        self.spin_market_ai_daily_calls = NoScrollSpinBox()
        self.spin_market_ai_daily_calls.setRange(1, 500)
        self.spin_market_ai_daily_calls.setValue(int(self._market_intelligence_config().get("ai", {}).get("max_calls_per_day", 30)))
        form.addRow("AI 하루 호출수:", self.spin_market_ai_daily_calls)
        self.spin_market_ai_symbol_calls = NoScrollSpinBox()
        self.spin_market_ai_symbol_calls.setRange(1, 50)
        self.spin_market_ai_symbol_calls.setValue(int(self._market_intelligence_config().get("ai", {}).get("max_calls_per_symbol", 3)))
        form.addRow("AI 종목당 호출수:", self.spin_market_ai_symbol_calls)
        self.spin_market_ai_budget = NoScrollSpinBox()
        self.spin_market_ai_budget.setRange(100, 100000)
        self.spin_market_ai_budget.setValue(int(self._market_intelligence_config().get("ai", {}).get("daily_budget_krw", 1000)))
        form.addRow("AI 하루 예산(원):", self.spin_market_ai_budget)

        return group
