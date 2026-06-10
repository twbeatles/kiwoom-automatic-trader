"""Market intelligence mixin for KiwoomProTrader."""

from __future__ import annotations

import copy
import datetime
import hashlib
import html
import json
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.support.ui_text import (
    AI_PROVIDER_CHOICES,
    REPLAY_AUDIT_CHOICES,
    REPLAY_SCOPE_CHOICES,
    combo_value,
    display_action_policy,
    display_allowed,
    display_event_severity,
    display_event_type,
    display_exit_policy,
    display_market_state,
    display_news_sentiment,
    display_regime,
    display_replay_scope,
    display_source_health,
    display_source_name,
    display_status,
    display_yes_no,
    populate_combo,
    set_combo_value,
)
from app.support.widgets import NoScrollComboBox, NoScrollSpinBox
from config import Config
from data.providers import AIProvider, DartProvider, MacroProvider, NaverTrendProvider, NewsProvider
from app.mixins._typing import TraderMixinBase


class MarketIntelSettingsUIMixin(TraderMixinBase):
    def _bind_market_intelligence_signals(self):
        for name in (
            "chk_market_intel_enabled",
            "chk_market_news",
            "chk_market_dart",
            "chk_market_datalab",
            "chk_market_macro",
            "chk_market_intel_strict_guard",
            "chk_market_ai_enabled",
            "spin_market_news_refresh",
            "spin_market_macro_refresh",
            "spin_market_news_block",
            "spin_market_news_boost",
            "spin_market_ai_daily_calls",
            "spin_market_ai_symbol_calls",
            "spin_market_ai_budget",
            "combo_market_ai_provider",
            "input_market_ai_model",
        ):
            control = getattr(self, name, None)
            if control is None:
                continue
            for signal_name in ("toggled", "valueChanged", "currentTextChanged", "textChanged"):
                signal = getattr(control, signal_name, None)
                if signal is not None:
                    signal.connect(self._update_market_intelligence_config_from_ui)
                    break
    def _update_market_intelligence_config_from_ui(self, *_args):
        cfg = self._market_intelligence_config()
        cfg["enabled"] = bool(getattr(self, "chk_market_intel_enabled", None) and self.chk_market_intel_enabled.isChecked())
        cfg["providers"]["news"] = bool(getattr(self, "chk_market_news", None) and self.chk_market_news.isChecked())
        cfg["providers"]["dart"] = bool(getattr(self, "chk_market_dart", None) and self.chk_market_dart.isChecked())
        cfg["providers"]["datalab"] = bool(getattr(self, "chk_market_datalab", None) and self.chk_market_datalab.isChecked())
        cfg["providers"]["macro"] = bool(getattr(self, "chk_market_macro", None) and self.chk_market_macro.isChecked())
        policy = cfg.get("source_policy", {})
        if not isinstance(policy, dict):
            policy = {}
            cfg["source_policy"] = policy
        policy["strict_entry_guard"] = bool(
            getattr(self, "chk_market_intel_strict_guard", None)
            and self.chk_market_intel_strict_guard.isChecked()
        )
        if hasattr(self, "spin_market_news_refresh"):
            refresh = int(self.spin_market_news_refresh.value())
            cfg["refresh_sec"]["news"] = refresh
            cfg["refresh_sec"]["dart"] = refresh
            cfg["refresh_sec"]["datalab"] = refresh
        if hasattr(self, "spin_market_macro_refresh"):
            cfg["refresh_sec"]["macro"] = int(self.spin_market_macro_refresh.value())
        if hasattr(self, "spin_market_news_block"):
            cfg["scoring"]["news_block_threshold"] = -abs(int(self.spin_market_news_block.value()))
        if hasattr(self, "spin_market_news_boost"):
            cfg["scoring"]["news_boost_threshold"] = abs(int(self.spin_market_news_boost.value()))
        if hasattr(self, "chk_market_ai_enabled"):
            cfg["ai"]["enabled"] = bool(self.chk_market_ai_enabled.isChecked())
        if hasattr(self, "combo_market_ai_provider"):
            cfg["ai"]["provider"] = combo_value(self.combo_market_ai_provider, "gemini").lower()
        if hasattr(self, "input_market_ai_model"):
            cfg["ai"]["model"] = str(self.input_market_ai_model.text() or cfg["ai"].get("model", "gemini-2.5-flash-lite"))
        if hasattr(self, "spin_market_ai_daily_calls"):
            cfg["ai"]["max_calls_per_day"] = int(self.spin_market_ai_daily_calls.value())
        if hasattr(self, "spin_market_ai_symbol_calls"):
            cfg["ai"]["max_calls_per_symbol"] = int(self.spin_market_ai_symbol_calls.value())
        if hasattr(self, "spin_market_ai_budget"):
            cfg["ai"]["daily_budget_krw"] = int(self.spin_market_ai_budget.value())
        if hasattr(self, "config"):
            self.config.market_intelligence = cfg
    def _create_market_intelligence_settings_tab(self):
        from PyQt6.QtWidgets import QCheckBox

        cfg = self._market_intelligence_config()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        body = QVBoxLayout(content)

        intro = QLabel(
            "시장 인텔리전스는 뉴스, 공시, 검색량, 매크로 데이터를 읽어 자동매매를 보조합니다. "
            "초보자는 먼저 '기본 사용'과 '점수/차단 기준'만 확인해도 충분합니다."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b949e;")
        body.addWidget(intro)

        basic_group = QGroupBox("기본 사용")
        basic_form = QFormLayout(basic_group)
        self.chk_market_intel_enabled = QCheckBox("시장 인텔리전스 사용")
        self.chk_market_intel_enabled.setChecked(bool(cfg.get("enabled", True)))
        basic_form.addRow("", self.chk_market_intel_enabled)
        source_policy = cfg.get("source_policy", {}) if isinstance(cfg.get("source_policy"), dict) else {}
        self.chk_market_intel_strict_guard = QCheckBox("인텔리전스 준비 전 신규 진입 차단")
        self.chk_market_intel_strict_guard.setToolTip("실거래에서 fail-closed 정책이 필요할 때 켭니다.")
        self.chk_market_intel_strict_guard.setChecked(bool(source_policy.get("strict_entry_guard", False)))
        basic_form.addRow("", self.chk_market_intel_strict_guard)
        body.addWidget(basic_group)

        source_group = QGroupBox("데이터 소스")
        source_form = QFormLayout(source_group)
        self.chk_market_news = QCheckBox("NAVER 뉴스 사용")
        self.chk_market_news.setChecked(bool(cfg.get("providers", {}).get("news", True)))
        self.chk_market_dart = QCheckBox("OpenDART 공시 사용")
        self.chk_market_dart.setChecked(bool(cfg.get("providers", {}).get("dart", True)))
        self.chk_market_datalab = QCheckBox("NAVER 데이터랩 사용")
        self.chk_market_datalab.setChecked(bool(cfg.get("providers", {}).get("datalab", True)))
        self.chk_market_macro = QCheckBox("FRED 매크로 데이터 사용")
        self.chk_market_macro.setChecked(bool(cfg.get("providers", {}).get("macro", True)))
        provider_row = QHBoxLayout()
        provider_row.addWidget(self.chk_market_news)
        provider_row.addWidget(self.chk_market_dart)
        provider_row.addWidget(self.chk_market_datalab)
        provider_row.addWidget(self.chk_market_macro)
        source_form.addRow("사용 소스:", provider_row)

        self.input_naver_client_id = QLineEdit()
        self.input_naver_client_id.setPlaceholderText("NAVER Client ID")
        source_form.addRow("NAVER Client ID:", self.input_naver_client_id)
        self.input_naver_client_secret = QLineEdit()
        self.input_naver_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_naver_client_secret.setPlaceholderText("NAVER Client Secret")
        source_form.addRow("NAVER Client Secret:", self.input_naver_client_secret)

        self.input_dart_api_key = QLineEdit()
        self.input_dart_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_dart_api_key.setPlaceholderText("OPEN_DART_API_KEY")
        source_form.addRow("DART API Key:", self.input_dart_api_key)

        self.input_fred_api_key = QLineEdit()
        self.input_fred_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_fred_api_key.setPlaceholderText("FRED_API_KEY")
        source_form.addRow("FRED API Key:", self.input_fred_api_key)
        body.addWidget(source_group)

        refresh_group = QGroupBox("갱신 주기")
        refresh_form = QFormLayout(refresh_group)
        self.spin_market_news_refresh = NoScrollSpinBox()
        self.spin_market_news_refresh.setRange(10, 600)
        self.spin_market_news_refresh.setValue(int(cfg.get("refresh_sec", {}).get("news", 60)))
        refresh_form.addRow("뉴스/공시 갱신(초):", self.spin_market_news_refresh)
        self.spin_market_macro_refresh = NoScrollSpinBox()
        self.spin_market_macro_refresh.setRange(30, 1800)
        self.spin_market_macro_refresh.setValue(int(cfg.get("refresh_sec", {}).get("macro", 300)))
        refresh_form.addRow("매크로 갱신(초):", self.spin_market_macro_refresh)
        body.addWidget(refresh_group)

        scoring_group = QGroupBox("점수/차단 기준")
        scoring_form = QFormLayout(scoring_group)
        self.spin_market_news_block = NoScrollSpinBox()
        self.spin_market_news_block.setRange(10, 100)
        self.spin_market_news_block.setValue(abs(int(cfg.get("scoring", {}).get("news_block_threshold", -60))))
        scoring_form.addRow("신규 진입 차단 점수:", self.spin_market_news_block)
        self.spin_market_news_boost = NoScrollSpinBox()
        self.spin_market_news_boost.setRange(10, 100)
        self.spin_market_news_boost.setValue(abs(int(cfg.get("scoring", {}).get("news_boost_threshold", 60))))
        scoring_form.addRow("우선순위 강화 점수:", self.spin_market_news_boost)
        body.addWidget(scoring_group)

        ai_group = QGroupBox("AI 요약")
        ai_form = QFormLayout(ai_group)
        self.chk_market_ai_enabled = QCheckBox("AI 요약 사용")
        self.chk_market_ai_enabled.setChecked(bool(cfg.get("ai", {}).get("enabled", False)))
        ai_form.addRow("", self.chk_market_ai_enabled)
        self.combo_market_ai_provider = NoScrollComboBox()
        populate_combo(self.combo_market_ai_provider, AI_PROVIDER_CHOICES, str(cfg.get("ai", {}).get("provider", "gemini")))
        ai_form.addRow("AI 제공사:", self.combo_market_ai_provider)
        self.input_market_ai_model = QLineEdit(str(cfg.get("ai", {}).get("model", "gemini-2.5-flash-lite")))
        self.input_market_ai_model.setPlaceholderText("예: gemini-2.5-flash-lite")
        ai_form.addRow("모델 이름:", self.input_market_ai_model)
        self.input_ai_api_key = QLineEdit()
        self.input_ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_ai_api_key.setPlaceholderText("AI_API_KEY")
        ai_form.addRow("AI API Key:", self.input_ai_api_key)

        self.spin_market_ai_daily_calls = NoScrollSpinBox()
        self.spin_market_ai_daily_calls.setRange(1, 500)
        self.spin_market_ai_daily_calls.setValue(int(cfg.get("ai", {}).get("max_calls_per_day", 30)))
        ai_form.addRow("하루 최대 호출 수:", self.spin_market_ai_daily_calls)
        self.spin_market_ai_symbol_calls = NoScrollSpinBox()
        self.spin_market_ai_symbol_calls.setRange(1, 50)
        self.spin_market_ai_symbol_calls.setValue(int(cfg.get("ai", {}).get("max_calls_per_symbol", 3)))
        ai_form.addRow("종목당 최대 호출 수:", self.spin_market_ai_symbol_calls)
        self.spin_market_ai_budget = NoScrollSpinBox()
        self.spin_market_ai_budget.setRange(100, 100000)
        self.spin_market_ai_budget.setValue(int(cfg.get("ai", {}).get("daily_budget_krw", 1000)))
        ai_form.addRow("하루 예산(원):", self.spin_market_ai_budget)
        body.addWidget(ai_group)

        note_group = QGroupBox("설명/주의사항")
        note_layout = QVBoxLayout(note_group)
        note = QLabel(
            "1. 악재 뉴스나 공시는 신규 진입을 막거나 기존 포지션 청산 정책을 강화할 수 있습니다.\n"
            "2. AI 요약은 보조 수단입니다. 결정론적 규칙이 항상 우선합니다.\n"
            "3. 실거래 전에는 API 키와 로그 저장 위치를 반드시 점검하세요."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #d29922;")
        note_layout.addWidget(note)
        body.addWidget(note_group)

        body.addStretch()
        return widget
