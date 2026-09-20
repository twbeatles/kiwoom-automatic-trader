"""Backtest intelligence sidecar (SRP: JSONL load/merge/compose only)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._guards import BacktestGuardsMixin
from .models import BacktestIntelligenceEvent


class BacktestIntelEventsMixin(BacktestGuardsMixin):
    """Backtest intelligence sidecar (SRP: JSONL load/merge/compose only)."""

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @classmethod
    def load_intelligence_events_jsonl(cls, path: str | Path) -> List[BacktestIntelligenceEvent]:
        records: List[BacktestIntelligenceEvent] = []
        file_path = Path(path)
        if not file_path.exists():
            return records
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = str(line or "").strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                ts = cls._parse_timestamp(record.get("ts"))
                if ts is None:
                    continue
                payload = record.get("payload", {})
                if not isinstance(payload, dict):
                    payload = {}
                raw_ref = record.get("raw_ref", "")
                if not payload and isinstance(raw_ref, str) and raw_ref:
                    try:
                        parsed = json.loads(raw_ref)
                        if isinstance(parsed, dict):
                            payload = parsed
                    except Exception:
                        payload = {}
                records.append(
                    BacktestIntelligenceEvent(
                        ts=ts,
                        scope=str(record.get("scope", "symbol") or "symbol"),
                        symbol=str(record.get("symbol", "") or ""),
                        source=str(record.get("source", "") or ""),
                        event_type=str(record.get("event_type", "") or ""),
                        score=float(record.get("score", 0.0) or 0.0),
                        tags=list(record.get("tags", []) or []),
                        summary=str(record.get("summary", "") or ""),
                        blocking=bool(record.get("blocking", False)),
                        event_id=str(record.get("event_id", "") or ""),
                        payload=payload,
                        raw_ref=raw_ref,
                    )
                )
        return sorted(records, key=lambda event: (event.ts, event.scope, event.symbol, event.event_type, event.event_id))

    @staticmethod
    def _payload_from_event(event: BacktestIntelligenceEvent) -> Dict[str, Any]:
        if isinstance(event.payload, dict) and event.payload:
            return dict(event.payload)
        if isinstance(event.raw_ref, dict):
            return dict(event.raw_ref)
        if isinstance(event.raw_ref, str) and event.raw_ref:
            try:
                parsed = json.loads(event.raw_ref)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    def _merge_scope_state(self, state: Dict[str, Any], event: BacktestIntelligenceEvent, payload: Dict[str, Any]):
        state["intel_status"] = "fresh"
        state["status"] = "fresh"
        state["last_event_ts"] = event.ts
        state["source"] = str(event.source or state.get("source", ""))
        state["event_type"] = str(event.event_type or payload.get("event_type", state.get("event_type", "")) or "")
        state["event_severity"] = str(
            payload.get("event_severity", "critical" if event.blocking else ("high" if float(event.score or 0.0) <= -60 else "low"))
            or "low"
        )
        if payload:
            state.update(payload)
        if event.event_id or payload.get("event_id"):
            state["last_event_id"] = str(event.event_id or payload.get("event_id") or "")

        if event.source == "news":
            state["news_score"] = float(payload.get("news_score", event.score))
            if event.event_type == "headline_velocity":
                state["headline_velocity"] = int(payload.get("headline_velocity", max(1, int(abs(event.score) or len(event.tags)))))
        elif event.source == "dart":
            state["dart_risk_level"] = "high" if event.blocking or float(event.score or 0.0) <= -60 else str(payload.get("dart_risk_level", "normal"))
        elif event.source == "macro":
            if "macro_regime" in payload:
                state["macro_regime"] = str(payload.get("macro_regime", "neutral"))
            elif event.blocking or float(event.score or 0.0) < 0:
                state["macro_regime"] = "risk_off"
            elif float(event.score or 0.0) > 0:
                state["macro_regime"] = "risk_on"
            else:
                state["macro_regime"] = "neutral"
        elif event.source == "theme":
            state["theme_score"] = float(payload.get("theme_score", event.score))

        if event.blocking:
            state["blocking"] = True
        if "action_policy" in payload:
            current = str(state.get("action_policy", "allow") or "allow")
            incoming = str(payload.get("action_policy", "allow") or "allow")
            state["action_policy"] = incoming if self._policy_rank(incoming) >= self._policy_rank(current) else current
        elif event.blocking and self._policy_rank(str(state.get("action_policy", "allow") or "allow")) < self._policy_rank("block_entry"):
            state["action_policy"] = "block_entry"

        if "exit_policy" in payload:
            current_exit = str(state.get("exit_policy", "none") or "none")
            incoming_exit = str(payload.get("exit_policy", "none") or "none")
            if self._exit_policy_rank(incoming_exit) >= self._exit_policy_rank(current_exit):
                state["exit_policy"] = incoming_exit
        elif str(state.get("action_policy", "allow") or "allow") in {"reduce_size", "tighten_exit", "force_exit"}:
            state["exit_policy"] = str(state.get("action_policy", "allow") or "allow")

        if "portfolio_budget_scale" in payload:
            current_scale = float(state.get("portfolio_budget_scale", 1.0) or 1.0)
            incoming_scale = max(0.1, float(payload.get("portfolio_budget_scale", 1.0) or 1.0))
            state["portfolio_budget_scale"] = min(current_scale, incoming_scale)

    def _apply_intelligence_event(
        self,
        symbol_intelligence_state: Dict[str, Dict[str, Any]],
        scoped_intelligence_state: Dict[str, Dict[str, Any]],
        event: BacktestIntelligenceEvent,
    ):
        payload = self._payload_from_event(event)
        scope = str(event.scope or payload.get("scope", "symbol") or "symbol").lower()
        if scope == "market":
            state = scoped_intelligence_state.setdefault("market", {})
        elif scope == "sector":
            sector = str(payload.get("sector", "") or payload.get("scope_key", "") or event.symbol or "")
            if not sector:
                return
            state = scoped_intelligence_state.setdefault("sector", {}).setdefault(sector, {})
        elif scope == "theme":
            theme = str(payload.get("theme", "") or payload.get("scope_key", "") or event.symbol or "")
            if not theme:
                return
            state = scoped_intelligence_state.setdefault("theme", {}).setdefault(theme, {})
        else:
            symbol = str(event.symbol or payload.get("symbol", "") or "")
            if not symbol:
                return
            state = symbol_intelligence_state.setdefault(symbol, {})
        self._merge_scope_state(state, event, payload)

    def _compose_effective_intelligence(
        self,
        *,
        symbol: str,
        meta: Dict[str, Any],
        symbol_intelligence_state: Dict[str, Dict[str, Any]],
        scoped_intelligence_state: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        layers: List[Dict[str, Any]] = []
        market_state = scoped_intelligence_state.get("market", {})
        if isinstance(market_state, dict) and market_state:
            layers.append(market_state)

        sector = str(meta.get("sector", "") or meta.get("industry", "") or "").strip()
        if sector:
            sector_state = scoped_intelligence_state.get("sector", {}).get(sector, {})
            if isinstance(sector_state, dict) and sector_state:
                layers.append(sector_state)

        themes_raw = meta.get("theme_keywords", meta.get("themes", []))
        theme_names: List[str] = []
        if isinstance(themes_raw, str) and themes_raw.strip():
            theme_names = [themes_raw.strip()]
        elif isinstance(themes_raw, list):
            theme_names = [str(theme or "").strip() for theme in themes_raw if str(theme or "").strip()]
        for theme in theme_names:
            theme_state = scoped_intelligence_state.get("theme", {}).get(theme, {})
            if isinstance(theme_state, dict) and theme_state:
                layers.append(theme_state)

        symbol_state = symbol_intelligence_state.get(symbol, {})
        if isinstance(symbol_state, dict) and symbol_state:
            layers.append(symbol_state)

        combined: Dict[str, Any] = {
            "intel_status": "idle",
            "status": "idle",
            "news_score": 0.0,
            "dart_risk_level": "normal",
            "macro_regime": "neutral",
            "theme_score": 0.0,
            "headline_velocity": 0,
            "action_policy": "allow",
            "exit_policy": "none",
            "size_multiplier": 1.0,
            "portfolio_budget_scale": 1.0,
            "blocking": False,
            "last_event_id": "",
            "event_type": "",
            "event_severity": "low",
        }
        action_rank = 0
        exit_rank = 0
        latest_ts: Optional[datetime] = None
        source_health: List[str] = []
        cumulative_news_score = 0.0
        combined_size_multiplier = 1.0
        combined_budget_scale = 1.0
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            status = str(layer.get("status", layer.get("intel_status", "idle")) or "idle")
            if status in {"error", "partial", "stale"}:
                combined["status"] = status
                combined["intel_status"] = status
            elif combined["status"] == "idle" and status:
                combined["status"] = status
                combined["intel_status"] = status

            cumulative_news_score += float(layer.get("news_score", 0.0) or 0.0)
            combined["theme_score"] = max(combined["theme_score"], float(layer.get("theme_score", 0.0) or 0.0))
            combined["headline_velocity"] = max(combined["headline_velocity"], int(layer.get("headline_velocity", 0) or 0))
            if str(layer.get("dart_risk_level", "normal") or "normal") == "high":
                combined["dart_risk_level"] = "high"
            macro_regime = str(layer.get("macro_regime", "neutral") or "neutral")
            if macro_regime == "risk_off":
                combined["macro_regime"] = "risk_off"
            elif macro_regime == "risk_on" and combined["macro_regime"] != "risk_off":
                combined["macro_regime"] = "risk_on"

            layer_policy = str(layer.get("action_policy", "allow") or "allow")
            if self._policy_rank(layer_policy) >= action_rank:
                action_rank = self._policy_rank(layer_policy)
                combined["action_policy"] = layer_policy

            layer_exit = str(layer.get("exit_policy", "none") or "none")
            if self._exit_policy_rank(layer_exit) >= exit_rank:
                exit_rank = self._exit_policy_rank(layer_exit)
                combined["exit_policy"] = self._exit_policy_from_rank(exit_rank)

            size_multiplier = float(layer.get("size_multiplier", 1.0) or 1.0)
            if size_multiplier > 0:
                combined_size_multiplier *= size_multiplier
            budget_scale = float(layer.get("portfolio_budget_scale", 1.0) or 1.0)
            if budget_scale > 0:
                combined_budget_scale = min(combined_budget_scale, budget_scale)

            if bool(layer.get("blocking", False)):
                combined["blocking"] = True
            source_health_text = str(layer.get("source_health", "") or "").strip()
            if source_health_text:
                source_health.append(source_health_text)
            layer_ts = layer.get("last_event_ts")
            if isinstance(layer_ts, datetime) and (latest_ts is None or layer_ts >= latest_ts):
                latest_ts = layer_ts
                combined["last_event_id"] = str(layer.get("last_event_id", "") or combined.get("last_event_id", ""))
                combined["event_type"] = str(layer.get("event_type", "") or combined.get("event_type", ""))
                combined["event_severity"] = str(layer.get("event_severity", "low") or combined.get("event_severity", "low"))

        combined["news_score"] = max(-100.0, min(100.0, cumulative_news_score))
        combined["size_multiplier"] = max(0.1, min(2.0, combined_size_multiplier))
        combined["portfolio_budget_scale"] = max(0.1, min(1.0, combined_budget_scale))
        combined["source_health"] = " | ".join(dict.fromkeys(source_health))
        return combined
