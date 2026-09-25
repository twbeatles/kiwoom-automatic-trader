"""Unified intel timeline helpers (P3).

Merges the two JSONL-sourced replay feeds — market-intelligence events and
decision-audit records — into one chronological timeline for the replay
drawer. Pure functions over parsed dicts; JSONL file IO stays with the
existing view mixin (``_read_jsonl_tail_records``), so file paths/sources
are unchanged.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


def parse_ts(value: Any) -> Optional[datetime.datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def _payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = record.get("payload", {})
    if isinstance(payload, dict):
        return payload
    raw_ref = record.get("raw_ref", "")
    if isinstance(raw_ref, dict):
        return dict(raw_ref)
    return {}


def normalize_event_record(record: Dict[str, Any], index: int) -> Dict[str, Any]:
    payload = _payload(record)
    target = (
        str(record.get("symbol", "") or "")
        or str(payload.get("sector", "") or "")
        or str(payload.get("theme", "") or "")
    )
    summary = str(record.get("summary", "") or "")
    policy = str(payload.get("action_policy", "") or "")
    exit_policy = str(payload.get("exit_policy", "") or "")
    headline = " / ".join(part for part in (record.get("event_type", ""), summary) if part)
    return {
        "kind": "event",
        "ts": parse_ts(record.get("ts", "")),
        "ts_text": str(record.get("ts", "") or ""),
        "target": target,
        "headline": headline or str(payload.get("sector", "") or payload.get("theme", "") or "-"),
        "policy": " / ".join(part for part in (policy, exit_policy) if part),
        "sort_key": (parse_ts(record.get("ts", "")) or datetime.datetime.min, 0, index),
        "source": dict(record),
    }


def normalize_audit_record(record: Dict[str, Any], index: int) -> Dict[str, Any]:
    allowed = bool(record.get("allowed", False))
    headline = f"{'허용' if allowed else '차단'}: {record.get('reason', '')}"
    policy = " / ".join(
        part
        for part in (str(record.get("action_policy", "") or ""), str(record.get("exit_policy", "") or ""))
        if part
    )
    return {
        "kind": "audit",
        "ts": parse_ts(record.get("ts", "")),
        "ts_text": str(record.get("ts", "") or ""),
        "target": str(record.get("symbol", "") or ""),
        "headline": headline,
        "policy": policy,
        "sort_key": (parse_ts(record.get("ts", "")) or datetime.datetime.min, 1, index),
        "source": dict(record),
    }


def build_intel_timeline(
    event_records: List[Any] | None,
    audit_records: List[Any] | None,
    *,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Merge event+audit dicts into one chronological (ascending) timeline."""
    entries: List[Dict[str, Any]] = []
    for idx, record in enumerate(event_records or []):
        if isinstance(record, dict):
            entries.append(normalize_event_record(record, idx))
    offset = len(entries)
    for idx, record in enumerate(audit_records or []):
        if isinstance(record, dict):
            entries.append(normalize_audit_record(record, offset + idx))
    entries.sort(key=lambda entry: entry["sort_key"])
    bound = max(1, int(limit or 100))
    return entries[-bound:]


def timeline_row(entry: Dict[str, Any]) -> List[str]:
    kind_label = "이벤트" if entry.get("kind") == "event" else "감사"
    return [
        str(entry.get("ts_text", "") or ""),
        kind_label,
        str(entry.get("target", "") or ""),
        str(entry.get("headline", "") or ""),
        str(entry.get("policy", "") or ""),
    ]
