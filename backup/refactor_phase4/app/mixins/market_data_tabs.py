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

class MarketDataTabsMixin:
    def _load_chart(self):
        """차트 데이터 조회 (비동기)"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        code = self.chart_code_input.text().strip()
        chart_type = self.chart_type_combo.currentText()
        
        # 버튼 비활성화
        btn = self.sender()
        if isinstance(btn, QPushButton):
            btn.setEnabled(False)
            btn.setText("⏳ 조회 중...")
        
        def worker_fn():
            # API 호출 (백그라운드)
            if "일봉" in chart_type:
                return self.rest_client.get_daily_chart(code, 60)
            elif "주봉" in chart_type:
                return self.rest_client.get_weekly_chart(code, 52)
            else:
                interval = int(chart_type.replace("분봉", ""))
                return self.rest_client.get_minute_chart(code, interval, 60)
        
        def on_complete(data):
            # UI 복구
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("🔄 차트 조회")
            
            if not data:
                self.chart_info.setText("❌ 데이터 없음")
                self.log(f"❌ 차트 데이터 없음: {code}")
                return

            try:
                self.chart_table.setRowCount(len(data))
                for i, candle in enumerate(data):
                    items = [candle.date, f"{candle.open_price:,}", f"{candle.high_price:,}",
                            f"{candle.low_price:,}", f"{candle.close_price:,}", f"{candle.volume:,}"]
                    for j, text in enumerate(items):
                        self.chart_table.setItem(i, j, QTableWidgetItem(str(text)))
                
                self.chart_info.setText(f"📊 {code} {chart_type} - {len(data)}개 조회")
                self.log(f"📈 차트 조회 완료: {code} ({chart_type})")
            except Exception as e:
                self.log(f"❌ 차트 UI 업데이트 오류: {e}")

        def on_error(e):
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("🔄 차트 조회")
            self.log(f"❌ 차트 조회 실패: {e}")

        # 워커 실행
        worker = Worker(worker_fn)
        worker.signals.finished.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _load_orderbook(self):
        """호가 데이터 조회 (비동기)"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        code = self.hoga_code_input.text().strip()
        
        # 버튼 비활성화
        btn = self.sender()
        if isinstance(btn, QPushButton):
            btn.setEnabled(False)
            btn.setText("⏳ 조회 중...")
            
        def worker_fn():
            return self.rest_client.get_order_book(code)
            
        def on_complete(ob):
            # UI 복구
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("🔄 호가 조회")
            
            if not ob:
                self.log(f"❌ 호가 데이터 없음: {code}")
                return
                
            try:
                for i in range(10):
                    # 매도 호가 (역순)
                    idx = 9 - i
                    self.ask_table.setItem(i, 0, QTableWidgetItem(f"{ob.ask_prices[idx]:,}"))
                    self.ask_table.setItem(i, 1, QTableWidgetItem(f"{ob.ask_volumes[idx]:,}"))
                    # 매수 호가
                    self.bid_table.setItem(i, 0, QTableWidgetItem(f"{ob.bid_prices[i]:,}"))
                    self.bid_table.setItem(i, 1, QTableWidgetItem(f"{ob.bid_volumes[i]:,}"))
                
                self.hoga_info.setText(f"총 매도잔량: {ob.total_ask_volume:,} | 총 매수잔량: {ob.total_bid_volume:,}")
                self.log(f"📋 호가 조회 완료: {code}")
            except Exception as e:
                self.log(f"❌ 호가 UI 업데이트 오류: {e}")
                
        def on_error(e):
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("🔄 호가 조회")
            self.log(f"❌ 호가 조회 실패: {e}")
            
        worker = Worker(worker_fn)
        worker.signals.finished.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _load_conditions(self):
        """조건식 목록 조회"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return

        btn = self.sender() if isinstance(self.sender(), QPushButton) else None
        if btn:
            btn.setEnabled(False)
            btn.setText("⏳ 조회 중...")

        worker = Worker(self.rest_client.get_condition_list)

        def on_complete(conditions):
            if btn:
                btn.setEnabled(True)
                btn.setText("🔄 목록 갱신")
            self.condition_combo.clear()
            for cond in conditions or []:
                self.condition_combo.addItem(f"{cond['index']}: {cond['name']}", cond)
            self.log(f"🔍 조건식 {len(conditions or [])}개 로드")

        def on_error(e):
            if btn:
                btn.setEnabled(True)
                btn.setText("🔄 목록 갱신")
            self.log(f"❌ 조건식 조회 실패: {e}")

        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _execute_condition(self):
        """조건검색 실행"""
        if not self.rest_client:
            return
        
        cond_data = self.condition_combo.currentData()
        if not cond_data:
            return

        btn = self.sender() if isinstance(self.sender(), QPushButton) else None
        if btn:
            btn.setEnabled(False)
            btn.setText("⏳ 검색 중...")

        worker = Worker(self.rest_client.search_by_condition, cond_data['index'], cond_data['name'])

        def on_complete(results):
            if btn:
                btn.setEnabled(True)
                btn.setText("🔍 검색 실행")
            results = results or []
            self.condition_table.setRowCount(len(results))
            for i, stock in enumerate(results):
                items = [stock['code'], stock['name'], f"{stock['current_price']:,}",
                        f"{stock['change_rate']:.2f}%", f"{stock['volume']:,}"]
                for j, text in enumerate(items):
                    self.condition_table.setItem(i, j, QTableWidgetItem(str(text)))
            
            self.condition_info.setText(f"🔍 {len(results)}개 종목 검색됨")
            self.log(f"🔍 조건검색 완료: {len(results)}개")

        def on_error(e):
            if btn:
                btn.setEnabled(True)
                btn.setText("🔍 검색 실행")
            self.log(f"❌ 조건검색 실패: {e}")

        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

    def _apply_condition_result(self):
        """조건검색 결과를 감시 종목에 적용"""
        codes = []
        for i in range(self.condition_table.rowCount()):
            item = self.condition_table.item(i, 0)
            if item:
                codes.append(item.text())
        
        if codes:
            self.input_codes.setText(",".join(codes[:10]))  # 최대 10개
            self.log(f"📌 {len(codes[:10])}개 종목 적용")

    def _load_ranking(self):
        """순위 정보 조회"""
        if not self.rest_client:
            self.log("❌ API 연결 필요")
            return
        
        ranking_type = self.ranking_type.currentText()
        market_idx = self.ranking_market.currentIndex()
        market = str(market_idx)
        
        btn = self.sender() if isinstance(self.sender(), QPushButton) else None
        if btn:
            btn.setEnabled(False)
            btn.setText("⏳ 조회 중...")

        if "거래량" in ranking_type:
            worker = Worker(self.rest_client.get_volume_ranking, market, 30)
        elif "상승" in ranking_type:
            worker = Worker(self.rest_client.get_fluctuation_ranking, market, "1", 30)
        else:
            worker = Worker(self.rest_client.get_fluctuation_ranking, market, "2", 30)

        def on_complete(data):
            if btn:
                btn.setEnabled(True)
                btn.setText("🔄 순위 조회")
            data = data or []
            self.ranking_table.setRowCount(len(data))
            for i, item in enumerate(data):
                items = [str(item['rank']), item['code'], item['name'],
                        f"{item['current_price']:,}", f"{item['change_rate']:.2f}%", f"{item['volume']:,}"]
                for j, text in enumerate(items):
                    self.ranking_table.setItem(i, j, QTableWidgetItem(str(text)))
            
            self.log(f"🏆 {ranking_type} 조회 완료")

        def on_error(e):
            if btn:
                btn.setEnabled(True)
                btn.setText("🔄 순위 조회")
            self.log(f"❌ 순위 조회 실패: {e}")

        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)
        self.threadpool.start(worker)

