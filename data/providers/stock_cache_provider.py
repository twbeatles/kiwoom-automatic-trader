"""Local stock-master cache provider used by stock search dialog."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class StockMasterCacheProvider:
    def __init__(self, cache_path: str = "data/stock_master_cache.json"):
        self.cache_path = Path(cache_path)

    @staticmethod
    def _default_payload() -> Dict[str, Any]:
        return {"updated_at": "", "items": []}

    def load(self) -> Dict[str, Any]:
        if not self.cache_path.exists():
            return self._default_payload()
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            return self._default_payload()

        items = payload.get("items")
        if not isinstance(items, list):
            payload["items"] = []
        payload.setdefault("updated_at", "")
        return payload

    def save(self, payload: Dict[str, Any]) -> None:
        data = {
            "updated_at": str(payload.get("updated_at") or ""),
            "items": list(payload.get("items") or []),
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def upsert(
        self,
        code: str,
        name: str,
        market: str,
        current_price: Optional[int] = None,
    ) -> None:
        code = str(code or "").strip()
        if len(code) != 6 or not code.isdigit():
            return

        payload = self.load()
        items: List[Dict[str, Any]] = payload.get("items", [])

        normalized = {
            "code": code,
            "name": str(name or code),
            "market": str(market or "UNKNOWN"),
        }
        if isinstance(current_price, int) and current_price > 0:
            normalized["current_price"] = current_price

        replaced = False
        for idx, row in enumerate(items):
            if str(row.get("code", "")).strip() == code:
                updated = dict(row)
                updated.update(normalized)
                items[idx] = updated
                replaced = True
                break
        if not replaced:
            items.append(normalized)

        payload["items"] = items
        payload["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        self.save(payload)

    def search(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        query = str(keyword or "").strip().lower()
        if not query:
            return []

        payload = self.load()
        items: List[Dict[str, Any]] = payload.get("items", [])

        starts_with: List[Dict[str, Any]] = []
        contains: List[Dict[str, Any]] = []
        for item in items:
            code = str(item.get("code", "")).strip()
            name = str(item.get("name", "")).strip()
            if not code:
                continue
            code_hit = query in code.lower()
            name_hit = query in name.lower()
            if not (code_hit or name_hit):
                continue
            row = {
                "code": code,
                "name": name,
                "market": str(item.get("market", "")),
                "current_price": int(item.get("current_price", 0) or 0),
                "source": "cache",
            }
            if code.lower().startswith(query) or name.lower().startswith(query):
                starts_with.append(row)
            else:
                contains.append(row)

        ordered = starts_with + contains
        return ordered[: max(1, int(limit))]
