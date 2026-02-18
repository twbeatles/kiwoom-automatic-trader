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

class OrderSyncMixin:
    def _on_realtime(self, data: ExecutionData):
        self.sig_execution.emit(data)

    def _on_order_realtime(self, data):
        """주문 체결 실시간 데이터 수신 (WebSocket Thread) -> Main Thread"""
        self.sig_order_execution.emit(data)

    def _on_order_execution(self, data):
        """주문 체결/접수/확인 처리 (Main Thread)"""
        try:
            code = str(data.get('code') or data.get('stk_cd') or '').strip()
            info = self.universe.get(code, {}) if code else {}
            name = data.get('name') or data.get('stk_nm') or info.get('name', code)

            raw_order_type = str(data.get('order_type') or data.get('ord_tp') or data.get('bs_tp') or '').strip()
            order_type_map = {
                '1': '매수', '2': '매도',
                '3': '매수취소', '4': '매도취소',
                '5': '매수정정', '6': '매도정정',
            }
            order_type = order_type_map.get(raw_order_type, raw_order_type or '주문')

            order_status = str(data.get('order_status') or data.get('ord_st') or data.get('status') or '').strip()
            qty = self._to_int(data.get('exec_qty', data.get('qty', data.get('ord_qty', 0))))
            price = self._to_int(data.get('exec_price', data.get('price', data.get('ord_prc', 0))))

            if not order_status:
                order_status = '체결' if qty > 0 else '알림'

            msg = f"🔔 {order_type} {order_status} - {name} {qty}주"
            if price > 0:
                msg += f" @ {price:,}원"
            self.log(msg)

            side = ''
            if '매수' in order_type:
                side = 'buy'
            elif '매도' in order_type:
                side = 'sell'

            if code and qty > 0 and side:
                self._last_exec_event[code] = {
                    'side': side,
                    'qty': qty,
                    'price': price,
                    'timestamp': datetime.datetime.now(),
                }

            if code and ('체결' in order_status or qty > 0):
                self._sync_position_from_account(code)

            if code and any(x in order_status for x in ['취소', '거부', '실패']):
                self._clear_pending_order(code)
                if code in self.universe:
                    if self.universe[code].get('held', 0) > 0:
                        self.universe[code]['status'] = '보유'
                    else:
                        self.universe[code]['status'] = '감시'
        except Exception as e:
            self.logger.error(f"주문 체결 처리 오류: {e}")

    def _to_int(value, default=0) -> int:
        """숫자/문자열 값을 안전하게 int로 변환"""
        try:
            if value is None:
                return default
            text = str(value).strip().replace(',', '')
            if text == '':
                return default
            return int(float(text))
        except (ValueError, TypeError):
            return default

    def _set_pending_order(self, code: str, side: str, reason: str):
        if not code:
            return
        self._pending_order_state[code] = {
            'side': side,
            'reason': reason,
            'until': datetime.datetime.now() + datetime.timedelta(seconds=5),
        }

    def _clear_pending_order(self, code: str):
        self._pending_order_state.pop(code, None)

    def _sync_position_from_account(self, code: str):
        """주문 체결 이벤트 이후 계좌 포지션 기반 동기화"""
        if not code or code not in self.universe:
            return
        if not (self.rest_client and self.current_account):
            return
        if code in self._position_sync_pending:
            return

        self._position_sync_pending.add(code)

        worker = Worker(self.rest_client.get_positions, self.current_account)
        worker.signals.result.connect(lambda positions, c=code: self._on_position_sync_result(c, positions))
        worker.signals.error.connect(lambda e, c=code: self._on_position_sync_error(c, e))
        self.threadpool.start(worker)

    def _on_position_sync_result(self, code: str, positions):
        self._position_sync_pending.discard(code)

        info = self.universe.get(code)
        if not info:
            return

        now = datetime.datetime.now()
        prev_held = int(info.get('held', 0))
        prev_buy_price = int(info.get('buy_price', 0))
        pending = self._pending_order_state.get(code)

        matched = None
        for pos in positions or []:
            if getattr(pos, 'code', '') == code:
                matched = pos
                break

        if matched:
            new_held = max(0, int(getattr(matched, 'quantity', 0)))
            new_buy_price = int(getattr(matched, 'buy_price', 0))
            new_invest_amount = int(getattr(matched, 'buy_amount', 0))
        else:
            new_held = 0
            new_buy_price = 0
            new_invest_amount = 0

        delta = new_held - prev_held
        exec_event = self._last_exec_event.get(code, {})

        if delta > 0:
            buy_qty = delta
            fill_price = self._to_int(exec_event.get('price', 0)) if exec_event.get('side') == 'buy' else 0
            if fill_price <= 0:
                fill_price = new_buy_price or int(info.get('current', 0))
            amount = max(0, fill_price * buy_qty)

            self._add_trade({
                'code': code,
                'name': info.get('name', code),
                'type': '매수',
                'price': fill_price,
                'quantity': buy_qty,
                'amount': amount,
                'profit': 0,
                'reason': '체결동기화',
            })
            self.strategy.update_market_investment(code, amount, is_buy=True)
            self.strategy.update_sector_investment(code, amount, is_buy=True)
            if self.sound:
                self.sound.play_buy()

        elif delta < 0:
            sell_qty = -delta
            fill_price = self._to_int(exec_event.get('price', 0)) if exec_event.get('side') == 'sell' else 0
            if fill_price <= 0:
                fill_price = int(info.get('current', 0))
            amount = max(0, fill_price * sell_qty)
            profit = (fill_price - prev_buy_price) * sell_qty if prev_buy_price > 0 else 0
            reason = pending.get('reason', '체결동기화') if pending else '체결동기화'

            self._add_trade({
                'code': code,
                'name': info.get('name', code),
                'type': '매도',
                'price': fill_price,
                'quantity': sell_qty,
                'amount': amount,
                'profit': profit,
                'reason': reason,
            })
            self.strategy.update_consecutive_results(profit > 0)
            self.strategy.update_market_investment(code, amount, is_buy=False)
            self.strategy.update_sector_investment(code, amount, is_buy=False)
            if self.sound:
                self.sound.play_sell() if profit > 0 else self.sound.play_loss()
            if self.telegram:
                self.telegram.send(f"🔴 매도 체결: {info.get('name', code)} {sell_qty}주 손익: {profit:+,}원")

        info['held'] = new_held
        info['buy_price'] = new_buy_price
        info['invest_amount'] = new_invest_amount

        if new_held > 0:
            info['status'] = '보유'
            info['cooldown_until'] = None
            if not info.get('buy_time'):
                info['buy_time'] = now
        else:
            info['status'] = '감시'
            info['buy_time'] = None
            info['max_profit_rate'] = 0
            info['partial_profit_levels'] = set()

            if prev_held > 0 and hasattr(self, 'chk_use_cooldown') and self.chk_use_cooldown.isChecked():
                cooldown_minutes = self.spin_cooldown_min.value()
                info['cooldown_until'] = now + datetime.timedelta(minutes=cooldown_minutes)
                info['status'] = '쿨다운'

        cooldown_until = info.get('cooldown_until')
        if info.get('held', 0) == 0 and cooldown_until and now < cooldown_until:
            info['status'] = '쿨다운'

        if pending:
            if delta != 0:
                self._clear_pending_order(code)
            elif now < pending.get('until', now):
                if pending.get('side') == 'buy' and info.get('held', 0) == 0:
                    info['status'] = '매수접수'
                elif pending.get('side') == 'sell' and info.get('held', 0) > 0:
                    info['status'] = '매도접수'
            else:
                self._clear_pending_order(code)

        if delta != 0:
            self._last_exec_event.pop(code, None)

        self.sig_update_table.emit()

    def _on_position_sync_error(self, code: str, error: Exception):
        self._position_sync_pending.discard(code)
        self.logger.warning(f"포지션 동기화 실패 [{code}]: {error}")

