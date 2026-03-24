"""NAVER News Search provider."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

import requests


class NewsProvider:
    BASE_URL = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = str(client_id or "").strip()
        self.client_secret = str(client_secret or "").strip()

    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search(self, query: str, display: int = 10, sort: str = "date") -> List[Dict[str, Any]]:
        if not self.available() or not query:
            return []
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {
            "query": query,
            "display": max(1, min(int(display), 100)),
            "sort": str(sort or "date"),
        }
        try:
            response = requests.get(self.BASE_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", [])
            if not isinstance(items, list):
                return []
            return [self._normalize_item(item) for item in items if isinstance(item, dict)]
        except Exception:
            return []

    @staticmethod
    def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
        title = str(item.get("title", "") or "")
        link = str(item.get("link", "") or "")
        origin_link = str(item.get("originallink", "") or "")
        description = str(item.get("description", "") or "")
        published = str(item.get("pubDate", "") or "")
        published_at = None
        if published:
            try:
                published_at = parsedate_to_datetime(published)
            except (TypeError, ValueError, IndexError):
                published_at = None
        return {
            "title": title,
            "link": link,
            "origin_link": origin_link,
            "description": description,
            "published_at": published_at,
            "published": published,
            "fetched_at": datetime.now(),
        }
