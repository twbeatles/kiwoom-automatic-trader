"""Trading session lifecycle mixin for KiwoomProTrader."""

import datetime
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
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
            baseline = int(getattr(self, "deposit", 0) or 0) or int(getattr(self, "initial_deposit", 0) or 0)
            if baseline > 0:
                self.daily_initial_deposit = baseline

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
        if cfg is not None and not self.chk_mock.isChecked():
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
        self._last_exec_event.clear()
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
