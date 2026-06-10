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


class TradingSessionExternalFlowMixin(TraderMixinBase):
    def _set_external_disabled_state(self, codes: List[str]):
        for code in codes:
            info = self.universe.get(code)
            if not info:
                continue
            info["external_status"] = "disabled"
            info["external_error"] = "external_data_disabled"
            self._dirty_codes.add(code)
        if codes and not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    @staticmethod
    def _to_int_safe(value, default: int = 0) -> int:
        try:
            if value is None:
                return default
            text = str(value).strip().replace(",", "")
            if not text:
                return default
            return int(float(text))
        except (ValueError, TypeError):
            return default
    def _is_external_data_fresh(self, code: str, now_ts: Optional[float] = None) -> bool:
        if not code or code not in self.universe:
            return False
        info = self.universe.get(code, {})
        updated_at = info.get("external_updated_at")
        if not isinstance(updated_at, datetime.datetime):
            return False
        if str(info.get("external_status", "")).lower() == "error":
            return False
        ts = now_ts if now_ts is not None else time.time()
        age_sec = ts - updated_at.timestamp()
        return age_sec <= float(getattr(Config, "EXTERNAL_FLOW_STALE_SEC", 30))
    def _request_external_refresh(self, code: str, reason: str = "on_demand", force: bool = False) -> bool:
        if not code:
            return False
        return self._request_external_refresh_batch([code], reason=reason, force=force)
    def _request_external_refresh_batch(
        self, codes: List[str], reason: str = "periodic", force: bool = False
    ) -> bool:
        if not codes:
            return False
        rest_client = getattr(self, "rest_client", None)
        current_account = getattr(self, "current_account", "")
        if not (rest_client and current_account):
            return False
        if not self._external_data_enabled():
            self._set_external_disabled_state([c for c in codes if c in self.universe])
            return False

        now_ts = time.time()
        debounce_sec = float(getattr(Config, "EXTERNAL_FLOW_ON_DEMAND_DEBOUNCE_SEC", 5))
        inflight = getattr(self, "_external_refresh_inflight", set())
        selected_codes: List[str] = []
        for code in codes:
            if code not in self.universe:
                continue
            if code in inflight:
                continue
            last_ts = float(getattr(self, "_external_last_fetch_ts", {}).get(code, 0.0))
            if not force and (now_ts - last_ts) < debounce_sec:
                continue
            selected_codes.append(code)

        if not selected_codes:
            return False

        for code in selected_codes:
            inflight.add(code)
            info = self.universe.get(code, {})
            if info.get("external_status") != "fresh":
                info["external_status"] = "refreshing"
                self._dirty_codes.add(code)

        if not hasattr(self, "_external_refresh_inflight"):
            self._external_refresh_inflight = set(inflight)
        if not hasattr(self, "_external_last_fetch_ts") or not isinstance(self._external_last_fetch_ts, dict):
            self._external_last_fetch_ts = {}

        if not hasattr(self, "threadpool"):
            try:
                payload = self._fetch_external_flow_worker(selected_codes)
                self._on_external_flow_result(selected_codes, payload)
            except Exception as exc:
                self._on_external_flow_error(selected_codes, exc)
            return True

        worker = Worker(self._fetch_external_flow_worker, selected_codes)
        worker.signals.result.connect(
            lambda payload, requested=selected_codes: self._on_external_flow_result(requested, payload)
        )
        worker.signals.error.connect(
            lambda error, requested=selected_codes: self._on_external_flow_error(requested, error)
        )
        self.threadpool.start(worker)
        return True
    def _fetch_external_flow_worker(self, codes: List[str]) -> Dict[str, Dict]:
        payload: Dict[str, Dict] = {}
        for code in codes:
            investor = {}
            program = {}
            errors: List[str] = []
            try:
                investor = self.rest_client.get_investor_trading(code) or {}
            except Exception as exc:
                errors.append(f"investor:{exc}")
            try:
                program = self.rest_client.get_program_trading(code) or {}
            except Exception as exc:
                errors.append(f"program:{exc}")
            payload[code] = {
                "investor": investor if isinstance(investor, dict) else {},
                "program": program if isinstance(program, dict) else {},
                "error": "; ".join(errors),
            }
        return payload
    def _on_external_flow_result(self, requested_codes: List[str], payload: Dict[str, Dict]):
        now_dt = datetime.datetime.now()
        now_ts = now_dt.timestamp()
        inflight = getattr(self, "_external_refresh_inflight", set())
        fetch_ts = getattr(self, "_external_last_fetch_ts", {})
        for code in requested_codes:
            inflight.discard(code)
            info = self.universe.get(code)
            if not info:
                continue
            row = payload.get(code, {}) if isinstance(payload, dict) else {}
            investor = row.get("investor", {}) if isinstance(row, dict) else {}
            program = row.get("program", {}) if isinstance(row, dict) else {}
            error = str(row.get("error", "") or "") if isinstance(row, dict) else ""
            if error or (not investor and not program):
                info["external_status"] = "error"
                info["external_error"] = error or "empty_external_response"
                if isinstance(fetch_ts, dict):
                    fetch_ts[code] = now_ts
                self._log_once(
                    f"external_error:{code}",
                    f"[외부데이터] {info.get('name', code)} 수집 실패: {info['external_error']}",
                )
            else:
                investor_net = (
                    self._to_int_safe(investor.get("individual_net", 0))
                    + self._to_int_safe(investor.get("foreign_net", 0))
                    + self._to_int_safe(investor.get("institution_net", 0))
                )
                program_net = self._to_int_safe(program.get("net", 0))
                info["investor_net"] = investor_net
                info["program_net"] = program_net
                info["external_updated_at"] = now_dt
                info["external_status"] = "fresh"
                info["external_error"] = ""
                if isinstance(fetch_ts, dict):
                    fetch_ts[code] = now_ts
            self._dirty_codes.add(code)

        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    def _on_external_flow_error(self, requested_codes: List[str], error: Exception):
        now_ts = time.time()
        fetch_ts = getattr(self, "_external_last_fetch_ts", {})
        inflight = getattr(self, "_external_refresh_inflight", set())
        for code in requested_codes:
            inflight.discard(code)
            info = self.universe.get(code)
            if not info:
                continue
            info["external_status"] = "error"
            info["external_error"] = str(error)
            if isinstance(fetch_ts, dict):
                fetch_ts[code] = now_ts
            self._dirty_codes.add(code)
            self._log_once(
                f"external_error:{code}",
                f"[외부데이터] {info.get('name', code)} 수집 실패: {error}",
            )
        if requested_codes and not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
    def _on_external_refresh_timer(self):
        if not self.is_running:
            return
        codes = list(self.universe.keys())
        if codes:
            self._request_external_refresh_batch(codes, reason="periodic", force=True)
    def _start_external_refresh_loop(self, codes: List[str]):
        if not self._external_data_enabled():
            self._set_external_disabled_state(codes)
            return

        if codes:
            self._request_external_refresh_batch(codes, reason="startup", force=True)

        if not hasattr(self, "threadpool"):
            return

        if not hasattr(self, "_external_refresh_timer") or self._external_refresh_timer is None:
            try:
                self._external_refresh_timer = QTimer(self)
            except TypeError:
                self._external_refresh_timer = QTimer()
            self._external_refresh_timer.timeout.connect(self._on_external_refresh_timer)
        refresh_sec = max(1, int(getattr(Config, "EXTERNAL_FLOW_REFRESH_SEC", 10)))
        self._external_refresh_timer.setInterval(refresh_sec * 1000)

        if codes and not self._external_refresh_timer.isActive():
            self._external_refresh_timer.start()
    def _stop_external_refresh_loop(self):
        timer = getattr(self, "_external_refresh_timer", None)
        if timer is not None:
            timer.stop()
        if hasattr(self, "_external_refresh_inflight"):
            self._external_refresh_inflight.clear()
        if hasattr(self, "_external_last_fetch_ts") and isinstance(self._external_last_fetch_ts, dict):
            self._external_last_fetch_ts.clear()
