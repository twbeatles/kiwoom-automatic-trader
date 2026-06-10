"""Trading session lifecycle mixin for KiwoomProTrader."""

from collections import deque
import datetime
import time
from typing import Any, Deque, Dict, List, Literal, Optional, Tuple, overload

from PyQt6.QtCore import QCoreApplication, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem

from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


BackgroundUniversePayload = Tuple[List[str], Dict[str, Dict[str, Any]], List[str]]


class TradingSessionRiskStateMixin(TraderMixinBase):
    def _set_global_risk_mode(self, mode: str, until: Optional[datetime.datetime], reason: str = ""):
        current_mode = str(getattr(self, "_global_risk_mode", "normal"))
        current_until = getattr(self, "_global_risk_until", None)
        self._global_risk_mode = str(mode)
        self._global_risk_until = until if isinstance(until, datetime.datetime) else None
        if current_mode != self._global_risk_mode or current_until != self._global_risk_until:
            suffix = f" ({reason})" if reason else ""
            until_text = self._global_risk_until.strftime("%H:%M:%S") if self._global_risk_until else "-"
            self._log_once(
                f"global_risk_mode:{self._global_risk_mode}",
                f"[리스크모드] {current_mode} -> {self._global_risk_mode} (until={until_text}){suffix}",
            )
    def _maybe_release_global_risk_mode(self, now_dt: datetime.datetime):
        if str(getattr(self, "_global_risk_mode", "normal")) != "shock":
            return
        until = getattr(self, "_global_risk_until", None)
        if isinstance(until, datetime.datetime) and now_dt >= until:
            self._set_global_risk_mode("normal", None, reason="shock_cooldown_expired")
    def _update_shock_mode(self, market_key: str, now_dt: Optional[datetime.datetime] = None):
        now = now_dt or datetime.datetime.now()
        cfg = getattr(self, "config", None)
        if cfg is None or not bool(getattr(cfg, "use_shock_guard", True)):
            self._maybe_release_global_risk_mode(now)
            return
        series = self._get_index_series(market_key)
        if not series:
            self._maybe_release_global_risk_mode(now)
            return

        now_ts = now.timestamp()
        ret_1m = self._series_return_pct(series, 60, now_ts)
        ret_5m = self._series_return_pct(series, 300, now_ts)
        shock_1m = float(getattr(cfg, "shock_1m_pct", getattr(Config, "DEFAULT_SHOCK_1M_PCT", 1.5)))
        shock_5m = float(getattr(cfg, "shock_5m_pct", getattr(Config, "DEFAULT_SHOCK_5M_PCT", 2.8)))
        if abs(ret_1m) >= shock_1m or abs(ret_5m) >= shock_5m:
            cooldown_min = max(1, int(getattr(cfg, "shock_cooldown_min", getattr(Config, "DEFAULT_SHOCK_COOLDOWN_MIN", 10))))
            until = now + datetime.timedelta(minutes=cooldown_min)
            self._set_global_risk_mode("shock", until, reason=f"{market_key} ret1m={ret_1m:.2f}% ret5m={ret_5m:.2f}%")
        else:
            self._maybe_release_global_risk_mode(now)
    def _probe_market_status_support(self):
        if bool(getattr(self, "_market_status_probe_done", False)):
            return
        self._market_status_probe_done = True
        rest_client = getattr(self, "rest_client", None)
        getter = getattr(rest_client, "get_market_status", None)
        if not callable(getter):
            self._official_market_status_available = False
            self._log_once("market_status_probe", "[시장상태] 공식 상태연동 미지원, 가격기반 프록시로 동작합니다.")
            return
        try:
            payload = getter() or {}
            self._official_market_status_available = bool(payload)
            if not self._official_market_status_available:
                self._log_once("market_status_probe", "[시장상태] 공식 상태 응답 없음, 가격기반 프록시로 폴백합니다.")
        except Exception as exc:
            self._official_market_status_available = False
            self._log_once("market_status_probe", f"[시장상태] 공식 상태연동 실패({exc}), 가격기반 프록시로 폴백합니다.")
    def _apply_market_state(self, info: Dict[str, Any], state: str, now_dt: datetime.datetime):
        prev_state = str(info.get("market_state", "normal") or "normal")
        next_state = str(state or "normal")
        if next_state == "normal":
            info["market_state"] = "normal"
            info["market_state_until"] = None
            return

        if next_state in {"vi", "halt"}:
            info["market_state"] = next_state
            info["market_state_until"] = None
            return

        if next_state == "reopen_cooldown":
            cfg = getattr(self, "config", None)
            cooldown_min = max(
                1,
                int(
                    getattr(
                        cfg,
                        "vi_cooldown_min",
                        getattr(Config, "DEFAULT_VI_COOLDOWN_MIN", 7),
                    )
                ),
            )
            info["market_state"] = "reopen_cooldown"
            info["market_state_until"] = now_dt + datetime.timedelta(minutes=cooldown_min)
            return

        if prev_state != next_state:
            info["market_state"] = next_state
    def _update_market_state_from_execution(
        self, code: str, info: Dict[str, Any], data: Any, now_dt: Optional[datetime.datetime] = None
    ):
        now = now_dt or datetime.datetime.now()
        cfg = getattr(self, "config", None)
        if cfg is None or not bool(getattr(cfg, "use_vi_guard", True)):
            info["market_state"] = "normal"
            info["market_state_until"] = None
            return

        tick_map = getattr(self, "_recent_ticks_by_code", None)
        if not isinstance(tick_map, dict):
            tick_map = {}
            self._recent_ticks_by_code = tick_map
        series = tick_map.get(code)
        if not isinstance(series, deque):
            series = deque(maxlen=1800)
            tick_map[code] = series

        current = int(info.get("current", 0) or 0)
        if current > 0:
            series.append((now.timestamp(), current))

        status_text = str(getattr(data, "trading_status", "") or "").upper()
        event_text = str(getattr(data, "market_event", "") or "").upper()
        state = str(info.get("market_state", "normal") or "normal")
        state_until = info.get("market_state_until")
        if state == "reopen_cooldown" and isinstance(state_until, datetime.datetime) and now >= state_until:
            state = "normal"
            info["market_state"] = "normal"
            info["market_state_until"] = None

        official_halt = any(token in status_text for token in ("HALT", "STOP", "SUSPEND")) or "HALT" in event_text
        official_vi = any(token in status_text for token in ("VI", "VOLATILITY")) or "VI" in event_text

        if official_halt:
            self._apply_market_state(info, "halt", now)
            return
        if official_vi:
            self._apply_market_state(info, "vi", now)
            return

        vi_proxy_1m = float(getattr(cfg, "vi_proxy_1m_pct", getattr(Config, "DEFAULT_VI_PROXY_1M_PCT", 4.0)))
        vi_proxy_spread = float(
            getattr(cfg, "vi_proxy_spread_pct", getattr(Config, "DEFAULT_VI_PROXY_SPREAD_PCT", 1.2))
        )
        ret_1m_code = abs(self._code_return_pct(series, 60, now.timestamp()))
        spread_pct = abs(self._calc_spread_pct(info))
        proxy_vi = (ret_1m_code >= vi_proxy_1m) or (spread_pct >= vi_proxy_spread)

        current_state = str(info.get("market_state", "normal") or "normal")
        if proxy_vi:
            self._apply_market_state(info, "vi", now)
            return

        if current_state == "vi":
            self._apply_market_state(info, "reopen_cooldown", now)
            return
        if current_state == "halt":
            self._apply_market_state(info, "reopen_cooldown", now)
            return
    def _start_index_feed(self, codes: List[str]):
        self._probe_market_status_support()
        ws_client = getattr(self, "ws_client", None)
        if ws_client is None:
            return
        index_codes = list(getattr(Config, "DEFAULT_INDEX_CODES", ["001", "101"]))
        try:
            set_on_index = getattr(ws_client, "set_on_index", None)
            if callable(set_on_index):
                set_on_index(self._on_index_tick)
            subscribe_index = getattr(ws_client, "subscribe_index", None)
            if callable(subscribe_index):
                subscribe_index(index_codes, self._on_index_tick)
                self._index_feed_codes = index_codes
                self._log_once("index_feed", f"[인덱스] 실시간 지수 구독 시작: {', '.join(index_codes)}")
        except Exception as exc:
            self._log_once("index_feed_fail", f"[인덱스] 구독 실패({exc}), 종목 프록시 기반 감지만 유지합니다.")
    def _stop_index_feed(self):
        ws_client = getattr(self, "ws_client", None)
        index_codes = list(getattr(self, "_index_feed_codes", []))
        if ws_client is not None and index_codes:
            try:
                ws_client.unsubscribe(index_codes)
            except Exception:
                pass
        self._index_feed_codes = []
        mapping = getattr(self, "_index_ticks_by_market", None)
        if isinstance(mapping, dict):
            mapping.clear()
        fallback_map = getattr(self, "_shock_fallback_rep_by_market", None)
        if isinstance(fallback_map, dict):
            fallback_map.clear()
    def _on_index_tick(self, tick):
        try:
            code = str(getattr(tick, "code", "") or "")
            value = float(getattr(tick, "value", 0) or 0)
            if value <= 0:
                return
            market_key = self._market_key_from_index_code(code)
            series = self._get_index_series(market_key)
            series.append((time.time(), value))
            self._update_shock_mode(market_key)
        except Exception:
            return
