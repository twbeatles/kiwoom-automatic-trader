"""REST numeric parsing helpers (SRP: value coercion only)."""

from typing import Any


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
