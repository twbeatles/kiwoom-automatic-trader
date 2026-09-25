"""Portfolio PnL/weight/exposure summary helpers (P2).

Pure functions over plain dicts so they stay Qt-free and unit-testable.
Callers pass ``universe`` / ``external_positions`` mappings plus the
``trade_history`` list; missing keys default to zero/empty.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _to_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def position_eval(info: Dict[str, Any]) -> Dict[str, float]:
    """Unrealized PnL snapshot for one position mapping."""
    held = _to_int(info.get("held", 0))
    buy_price = _to_int(info.get("buy_price", 0))
    current = _to_int(info.get("current", 0))
    invest = _to_int(info.get("invest_amount", held * buy_price))
    eval_amount = held * current if held and current else _to_int(info.get("eval_amount", 0))
    profit = eval_amount - invest if held else 0
    profit_rate = (profit / invest * 100.0) if held and invest > 0 else 0.0
    return {
        "held": float(held),
        "invest_amount": float(invest),
        "eval_amount": float(eval_amount),
        "unrealized_pnl": float(profit),
        "profit_rate": float(profit_rate),
    }


def compute_portfolio_summary(
    universe: Dict[str, Dict[str, Any]] | None,
    external_positions: Dict[str, Dict[str, Any]] | None,
    trade_history: List[Dict[str, Any]] | None,
    *,
    today: str = "",
) -> Dict[str, Any]:
    """Aggregate realized/unrealized PnL, weights, and exposures."""
    universe = universe if isinstance(universe, dict) else {}
    external = external_positions if isinstance(external_positions, dict) else {}
    history = trade_history if isinstance(trade_history, list) else []

    per_code: Dict[str, Dict[str, float]] = {}
    eval_total = 0.0
    invest_total = 0.0
    unrealized_total = 0.0
    exposures: Dict[str, Dict[str, float]] = {"market": {}, "sector": {}}
    sync_failed_codes: List[str] = []
    external_codes = sorted(external.keys())

    tracked = dict(universe)
    for code in external_codes:
        if code not in tracked:
            tracked[code] = external[code] if isinstance(external[code], dict) else {}

    for code, raw in tracked.items():
        info = raw if isinstance(raw, dict) else {}
        snap = position_eval(info)
        per_code[code] = snap
        eval_total += snap["eval_amount"]
        invest_total += snap["invest_amount"]
        unrealized_total += snap["unrealized_pnl"]
        if str(info.get("status", "")) == "sync_failed":
            sync_failed_codes.append(code)
        for group, key in (("market", "market_type"), ("sector", "sector")):
            label = str(info.get(key, "") or "").strip() or ("외부" if code in external else "미분류")
            bucket = exposures[group]
            bucket[label] = bucket.get(label, 0.0) + snap["eval_amount"]

    weights = {
        code: (snap["eval_amount"] / eval_total if eval_total > 0 else 0.0)
        for code, snap in per_code.items()
    }

    scoped = [r for r in history if isinstance(r, dict) and (not today or str(r.get("timestamp", "")).startswith(today))]
    realized = sum(_to_float(r.get("profit", 0)) for r in scoped if r.get("type") == "매도")
    read_only_codes = sorted(
        code for code, raw in tracked.items() if isinstance(raw, dict) and bool(raw.get("read_only", False))
    )

    top_weights = sorted(weights.items(), key=lambda kv: -kv[1])[:3]
    return {
        "realized_pnl": float(realized),
        "unrealized_pnl": float(unrealized_total),
        "total_pnl": float(realized + unrealized_total),
        "invest_total": float(invest_total),
        "eval_total": float(eval_total),
        "weights": weights,
        "top_weights": [(code, float(w)) for code, w in top_weights],
        "exposures": exposures,
        "counts": {
            "universe": len(universe),
            "external": len(external),
            "tracked": len(tracked),
            "sync_failed": len(sync_failed_codes),
            "read_only": len(read_only_codes),
        },
        "sync_failed_codes": sorted(sync_failed_codes),
        "external_codes": external_codes,
        "read_only_codes": read_only_codes,
        "per_code": per_code,
    }
