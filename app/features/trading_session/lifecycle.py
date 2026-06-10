"""Trading session lifecycle mixin for KiwoomProTrader."""

from collections import deque
import datetime
import time
from typing import Any, Deque, Dict, List, Literal, Optional, Tuple, cast, overload

from PyQt6.QtCore import QCoreApplication, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem

from app.support.worker import Worker
from config import Config
from app.mixins._typing import TraderMixinBase


BackgroundUniversePayload = Tuple[List[str], Dict[str, Dict[str, Any]], List[str]]


class TradingSessionLifecycleMixin(TraderMixinBase):
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

        self._apply_account_position_snapshot(
            codes,
            positions,
            reset_tracking=True,
            rebuild_strategy=True,
            log_external=True,
        )
        return True, ""
    def _log_trading_preflight(self, codes: List[str]) -> None:
        cfg = getattr(self, "config", None)
        execution_mode = str(getattr(cfg, "execution_mode", getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only")))
        is_mock = bool(hasattr(self, "chk_mock") and self.chk_mock.isChecked())
        intel_cfg = getattr(cfg, "market_intelligence", {}) if cfg is not None else {}
        source_policy = intel_cfg.get("source_policy", {}) if isinstance(intel_cfg, dict) and isinstance(intel_cfg.get("source_policy"), dict) else {}
        strict_intel = bool(source_policy.get("strict_entry_guard", False))
        rest_client = getattr(self, "rest_client", None)
        open_order_support = bool(getattr(rest_client, "supports_open_orders", False))
        account = str(getattr(self, "current_account", "") or "")
        ws_client = getattr(self, "ws_client", None)
        ws_ready = "ready" if ws_client is not None else "not_configured"
        self.log(
            "[preflight] "
            f"mode={execution_mode} api={'mock' if is_mock else 'live'} account={account or '-'} "
            f"codes={len(codes)} ws={ws_ready} intel_strict={strict_intel} "
            f"open_orders={'supported' if open_order_support else 'unsupported'}"
        )
        if execution_mode == "signal_only":
            self.log("[preflight] signal-only mode: broker order APIs will not be called.")
        if not open_order_support:
            self.log("[preflight] open-order recovery is unavailable until a verified Kiwoom REST endpoint is configured.")
    def start_trading(self, from_schedule: bool = False) -> bool:
        if self.is_running:
            self.log("자동매매가 이미 실행 중입니다.")
            return False
        if bool(getattr(self, "_trading_start_inflight", False)):
            self.log("자동매매 시작이 진행 중입니다.")
            return False

        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 API를 연결해주세요.")
            return False

        raw_codes = [c.strip() for c in self.input_codes.text().split(",") if c.strip()]
        if not raw_codes:
            QMessageBox.warning(self, "경고", "감시 종목 코드를 입력해주세요.")
            return False

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
            return False

        cfg = getattr(self, "config", None)
        primary = self._strategy_primary_id()
        unsupported = getattr(Config, "AUTOTRADING_UNSUPPORTED_STRATEGIES", set())
        if primary in unsupported:
            self.log(f"[전략가드] 자동매매 비지원 전략 차단: {primary}")
            QMessageBox.warning(
                self,
                "자동매매 전략 제한",
                f"선택 전략 `{primary}` 은(는) 현재 자동매매를 지원하지 않습니다.\n백테스트/연구 모드에서만 사용하세요.",
            )
            return False

        if cfg is not None and bool(getattr(cfg, "use_split", False)):
            policy = str(getattr(cfg, "execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market")))
            if policy != "limit":
                QMessageBox.warning(
                    self,
                    "분할 매수 제한",
                    "분할 매수는 현재 지정가 주문 방식에서만 지원합니다.\n주문 방식을 `지정가 우선`으로 바꿔주세요.",
                )
                return False

        if not self._confirm_live_trading_guard():
            return False

        self._log_trading_preflight(valid_codes)

        # Keep live routing constrained to KR stock long path in phase-1.
        is_mock = bool(hasattr(self, "chk_mock") and self.chk_mock.isChecked())
        if cfg is not None and not is_mock:
            if str(getattr(cfg, "asset_scope", "kr_stock_live")) != "kr_stock_live":
                QMessageBox.warning(
                    self,
                    "실주문 범위 제한",
                    "실주문은 현재 `kr_stock_live` 범위만 지원합니다. 모의/백테스트 모드를 사용하세요.",
                )
                return False
            if bool(getattr(cfg, "short_enabled", False)):
                QMessageBox.warning(
                    self,
                    "실주문 숏 제한",
                    "숏 포지션은 현재 백테스트/시뮬레이션에서만 지원합니다.",
                )
                return False
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
                return False

        try:
            self._trading_start_inflight = True
            self._scheduled_start_requested = bool(from_schedule)
            self._rollover_daily_metrics(reset_baseline=True)
            self.daily_loss_triggered = False
            self.time_liquidate_executed = False
            self._global_risk_mode = "normal"
            self._global_risk_until = None
            self._order_health_mode = "normal"
            self._order_health_until = None
            if hasattr(self, "_recent_ticks_by_code") and isinstance(self._recent_ticks_by_code, dict):
                self._recent_ticks_by_code.clear()
            if hasattr(self, "_guard_reason_by_code") and isinstance(self._guard_reason_by_code, dict):
                self._guard_reason_by_code.clear()
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_emergency.setEnabled(True)
            if hasattr(self, "_sync_failed_codes"):
                self._sync_failed_codes.clear()

            # 테스트 하네스(스레드풀 없음)에서는 기존 동기 경로 유지
            if not hasattr(self, "threadpool"):
                initialized_codes = cast(List[str], self._init_universe(valid_codes))
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
                start_market_intel = getattr(self, "_start_market_intelligence_loop", None)
                if callable(start_market_intel):
                    start_market_intel(initialized_codes)
                if self.ws_client:
                    self.ws_client.connect()
                    self.ws_client.subscribe_execution(initialized_codes, self._on_realtime)
                    self.ws_client.subscribe_order_execution(self._on_order_realtime)
                    self._start_index_feed(initialized_codes)
                self.is_running = True
                self.schedule_started = bool(getattr(self, "_scheduled_start_requested", False))
                self._scheduled_start_requested = False
                self._trading_start_inflight = False
                self.log(f"매매 시작 - {len(initialized_codes)}개 종목")
                if self.telegram:
                    self.telegram.send(f"매매 시작\n종목: {', '.join(initialized_codes)}")
                return True

            self.log(f"유니버스 초기화 중... ({len(valid_codes)}개 종목)")
            worker = Worker(self._init_universe, valid_codes, True)

            def on_result(payload: BackgroundUniversePayload):
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
                    start_market_intel = getattr(self, "_start_market_intelligence_loop", None)
                    if callable(start_market_intel):
                        start_market_intel(initialized_codes)

                    self._dirty_codes.update(initialized_codes)
                    self.sig_update_table.emit()

                    if failed_codes:
                        self.log(f"{len(failed_codes)}개 종목 초기화 실패: {', '.join(failed_codes)}")

                    if self.ws_client:
                        self.ws_client.connect()
                        self.ws_client.subscribe_execution(initialized_codes, self._on_realtime)
                        self.ws_client.subscribe_order_execution(self._on_order_realtime)
                        self._start_index_feed(initialized_codes)

                    self.is_running = True
                    self.schedule_started = bool(getattr(self, "_scheduled_start_requested", False))
                    self._scheduled_start_requested = False
                    self._trading_start_inflight = False
                    self.log(f"매매 시작 - {len(initialized_codes)}개 종목")
                    if self.telegram:
                        self.telegram.send(f"매매 시작\n종목: {', '.join(initialized_codes)}")
                except Exception as exc:
                    self._scheduled_start_requested = False
                    self._trading_start_inflight = False
                    self.stop_trading()
                    self.log(f"매매 시작 실패: {exc}")
                    QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{exc}")

            def on_error(exc):
                self._scheduled_start_requested = False
                self._trading_start_inflight = False
                self.stop_trading()
                self.log(f"매매 시작 실패: {exc}")
                QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{exc}")

            worker.signals.result.connect(on_result)
            worker.signals.error.connect(on_error)
            self.threadpool.start(worker)
            return True
        except Exception as exc:
            self._scheduled_start_requested = False
            self._trading_start_inflight = False
            self.stop_trading()
            self.log(f"매매 시작 실패: {exc}")
            QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{exc}")
            return False
    def stop_trading(self):
        was_running = self.is_running
        self._set_trading_stopped_state()

        def finalize_cleanup(cleanup_result):
            unresolved_codes = set(cleanup_result.get("unresolved_codes", [])) if isinstance(cleanup_result, dict) else set()
            release_all_reserved = getattr(self, "_release_all_reserved_cash", None)
            if callable(release_all_reserved) and not unresolved_codes:
                released = release_all_reserved(reason="STOP_TRADING")
                released_total = int(released) if isinstance(released, (int, float, str)) else 0
                if released_total > 0 and hasattr(self, "log"):
                    self.log(f"Reserved cash reconciled on stop: +{released_total:,}")

        async_started = False
        if not bool(getattr(self, "_shutdown_in_progress", False)):
            async_cleanup = getattr(self, "_cleanup_active_orders_async", None)
            if callable(async_cleanup):
                async_started = bool(async_cleanup("stop_trading", on_done=finalize_cleanup))
        if not async_started:
            cleanup_result = self._cancel_pending_orders_before_stop()
            finalize_cleanup(cleanup_result)
        self._last_exec_event.clear()
        self._disconnect_realtime_clients()

        if was_running:
            self.log("매매 중지")
            if self.telegram:
                self.telegram.send("매매 중지")
    def _time_liquidate(self):
        """장마감 시간 청산."""
        liquidated_count = 0
        for code, info in self._collect_liquidation_targets():
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
    def _init_universe(self, codes: List[str], background: bool = False) -> List[str] | BackgroundUniversePayload:
        target_universe: Dict[str, Dict[str, Any]] = {}
        failed_codes: List[str] = []
        initialized_codes: List[str] = []

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
                    "market_state": "normal",
                    "market_state_until": None,
                    "last_guard_reason": "",
                    "time_stop_eligible": True,
                    "entry_origin": "watch",
                    "sync_failed_reason": "",
                }
                ensure_market_intel = getattr(self, "_ensure_market_intel_state", None)
                if callable(ensure_market_intel):
                    ensure_market_intel(target_universe[code])
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
