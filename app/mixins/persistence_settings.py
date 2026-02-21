"""Persistence/settings mixin for KiwoomProTrader."""

import csv
import datetime
import json
import os
from pathlib import Path

try:
    import keyring
    KEYRING_AVAILABLE = True
except ModuleNotFoundError:
    KEYRING_AVAILABLE = False

    class _NoopKeyring:
        @staticmethod
        def set_password(service_name, username, password):
            return None

        @staticmethod
        def get_password(service_name, username):
            return None

    keyring = _NoopKeyring()
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from config import Config
from dark_theme import DARK_STYLESHEET
from light_theme import LIGHT_STYLESHEET


class PersistenceSettingsMixin:
    def _add_trade(self, record: dict):
        """거래 기록 추가."""
        record["timestamp"] = datetime.datetime.now().isoformat()
        self.trade_history.append(record)
        self._history_dirty = True
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if hasattr(self, "history_table") and record["timestamp"].startswith(today):
            self.history_table.insertRow(0)
            time_str = record["timestamp"].split("T")[-1][:8]
            items = [
                time_str,
                record.get("name", record.get("code", "")),
                record.get("type", ""),
                f"{record.get('price', 0):,}",
                str(record.get("quantity", 0)),
                f"{record.get('amount', 0):,}",
                f"{record.get('profit', 0):+,}",
                record.get("reason", ""),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6:
                    item.setForeground(QColor("#e63946" if record.get("profit", 0) > 0 else "#4361ee"))
                self.history_table.setItem(0, col, item)
        else:
            self._refresh_history_table()

        if record.get("type") == "매수":
            self.trade_count += 1
        if record.get("profit", 0) > 0:
            self.win_count += 1
        self.total_realized_profit += record.get("profit", 0)
        if record.get("type") == "매도":
            self.daily_realized_profit = int(getattr(self, "daily_realized_profit", 0) or 0) + int(
                record.get("profit", 0) or 0
            )

    def _refresh_history_table(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_history = [r for r in self.trade_history if r.get("timestamp", "").startswith(today)]

        self.history_table.setUpdatesEnabled(False)
        try:
            self.history_table.setRowCount(len(today_history))
            for row, record in enumerate(reversed(today_history)):
                timestamp = record.get("timestamp", "")
                time_str = timestamp.split("T")[-1][:8] if "T" in timestamp else timestamp
                items = [
                    time_str,
                    record.get("name", record.get("code", "")),
                    record.get("type", ""),
                    f"{record.get('price', 0):,}",
                    str(record.get("quantity", 0)),
                    f"{record.get('amount', 0):,}",
                    f"{record.get('profit', 0):+,}",
                    record.get("reason", ""),
                ]
                for col, text in enumerate(items):
                    text_str = str(text)
                    item = self.history_table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem(text_str)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        self.history_table.setItem(row, col, item)
                    elif item.text() != text_str:
                        item.setText(text_str)
                    if col == 6:
                        item.setForeground(QColor("#e63946" if record.get("profit", 0) > 0 else "#4361ee"))
        finally:
            self.history_table.setUpdatesEnabled(True)
        if hasattr(self, "stats_labels"):
            self._update_stats()

    def _export_csv(self):
        if not self.trade_history:
            QMessageBox.information(self, "알림", "내보낼 내역이 없습니다.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "CSV 저장",
            f"trades_{datetime.datetime.now():%Y%m%d}.csv",
            "CSV (*.csv)",
        )
        if filename:
            with open(filename, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["시간", "코드", "종목", "구분", "가격", "수량", "금액", "손익", "사유"])
                for record in self.trade_history:
                    writer.writerow(
                        [
                            record.get("timestamp"),
                            record.get("code"),
                            record.get("name"),
                            record.get("type"),
                            record.get("price"),
                            record.get("quantity"),
                            record.get("amount"),
                            record.get("profit"),
                            record.get("reason"),
                        ]
                    )
            self.log(f"📤 CSV 저장: {filename}")

    def _clear_today_history(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        count = sum(1 for r in self.trade_history if r.get("timestamp", "").startswith(today))
        if count == 0:
            return
        if QMessageBox.question(self, "확인", f"오늘 기록 {count}건 삭제?") == QMessageBox.StandardButton.Yes:
            self.trade_history = [r for r in self.trade_history if not r.get("timestamp", "").startswith(today)]
            self._save_trade_history()
            self._refresh_history_table()

    def _update_stats(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_trades = [r for r in self.trade_history if r.get("timestamp", "").startswith(today)]
        sells = [r for r in today_trades if r.get("type") == "매도"]

        wins = sum(1 for r in sells if r.get("profit", 0) > 0)
        total_profit = sum(r.get("profit", 0) for r in sells)
        profits = [r.get("profit", 0) for r in sells]

        self.stats_labels["trades"].setText(str(len(today_trades)))
        self.stats_labels["wins"].setText(f"{wins}/{len(sells)}")
        self.stats_labels["winrate"].setText(f"{wins / len(sells) * 100:.1f}%" if sells else "-")
        self.stats_labels["profit"].setText(f"{total_profit:+,} 원")
        self.stats_labels["max_profit"].setText(f"{max(profits):+,}" if profits else "-")
        self.stats_labels["max_loss"].setText(f"{min(profits):+,}" if profits else "-")

    def _load_trade_history(self):
        """거래 내역 로드."""
        try:
            if os.path.exists(Config.TRADE_HISTORY_FILE):
                with open(Config.TRADE_HISTORY_FILE, "r", encoding="utf-8") as file:
                    self.trade_history = json.load(file)
        except json.JSONDecodeError as exc:
            self.logger.warning(f"거래 내역 파싱 실패: {exc}")
            self.trade_history = []
        except OSError as exc:
            self.logger.warning(f"거래 내역 로드 실패: {exc}")

    def _save_trade_history(self):
        """거래 내역 저장 (비동기 처리)."""
        if not hasattr(self, "threadpool"):
            # 테스트/동기 환경 대응
            self._save_trade_history_sync()
            return

        # 현재 히스토리를 얕은 복사하여 백그라운드 스레드로 넘김
        history_snapshot = list(self.trade_history)
        worker = Worker(self._save_trade_history_worker, history_snapshot)
        self.threadpool.start(worker)

    def _save_trade_history_worker(self, history: list):
        """실제 파일 IO 수행 워커"""
        try:
            Path(Config.TRADE_HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(Config.TRADE_HISTORY_FILE, "w", encoding="utf-8") as file:
                json.dump(history, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.logger.error(f"거래 내역 저장 실패: {exc}")

    def _save_trade_history_sync(self):
        """동기 거래 내역 저장 (테스트용)"""
        try:
            Path(Config.TRADE_HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(Config.TRADE_HISTORY_FILE, "w", encoding="utf-8") as file:
                json.dump(self.trade_history, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.logger.error(f"거래 내역 동기 저장 실패: {exc}")

    def _save_settings(self):
        settings = {
            "settings_version": int(getattr(Config, "SETTINGS_SCHEMA_VERSION", 3)),
            "is_mock": self.chk_mock.isChecked(),
            "auto_start": self.chk_auto_start.isChecked(),
            "codes": self.input_codes.text(),
            "betting_ratio": self.spin_betting.value(),
            "betting": self.spin_betting.value(),
            "k_value": self.spin_k.value(),
            "ts_start": self.spin_ts_start.value(),
            "ts_stop": self.spin_ts_stop.value(),
            "loss_cut": self.spin_loss.value(),
            "use_rsi": self.chk_use_rsi.isChecked(),
            "rsi_upper": self.spin_rsi_upper.value(),
            "rsi_period": self.spin_rsi_period.value(),
            "use_macd": self.chk_use_macd.isChecked(),
            "use_bb": self.chk_use_bb.isChecked(),
            "bb_k": self.spin_bb_k.value(),
            "use_dmi": self.chk_use_dmi.isChecked(),
            "adx": self.spin_adx.value(),
            "use_volume": self.chk_use_volume.isChecked(),
            "volume_mult": self.spin_volume_mult.value(),
            "use_risk": self.chk_use_risk.isChecked(),
            "max_loss": self.spin_max_loss.value(),
            "max_holdings": self.spin_max_holdings.value(),
            "tg_token": self.input_tg_token.text(),
            "tg_chat": self.input_tg_chat.text(),
            "use_telegram": self.chk_use_telegram.isChecked(),
            "use_ma": self.chk_use_ma.isChecked(),
            "ma_short": self.spin_ma_short.value(),
            "ma_long": self.spin_ma_long.value(),
            "use_time_strategy": self.chk_use_time_strategy.isChecked(),
            "use_atr_sizing": self.chk_use_atr_sizing.isChecked(),
            "risk_percent": self.spin_risk_percent.value(),
            "use_split": self.chk_use_split.isChecked(),
            "split_count": self.spin_split_count.value(),
            "split_percent": self.spin_split_percent.value(),
            "use_stoch_rsi": self.chk_use_stoch_rsi.isChecked(),
            "stoch_upper": self.spin_stoch_upper.value(),
            "stoch_lower": self.spin_stoch_lower.value(),
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
            "schedule": dict(self.schedule) if isinstance(self.schedule, dict) else {
                "enabled": False,
                "start": "09:00",
                "end": "15:19",
                "liquidate": True,
            },
            "theme": self.current_theme,
        }

        # v3+ extended strategy/backtest schema
        cfg = getattr(self, "config", None)
        settings["strategy_pack"] = dict(
            getattr(cfg, "strategy_pack", getattr(Config, "DEFAULT_STRATEGY_PACK", {}))
        )
        settings["strategy_params"] = dict(
            getattr(cfg, "strategy_params", getattr(Config, "DEFAULT_STRATEGY_PARAMS", {}))
        )
        settings["portfolio_mode"] = str(
            getattr(cfg, "portfolio_mode", getattr(Config, "DEFAULT_PORTFOLIO_MODE", "single_strategy"))
        )
        settings["short_enabled"] = bool(
            getattr(cfg, "short_enabled", getattr(Config, "DEFAULT_SHORT_ENABLED", False))
        )
        settings["asset_scope"] = str(
            getattr(cfg, "asset_scope", getattr(Config, "DEFAULT_ASSET_SCOPE", "kr_stock_live"))
        )
        settings["backtest_config"] = dict(
            getattr(cfg, "backtest_config", getattr(Config, "DEFAULT_BACKTEST_CONFIG", {}))
        )
        settings["feature_flags"] = dict(
            getattr(cfg, "feature_flags", getattr(Config, "FEATURE_FLAGS", {}))
        )
        settings["execution_policy"] = str(
            getattr(cfg, "execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market"))
        )
        if hasattr(self, "combo_strategy_pack"):
            settings["strategy_pack"]["primary_strategy"] = str(self.combo_strategy_pack.currentText())
        if hasattr(self, "combo_portfolio_mode"):
            settings["portfolio_mode"] = str(self.combo_portfolio_mode.currentText())
        if hasattr(self, "chk_short_enabled"):
            settings["short_enabled"] = bool(self.chk_short_enabled.isChecked())
        if hasattr(self, "combo_asset_scope"):
            settings["asset_scope"] = str(self.combo_asset_scope.currentText())
        if hasattr(self, "combo_execution_policy"):
            settings["execution_policy"] = str(self.combo_execution_policy.currentText())
        if hasattr(self, "combo_backtest_timeframe"):
            settings["backtest_config"]["timeframe"] = str(self.combo_backtest_timeframe.currentText())
        if hasattr(self, "spin_backtest_lookback"):
            settings["backtest_config"]["lookback_days"] = int(self.spin_backtest_lookback.value())
        if hasattr(self, "spin_backtest_commission"):
            settings["backtest_config"]["commission_bps"] = float(self.spin_backtest_commission.value())
        if hasattr(self, "spin_backtest_slippage"):
            settings["backtest_config"]["slippage_bps"] = float(self.spin_backtest_slippage.value())
        if hasattr(self, "chk_feature_modular_pack"):
            settings["feature_flags"]["use_modular_strategy_pack"] = bool(self.chk_feature_modular_pack.isChecked())
        if hasattr(self, "chk_feature_backtest"):
            settings["feature_flags"]["enable_backtest"] = bool(self.chk_feature_backtest.isChecked())
        if hasattr(self, "chk_feature_external_data"):
            settings["feature_flags"]["enable_external_data"] = bool(self.chk_feature_external_data.isChecked())

        app_key = self.input_app_key.text().strip()
        secret_key = self.input_secret.text().strip()

        if not KEYRING_AVAILABLE:
            if app_key:
                settings["app_key"] = app_key
            if secret_key:
                settings["secret_key"] = secret_key

        try:
            if app_key:
                try:
                    keyring.set_password("KiwoomTrader", "app_key", app_key)
                except Exception as e:
                    self.logger.warning(f"Keyring app_key 저장 실패 (OS 환경 이슈일 수 있음): {e}")
                    settings["app_key"] = app_key
            if secret_key:
                try:
                    keyring.set_password("KiwoomTrader", "secret_key", secret_key)
                except Exception as e:
                    self.logger.warning(f"Keyring secret_key 저장 실패 (OS 환경 이슈일 수 있음): {e}")
                    settings["secret_key"] = secret_key

            Path(Config.SETTINGS_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(Config.SETTINGS_FILE, "w", encoding="utf-8") as file:
                json.dump(settings, file, ensure_ascii=False, indent=2)

            self._set_auto_start(self.chk_auto_start.isChecked())
            if KEYRING_AVAILABLE:
                self.log("✅ 설정 저장 완료 (Keyring 암호화)")
            else:
                self.log("✅ 설정 저장 완료 (⚠️ Keyring 미사용 - 평문 저장)")
        except Exception as exc:
            self.log(f"❌ 저장 실패: {exc}")

    def _load_settings(self):
        try:
            if not os.path.exists(Config.SETTINGS_FILE):
                return

            with open(Config.SETTINGS_FILE, "r", encoding="utf-8") as file:
                settings = json.load(file)
            settings_version = int(settings.get("settings_version", 1))
            if settings_version < 3:
                settings.setdefault("strategy_pack", dict(getattr(Config, "DEFAULT_STRATEGY_PACK", {})))
                settings.setdefault("strategy_params", dict(getattr(Config, "DEFAULT_STRATEGY_PARAMS", {})))
                settings.setdefault("portfolio_mode", getattr(Config, "DEFAULT_PORTFOLIO_MODE", "single_strategy"))
                settings.setdefault("short_enabled", getattr(Config, "DEFAULT_SHORT_ENABLED", False))
                settings.setdefault("asset_scope", getattr(Config, "DEFAULT_ASSET_SCOPE", "kr_stock_live"))
                settings.setdefault("backtest_config", dict(getattr(Config, "DEFAULT_BACKTEST_CONFIG", {})))
                settings.setdefault("feature_flags", dict(getattr(Config, "FEATURE_FLAGS", {})))
                settings.setdefault("execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market"))


            app_key = ""
            secret_key = ""
            try:
                app_key = keyring.get_password("KiwoomTrader", "app_key") or ""
            except Exception as exc:
                self.logger.warning(f"Keyring app_key 로드 실패: {exc}")
            try:
                secret_key = keyring.get_password("KiwoomTrader", "secret_key") or ""
            except Exception as exc:
                self.logger.warning(f"Keyring secret_key 로드 실패: {exc}")

            if not app_key and "app_key" in settings:
                app_key = settings["app_key"]
            if not secret_key and "secret_key" in settings:
                secret_key = settings["secret_key"]

            self.input_app_key.setText(app_key)
            self.input_secret.setText(secret_key)

            self.chk_mock.setChecked(settings.get("is_mock", False))
            self.chk_auto_start.setChecked(settings.get("auto_start", False))
            self.input_codes.setText(settings.get("codes", Config.DEFAULT_CODES))
            self.spin_betting.setValue(settings.get("betting_ratio", settings.get("betting", Config.DEFAULT_BETTING_RATIO)))
            self.spin_k.setValue(settings.get("k_value", Config.DEFAULT_K_VALUE))
            self.spin_ts_start.setValue(settings.get("ts_start", Config.DEFAULT_TS_START))
            self.spin_ts_stop.setValue(settings.get("ts_stop", Config.DEFAULT_TS_STOP))
            self.spin_loss.setValue(settings.get("loss_cut", Config.DEFAULT_LOSS_CUT))
            self.chk_use_rsi.setChecked(settings.get("use_rsi", True))
            self.spin_rsi_upper.setValue(settings.get("rsi_upper", 70))
            self.spin_rsi_period.setValue(settings.get("rsi_period", 14))
            self.chk_use_macd.setChecked(settings.get("use_macd", True))
            self.chk_use_bb.setChecked(settings.get("use_bb", False))
            self.spin_bb_k.setValue(settings.get("bb_k", 2.0))
            self.chk_use_dmi.setChecked(settings.get("use_dmi", False))
            self.spin_adx.setValue(settings.get("adx", 25))
            self.chk_use_volume.setChecked(settings.get("use_volume", True))
            self.spin_volume_mult.setValue(settings.get("volume_mult", 1.5))
            self.chk_use_risk.setChecked(settings.get("use_risk", True))
            self.spin_max_loss.setValue(settings.get("max_loss", 3.0))
            self.spin_max_holdings.setValue(settings.get("max_holdings", 5))
            self.input_tg_token.setText(settings.get("tg_token", ""))
            self.input_tg_chat.setText(settings.get("tg_chat", ""))
            self.chk_use_telegram.setChecked(settings.get("use_telegram", False))

            if hasattr(self, "chk_use_ma"):
                self.chk_use_ma.setChecked(settings.get("use_ma", False))
            if hasattr(self, "spin_ma_short"):
                self.spin_ma_short.setValue(settings.get("ma_short", 5))
            if hasattr(self, "spin_ma_long"):
                self.spin_ma_long.setValue(settings.get("ma_long", 20))
            if hasattr(self, "chk_use_time_strategy"):
                self.chk_use_time_strategy.setChecked(settings.get("use_time_strategy", False))
            if hasattr(self, "chk_use_atr_sizing"):
                self.chk_use_atr_sizing.setChecked(settings.get("use_atr_sizing", False))
            if hasattr(self, "spin_risk_percent"):
                self.spin_risk_percent.setValue(settings.get("risk_percent", 1.0))
            if hasattr(self, "chk_use_split"):
                self.chk_use_split.setChecked(settings.get("use_split", False))
            if hasattr(self, "spin_split_count"):
                self.spin_split_count.setValue(settings.get("split_count", 3))
            if hasattr(self, "spin_split_percent"):
                self.spin_split_percent.setValue(settings.get("split_percent", 0.5))
            if hasattr(self, "chk_use_stoch_rsi"):
                self.chk_use_stoch_rsi.setChecked(settings.get("use_stoch_rsi", False))
            if hasattr(self, "spin_stoch_upper"):
                self.spin_stoch_upper.setValue(settings.get("stoch_upper", 80))
            if hasattr(self, "spin_stoch_lower"):
                self.spin_stoch_lower.setValue(settings.get("stoch_lower", 20))
            if hasattr(self, "chk_use_mtf"):
                self.chk_use_mtf.setChecked(settings.get("use_mtf", False))
            if hasattr(self, "chk_use_partial_profit"):
                self.chk_use_partial_profit.setChecked(settings.get("use_partial_profit", False))
            if hasattr(self, "chk_use_gap"):
                self.chk_use_gap.setChecked(settings.get("use_gap", False))
            if hasattr(self, "chk_use_dynamic_sizing"):
                self.chk_use_dynamic_sizing.setChecked(settings.get("use_dynamic_sizing", False))
            if hasattr(self, "chk_use_market_limit"):
                self.chk_use_market_limit.setChecked(settings.get("use_market_limit", False))
            if hasattr(self, "spin_market_limit"):
                self.spin_market_limit.setValue(settings.get("market_limit", 30))
            if hasattr(self, "chk_use_sector_limit"):
                self.chk_use_sector_limit.setChecked(settings.get("use_sector_limit", False))
            if hasattr(self, "spin_sector_limit"):
                self.spin_sector_limit.setValue(settings.get("sector_limit", 20))
            if hasattr(self, "chk_use_atr_stop"):
                self.chk_use_atr_stop.setChecked(settings.get("use_atr_stop", False))
            if hasattr(self, "spin_atr_mult"):
                self.spin_atr_mult.setValue(settings.get("atr_mult", 2.0))
            if hasattr(self, "chk_use_sound"):
                self.chk_use_sound.setChecked(settings.get("use_sound", False))
            if hasattr(self, "chk_use_liquidity"):
                self.chk_use_liquidity.setChecked(settings.get("use_liquidity", False))
            if hasattr(self, "spin_min_value"):
                self.spin_min_value.setValue(settings.get("min_value", Config.DEFAULT_MIN_AVG_VALUE / 100_000_000))
            if hasattr(self, "chk_use_spread"):
                self.chk_use_spread.setChecked(settings.get("use_spread", False))
            if hasattr(self, "spin_spread_max"):
                self.spin_spread_max.setValue(settings.get("spread_max", Config.DEFAULT_MAX_SPREAD_PCT))
            if hasattr(self, "chk_use_breakout_confirm"):
                self.chk_use_breakout_confirm.setChecked(settings.get("use_breakout_confirm", False))
            if hasattr(self, "spin_breakout_ticks"):
                self.spin_breakout_ticks.setValue(settings.get("breakout_ticks", Config.DEFAULT_BREAKOUT_TICKS))
            if hasattr(self, "chk_use_cooldown"):
                self.chk_use_cooldown.setChecked(settings.get("use_cooldown", False))
            if hasattr(self, "spin_cooldown_min"):
                self.spin_cooldown_min.setValue(settings.get("cooldown_min", Config.DEFAULT_COOLDOWN_MINUTES))
            if hasattr(self, "chk_use_time_stop"):
                self.chk_use_time_stop.setChecked(settings.get("use_time_stop", False))
            if hasattr(self, "spin_time_stop_min"):
                self.spin_time_stop_min.setValue(settings.get("time_stop_min", Config.DEFAULT_MAX_HOLD_MINUTES))
            if hasattr(self, "chk_use_entry_score"):
                self.chk_use_entry_score.setChecked(settings.get("use_entry_scoring", Config.USE_ENTRY_SCORING))
            if hasattr(self, "spin_entry_score_threshold"):
                self.spin_entry_score_threshold.setValue(settings.get("entry_score_threshold", Config.ENTRY_SCORE_THRESHOLD))

            if isinstance(settings.get("schedule"), dict):
                raw_schedule = settings.get("schedule", {})
                self.schedule = {
                    "enabled": bool(raw_schedule.get("enabled", self.schedule.get("enabled", False))),
                    "start": str(raw_schedule.get("start", self.schedule.get("start", "09:00"))),
                    "end": str(raw_schedule.get("end", self.schedule.get("end", "15:19"))),
                    "liquidate": bool(raw_schedule.get("liquidate", self.schedule.get("liquidate", True))),
                }

            saved_theme = settings.get("theme", "dark")
            if saved_theme != self.current_theme:
                self.current_theme = saved_theme
                self.setStyleSheet(LIGHT_STYLESHEET if saved_theme == "light" else DARK_STYLESHEET)

            # v3+ strategy/backtest UI restore
            if hasattr(self, "combo_strategy_pack") and isinstance(settings.get("strategy_pack"), dict):
                primary = settings.get("strategy_pack", {}).get("primary_strategy", "volatility_breakout")
                self.combo_strategy_pack.setCurrentText(str(primary))
            if hasattr(self, "combo_portfolio_mode"):
                self.combo_portfolio_mode.setCurrentText(str(settings.get("portfolio_mode", "single_strategy")))
            if hasattr(self, "chk_short_enabled"):
                self.chk_short_enabled.setChecked(bool(settings.get("short_enabled", False)))
            if hasattr(self, "combo_asset_scope"):
                self.combo_asset_scope.setCurrentText(str(settings.get("asset_scope", "kr_stock_live")))
            if hasattr(self, "combo_execution_policy"):
                self.combo_execution_policy.setCurrentText(str(settings.get("execution_policy", "market")))
            bt_cfg = settings.get("backtest_config", {}) if isinstance(settings.get("backtest_config"), dict) else {}
            if hasattr(self, "combo_backtest_timeframe"):
                self.combo_backtest_timeframe.setCurrentText(str(bt_cfg.get("timeframe", "1d")))
            if hasattr(self, "spin_backtest_lookback"):
                self.spin_backtest_lookback.setValue(int(bt_cfg.get("lookback_days", 365)))
            if hasattr(self, "spin_backtest_commission"):
                self.spin_backtest_commission.setValue(float(bt_cfg.get("commission_bps", 5.0)))
            if hasattr(self, "spin_backtest_slippage"):
                self.spin_backtest_slippage.setValue(float(bt_cfg.get("slippage_bps", 3.0)))
            flags = settings.get("feature_flags", {}) if isinstance(settings.get("feature_flags"), dict) else {}
            if hasattr(self, "chk_feature_modular_pack"):
                self.chk_feature_modular_pack.setChecked(bool(flags.get("use_modular_strategy_pack", True)))
            if hasattr(self, "chk_feature_backtest"):
                self.chk_feature_backtest.setChecked(bool(flags.get("enable_backtest", True)))
            if hasattr(self, "chk_feature_external_data"):
                self.chk_feature_external_data.setChecked(bool(flags.get("enable_external_data", True)))

            cfg = getattr(self, "config", None)
            if cfg is not None:
                cfg.strategy_pack = dict(settings.get("strategy_pack", getattr(cfg, "strategy_pack", {})))
                cfg.strategy_params = dict(settings.get("strategy_params", getattr(cfg, "strategy_params", {})))
                cfg.portfolio_mode = str(settings.get("portfolio_mode", getattr(cfg, "portfolio_mode", "single_strategy")))
                cfg.short_enabled = bool(settings.get("short_enabled", getattr(cfg, "short_enabled", False)))
                cfg.asset_scope = str(settings.get("asset_scope", getattr(cfg, "asset_scope", "kr_stock_live")))
                cfg.backtest_config = dict(settings.get("backtest_config", getattr(cfg, "backtest_config", {})))
                cfg.feature_flags = dict(settings.get("feature_flags", getattr(cfg, "feature_flags", {})))
                cfg.execution_policy = str(settings.get("execution_policy", getattr(cfg, "execution_policy", "market")))

            self.log("📂 설정 불러옴")
        except (json.JSONDecodeError, FileNotFoundError, OSError) as exc:
            self.logger.warning(f"설정 로드 실패: {exc}")
