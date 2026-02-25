"""Trading session lifecycle mixin for KiwoomProTrader."""

import datetime
import time
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem

from app.support.worker import Worker
from config import Config


class TradingSessionMixin:
    def _rollover_daily_metrics(self, now: Optional[datetime.datetime] = None, reset_baseline: bool = False):
        now_dt = now or datetime.datetime.now()
        today = now_dt.date()
        current_day = getattr(self, "_trading_day", None)
        if current_day != today:
            self._trading_day = today
            self.daily_realized_profit = 0
            self.daily_initial_deposit = 0
            self.daily_loss_triggered = False

        if reset_baseline and int(getattr(self, "daily_initial_deposit", 0) or 0) <= 0:
            cfg = getattr(self, "config", None)
            basis = str(getattr(cfg, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")))
            if basis == "total_equity":
                baseline = int(getattr(self, "total_equity", 0) or 0) or int(getattr(self, "deposit", 0) or 0)
            else:
                baseline = int(getattr(self, "deposit", 0) or 0)
            if baseline <= 0:
                baseline = int(getattr(self, "initial_deposit", 0) or 0)
            if baseline > 0:
                self.daily_initial_deposit = baseline

    def _strategy_primary_id(self) -> str:
        cfg = getattr(self, "config", None)
        pack = getattr(cfg, "strategy_pack", {}) if cfg is not None else {}
        if isinstance(pack, dict):
            return str(pack.get("primary_strategy", "volatility_breakout"))
        return "volatility_breakout"

    def _external_data_enabled(self) -> bool:
        cfg = getattr(self, "config", None)
        flags = getattr(cfg, "feature_flags", {}) if cfg is not None else {}
        if not isinstance(flags, dict):
            flags = {}
        return bool(flags.get("enable_external_data", True))

    def _log_once(self, key: str, message: str):
        cooldown_map = getattr(self, "_log_cooldown_map", None)
        if cooldown_map is None:
            cooldown_map = {}
            self._log_cooldown_map = cooldown_map
        now_ts = time.time()
        last_ts = float(cooldown_map.get(key, 0.0))
        if now_ts - last_ts >= float(getattr(Config, "LOG_DEDUP_SEC", 30)):
            self.log(message)
            cooldown_map[key] = now_ts

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

    @staticmethod
    def _time_strategy_phase(now_dt: Optional[datetime.datetime] = None) -> str:
        now = now_dt or datetime.datetime.now()
        minute_of_day = now.hour * 60 + now.minute
        if minute_of_day < (9 * 60 + 30):
            return "aggressive"
        if minute_of_day < (14 * 60 + 30):
            return "normal"
        return "conservative"

    def _maybe_recalculate_time_strategy_targets(self, now_dt: Optional[datetime.datetime] = None):
        cfg = getattr(self, "config", None)
        if not (self.is_running and cfg is not None and bool(getattr(cfg, "use_time_strategy", False))):
            self._last_time_strategy_phase = None
            return
        if not self.universe:
            return
        phase = self._time_strategy_phase(now_dt)
        if phase == getattr(self, "_last_time_strategy_phase", None):
            return
        self._last_time_strategy_phase = phase
        for code in self.universe.keys():
            self.universe[code]["target"] = self.strategy.calculate_target_price(code)
            self._dirty_codes.add(code)
        self.log(f"[시간전략] 구간 전환({phase})으로 목표가 재계산: {len(self.universe)}종목")
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()

    def _sync_positions_snapshot(self, codes: List[str]) -> Tuple[bool, str]:
        """매매 시작 직후 계좌 포지션 스냅샷을 유니버스에 강제 반영한다."""
        if not (self.rest_client and self.current_account):
            return False, "계좌 동기화에 필요한 API/계좌 정보가 준비되지 않았습니다."

        try:
            positions = self.rest_client.get_positions(self.current_account)
        except Exception as exc:
            return False, f"계좌 포지션 조회 실패: {exc}"

        if positions is None:
            return False, "계좌 포지션 조회 실패: 응답이 비어 있습니다."

        if hasattr(self, "strategy"):
            self.strategy.reset_tracking()

        positions_by_code = {getattr(pos, "code", ""): pos for pos in positions or []}
        universe_codes = set(codes)
        now = datetime.datetime.now()

        for code in codes:
            info = self.universe.get(code, {})
            matched = positions_by_code.get(code)
            if matched:
                held = max(0, int(getattr(matched, "quantity", 0)))
                buy_price = int(getattr(matched, "buy_price", 0))
                invest_amount = int(getattr(matched, "buy_amount", 0))
            else:
                held = 0
                buy_price = 0
                invest_amount = 0

            info["held"] = held
            info["buy_price"] = buy_price
            info["invest_amount"] = invest_amount

            if held > 0:
                info["status"] = "holding"
                info["buy_time"] = now
                info["cooldown_until"] = None
                if hasattr(self, "strategy") and invest_amount > 0:
                    self.strategy.update_market_investment(code, invest_amount, is_buy=True)
                    self.strategy.update_sector_investment(code, invest_amount, is_buy=True)
            else:
                info["status"] = "watch"
                info["buy_time"] = None
                info["max_profit_rate"] = 0
                info["partial_profit_levels"] = set()

            if hasattr(self, "_sync_failed_codes"):
                self._sync_failed_codes.discard(code)
            diag_touch = getattr(self, "_diag_touch", None)
            if callable(diag_touch):
                diag_touch(code, sync_status=str(info.get("status", "")), retry_count=0, last_sync_error="")

        external_codes = sorted(c for c in positions_by_code.keys() if c and c not in universe_codes)
        if external_codes:
            preview = ", ".join(external_codes[:5])
            suffix = " ..." if len(external_codes) > 5 else ""
            self.log(f"유니버스 외 보유 종목 감지(자동청산 제외): {preview}{suffix}")

        self._holding_or_pending_count = sum(
            1 for code in codes if int(self.universe.get(code, {}).get("held", 0)) > 0
        )
        self._dirty_codes.update(codes)
        if not hasattr(self, "_ui_flush_timer"):
            self.sig_update_table.emit()
        return True, ""

    def start_trading(self):
        if self.is_running:
            self.log("자동매매가 이미 실행 중입니다.")
            return

        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 API를 연결해주세요.")
            return

        raw_codes = [c.strip() for c in self.input_codes.text().split(",") if c.strip()]
        if not raw_codes:
            QMessageBox.warning(self, "경고", "감시 종목 코드를 입력해주세요.")
            return

        valid_codes: List[str] = []
        invalid_codes: List[str] = []
        seen = set()
        for code in raw_codes:
            if len(code) == 6 and code.isdigit():
                if code not in seen:
                    seen.add(code)
                    valid_codes.append(code)
            else:
                invalid_codes.append(code)

        if invalid_codes:
            preview = ", ".join(invalid_codes[:5])
            suffix = " ..." if len(invalid_codes) > 5 else ""
            self.log(f"잘못된 종목코드 제외: {preview}{suffix}")
            QMessageBox.warning(
                self,
                "경고",
                f"6자리 숫자 종목코드만 허용됩니다.\n제외된 코드: {preview}{suffix}",
            )

        if not valid_codes:
            QMessageBox.warning(self, "경고", "유효한 6자리 종목코드를 입력해주세요.")
            return

        if not self._confirm_live_trading_guard():
            return

        # Keep live routing constrained to KR stock long path in phase-1.
        cfg = getattr(self, "config", None)
        is_mock = bool(hasattr(self, "chk_mock") and self.chk_mock.isChecked())
        if cfg is not None and not is_mock:
            if str(getattr(cfg, "asset_scope", "kr_stock_live")) != "kr_stock_live":
                QMessageBox.warning(
                    self,
                    "실주문 범위 제한",
                    "실주문은 현재 `kr_stock_live` 범위만 지원합니다. 모의/백테스트 모드를 사용하세요.",
                )
                return
            if bool(getattr(cfg, "short_enabled", False)):
                QMessageBox.warning(
                    self,
                    "실주문 숏 제한",
                    "숏 포지션은 현재 백테스트/시뮬레이션에서만 지원합니다.",
                )
                return
            primary = self._strategy_primary_id()
            capabilities = getattr(Config, "STRATEGY_CAPABILITIES", {})
            cap = capabilities.get(primary)
            if not cap or not bool(cap.get("live_supported", False)):
                supported = sorted(
                    k for k, v in capabilities.items() if isinstance(v, dict) and bool(v.get("live_supported", False))
                )
                supported_text = ", ".join(supported) if supported else "(none)"
                self.log(f"[전략가드] 실거래 미지원 전략 차단: {primary}")
                QMessageBox.warning(
                    self,
                    "실거래 전략 제한",
                    f"선택 전략 `{primary}` 은(는) 실거래를 지원하지 않습니다.\n허용 전략: {supported_text}",
                )
                return

        try:
            self._rollover_daily_metrics(reset_baseline=True)
            self.daily_loss_triggered = False
            self.time_liquidate_executed = False
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_emergency.setEnabled(True)
            if hasattr(self, "_sync_failed_codes"):
                self._sync_failed_codes.clear()

            # 테스트 하네스(스레드풀 없음)에서는 기존 동기 경로 유지
            if not hasattr(self, "threadpool"):
                initialized_codes = self._init_universe(valid_codes)
                if not initialized_codes:
                    raise RuntimeError("유니버스 초기화에 성공한 종목이 없습니다.")
                synced, reason = self._sync_positions_snapshot(initialized_codes)
                if not synced:
                    raise RuntimeError(reason)
                if cfg is not None and bool(getattr(cfg, "use_time_strategy", False)):
                    self._last_time_strategy_phase = self._time_strategy_phase()
                else:
                    self._last_time_strategy_phase = None
                self._start_external_refresh_loop(initialized_codes)
                if self.ws_client:
                    self.ws_client.connect()
                    self.ws_client.subscribe_execution(initialized_codes, self._on_realtime)
                    self.ws_client.subscribe_order_execution(self._on_order_realtime)
                self.is_running = True
                self.log(f"매매 시작 - {len(initialized_codes)}개 종목")
                if self.telegram:
                    self.telegram.send(f"매매 시작\n종목: {', '.join(initialized_codes)}")
                return

            self.log(f"유니버스 초기화 중... ({len(valid_codes)}개 종목)")
            worker = Worker(self._init_universe, valid_codes, True)

            def on_result(payload: Tuple[List[str], Dict[str, Dict], List[str]]):
                try:
                    initialized_codes, universe, failed_codes = payload
                    if not initialized_codes:
                        raise RuntimeError("유니버스 초기화에 성공한 종목이 없습니다.")

                    self.universe = universe
                    self.table.setRowCount(len(initialized_codes))
                    self._code_to_row = {code: idx for idx, code in enumerate(initialized_codes)}
                    self._holding_or_pending_count = 0

                    for code in initialized_codes:
                        self.universe[code]["target"] = self.strategy.calculate_target_price(code)

                    synced, reason = self._sync_positions_snapshot(initialized_codes)
                    if not synced:
                        raise RuntimeError(reason)
                    if cfg is not None and bool(getattr(cfg, "use_time_strategy", False)):
                        self._last_time_strategy_phase = self._time_strategy_phase()
                    else:
                        self._last_time_strategy_phase = None
                    self._start_external_refresh_loop(initialized_codes)

                    self._dirty_codes.update(initialized_codes)
                    self.sig_update_table.emit()

                    if failed_codes:
                        self.log(f"{len(failed_codes)}개 종목 초기화 실패: {', '.join(failed_codes)}")

                    if self.ws_client:
                        self.ws_client.connect()
                        self.ws_client.subscribe_execution(initialized_codes, self._on_realtime)
                        self.ws_client.subscribe_order_execution(self._on_order_realtime)

                    self.is_running = True
                    self.log(f"매매 시작 - {len(initialized_codes)}개 종목")
                    if self.telegram:
                        self.telegram.send(f"매매 시작\n종목: {', '.join(initialized_codes)}")
                except Exception as exc:
                    self.stop_trading()
                    self.log(f"매매 시작 실패: {exc}")
                    QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{exc}")

            def on_error(exc):
                self.stop_trading()
                self.log(f"매매 시작 실패: {exc}")
                QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{exc}")

            worker.signals.result.connect(on_result)
            worker.signals.error.connect(on_error)
            self.threadpool.start(worker)
        except Exception as exc:
            self.stop_trading()
            self.log(f"매매 시작 실패: {exc}")
            QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{exc}")

    def stop_trading(self):
        was_running = self.is_running
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_emergency.setEnabled(False)
        self.schedule_started = False
        self._position_sync_pending.clear()
        if hasattr(self, "_position_sync_batch"):
            self._position_sync_batch.clear()
        if hasattr(self, "_position_sync_scheduled"):
            self._position_sync_scheduled = False
        if hasattr(self, "_position_sync_retry_count"):
            self._position_sync_retry_count = 0
        self._pending_order_state.clear()
        if hasattr(self, "_manual_pending_state"):
            self._manual_pending_state.clear()
        self._last_exec_event.clear()
        self._last_time_strategy_phase = None
        self._stop_external_refresh_loop()
        release_all_reserved = getattr(self, "_release_all_reserved_cash", None)
        if callable(release_all_reserved):
            released_total = int(release_all_reserved(reason="STOP_TRADING") or 0)
            if released_total > 0 and hasattr(self, "log"):
                self.log(f"Reserved cash reconciled on stop: +{released_total:,}")

        try:
            if self.ws_client:
                self.ws_client.unsubscribe_all()
                self.ws_client.disconnect()
        except Exception as exc:
            self.log(f"WebSocket 종료 중 오류: {exc}")

        if was_running:
            self.log("매매 중지")
            if self.telegram:
                self.telegram.send("매매 중지")

    def _time_liquidate(self):
        """장마감 시간 청산."""
        liquidated_count = 0
        for code, info in self.universe.items():
            held = info.get("held", 0)
            if held > 0:
                name = info.get("name", code)
                current = info.get("current", 0)
                self.log(f"시간 청산 시작: {name} {held}주")
                self._execute_sell(code, held, current, "시간청산")
                liquidated_count += 1

        if liquidated_count > 0:
            self.log(f"시간 청산 완료: {liquidated_count}개 종목")
            if self.telegram:
                self.telegram.send(f"장마감 청산: {liquidated_count}개 종목")

    def _init_universe(self, codes, background: bool = False):
        target_universe: Dict[str, Dict] = {}
        failed_codes = []
        initialized_codes = []

        for code in codes:
            try:
                if not self.rest_client:
                    continue
                quote = self.rest_client.get_stock_quote(code)
                if not quote:
                    failed_codes.append(code)
                    self.log(f"{code} 시세 조회 실패")
                    continue

                price_history = []
                daily_prices = []
                minute_prices = []
                high_history = []
                low_history = []
                volume_history = []
                value_history = []
                prev_high = quote.high_price
                prev_low = quote.low_price

                try:
                    daily = self.rest_client.get_daily_chart(code, 60)
                    if daily:
                        normalized_daily = list(reversed(daily))
                        for candle in normalized_daily:
                            price_history.append(candle.close_price)
                            daily_prices.append(candle.close_price)
                            high_history.append(candle.high_price)
                            low_history.append(candle.low_price)
                            volume_history.append(candle.volume)
                            value_history.append(candle.volume * candle.close_price)
                        ref_idx = 1 if len(daily) > 1 else 0
                        prev_high = daily[ref_idx].high_price
                        prev_low = daily[ref_idx].low_price
                except Exception as chart_err:
                    self.log(f"{code} 일봉 로드 실패: {chart_err}")

                try:
                    minute = self.rest_client.get_minute_chart(code, 1, 60)
                    if minute:
                        minute_prices = [candle.close_price for candle in reversed(minute)]
                except Exception as minute_err:
                    self.log(f"{code} 분봉 로드 실패: {minute_err}")

                if not minute_prices:
                    minute_prices = list(price_history[-60:]) if price_history else [quote.current_price]

                avg_volume_5 = int(sum(volume_history[-5:]) / 5) if len(volume_history) >= 5 else 0
                avg_volume_20 = int(sum(volume_history[-20:]) / 20) if len(volume_history) >= 20 else (
                    int(sum(volume_history) / len(volume_history)) if volume_history else 0
                )
                avg_value_20 = int(sum(value_history[-20:]) / 20) if len(value_history) >= 20 else (
                    int(sum(value_history) / len(value_history)) if value_history else 0
                )

                target_universe[code] = {
                    "name": quote.name,
                    "current": quote.current_price,
                    "open": quote.open_price,
                    "high": quote.high_price,
                    "low": quote.low_price,
                    "prev_close": quote.prev_close,
                    "prev_high": prev_high,
                    "prev_low": prev_low,
                    "daily_prices": daily_prices if daily_prices else list(price_history),
                    "minute_prices": minute_prices,
                    "market_type": quote.market_type,
                    "sector": quote.sector or "기타",
                    "target": 0,
                    "held": 0,
                    "buy_price": 0,
                    "max_profit_rate": 0,
                    "status": "watch",
                    "price_history": price_history,
                    "high_history": high_history,
                    "low_history": low_history,
                    "volume_history": volume_history,
                    "current_volume": quote.volume,
                    "avg_volume_5": avg_volume_5,
                    "avg_volume_20": avg_volume_20,
                    "avg_value_20": avg_value_20,
                    "ask_price": quote.ask_price,
                    "bid_price": quote.bid_price,
                    "breakout_hits": 0,
                    "cooldown_until": None,
                    "buy_time": None,
                    "partial_profit_levels": set(),
                    "investor_net": 0,
                    "program_net": 0,
                    "external_updated_at": None,
                    "external_status": "idle",
                    "external_error": "",
                }
                diag_touch = getattr(self, "_diag_touch", None)
                if callable(diag_touch):
                    diag_touch(code, sync_status="watch", retry_count=0, last_sync_error="")

                if not background:
                    self.universe = target_universe
                    target_universe[code]["target"] = self.strategy.calculate_target_price(code)

                initialized_codes.append(code)
            except Exception as exc:
                failed_codes.append(code)
                self.log(f"{code} 초기화 오류: {exc}")

        if background:
            return initialized_codes, target_universe, failed_codes

        self.universe = target_universe
        self.table.setRowCount(len(initialized_codes))
        self._code_to_row = {code: idx for idx, code in enumerate(initialized_codes)}
        self._holding_or_pending_count = 0
        self._dirty_codes.update(initialized_codes)
        self.sig_update_table.emit()

        if failed_codes:
            self.log(f"{len(failed_codes)}개 종목 초기화 실패: {', '.join(failed_codes)}")

        return initialized_codes

    def _update_row(self, row, code):
        if row < 0:
            return
        info = self.universe.get(code, {})
        profit_rate = 0.0
        if info.get("held", 0) > 0 and info.get("buy_price", 0) > 0:
            profit_rate = (info["current"] - info["buy_price"]) / info["buy_price"] * 100

        data = [
            info.get("name", code),
            f"{info.get('current', 0):,}",
            f"{info.get('target', 0):,}",
            info.get("status", ""),
            str(info.get("held", 0)),
            f"{info.get('buy_price', 0):,}",
            f"{profit_rate:.2f}%",
            f"{info.get('max_profit_rate', 0):.2f}%",
            f"{info.get('invest_amount', 0):,}",
        ]
        for col, text in enumerate(data):
            text_str = str(text)
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem(text_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
            elif item.text() != text_str:
                item.setText(text_str)

            if col == 6:
                if profit_rate > 0:
                    item.setForeground(QColor("#e63946"))
                elif profit_rate < 0:
                    item.setForeground(QColor("#4361ee"))

    def _refresh_table(self):
        if not self.universe or not self._dirty_codes:
            return

        if "__all__" in self._dirty_codes:
            codes_to_update = list(self.universe.keys())
            self._dirty_codes.clear()
        else:
            codes_to_update = []
            limit = max(1, int(Config.TABLE_BATCH_LIMIT))
            while self._dirty_codes and len(codes_to_update) < limit:
                code = self._dirty_codes.pop()
                if code in self.universe:
                    codes_to_update.append(code)

        if not codes_to_update:
            return

        if len(self._code_to_row) != len(self.universe):
            self.table.setRowCount(len(self.universe))
            self._code_to_row = {code: idx for idx, code in enumerate(self.universe.keys())}

        self.table.setUpdatesEnabled(False)
        try:
            for code in codes_to_update:
                row = self._code_to_row.get(code)
                if row is None:
                    self._code_to_row = {c: idx for idx, c in enumerate(self.universe.keys())}
                    row = self._code_to_row.get(code)
                if row is not None:
                    self._update_row(row, code)
        finally:
            self.table.setUpdatesEnabled(True)

    def _emergency_liquidate(self):
        """긴급 전체 청산."""
        if not self.is_connected:
            self.log("API 연결 필요")
            return

        holding_count = sum(1 for info in self.universe.values() if info.get("held", 0) > 0)
        if holding_count == 0:
            QMessageBox.information(self, "알림", "청산할 보유 종목이 없습니다.")
            return

        confirm = QMessageBox.warning(
            self,
            "긴급 청산 확인",
            f"보유 중인 {holding_count}개 종목을 모두 시장가로 청산합니다.\n\n"
            "이 작업은 되돌릴 수 없습니다.\n정말 실행하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self.log("긴급 전체 청산 시작")
            liquidated_count = 0
            for code, info in self.universe.items():
                held = info.get("held", 0)
                if held > 0:
                    name = info.get("name", code)
                    current = info.get("current", 0)
                    self.log(f"  - {name} {held}주 청산 중...")
                    self._execute_sell(code, held, current, "긴급청산")
                    liquidated_count += 1

            if self.sound:
                self.sound.play_warning()
            if self.telegram:
                self.telegram.send(f"긴급 전체 청산: {liquidated_count}개 종목")

            self.log(f"긴급 청산 완료: {liquidated_count}개 종목")
