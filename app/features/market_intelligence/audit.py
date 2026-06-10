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


class MarketIntelAuditMixin(TraderMixinBase):
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
