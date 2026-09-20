"""REST payload helpers (SRP: parsing/coercion only)."""

from typing import Any, Dict, List, Optional

from .models import PriceType


def _safe_int(value: Any, default: int = 0, *, absolute: bool = False) -> int:
    try:
        if value is None:
            return default
        text = str(value).strip().replace(",", "")
        if text in {"", "-", "+", "--"}:
            return default
        result = int(float(text))
        return abs(result) if absolute else result
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip().replace(",", "").replace("%", "")
        if text in {"", "-", "+", "--"}:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def _pick(mapping: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping[key]
    return default


def _as_records(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict) and value:
        return [value]
    return []


def _payload_dict(result: Optional[Dict[str, Any]], *keys: str) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    for key in keys:
        candidate = result.get(key)
        if isinstance(candidate, dict) and candidate:
            return candidate
    return result


def _payload_records(result: Optional[Dict[str, Any]], *keys: str) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    for key in keys:
        records = _as_records(result.get(key))
        if records:
            return records
    return []


def _trde_tp(price_type: PriceType) -> str:
    mapping = {
        PriceType.MARKET: "3",
        PriceType.CONDITIONAL: "5",
        PriceType.BEST: "6",
        PriceType.PRIORITY: "7",
        PriceType.AFTER_MARKET: "81",
    }
    return mapping.get(price_type, "0")


def _parse_order_side(item: Dict[str, Any]) -> str:
    """주문 방향 파싱 (SRP: pure mapping, orders/account 공유)."""
    label = str(item.get("io_tp_nm") or item.get("ord_stt") or "").strip()
    if "매수" in label:
        return "buy"
    if "매도" in label:
        return "sell"
    raw_trde = str(item.get("trde_tp") or "").strip()
    if raw_trde == "2":
        return "buy"
    if raw_trde == "1":
        return "sell"
    raw_side = str(item.get("ord_tp") or item.get("bs_tp") or "").strip()
    if raw_side == "1":
        return "buy"
    if raw_side == "2":
        return "sell"
    return raw_side or raw_trde


def _order_no_from_result(result: Optional[Dict[str, Any]]) -> str:
    """주문번호 추출 (SRP: pure mapping)."""
    if not isinstance(result, dict):
        return ""
    output = result.get("output")
    if isinstance(output, dict):
        value = output.get("ord_no")
        if value:
            return str(value)
    return str(result.get("ord_no") or "")
