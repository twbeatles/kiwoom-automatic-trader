"""Execution engine mixin for KiwoomProTrader."""

import datetime
import json
import time
from collections import deque
from pathlib import Path

from api.models import ExecutionData
from app.support.execution_policy import ExecutionPolicy
from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


class ExecutionModeLifecycleMixin(TraderMixinBase):
    def _execution_mode(self) -> str:
        cfg = getattr(self, "config", None)
        mode = str(getattr(cfg, "execution_mode", getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only")) or "")
        if mode not in getattr(Config, "EXECUTION_MODES", {"signal_only", "live"}):
            return str(getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"))
        return mode
    def _is_signal_only_mode(self) -> bool:
        return self._execution_mode() == "signal_only"
    def _record_order_lifecycle_event(self, event: dict) -> None:
        payload = dict(event)
        payload.setdefault("ts", datetime.datetime.now().isoformat())
        path = Path(getattr(Config, "ORDER_LIFECYCLE_EVENTS_FILE", "data/order_lifecycle_events.jsonl"))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.warning(f"order lifecycle event write failed: {exc}")
    def _record_signal_only_order(
        self,
        *,
        side: str,
        code: str,
        quantity: int,
        price: int = 0,
        reason: str = "",
        payload: dict | None = None,
    ) -> None:
        event = {
            "event": "signal_only_order_skipped",
            "execution_mode": "signal_only",
            "side": side,
            "code": code,
            "quantity": max(0, int(quantity or 0)),
            "price": max(0, int(price or 0)),
            "reason": reason,
            "payload": payload or {},
        }
        self._record_order_lifecycle_event(event)
        if hasattr(self, "log"):
            self.log(
                f"[signal-only] {side.upper()} skipped {code} "
                f"qty={event['quantity']} price={event['price']} reason={reason or '-'}"
            )
    def _record_decision_audit_once(
        self,
        code: str,
        info: dict,
        *,
        allowed: bool,
        reason: str,
        conditions: dict | None = None,
        metrics: dict | None = None,
        quantity: int = 0,
    ):
        recorder = getattr(self, "_record_decision_audit_event", None)
        if not callable(recorder):
            return
        state = info.get("market_intel", {}) if isinstance(info.get("market_intel"), dict) else {}
        key = (
            f"{code}:{int(bool(allowed))}:{reason}:{state.get('last_event_id', '')}:"
            f"{int(time.time() // 30)}:{int(quantity or 0)}"
        )
        cache = getattr(self, "_decision_audit_keys", None)
        if not isinstance(cache, dict):
            cache = {}
            self._decision_audit_keys = cache
        if key in cache:
            return
        cache[key] = time.time()
        if len(cache) > 500:
            cutoff = time.time() - 3600
            for old_key in list(cache.keys()):
                if float(cache.get(old_key, 0.0)) < cutoff:
                    cache.pop(old_key, None)
        recorder(
            code=code,
            info=info,
            allowed=allowed,
            reason=reason,
            conditions=conditions,
            metrics=metrics,
            quantity=quantity,
        )
