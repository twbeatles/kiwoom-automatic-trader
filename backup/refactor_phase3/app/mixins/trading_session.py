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

class TradingSessionMixin:
    def start_trading(self):
        if self.is_running:
            self.log("⚠️ 이미 자동매매가 실행 중입니다.")
            return

        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 API에 연결하세요.")
            return
        
        codes = [c.strip() for c in self.input_codes.text().split(",") if c.strip()]
        if not codes:
            QMessageBox.warning(self, "경고", "감시 종목을 입력하세요.")
            return

        if not self._confirm_live_trading_guard():
            return
        
        try:
            self.is_running = True
            self.daily_loss_triggered = False
            self.time_liquidate_executed = False
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_emergency.setEnabled(True)  # v4.3 긴급청산 활성화
            
            if self.ws_client:
                self.ws_client.connect()
                self.ws_client.subscribe_execution(codes, self._on_realtime)
                self.ws_client.subscribe_order_execution(self._on_order_realtime)
            
            self._init_universe(codes)
            self.log(f"🚀 매매 시작 - {len(codes)}개 종목")
            
            if self.telegram:
                self.telegram.send(f"🚀 매매 시작\n종목: {', '.join(codes)}")
        except Exception as e:
            self.is_running = False
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.log(f"❌ 매매 시작 실패: {e}")
            QMessageBox.critical(self, "오류", f"매매 시작 중 오류:\n{e}")

    def stop_trading(self):
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_emergency.setEnabled(False)  # v4.3 긴급청산 비활성화
        self._position_sync_pending.clear()
        self._pending_order_state.clear()
        self._last_exec_event.clear()
        
        try:
            if self.ws_client:
                self.ws_client.unsubscribe_all()
                self.ws_client.disconnect()
        except Exception as e:
            self.log(f"⚠️ WebSocket 종료 중 오류: {e}")
        
        self.log("⏹️ 매매 중지")
        if self.telegram:
            self.telegram.send("⏹️ 매매 중지됨")

    def _time_liquidate(self):
        """장 마감 전 청산"""
        liquidated_count = 0
        for code, info in self.universe.items():
            held = info.get('held', 0)
            if held > 0:
                name = info.get('name', code)
                current = info.get('current', 0)
                self.log(f"⏰ 시간 청산 시작: {name} {held}주")
                self._execute_sell(code, held, current, "시간청산")
                liquidated_count += 1
        
        if liquidated_count > 0:
            self.log(f"⏰ 시간 청산 완료: {liquidated_count}개 종목")
            if self.telegram:
                self.telegram.send(f"⏰ 장마감 청산: {liquidated_count}개 종목")

    def _init_universe(self, codes):
        self.universe = {}
        self.table.setRowCount(len(codes))
        failed_codes = []
        
        for i, code in enumerate(codes):
            try:
                if self.rest_client:
                    quote = self.rest_client.get_stock_quote(code)
                    if quote:
                        # 일봉 데이터로 가격 히스토리 초기화
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
                                # 최신 데이터가 앞에 오므로 역순 정렬
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
                            self.log(f"⚠️ {code} 차트 데이터 로드 실패: {chart_err}")

                        try:
                            minute = self.rest_client.get_minute_chart(code, 1, 60)
                            if minute:
                                minute_prices = [candle.close_price for candle in reversed(minute)]
                        except Exception as minute_err:
                            self.log(f"⚠️ {code} 분봉 데이터 로드 실패: {minute_err}")

                        if not minute_prices:
                            minute_prices = list(price_history[-60:]) if price_history else [quote.current_price]
                        
                        avg_volume_5 = int(sum(volume_history[-5:]) / 5) if len(volume_history) >= 5 else 0
                        avg_volume_20 = int(sum(volume_history[-20:]) / 20) if len(volume_history) >= 20 else (
                            int(sum(volume_history) / len(volume_history)) if volume_history else 0
                        )
                        avg_value_20 = int(sum(value_history[-20:]) / 20) if len(value_history) >= 20 else (
                            int(sum(value_history) / len(value_history)) if value_history else 0
                        )

                        self.universe[code] = {
                            "name": quote.name, "current": quote.current_price,
                            "open": quote.open_price, "high": quote.high_price,
                            "low": quote.low_price, "prev_close": quote.prev_close,
                            "prev_high": prev_high, "prev_low": prev_low,
                            "daily_prices": daily_prices if daily_prices else list(price_history),
                            "minute_prices": minute_prices,
                            "market_type": quote.market_type, "sector": quote.sector or "기타",
                            "target": 0, "held": 0, "buy_price": 0,
                            "max_profit_rate": 0, "status": "감시",
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
                        
                        # 목표가 계산
                        target = self.strategy.calculate_target_price(code)
                        self.universe[code]["target"] = target
                        
                        self._update_row(i, code)
                    else:
                        failed_codes.append(code)
                        self.log(f"⚠️ {code} 시세 조회 실패")
            except Exception as e:
                failed_codes.append(code)
                self.log(f"⚠️ {code} 초기화 오류: {e}")
        
        if failed_codes:
            self.log(f"⚠️ {len(failed_codes)}개 종목 초기화 실패: {', '.join(failed_codes)}")

    def _update_row(self, row, code):
        info = self.universe.get(code, {})
        profit_rate = 0
        if info.get('held', 0) > 0 and info.get('buy_price', 0) > 0:
            profit_rate = (info['current'] - info['buy_price']) / info['buy_price'] * 100
        
        data = [
            info.get("name", code), f"{info.get('current', 0):,}",
            f"{info.get('target', 0):,}", info.get("status", ""),
            str(info.get("held", 0)), f"{info.get('buy_price', 0):,}",
            f"{profit_rate:.2f}%", f"{info.get('max_profit_rate', 0):.2f}%",
            f"{info.get('invest_amount', 0):,}"
        ]
        self.table.setUpdatesEnabled(False)
        try:
            for col, text in enumerate(data):
                existing = self.table.item(row, col)
                text_str = str(text)
                if existing and existing.text() == text_str:
                    continue  # 변경 없으면 스킵
                item = QTableWidgetItem(text_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6 and profit_rate != 0:
                    item.setForeground(QColor("#e63946" if profit_rate > 0 else "#4361ee"))
                self.table.setItem(row, col, item)
        finally:
            self.table.setUpdatesEnabled(True)

    def _refresh_table(self):
        for i, code in enumerate(self.universe.keys()):
            self._update_row(i, code)

    def _emergency_liquidate(self):
        """긴급 전체 청산"""
        if not self.is_connected:
            self.log("❌ API 연결 필요")
            return
        
        holding_count = sum(1 for info in self.universe.values() if info.get('held', 0) > 0)
        if holding_count == 0:
            QMessageBox.information(self, "알림", "청산할 보유 종목이 없습니다.")
            return
        
        confirm = QMessageBox.warning(self, "⚠️ 긴급 청산 확인",
            f"보유 중인 {holding_count}개 종목을 모두 시장가로 청산합니다.\n\n"
            "이 작업은 되돌릴 수 없습니다.\n정말 실행하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.log("🚨 긴급 전체 청산 시작")
            liquidated_count = 0
            for code, info in self.universe.items():
                held = info.get('held', 0)
                if held > 0:
                    name = info.get('name', code)
                    current = info.get('current', 0)
                    self.log(f"  → {name} {held}주 청산 중...")
                    self._execute_sell(code, held, current, "긴급청산")
                    liquidated_count += 1
            
            if self.sound:
                self.sound.play_warning()
            if self.telegram:
                self.telegram.send(f"🚨 긴급 전체 청산: {liquidated_count}개 종목")
            
            self.log(f"🚨 긴급 청산 완료: {liquidated_count}개 종목")

