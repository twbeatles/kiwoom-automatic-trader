"""DART (OpenDART) provider.

Requires: OPEN_DART_API_KEY env var.
"""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import requests


class DartProvider:
    BASE_URL = "https://opendart.fss.or.kr/api"
    CORP_CODE_URL = f"{BASE_URL}/corpCode.xml"

    def __init__(self, api_key: str = "", cache_dir: str = "data"):
        self.api_key = api_key or os.getenv("OPEN_DART_API_KEY", "")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "dart_corp_codes.json"

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

    def get_financial_statement(
        self, corp_code: str, bsns_year: str, reprt_code: str = "11011"
    ) -> List[Dict[str, Any]]:
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
            result = payload.get("list", [])
            return result if isinstance(result, list) else []
        except Exception:
            return []

    def get_corp_code_map(self, force_refresh: bool = False) -> Dict[str, str]:
        if not self.available():
            return {}
        if not force_refresh and self.cache_path.exists():
            try:
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return {str(k): str(v) for k, v in payload.items() if str(k) and str(v)}
            except (OSError, json.JSONDecodeError):
                pass
        try:
            response = requests.get(self.CORP_CODE_URL, params={"crtfc_key": self.api_key}, timeout=20)
            response.raise_for_status()
            mapping = self._parse_corp_code_zip(response.content)
            if mapping:
                self.cache_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
            return mapping
        except Exception:
            return {}

    def resolve_corp_code(self, stock_code: str, force_refresh: bool = False) -> str:
        code = str(stock_code or "").strip()
        if not code:
            return ""
        mapping = self.get_corp_code_map(force_refresh=force_refresh)
        return str(mapping.get(code, "") or "")

    def get_recent_disclosures(
        self,
        stock_code: str,
        start_date: str = "",
        end_date: str = "",
        page_count: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self.available() or not stock_code:
            return []
        corp_code = self.resolve_corp_code(stock_code)
        if not corp_code:
            return []
        url = f"{self.BASE_URL}/list.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": start_date,
            "end_de": end_date,
            "page_count": max(1, min(int(page_count), 100)),
            "last_reprt_at": "Y",
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            payload = res.json()
            if str(payload.get("status")) != "000":
                return []
            result = payload.get("list", [])
            return result if isinstance(result, list) else []
        except Exception:
            return []

    @staticmethod
    def _parse_corp_code_zip(raw: bytes) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        with ZipFile(BytesIO(raw)) as zipped:
            names = zipped.namelist()
            if not names:
                return {}
            with zipped.open(names[0]) as xml_file:
                root = ET.parse(xml_file).getroot()
                for item in root.findall("list"):
                    corp_code = str(item.findtext("corp_code", "") or "").strip()
                    stock_code = str(item.findtext("stock_code", "") or "").strip()
                    if corp_code and stock_code:
                        mapping[stock_code] = corp_code
        return mapping
