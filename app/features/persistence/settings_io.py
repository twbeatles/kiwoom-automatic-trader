"""Persistence/settings mixin for KiwoomProTrader."""

import copy
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

        @staticmethod
        def delete_password(service_name, username):
            return None

    keyring = _NoopKeyring()
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from app.support.ui_text import combo_value, set_combo_value
from app.support.worker import Worker
from config import Config
from dark_theme import DARK_STYLESHEET
from light_theme import LIGHT_STYLESHEET
from app.mixins._typing import TraderMixinBase


class PersistenceSettingsIOMixin(TraderMixinBase):
    def _save_settings(self):
        update_market_intel = getattr(self, "_update_market_intelligence_config_from_ui", None)
        if callable(update_market_intel):
            update_market_intel()
        settings = {
            "settings_version": int(getattr(Config, "SETTINGS_SCHEMA_VERSION", 7)),
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
            "max_daily_loss": self.spin_max_loss.value(),
            "max_holdings": self.spin_max_holdings.value(),
            "daily_loss_basis": combo_value(self.combo_daily_loss_basis, getattr(self.config, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")))
            if hasattr(self, "combo_daily_loss_basis")
            else getattr(self.config, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")),
            "sync_history_flush_on_exit": self.chk_sync_history_flush_on_exit.isChecked()
            if hasattr(self, "chk_sync_history_flush_on_exit")
            else bool(
                getattr(
                    self.config,
                    "sync_history_flush_on_exit",
                    getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True),
                )
            ),
            "allow_plaintext_secret_fallback": self.chk_allow_plaintext_secret_fallback.isChecked()
            if hasattr(self, "chk_allow_plaintext_secret_fallback")
            else bool(
                getattr(
                    self.config,
                    "allow_plaintext_secret_fallback",
                    getattr(Config, "DEFAULT_ALLOW_PLAINTEXT_SECRET_FALLBACK", False),
                )
            ),
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

        guard_defaults = self._v4_guard_defaults()
        for key, default in guard_defaults.items():
            settings[key] = default
        cfg = getattr(self, "config", None)
        if cfg is not None:
            for key in guard_defaults.keys():
                settings[key] = getattr(cfg, key, settings[key])
        if hasattr(self, "chk_use_shock_guard"):
            settings["use_shock_guard"] = bool(self.chk_use_shock_guard.isChecked())
        if hasattr(self, "spin_shock_1m"):
            settings["shock_1m_pct"] = float(self.spin_shock_1m.value())
        if hasattr(self, "spin_shock_5m"):
            settings["shock_5m_pct"] = float(self.spin_shock_5m.value())
        if hasattr(self, "spin_shock_cooldown"):
            settings["shock_cooldown_min"] = int(self.spin_shock_cooldown.value())
        if hasattr(self, "chk_use_vi_guard"):
            settings["use_vi_guard"] = bool(self.chk_use_vi_guard.isChecked())
        if hasattr(self, "spin_vi_cooldown"):
            settings["vi_cooldown_min"] = int(self.spin_vi_cooldown.value())
        if hasattr(self, "chk_use_regime_sizing"):
            settings["use_regime_sizing"] = bool(self.chk_use_regime_sizing.isChecked())
        if hasattr(self, "chk_use_liquidity_stress_guard"):
            settings["use_liquidity_stress_guard"] = bool(self.chk_use_liquidity_stress_guard.isChecked())
        if hasattr(self, "chk_use_slippage_guard"):
            settings["use_slippage_guard"] = bool(self.chk_use_slippage_guard.isChecked())
        if hasattr(self, "spin_max_slippage_bps"):
            settings["max_slippage_bps"] = float(self.spin_max_slippage_bps.value())
        if hasattr(self, "chk_use_order_health_guard"):
            settings["use_order_health_guard"] = bool(self.chk_use_order_health_guard.isChecked())

        # v3+ extended strategy/backtest schema
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
        settings["execution_mode"] = str(
            getattr(cfg, "execution_mode", getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"))
        )
        settings["market_intelligence"] = copy.deepcopy(
            getattr(cfg, "market_intelligence", getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {}))
        )
        if hasattr(self, "combo_strategy_pack"):
            settings["strategy_pack"]["primary_strategy"] = combo_value(self.combo_strategy_pack, "volatility_breakout")
        if hasattr(self, "combo_portfolio_mode"):
            settings["portfolio_mode"] = combo_value(self.combo_portfolio_mode, "single_strategy")
        if hasattr(self, "chk_short_enabled"):
            settings["short_enabled"] = bool(self.chk_short_enabled.isChecked())
        if hasattr(self, "combo_asset_scope"):
            settings["asset_scope"] = combo_value(self.combo_asset_scope, "kr_stock_live")
        if hasattr(self, "combo_execution_policy"):
            settings["execution_policy"] = combo_value(self.combo_execution_policy, "market")
        if hasattr(self, "combo_execution_mode"):
            settings["execution_mode"] = combo_value(
                self.combo_execution_mode,
                getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"),
            )
        if hasattr(self, "combo_backtest_timeframe"):
            settings["backtest_config"]["timeframe"] = combo_value(self.combo_backtest_timeframe, "1d")
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

        secret_values = {
            "app_key": self.input_app_key.text().strip() if hasattr(self, "input_app_key") else "",
            "secret_key": self.input_secret.text().strip() if hasattr(self, "input_secret") else "",
            "naver_client_id": self.input_naver_client_id.text().strip() if hasattr(self, "input_naver_client_id") else "",
            "naver_client_secret": self.input_naver_client_secret.text().strip()
            if hasattr(self, "input_naver_client_secret")
            else "",
            "dart_api_key": self.input_dart_api_key.text().strip() if hasattr(self, "input_dart_api_key") else "",
            "fred_api_key": self.input_fred_api_key.text().strip() if hasattr(self, "input_fred_api_key") else "",
            "ai_api_key": self.input_ai_api_key.text().strip() if hasattr(self, "input_ai_api_key") else "",
        }

        allow_plaintext = bool(settings.get("allow_plaintext_secret_fallback", False))
        is_mock = bool(settings.get("is_mock", False))
        # 모의투자 여부와 무관하게 평문 저장은 명시적 opt-in(`allow_plaintext_secret_fallback`)일 때만 허용.
        # 과거에는 is_mock 이면 자동 허용했으나, 모의/실전 동일 키를 재사용하는 사용자 노출 경로가 된다.
        allow_secret_fallback = allow_plaintext

        if KEYRING_AVAILABLE:
            for setting_name, _secret_name in self._secret_field_names():
                settings.pop(setting_name, None)
        else:
            for setting_name, _secret_name in self._secret_field_names():
                value = secret_values.get(setting_name, "")
                if value and allow_secret_fallback:
                    settings[setting_name] = value
                else:
                    settings.pop(setting_name, None)
            if any(secret_values.values()) and not allow_secret_fallback:
                mode_label = "mock" if is_mock else "live"
                self.logger.warning(
                    f"Keyring unavailable; plaintext secret fallback is disabled for {mode_label} mode."
                )
        try:
            for setting_name, secret_name in self._secret_field_names():
                value = secret_values.get(setting_name, "")
                if value:
                    try:
                        keyring.set_password("KiwoomTrader", secret_name, value)
                    except Exception as e:
                        self.logger.warning(f"Keyring {secret_name} 저장 실패 (OS 환경 이슈일 수 있음): {e}")
                        if allow_secret_fallback:
                            settings[setting_name] = value
                        else:
                            settings.pop(setting_name, None)
                else:
                    try:
                        keyring.delete_password("KiwoomTrader", secret_name)
                    except Exception as e:
                        self.logger.warning(f"Keyring {secret_name} 삭제 실패 (무시 가능): {e}")

            # atomic write: 저장 도중 크래시/강제 종료 시 기존 파일이 절단되지 않도록
            # tmp 파일 작성 후 os.replace 로 교체한다(거래내역 저장과 동일 정책).
            self._atomic_write_json(str(Config.SETTINGS_FILE), settings)

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
            self._apply_settings_schema_migration(settings)
            # Keep legacy secret keys visible to the refactor manifest while
            # actual loading is handled by _secret_field_names().
            if "app_key" in settings:
                pass
            if "secret_key" in settings:
                pass

            secret_values = {}
            for setting_name, secret_name in self._secret_field_names():
                value = ""
                try:
                    value = keyring.get_password("KiwoomTrader", secret_name) or ""
                except Exception as exc:
                    self.logger.warning(f"Keyring {secret_name} 로드 실패: {exc}")
                if not value and setting_name in settings:
                    value = settings[setting_name]
                secret_values[setting_name] = value

            self.input_app_key.setText(secret_values.get("app_key", ""))
            self.input_secret.setText(secret_values.get("secret_key", ""))
            if hasattr(self, "input_naver_client_id"):
                self.input_naver_client_id.setText(secret_values.get("naver_client_id", ""))
            if hasattr(self, "input_naver_client_secret"):
                self.input_naver_client_secret.setText(secret_values.get("naver_client_secret", ""))
            if hasattr(self, "input_dart_api_key"):
                self.input_dart_api_key.setText(secret_values.get("dart_api_key", ""))
            if hasattr(self, "input_fred_api_key"):
                self.input_fred_api_key.setText(secret_values.get("fred_api_key", ""))
            if hasattr(self, "input_ai_api_key"):
                self.input_ai_api_key.setText(secret_values.get("ai_api_key", ""))

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
            self.spin_max_loss.setValue(
                settings.get("max_daily_loss", settings.get("max_loss", Config.DEFAULT_MAX_DAILY_LOSS))
            )
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
                self.spin_market_limit.setValue(settings.get("market_limit", Config.DEFAULT_MARKET_LIMIT))
            if hasattr(self, "chk_use_sector_limit"):
                self.chk_use_sector_limit.setChecked(settings.get("use_sector_limit", False))
            if hasattr(self, "spin_sector_limit"):
                self.spin_sector_limit.setValue(settings.get("sector_limit", Config.DEFAULT_SECTOR_LIMIT))
            if hasattr(self, "combo_daily_loss_basis"):
                set_combo_value(
                    self.combo_daily_loss_basis,
                    str(settings.get("daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity"))),
                )
            if hasattr(self, "chk_sync_history_flush_on_exit"):
                self.chk_sync_history_flush_on_exit.setChecked(
                    bool(
                        settings.get(
                            "sync_history_flush_on_exit",
                            getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True),
                        )
                    )
                )
            if hasattr(self, "chk_allow_plaintext_secret_fallback"):
                self.chk_allow_plaintext_secret_fallback.setChecked(
                    bool(
                        settings.get(
                            "allow_plaintext_secret_fallback",
                            getattr(Config, "DEFAULT_ALLOW_PLAINTEXT_SECRET_FALLBACK", False),
                        )
                    )
                )
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
            if hasattr(self, "chk_use_shock_guard"):
                self.chk_use_shock_guard.setChecked(bool(settings.get("use_shock_guard", True)))
            if hasattr(self, "spin_shock_1m"):
                self.spin_shock_1m.setValue(float(settings.get("shock_1m_pct", getattr(Config, "DEFAULT_SHOCK_1M_PCT", 1.5))))
            if hasattr(self, "spin_shock_5m"):
                self.spin_shock_5m.setValue(float(settings.get("shock_5m_pct", getattr(Config, "DEFAULT_SHOCK_5M_PCT", 2.8))))
            if hasattr(self, "spin_shock_cooldown"):
                self.spin_shock_cooldown.setValue(
                    int(settings.get("shock_cooldown_min", getattr(Config, "DEFAULT_SHOCK_COOLDOWN_MIN", 10)))
                )
            if hasattr(self, "chk_use_vi_guard"):
                self.chk_use_vi_guard.setChecked(bool(settings.get("use_vi_guard", True)))
            if hasattr(self, "spin_vi_cooldown"):
                self.spin_vi_cooldown.setValue(
                    int(settings.get("vi_cooldown_min", getattr(Config, "DEFAULT_VI_COOLDOWN_MIN", 7)))
                )
            if hasattr(self, "chk_use_regime_sizing"):
                self.chk_use_regime_sizing.setChecked(bool(settings.get("use_regime_sizing", True)))
            if hasattr(self, "chk_use_liquidity_stress_guard"):
                self.chk_use_liquidity_stress_guard.setChecked(bool(settings.get("use_liquidity_stress_guard", True)))
            if hasattr(self, "chk_use_slippage_guard"):
                self.chk_use_slippage_guard.setChecked(bool(settings.get("use_slippage_guard", True)))
            if hasattr(self, "spin_max_slippage_bps"):
                self.spin_max_slippage_bps.setValue(
                    float(settings.get("max_slippage_bps", getattr(Config, "DEFAULT_MAX_SLIPPAGE_BPS", 15.0)))
                )
            if hasattr(self, "chk_use_order_health_guard"):
                self.chk_use_order_health_guard.setChecked(bool(settings.get("use_order_health_guard", True)))

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
                set_combo_value(self.combo_strategy_pack, str(primary))
            if hasattr(self, "combo_portfolio_mode"):
                set_combo_value(self.combo_portfolio_mode, str(settings.get("portfolio_mode", "single_strategy")))
            if hasattr(self, "chk_short_enabled"):
                self.chk_short_enabled.setChecked(bool(settings.get("short_enabled", False)))
            if hasattr(self, "combo_asset_scope"):
                set_combo_value(self.combo_asset_scope, str(settings.get("asset_scope", "kr_stock_live")))
            if hasattr(self, "combo_execution_policy"):
                set_combo_value(self.combo_execution_policy, str(settings.get("execution_policy", "market")))
            if hasattr(self, "combo_execution_mode"):
                set_combo_value(
                    self.combo_execution_mode,
                    str(settings.get("execution_mode", getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"))),
                )
            bt_cfg = settings.get("backtest_config", {}) if isinstance(settings.get("backtest_config"), dict) else {}
            if hasattr(self, "combo_backtest_timeframe"):
                set_combo_value(self.combo_backtest_timeframe, str(bt_cfg.get("timeframe", "1d")))
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
            market_intelligence = self._deep_merge_dict(
                copy.deepcopy(getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {})),
                copy.deepcopy(settings.get("market_intelligence", {}))
                if isinstance(settings.get("market_intelligence"), dict)
                else {},
            )
            if hasattr(self, "chk_market_intel_enabled"):
                self.chk_market_intel_enabled.setChecked(bool(market_intelligence.get("enabled", True)))
            source_policy = (
                market_intelligence.get("source_policy", {})
                if isinstance(market_intelligence.get("source_policy"), dict)
                else {}
            )
            if hasattr(self, "chk_market_intel_strict_guard"):
                self.chk_market_intel_strict_guard.setChecked(bool(source_policy.get("strict_entry_guard", False)))
            providers = (
                market_intelligence.get("providers", {})
                if isinstance(market_intelligence.get("providers"), dict)
                else {}
            )
            if hasattr(self, "chk_market_news"):
                self.chk_market_news.setChecked(bool(providers.get("news", True)))
            if hasattr(self, "chk_market_dart"):
                self.chk_market_dart.setChecked(bool(providers.get("dart", True)))
            if hasattr(self, "chk_market_datalab"):
                self.chk_market_datalab.setChecked(bool(providers.get("datalab", True)))
            if hasattr(self, "chk_market_macro"):
                self.chk_market_macro.setChecked(bool(providers.get("macro", True)))
            refresh_sec = (
                market_intelligence.get("refresh_sec", {})
                if isinstance(market_intelligence.get("refresh_sec"), dict)
                else {}
            )
            if hasattr(self, "spin_market_news_refresh"):
                self.spin_market_news_refresh.setValue(
                    int(refresh_sec.get("news", getattr(Config, "MARKET_INTEL_REFRESH_SEC", 60)))
                )
            if hasattr(self, "spin_market_macro_refresh"):
                self.spin_market_macro_refresh.setValue(
                    int(refresh_sec.get("macro", getattr(Config, "MARKET_INTEL_MACRO_REFRESH_SEC", 300)))
                )
            scoring = (
                market_intelligence.get("scoring", {})
                if isinstance(market_intelligence.get("scoring"), dict)
                else {}
            )
            if hasattr(self, "spin_market_news_block"):
                self.spin_market_news_block.setValue(abs(int(scoring.get("news_block_threshold", -60))))
            if hasattr(self, "spin_market_news_boost"):
                self.spin_market_news_boost.setValue(abs(int(scoring.get("news_boost_threshold", 60))))
            ai_cfg = market_intelligence.get("ai", {}) if isinstance(market_intelligence.get("ai"), dict) else {}
            if hasattr(self, "chk_market_ai_enabled"):
                self.chk_market_ai_enabled.setChecked(bool(ai_cfg.get("enabled", False)))
            if hasattr(self, "combo_market_ai_provider"):
                set_combo_value(self.combo_market_ai_provider, str(ai_cfg.get("provider", "gemini")))
            if hasattr(self, "input_market_ai_model"):
                self.input_market_ai_model.setText(str(ai_cfg.get("model", "gemini-2.5-flash-lite")))
            if hasattr(self, "spin_market_ai_daily_calls"):
                self.spin_market_ai_daily_calls.setValue(int(ai_cfg.get("max_calls_per_day", 30)))
            if hasattr(self, "spin_market_ai_symbol_calls"):
                self.spin_market_ai_symbol_calls.setValue(int(ai_cfg.get("max_calls_per_symbol", 3)))
            if hasattr(self, "spin_market_ai_budget"):
                self.spin_market_ai_budget.setValue(int(ai_cfg.get("daily_budget_krw", 1000)))

            cfg = getattr(self, "config", None)
            if cfg is not None:
                cfg.strategy_pack = self._deep_merge_dict(
                    copy.deepcopy(getattr(Config, "DEFAULT_STRATEGY_PACK", {})),
                    settings.get("strategy_pack", {}) if isinstance(settings.get("strategy_pack"), dict) else {},
                )
                cfg.strategy_params = dict(settings.get("strategy_params", getattr(cfg, "strategy_params", {})))
                cfg.portfolio_mode = str(settings.get("portfolio_mode", getattr(cfg, "portfolio_mode", "single_strategy")))
                cfg.short_enabled = bool(settings.get("short_enabled", getattr(cfg, "short_enabled", False)))
                cfg.asset_scope = str(settings.get("asset_scope", getattr(cfg, "asset_scope", "kr_stock_live")))
                cfg.backtest_config = self._deep_merge_dict(
                    copy.deepcopy(getattr(Config, "DEFAULT_BACKTEST_CONFIG", {})),
                    settings.get("backtest_config", {}) if isinstance(settings.get("backtest_config"), dict) else {},
                )
                cfg.feature_flags = self._deep_merge_dict(
                    copy.deepcopy(getattr(Config, "FEATURE_FLAGS", {})),
                    settings.get("feature_flags", {}) if isinstance(settings.get("feature_flags"), dict) else {},
                )
                cfg.execution_policy = str(settings.get("execution_policy", getattr(cfg, "execution_policy", "market")))
                cfg.execution_mode = str(
                    settings.get(
                        "execution_mode",
                        getattr(cfg, "execution_mode", getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only")),
                    )
                )
                cfg.market_intelligence = market_intelligence
                cfg.max_daily_loss = float(
                    settings.get("max_daily_loss", settings.get("max_loss", getattr(cfg, "max_daily_loss", 3.0)))
                )
                cfg.daily_loss_basis = str(
                    settings.get(
                        "daily_loss_basis",
                        getattr(cfg, "daily_loss_basis", getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity")),
                    )
                )
                cfg.sync_history_flush_on_exit = bool(
                    settings.get(
                        "sync_history_flush_on_exit",
                        getattr(
                            cfg,
                            "sync_history_flush_on_exit",
                            getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True),
                        ),
                    )
                )
                cfg.allow_plaintext_secret_fallback = bool(
                    settings.get(
                        "allow_plaintext_secret_fallback",
                        getattr(
                            cfg,
                            "allow_plaintext_secret_fallback",
                            getattr(Config, "DEFAULT_ALLOW_PLAINTEXT_SECRET_FALLBACK", False),
                        ),
                    )
                )
                for key, default in self._v4_guard_defaults().items():
                    setattr(cfg, key, settings.get(key, getattr(cfg, key, default)))
            sync_market_intel = getattr(self, "_update_market_intelligence_config_from_ui", None)
            if callable(sync_market_intel):
                sync_market_intel()

            self.log("📂 설정 불러옴")
        except (json.JSONDecodeError, FileNotFoundError, OSError) as exc:
            self.logger.warning(f"설정 로드 실패: {exc}")
    def _clear_stored_secrets(self):
        for _setting_name, secret_name in self._secret_field_names():
            try:
                keyring.delete_password("KiwoomTrader", secret_name)
            except Exception as exc:
                self.logger.warning(f"Keyring {secret_name} 삭제 실패 (무시 가능): {exc}")

        try:
            settings_path = Path(Config.SETTINGS_FILE)
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as file:
                    settings = json.load(file)
                if isinstance(settings, dict):
                    for setting_name, _secret_name in self._secret_field_names():
                        settings.pop(setting_name, None)
                    self._atomic_write_json(str(settings_path), settings)
        except (json.JSONDecodeError, OSError) as exc:
            self.logger.warning(f"평문 secret 정리 실패: {exc}")

        auth = getattr(self, "auth", None)
        invalidator = getattr(auth, "invalidate_token", None)
        if callable(invalidator):
            invalidator()
        for filename in ("kiwoom_token_cache.json", "kiwoom_token_cache_live.json", "kiwoom_token_cache_mock.json"):
            try:
                path = Path(getattr(Config, "BASE_DIR", ".")) / filename
                if path.exists():
                    path.unlink()
            except OSError as exc:
                self.logger.warning(f"토큰 캐시 삭제 실패 {filename}: {exc}")

        for attr in (
            "input_app_key",
            "input_secret",
            "input_naver_client_id",
            "input_naver_client_secret",
            "input_dart_api_key",
            "input_fred_api_key",
            "input_ai_api_key",
        ):
            widget = getattr(self, attr, None)
            setter = getattr(widget, "setText", None)
            if callable(setter):
                setter("")
        self.log("Stored API secrets and token caches cleared.")
