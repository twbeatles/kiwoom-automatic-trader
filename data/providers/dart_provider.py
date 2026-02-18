"""DART (OpenDART) provider.

Requires: OPEN_DART_API_KEY env var.
"""

import os
from typing import Any, Dict, List

import requests


class DartProvider:
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("OPEN_DART_API_KEY", "")

    def available(self) -> bool:
        return bool(self.api_key)

    def get_company_info(self, corp_code: str) -> Dict[str, Any]:
        if not self.available() or not corp_code:
            return {}
        url = f"{self.BASE_URL}/company.json"
        params = {"crtfc_key": self.api_key, "corp_code": corp_code}
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            payload = res.json()
            if str(payload.get("status")) != "000":
                return {}
            return payload
        except Exception:
            return {}

    def get_financial_statement(self, corp_code: str, bsns_year: str, reprt_code: str = "11011") -> List[Dict[str, Any]]:
        if not self.available() or not corp_code or not bsns_year:
            return []
        url = f"{self.BASE_URL}/fnlttSinglAcnt.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            payload = res.json()
            if str(payload.get("status")) != "000":
                return []
            return payload.get("list", [])
        except Exception:
            return []
