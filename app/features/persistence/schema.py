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


class PersistenceSchemaMixin(TraderMixinBase):
    @staticmethod
    def _deep_merge_dict(base: dict, override: dict) -> dict:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = PersistenceSchemaMixin._deep_merge_dict(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    @staticmethod
    def _v4_guard_defaults() -> dict:
        return {
            "use_shock_guard": bool(getattr(Config, "DEFAULT_USE_SHOCK_GUARD", True)),
            "shock_1m_pct": float(getattr(Config, "DEFAULT_SHOCK_1M_PCT", 1.5)),
            "shock_5m_pct": float(getattr(Config, "DEFAULT_SHOCK_5M_PCT", 2.8)),
            "shock_cooldown_min": int(getattr(Config, "DEFAULT_SHOCK_COOLDOWN_MIN", 10)),
            "use_vi_guard": bool(getattr(Config, "DEFAULT_USE_VI_GUARD", True)),
            "vi_cooldown_min": int(getattr(Config, "DEFAULT_VI_COOLDOWN_MIN", 7)),
            "vi_proxy_1m_pct": float(getattr(Config, "DEFAULT_VI_PROXY_1M_PCT", 4.0)),
            "vi_proxy_spread_pct": float(getattr(Config, "DEFAULT_VI_PROXY_SPREAD_PCT", 1.2)),
            "use_regime_sizing": bool(getattr(Config, "DEFAULT_USE_REGIME_SIZING", True)),
            "regime_elevated_atr_pct": float(getattr(Config, "DEFAULT_REGIME_ELEVATED_ATR_PCT", 2.5)),
            "regime_extreme_atr_pct": float(getattr(Config, "DEFAULT_REGIME_EXTREME_ATR_PCT", 4.0)),
            "regime_size_scale_elevated": float(getattr(Config, "DEFAULT_REGIME_SIZE_SCALE_ELEVATED", 0.7)),
            "regime_size_scale_extreme": float(getattr(Config, "DEFAULT_REGIME_SIZE_SCALE_EXTREME", 0.4)),
            "use_liquidity_stress_guard": bool(getattr(Config, "DEFAULT_USE_LIQUIDITY_STRESS_GUARD", True)),
            "stress_spread_pct": float(getattr(Config, "DEFAULT_STRESS_SPREAD_PCT", 1.0)),
            "stress_min_value_ratio": float(getattr(Config, "DEFAULT_STRESS_MIN_VALUE_RATIO", 0.35)),
            "use_slippage_guard": bool(getattr(Config, "DEFAULT_USE_SLIPPAGE_GUARD", True)),
            "max_slippage_bps": float(getattr(Config, "DEFAULT_MAX_SLIPPAGE_BPS", 15.0)),
            "slippage_window_trades": int(getattr(Config, "DEFAULT_SLIPPAGE_WINDOW_TRADES", 20)),
            "use_order_health_guard": bool(getattr(Config, "DEFAULT_USE_ORDER_HEALTH_GUARD", True)),
            "order_health_fail_count": int(getattr(Config, "DEFAULT_ORDER_HEALTH_FAIL_COUNT", 5)),
            "order_health_window_sec": int(getattr(Config, "DEFAULT_ORDER_HEALTH_WINDOW_SEC", 60)),
            "order_health_cooldown_sec": int(getattr(Config, "DEFAULT_ORDER_HEALTH_COOLDOWN_SEC", 180)),
        }
    @staticmethod
    def _secret_field_names() -> tuple[tuple[str, str], ...]:
        return (
            ("app_key", "app_key"),
            ("secret_key", "secret_key"),
            ("naver_client_id", "naver_client_id"),
            ("naver_client_secret", "naver_client_secret"),
            ("dart_api_key", "dart_api_key"),
            ("fred_api_key", "fred_api_key"),
            ("ai_api_key", "ai_api_key"),
        )
    def _apply_settings_schema_migration(self, settings: dict):
        version = int(settings.get("settings_version", 1))
        if version < 3:
            settings.setdefault("strategy_pack", dict(getattr(Config, "DEFAULT_STRATEGY_PACK", {})))
            settings.setdefault("strategy_params", dict(getattr(Config, "DEFAULT_STRATEGY_PARAMS", {})))
            settings.setdefault("portfolio_mode", getattr(Config, "DEFAULT_PORTFOLIO_MODE", "single_strategy"))
            settings.setdefault("short_enabled", getattr(Config, "DEFAULT_SHORT_ENABLED", False))
            settings.setdefault("asset_scope", getattr(Config, "DEFAULT_ASSET_SCOPE", "kr_stock_live"))
            settings.setdefault("backtest_config", dict(getattr(Config, "DEFAULT_BACKTEST_CONFIG", {})))
            settings.setdefault("feature_flags", dict(getattr(Config, "FEATURE_FLAGS", {})))
            settings.setdefault("execution_policy", getattr(Config, "DEFAULT_EXECUTION_POLICY", "market"))
            settings.setdefault("max_daily_loss", settings.get("max_loss", Config.DEFAULT_MAX_DAILY_LOSS))
        settings.setdefault("execution_mode", getattr(Config, "DEFAULT_EXECUTION_MODE", "signal_only"))
        settings.setdefault(
            "allow_plaintext_secret_fallback",
            bool(getattr(Config, "DEFAULT_ALLOW_PLAINTEXT_SECRET_FALLBACK", False)),
        )

        for key, default in (
            ("strategy_pack", getattr(Config, "DEFAULT_STRATEGY_PACK", {})),
            ("backtest_config", getattr(Config, "DEFAULT_BACKTEST_CONFIG", {})),
            ("feature_flags", getattr(Config, "FEATURE_FLAGS", {})),
        ):
            existing = settings.get(key, {})
            if isinstance(existing, dict):
                settings[key] = self._deep_merge_dict(copy.deepcopy(default), existing)
            else:
                settings[key] = copy.deepcopy(default)

        settings.setdefault(
            "daily_loss_basis",
            getattr(Config, "DEFAULT_DAILY_LOSS_BASIS", "total_equity"),
        )
        settings.setdefault(
            "sync_history_flush_on_exit",
            bool(getattr(Config, "DEFAULT_SYNC_HISTORY_FLUSH_ON_EXIT", True)),
        )
        settings.setdefault("market_limit", int(getattr(Config, "DEFAULT_MARKET_LIMIT", 70)))
        settings.setdefault("sector_limit", int(getattr(Config, "DEFAULT_SECTOR_LIMIT", 30)))

        for key, default in self._v4_guard_defaults().items():
            settings.setdefault(key, default)

        existing_market_intel = settings.get("market_intelligence", {})
        default_market_intel = copy.deepcopy(getattr(Config, "DEFAULT_MARKET_INTELLIGENCE_CONFIG", {}))
        if isinstance(existing_market_intel, dict):
            settings["market_intelligence"] = self._deep_merge_dict(default_market_intel, existing_market_intel)
        else:
            settings["market_intelligence"] = default_market_intel

        settings["settings_version"] = int(getattr(Config, "SETTINGS_SCHEMA_VERSION", 7))
    @staticmethod
    def _atomic_write_json(path: str, payload) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_name(f"{target.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, target)
