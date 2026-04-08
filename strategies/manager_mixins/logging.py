import time
from typing import Optional

from config import Config


class StrategyManagerLoggingMixin:
    def log(self, msg):
        self.trader.log(msg)

    def log_dedup(self, code: str, key: str, message: str, now_ts: Optional[float] = None):
        cooldown_map = getattr(self.trader, "_log_cooldown_map", None)
        if cooldown_map is None:
            cooldown_map = {}
            self.trader._log_cooldown_map = cooldown_map
        ts = now_ts if now_ts is not None else time.time()
        cache_key = f"{code}:{key}"
        last_ts = float(cooldown_map.get(cache_key, 0.0))
        if ts - last_ts >= float(getattr(Config, "LOG_DEDUP_SEC", 30)):
            self.log(message)
            cooldown_map[cache_key] = ts
