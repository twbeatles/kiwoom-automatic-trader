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

class PersistenceSettingsMixin:
    def _add_trade(self, record: dict):
        """거래 기록 추가 (지연 저장)"""
        record["timestamp"] = datetime.datetime.now().isoformat()
        self.trade_history.append(record)
        self._history_dirty = True  # 타이머에서 저장
        self._refresh_history_table()
        
        if record.get("type") == "매수":
            self.trade_count += 1
        if record.get("profit", 0) > 0:
            self.win_count += 1
        self.total_realized_profit += record.get("profit", 0)

    def _refresh_history_table(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_history = [r for r in self.trade_history if r.get('timestamp', '').startswith(today)]
        
        self.history_table.setRowCount(len(today_history))
        for row, r in enumerate(reversed(today_history)):
            time_str = r.get('timestamp', '').split('T')[-1][:8] if 'T' in r.get('timestamp', '') else r.get('timestamp', '')
            items = [time_str, r.get('name', r.get('code', '')), r.get('type', ''),
                     f"{r.get('price', 0):,}", str(r.get('quantity', 0)),
                     f"{r.get('amount', 0):,}", f"{r.get('profit', 0):+,}", r.get('reason', '')]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6:
                    item.setForeground(QColor("#e63946" if r.get('profit', 0) > 0 else "#4361ee"))
                self.history_table.setItem(row, col, item)
        if hasattr(self, 'stats_labels'):
            self._update_stats()

    def _export_csv(self):
        if not self.trade_history:
            QMessageBox.information(self, "알림", "내보낼 내역이 없습니다.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"trades_{datetime.datetime.now():%Y%m%d}.csv", "CSV (*.csv)")
        if filename:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["시간", "코드", "종목", "구분", "가격", "수량", "금액", "손익", "사유"])
                for r in self.trade_history:
                    writer.writerow([r.get('timestamp'), r.get('code'), r.get('name'), r.get('type'),
                                   r.get('price'), r.get('quantity'), r.get('amount'), r.get('profit'), r.get('reason')])
            self.log(f"📤 CSV 저장: {filename}")

    def _clear_today_history(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        count = sum(1 for r in self.trade_history if r.get('timestamp', '').startswith(today))
        if count == 0:
            return
        if QMessageBox.question(self, "확인", f"오늘 기록 {count}건 삭제?") == QMessageBox.StandardButton.Yes:
            self.trade_history = [r for r in self.trade_history if not r.get('timestamp', '').startswith(today)]
            self._save_trade_history()
            self._refresh_history_table()

    def _update_stats(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_trades = [r for r in self.trade_history if r.get('timestamp', '').startswith(today)]
        sells = [r for r in today_trades if r.get('type') == '매도']
        
        wins = sum(1 for r in sells if r.get('profit', 0) > 0)
        total_profit = sum(r.get('profit', 0) for r in sells)
        profits = [r.get('profit', 0) for r in sells]
        
        self.stats_labels["trades"].setText(str(len(today_trades)))
        self.stats_labels["wins"].setText(f"{wins}/{len(sells)}")
        self.stats_labels["winrate"].setText(f"{wins/len(sells)*100:.1f}%" if sells else "-")
        self.stats_labels["profit"].setText(f"{total_profit:+,} 원")
        self.stats_labels["max_profit"].setText(f"{max(profits):+,}" if profits else "-")
        self.stats_labels["max_loss"].setText(f"{min(profits):+,}" if profits else "-")

    def _load_trade_history(self):
        """거래 내역 로드"""
        try:
            if os.path.exists(Config.TRADE_HISTORY_FILE):
                with open(Config.TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.trade_history = json.load(f)
        except json.JSONDecodeError as e:
            self.logger.warning(f"거래 내역 파싱 실패: {e}")
            self.trade_history = []
        except OSError as e:
            self.logger.warning(f"거래 내역 로드 실패: {e}")

    def _save_trade_history(self):
        """거래 내역 저장"""
        try:
            with open(Config.TRADE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.error(f"거래 내역 저장 실패: {e}")

    def _save_settings(self):
        # 1. 일반 설정 저장
        settings = {
            "is_mock": self.chk_mock.isChecked(), 
            "auto_start": self.chk_auto_start.isChecked(),
            "codes": self.input_codes.text(),
            "betting": self.spin_betting.value(), "k_value": self.spin_k.value(),
            "ts_start": self.spin_ts_start.value(), "ts_stop": self.spin_ts_stop.value(),
            "loss_cut": self.spin_loss.value(),
            "use_rsi": self.chk_use_rsi.isChecked(), "rsi_upper": self.spin_rsi_upper.value(),
            "rsi_period": self.spin_rsi_period.value(),
            "use_macd": self.chk_use_macd.isChecked(),
            "use_bb": self.chk_use_bb.isChecked(), "bb_k": self.spin_bb_k.value(),
            "use_dmi": self.chk_use_dmi.isChecked(), "adx": self.spin_adx.value(),
            "use_volume": self.chk_use_volume.isChecked(), "volume_mult": self.spin_volume_mult.value(),
            "use_risk": self.chk_use_risk.isChecked(), "max_loss": self.spin_max_loss.value(),
            "max_holdings": self.spin_max_holdings.value(),
            "tg_token": self.input_tg_token.text(), "tg_chat": self.input_tg_chat.text(),
            "use_telegram": self.chk_use_telegram.isChecked(),
            # v4.3 신규 설정
            "use_ma": self.chk_use_ma.isChecked(),
            "ma_short": self.spin_ma_short.value(), "ma_long": self.spin_ma_long.value(),
            "use_time_strategy": self.chk_use_time_strategy.isChecked(),
            "use_atr_sizing": self.chk_use_atr_sizing.isChecked(),
            "risk_percent": self.spin_risk_percent.value(),
            "use_split": self.chk_use_split.isChecked(),
            "split_count": self.spin_split_count.value(), "split_percent": self.spin_split_percent.value(),
            "use_stoch_rsi": self.chk_use_stoch_rsi.isChecked(),
            "stoch_upper": self.spin_stoch_upper.value(), "stoch_lower": self.spin_stoch_lower.value(),
            "use_mtf": self.chk_use_mtf.isChecked(),
            "use_partial_profit": self.chk_use_partial_profit.isChecked(),
            "use_gap": self.chk_use_gap.isChecked(),
            "use_dynamic_sizing": self.chk_use_dynamic_sizing.isChecked(),
            "use_market_limit": self.chk_use_market_limit.isChecked(),
            "market_limit": self.spin_market_limit.value(),
            "use_sector_limit": self.chk_use_sector_limit.isChecked(),
            "sector_limit": self.spin_sector_limit.value(),
            "use_atr_stop": self.chk_use_atr_stop.isChecked(),
            "atr_mult": self.spin_atr_mult.value(),
            "use_sound": self.chk_use_sound.isChecked(),
            "use_liquidity": self.chk_use_liquidity.isChecked(),
            "min_value": self.spin_min_value.value(),
            "use_spread": self.chk_use_spread.isChecked(),
            "spread_max": self.spin_spread_max.value(),
            "use_breakout_confirm": self.chk_use_breakout_confirm.isChecked(),
            "breakout_ticks": self.spin_breakout_ticks.value(),
            "use_cooldown": self.chk_use_cooldown.isChecked(),
            "cooldown_min": self.spin_cooldown_min.value(),
            "use_time_stop": self.chk_use_time_stop.isChecked(),
            "time_stop_min": self.spin_time_stop_min.value(),
            "use_entry_scoring": self.chk_use_entry_score.isChecked(),
            "entry_score_threshold": self.spin_entry_score_threshold.value(),
            "schedule": self.schedule,
            "theme": self.current_theme,
        }
        
        # 2. 보안 설정 저장 (Keyring)
        app_key = self.input_app_key.text().strip()
        secret_key = self.input_secret.text().strip()
        
        try:
            if app_key:
                keyring.set_password("KiwoomTrader", "app_key", app_key)
            if secret_key:
                keyring.set_password("KiwoomTrader", "secret_key", secret_key)
            
            with open(Config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            # 자동 실행 레지스트리 설정
            self._set_auto_start(self.chk_auto_start.isChecked())
            
            self.log("✅ 설정 저장 완료 (Keyring 암호화)")
        except Exception as e:
            self.log(f"❌ 저장 실패: {e}")

    def _load_settings(self):
        try:
            if os.path.exists(Config.SETTINGS_FILE):
                with open(Config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    s = json.load(f)
                
                # 키 로드 (Keyring 우선, 없으면 JSON)
                app_key = keyring.get_password("KiwoomTrader", "app_key")
                secret_key = keyring.get_password("KiwoomTrader", "secret_key")
                
                # 마이그레이션: JSON에 있으면 Keyring으로 이동하고 JSON에서는 사용 안함
                if not app_key and "app_key" in s:
                    app_key = s["app_key"]
                if not secret_key and "secret_key" in s:
                    secret_key = s["secret_key"]
                
                self.input_app_key.setText(app_key if app_key else "")
                self.input_secret.setText(secret_key if secret_key else "")
                
                self.chk_mock.setChecked(s.get("is_mock", False))
                self.chk_auto_start.setChecked(s.get("auto_start", False))
                self.input_codes.setText(s.get("codes", Config.DEFAULT_CODES))
                self.spin_betting.setValue(s.get("betting", Config.DEFAULT_BETTING_RATIO))
                self.spin_k.setValue(s.get("k_value", Config.DEFAULT_K_VALUE))
                self.spin_ts_start.setValue(s.get("ts_start", Config.DEFAULT_TS_START))
                self.spin_ts_stop.setValue(s.get("ts_stop", Config.DEFAULT_TS_STOP))
                self.spin_loss.setValue(s.get("loss_cut", Config.DEFAULT_LOSS_CUT))
                self.chk_use_rsi.setChecked(s.get("use_rsi", True))
                self.spin_rsi_upper.setValue(s.get("rsi_upper", 70))
                self.spin_rsi_period.setValue(s.get("rsi_period", 14))
                self.chk_use_macd.setChecked(s.get("use_macd", True))
                self.chk_use_bb.setChecked(s.get("use_bb", False))
                self.spin_bb_k.setValue(s.get("bb_k", 2.0))
                self.chk_use_dmi.setChecked(s.get("use_dmi", False))
                self.spin_adx.setValue(s.get("adx", 25))
                self.chk_use_volume.setChecked(s.get("use_volume", True))
                self.spin_volume_mult.setValue(s.get("volume_mult", 1.5))
                self.chk_use_risk.setChecked(s.get("use_risk", True))
                self.spin_max_loss.setValue(s.get("max_loss", 3.0))
                self.spin_max_holdings.setValue(s.get("max_holdings", 5))
                self.input_tg_token.setText(s.get("tg_token", ""))
                self.input_tg_chat.setText(s.get("tg_chat", ""))
                self.chk_use_telegram.setChecked(s.get("use_telegram", False))
                
                # v4.3 신규 설정 로드
                if hasattr(self, 'chk_use_ma'):
                    self.chk_use_ma.setChecked(s.get("use_ma", False))
                if hasattr(self, 'spin_ma_short'):
                    self.spin_ma_short.setValue(s.get("ma_short", 5))
                if hasattr(self, 'spin_ma_long'):
                    self.spin_ma_long.setValue(s.get("ma_long", 20))
                if hasattr(self, 'chk_use_time_strategy'):
                    self.chk_use_time_strategy.setChecked(s.get("use_time_strategy", False))
                if hasattr(self, 'chk_use_atr_sizing'):
                    self.chk_use_atr_sizing.setChecked(s.get("use_atr_sizing", False))
                if hasattr(self, 'spin_risk_percent'):
                    self.spin_risk_percent.setValue(s.get("risk_percent", 1.0))
                if hasattr(self, 'chk_use_split'):
                    self.chk_use_split.setChecked(s.get("use_split", False))
                if hasattr(self, 'spin_split_count'):
                    self.spin_split_count.setValue(s.get("split_count", 3))
                if hasattr(self, 'spin_split_percent'):
                    self.spin_split_percent.setValue(s.get("split_percent", 0.5))
                if hasattr(self, 'chk_use_stoch_rsi'):
                    self.chk_use_stoch_rsi.setChecked(s.get("use_stoch_rsi", False))
                if hasattr(self, 'spin_stoch_upper'):
                    self.spin_stoch_upper.setValue(s.get("stoch_upper", 80))
                if hasattr(self, 'spin_stoch_lower'):
                    self.spin_stoch_lower.setValue(s.get("stoch_lower", 20))
                if hasattr(self, 'chk_use_mtf'):
                    self.chk_use_mtf.setChecked(s.get("use_mtf", False))
                if hasattr(self, 'chk_use_partial_profit'):
                    self.chk_use_partial_profit.setChecked(s.get("use_partial_profit", False))
                if hasattr(self, 'chk_use_gap'):
                    self.chk_use_gap.setChecked(s.get("use_gap", False))
                if hasattr(self, 'chk_use_dynamic_sizing'):
                    self.chk_use_dynamic_sizing.setChecked(s.get("use_dynamic_sizing", False))
                if hasattr(self, 'chk_use_market_limit'):
                    self.chk_use_market_limit.setChecked(s.get("use_market_limit", False))
                if hasattr(self, 'spin_market_limit'):
                    self.spin_market_limit.setValue(s.get("market_limit", 30))
                if hasattr(self, 'chk_use_sector_limit'):
                    self.chk_use_sector_limit.setChecked(s.get("use_sector_limit", False))
                if hasattr(self, 'spin_sector_limit'):
                    self.spin_sector_limit.setValue(s.get("sector_limit", 20))
                if hasattr(self, 'chk_use_atr_stop'):
                    self.chk_use_atr_stop.setChecked(s.get("use_atr_stop", False))
                if hasattr(self, 'spin_atr_mult'):
                    self.spin_atr_mult.setValue(s.get("atr_mult", 2.0))
                if hasattr(self, 'chk_use_sound'):
                    self.chk_use_sound.setChecked(s.get("use_sound", False))
                if hasattr(self, 'chk_use_liquidity'):
                    self.chk_use_liquidity.setChecked(s.get("use_liquidity", False))
                if hasattr(self, 'spin_min_value'):
                    self.spin_min_value.setValue(s.get("min_value", Config.DEFAULT_MIN_AVG_VALUE / 100_000_000))
                if hasattr(self, 'chk_use_spread'):
                    self.chk_use_spread.setChecked(s.get("use_spread", False))
                if hasattr(self, 'spin_spread_max'):
                    self.spin_spread_max.setValue(s.get("spread_max", Config.DEFAULT_MAX_SPREAD_PCT))
                if hasattr(self, 'chk_use_breakout_confirm'):
                    self.chk_use_breakout_confirm.setChecked(s.get("use_breakout_confirm", False))
                if hasattr(self, 'spin_breakout_ticks'):
                    self.spin_breakout_ticks.setValue(s.get("breakout_ticks", Config.DEFAULT_BREAKOUT_TICKS))
                if hasattr(self, 'chk_use_cooldown'):
                    self.chk_use_cooldown.setChecked(s.get("use_cooldown", False))
                if hasattr(self, 'spin_cooldown_min'):
                    self.spin_cooldown_min.setValue(s.get("cooldown_min", Config.DEFAULT_COOLDOWN_MINUTES))
                if hasattr(self, 'chk_use_time_stop'):
                    self.chk_use_time_stop.setChecked(s.get("use_time_stop", False))
                if hasattr(self, 'spin_time_stop_min'):
                    self.spin_time_stop_min.setValue(s.get("time_stop_min", Config.DEFAULT_MAX_HOLD_MINUTES))
                if hasattr(self, 'chk_use_entry_score'):
                    self.chk_use_entry_score.setChecked(s.get("use_entry_scoring", Config.USE_ENTRY_SCORING))
                if hasattr(self, 'spin_entry_score_threshold'):
                    self.spin_entry_score_threshold.setValue(s.get("entry_score_threshold", Config.ENTRY_SCORE_THRESHOLD))
                if isinstance(s.get("schedule"), dict):
                    self.schedule = s.get("schedule", self.schedule)
                
                # 테마 설정
                saved_theme = s.get("theme", "dark")
                if saved_theme != self.current_theme:
                    self.current_theme = saved_theme
                    if saved_theme == 'light':
                        self.setStyleSheet(LIGHT_STYLESHEET)
                    else:
                        self.setStyleSheet(DARK_STYLESHEET)
                
                self.log("📂 설정 불러옴")
        except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
            self.logger.warning(f"설정 로드 실패: {e}")

