"""Macro data provider (FRED free API)."""

import os
from typing import Dict, List

import requests


class MacroProvider:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        self.last_status = "idle"
        self.last_error = ""

    def _mark(self, status: str, error: str = ""):
        self.last_status = str(status or "idle")
        self.last_error = str(error or "")

    def available(self) -> bool:
        return bool(self.api_key)

    def get_series(self, series_id: str, start_date: str = "", end_date: str = "") -> List[Dict[str, str]]:
        if not self.available() or not series_id:
            self._mark("disabled" if not self.available() else "ok_empty")
            return []
        params = {
            "api_key": self.api_key,
            "series_id": series_id,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date
        try:
            res = requests.get(self.BASE_URL, params=params, timeout=10)
            res.raise_for_status()
            payload = res.json()
            observations = payload.get("observations", [])
            normalized = observations if isinstance(observations, list) else []
            self._mark("ok_with_data" if normalized else "ok_empty")
            return normalized
        except Exception as exc:
            self._mark("error", error=str(exc))
            return []

    def latest_value(self, series_id: str) -> float:
        rows = self.get_series(series_id)
        if not rows:
            return 0.0
        for row in reversed(rows):
            value = row.get("value", ".")
            if value not in {".", "", None}:
                try:
                    return float(value)
                except ValueError:
                    continue
        return 0.0

    def get_series_bundle(
        self, series_ids: List[str], start_date: str = "", end_date: str = ""
    ) -> Dict[str, List[Dict[str, str]]]:
        bundle: Dict[str, List[Dict[str, str]]] = {}
        for series_id in series_ids:
            sid = str(series_id or "").strip()
            if not sid:
                continue
            bundle[sid] = self.get_series(sid, start_date=start_date, end_date=end_date)
        return bundle

    def latest_values(self, series_ids: List[str]) -> Dict[str, float]:
        values: Dict[str, float] = {}
        had_error = False
        for series_id in series_ids:
            sid = str(series_id or "").strip()
            if not sid:
                continue
            values[sid] = self.latest_value(sid)
            had_error = had_error or self.last_status == "error"
        if had_error:
            self._mark("error", error=self.last_error)
        elif values and any(float(v or 0.0) != 0.0 for v in values.values()):
            self._mark("ok_with_data")
        else:
            self._mark("ok_empty")
        return values
