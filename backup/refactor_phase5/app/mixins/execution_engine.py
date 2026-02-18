"""KiwoomProTrader mixin module (refactored)."""

import csv
import datetime
import json
import logging
import os
import sys
import time
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import keyring
from PyQt6.QtCore import *
from PyQt6.QtGui import QColor, QFont, QTextCursor, QIcon, QAction, QShortcut, QKeySequence
from PyQt6.QtWidgets import *

from api import KiwoomAuth, KiwoomRESTClient, KiwoomWebSocketClient
from api.models import ExecutionData, OrderType, PriceType, StockQuote
from app.support.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox
from app.support.worker import Worker
from config import Config
from dark_theme import DARK_STYLESHEET
from light_theme import LIGHT_STYLESHEET
from ui_dialogs import (
    HelpDialog,
    ManualOrderDialog,
    PresetDialog,
    ProfileManagerDialog,
    ScheduleDialog,
    StockSearchDialog,
)

class ExecutionEngineMixin:
    def _on_execution(self, data: ExecutionData):
        """실시간 체결 데이터 수신 및 매매 결정"""
        if not self.is_running:
            return

        code = data.code
        if code not in self.universe:
            return
        
        info = self.universe[code]
        current_price = data.exec_price
        info["current"] = current_price
        if data.total_volume > 0:
            info["current_volume"] = data.total_volume
        if data.ask_price > 0:
            info["ask_price"] = data.ask_price
        if data.bid_price > 0:
            info["bid_price"] = data.bid_price
        
        # 가격 히스토리 업데이트
        if "price_history" in info:
            info["price_history"].append(current_price)
            if len(info["price_history"]) > Config.MAX_PRICE_HISTORY:
                info["price_history"].pop(0)
        if "minute_prices" in info:
            info["minute_prices"].append(current_price)
            if len(info["minute_prices"]) > Config.MAX_PRICE_HISTORY:
                info["minute_prices"].pop(0)
        
        # 매매 중지 상태거나 15시 이후면 매수 불가
        now = datetime.datetime.now()
        no_buy = now.hour >= Config.NO_ENTRY_HOUR
        
        held = info.get("held", 0)
        target = info.get("target", 0)
        buy_price = info.get("buy_price", 0)
        status = info.get("status", "감시")
        
        # 주문 진행/접수 중이면 중복 주문 방지
        if status in ["매수중", "매도중", "매수접수", "매도접수"]:
            return
        
        # === 보유 중인 경우: 매도 조건 체크 ===
        if held > 0 and buy_price > 0:
            profit_rate = (current_price - buy_price) / buy_price * 100
            
            # 최고 수익률 갱신
            if profit_rate > info.get("max_profit_rate", 0):
                info["max_profit_rate"] = profit_rate
            
            # ATR 손절 체크 (v4.3)
            atr_triggered, atr_stop = self.strategy.check_atr_stop_loss(code)
            if atr_triggered:
                self._execute_sell(code, held, current_price, "ATR손절")
                return
            
            # 절대 손절
            loss_limit = self.spin_loss.value()
            if profit_rate <= -loss_limit:
                self._execute_sell(code, held, current_price, f"손절({profit_rate:.1f}%)")
                return
            
            # 단계별 익절 (v4.3)
            partial = self.strategy.calculate_partial_take_profit(code, profit_rate)
            if partial:
                sell_qty = max(1, int(held * partial["sell_ratio"] / 100))
                self._execute_sell(code, sell_qty, current_price, f"부분익절{partial['level']+1}단계")
                self.strategy.mark_partial_profit_executed(code, partial["level"])
                return
            
            # 트레일링 스톱
            ts_start = self.spin_ts_start.value()
            ts_stop = self.spin_ts_stop.value()
            max_profit = info.get("max_profit_rate", 0)
            
            if max_profit >= ts_start:
                info["status"] = "트레일링"
                drop_from_high = max_profit - profit_rate
                if drop_from_high >= ts_stop:
                    self._execute_sell(code, held, current_price, f"트레일링({profit_rate:.1f}%)")
                    return

            # 시간 청산 (v4.3)
            if hasattr(self, 'chk_use_time_stop') and self.chk_use_time_stop.isChecked():
                buy_time = info.get("buy_time")
                if buy_time:
                    max_minutes = self.spin_time_stop_min.value()
                    if now - buy_time >= datetime.timedelta(minutes=max_minutes):
                        self._execute_sell(code, held, current_price, f"시간청산({max_minutes}분)")
                        return
        
        # === 미보유 시: 매수 조건 체크 ===
        elif held == 0 and target > 0 and not no_buy:
            # 최대 보유 종목 수 체크
            current_holdings = sum(
                1 for v in self.universe.values()
                if v.get("held", 0) > 0 or v.get("status") in ["매수중", "매수접수"]
            )
            max_holdings = self.spin_max_holdings.value()
            
            if current_holdings >= max_holdings:
                return

            # 쿨다운 체크 (v4.3)
            cooldown_until = info.get("cooldown_until")
            if cooldown_until and now < cooldown_until:
                return
            
            # 목표가 돌파 확인
            if current_price >= target:
                if hasattr(self, 'chk_use_breakout_confirm') and self.chk_use_breakout_confirm.isChecked():
                    hits = info.get("breakout_hits", 0) + 1
                    info["breakout_hits"] = hits
                    required_hits = self.spin_breakout_ticks.value()
                    if hits < required_hits:
                        return
                # 모든 매수 조건 체크
                passed, conditions = self.strategy.check_all_buy_conditions(code)
                
                if passed:
                    # 매수 수량 계산
                    if hasattr(self, 'chk_use_dynamic_sizing') and self.chk_use_dynamic_sizing.isChecked():
                        quantity = self.strategy.calculate_dynamic_position_size(code)
                    elif hasattr(self, 'chk_use_atr_sizing') and self.chk_use_atr_sizing.isChecked():
                        quantity = self.strategy.calculate_position_size(code, self.spin_risk_percent.value())
                    else:
                        quantity = self.strategy._default_position_size(code)
                    
                    if quantity > 0:
                        self._execute_buy(code, quantity, current_price)
            else:
                if info.get("breakout_hits"):
                    info["breakout_hits"] = 0
        
        self.sig_update_table.emit()

    def _execute_buy(self, code: str, quantity: int, price: int):
        """매수 실행 (비동기)"""
        info = self.universe.get(code, {})
        name = info.get("name", code)

        if quantity <= 0:
            return
        if info.get("status") in ["매수중", "매수접수"]:
            return
        
        if not (self.rest_client and self.current_account):
            self.log(f"❌ 매수 실패 [{name}]: API 연결 확인 필요")
            return

        # 중복 주문 방지 상태 설정
        info["status"] = "매수중"

        worker = Worker(self.rest_client.buy_market, self.current_account, code, quantity)
        worker.signals.result.connect(lambda res: self._on_buy_result(res, code, name, quantity, price))
        worker.signals.error.connect(lambda e: self._on_buy_error(e, code, name))
        self.threadpool.start(worker)

    def _on_buy_error(self, e, code, name):
        """매수 오류 처리"""
        self.log(f"❌ 매수 오류 [{name}]: {e}")
        self._clear_pending_order(code)
        # 상태 복구
        if code in self.universe:
            self.universe[code]["status"] = "감시"

    def _on_buy_result(self, result, code, name, quantity, price):
        """매수 결과 처리 (Main Thread)"""
        if result.success:
            if code in self.universe:
                self.universe[code]["status"] = "매수접수"
                self.universe[code]["cooldown_until"] = None
                self.universe[code]["breakout_hits"] = 0
            self._set_pending_order(code, "buy", "매수")
            self.log(f"🟢 매수 주문 접수: {name} {quantity}주")
            self._sync_position_from_account(code)
        else:
            self.log(f"❌ 매수 실패 [{name}]: {result.message}")
            if code in self.universe:
                self.universe[code]["status"] = "감시"  # 실패 시 상태 복구
            self._clear_pending_order(code)

    def _execute_sell(self, code: str, quantity: int, price: int, reason: str):
        """매도 실행 (비동기)"""
        info = self.universe.get(code, {})
        name = info.get("name", code)
        buy_price = info.get("buy_price", 0)

        if quantity <= 0:
            self.log(f"⚠️ 매도 수량 오류 [{name}]: {quantity}")
            return

        if info.get("status") in ["매도중", "매도접수"]:
            return

        held = info.get("held", 0)
        if held > 0 and quantity > held:
            quantity = held
        
        if not (self.rest_client and self.current_account):
            self.log(f"❌ 매도 실패 [{name}]: API 연결 확인 필요")
            return

        # 중복 주문 방지 상태 설정
        info["status"] = "매도중"

        worker = Worker(self.rest_client.sell_market, self.current_account, code, quantity)
        worker.signals.result.connect(lambda res: self._on_sell_result(res, code, name, quantity, price, buy_price, reason))
        worker.signals.error.connect(lambda e: self._on_sell_error(e, code, name))
        self.threadpool.start(worker)

    def _on_sell_error(self, e, code, name):
        """매도 오류 처리"""
        self.log(f"❌ 매도 오류 [{name}]: {e}")
        self._clear_pending_order(code)
        # 상태 복구
        if code in self.universe:
            # 보유 중이었으므로 보유 상태로 복구
            self.universe[code]["status"] = "보유"

    def _on_sell_result(self, result, code, name, quantity, price, buy_price, reason):
        """매도 결과 처리 (Main Thread)"""
        if result.success:
            if code in self.universe:
                self.universe[code]["status"] = "매도접수"
            self._set_pending_order(code, "sell", reason)
            self.log(f"🔴 매도 주문 접수: {name} {quantity}주 ({reason})")
            self._sync_position_from_account(code)
        else:
            self.log(f"❌ 매도 실패 [{name}]: {result.message}")
            if code in self.universe:
                self.universe[code]["status"] = "보유"  # 실패 시 상태 복구
            self._clear_pending_order(code)

