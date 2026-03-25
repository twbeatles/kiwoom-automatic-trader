"""NAVER Datalab search trend provider."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import requests


class NaverTrendProvider:
    BASE_URL = "https://openapi.naver.com/v1/datalab/search"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = str(client_id or "").strip()
        self.client_secret = str(client_secret or "").strip()
        self.last_status = "idle"
        self.last_error = ""

    def _mark(self, status: str, error: str = ""):
        self.last_status = str(status or "idle")
        self.last_error = str(error or "")

    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search_trend(
        self,
        keyword_groups: List[Dict[str, Any]],
        start_date: str = "",
        end_date: str = "",
        time_unit: str = "date",
    ) -> Dict[str, Any]:
        if not self.available() or not keyword_groups:
            self._mark("disabled" if not self.available() else "ok_empty")
            return {}
        today = date.today()
        payload = {
            "startDate": start_date or (today - timedelta(days=7)).isoformat(),
            "endDate": end_date or today.isoformat(),
            "timeUnit": str(time_unit or "date"),
            "keywordGroups": keyword_groups,
        }
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            normalized = result if isinstance(result, dict) else {}
            has_results = bool(isinstance(normalized.get("results"), list) and normalized.get("results"))
            self._mark("ok_with_data" if has_results else "ok_empty")
            return normalized
        except Exception as exc:
            self._mark("error", error=str(exc))
            return {}

    def latest_ratios(self, keywords: List[str]) -> Dict[str, float]:
        groups = []
        for keyword in keywords:
            text = str(keyword or "").strip()
            if not text:
                continue
            groups.append({"groupName": text, "keywords": [text]})
        payload = self.search_trend(groups)
        result = payload.get("results", []) if isinstance(payload, dict) else []
        ratios: Dict[str, float] = {}
        for row in result:
            if not isinstance(row, dict):
                continue
            group_name = str(row.get("title", "") or "")
            data = row.get("data", [])
            latest_ratio = 0.0
            if isinstance(data, list):
                for item in reversed(data):
                    if not isinstance(item, dict):
                        continue
                    try:
                        latest_ratio = float(item.get("ratio", 0.0) or 0.0)
                        break
                    except (TypeError, ValueError):
                        continue
            ratios[group_name] = latest_ratio
        if ratios and self.last_status != "error":
            self._mark("ok_with_data")
        elif self.last_status != "error":
            self._mark("ok_empty")
        return ratios

    @staticmethod
    def latest_timestamp(payload: Dict[str, Any]) -> datetime | None:
        result = payload.get("results", []) if isinstance(payload, dict) else []
        latest = ""
        for row in result:
            if not isinstance(row, dict):
                continue
            data = row.get("data", [])
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                latest = max(latest, str(item.get("period", "") or ""))
        if not latest:
            return None
        try:
            return datetime.fromisoformat(latest)
        except ValueError:
            return None
