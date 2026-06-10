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


class MarketIntelViewsMixin(TraderMixinBase):
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
