"""UI construction mixin for KiwoomProTrader."""

# pyright: reportWildcardImportFromLibrary=false
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import *

from app.support.backtest_runner import backtest_result_to_dict, metric_rows, run_backtest_from_files
from app.support.ui_text import (
    ASSET_SCOPE_CHOICES,
    BACKTEST_TIMEFRAME_CHOICES,
    DAILY_LOSS_BASIS_CHOICES,
    EXECUTION_MODE_CHOICES,
    EXECUTION_POLICY_CHOICES,
    PORTFOLIO_MODE_CHOICES,
    STRATEGY_CHOICES,
    populate_combo,
)
from app.support.worker import Worker
from app.support.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox
from config import Config
from dark_theme import DARK_STYLESHEET
from app.mixins._typing import TraderMixinBase


class UIBuildDataTabsMixin(TraderMixinBase):
    def _create_stats_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.stats_labels = {}
        stats_group = QGroupBox("📊 오늘의 성과")
        grid = QGridLayout()

        for i, (key, label) in enumerate([
            ("trades", "총 거래 횟수"), ("wins", "이익 거래"), ("winrate", "승률"),
            ("profit", "실현 손익"), ("max_profit", "최대 수익"), ("max_loss", "최대 손실")
        ]):
            grid.addWidget(QLabel(f"{label}:"), i // 3, (i % 3) * 2)
            lbl = QLabel("-")
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.stats_labels[key] = lbl
            grid.addWidget(lbl, i // 3, (i % 3) * 2 + 1)

        stats_group.setLayout(grid)
        layout.addWidget(stats_group)

        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self._update_stats)
        layout.addWidget(btn_refresh)
        layout.addStretch()
        return widget
    def _create_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.history_table = QTableWidget()
        cols = ["시간", "종목", "구분", "가격", "수량", "금액", "손익", "사유"]
        self.history_table.setColumnCount(len(cols))
        self.history_table.setHorizontalHeaderLabels(cols)
        history_header = self.history_table.horizontalHeader()
        if history_header is not None:
            history_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history_table)

        btn_layout = QHBoxLayout()
        btn_export = QPushButton("📤 CSV 내보내기")
        btn_export.clicked.connect(self._export_csv)
        btn_layout.addWidget(btn_export)
        btn_clear = QPushButton("🗑️ 오늘 기록 삭제")
        btn_clear.clicked.connect(self._clear_today_history)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._refresh_history_table()
        return widget
    def _create_diagnostics_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        action_row = QHBoxLayout()
        self.btn_diag_resync_selected = QPushButton("선택 종목 재동기화")
        self.btn_diag_resync_selected.clicked.connect(self._on_diagnostic_resync_selected)
        action_row.addWidget(self.btn_diag_resync_selected)
        self.btn_diag_release_sync_failed = QPushButton("동기화 실패 해제 요청")
        self.btn_diag_release_sync_failed.clicked.connect(self._on_diagnostic_release_sync_failed_selected)
        action_row.addWidget(self.btn_diag_release_sync_failed)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.diagnostic_table = QTableWidget()
        cols = [
            "코드",
            "종목명",
            "대기 주문 방향",
            "대기 주문 사유",
            "대기 만료 시각",
            "동기화 상태",
            "재시도 횟수",
            "마지막 동기화 오류",
            "최근 갱신",
            "외부 데이터 상태",
            "외부 데이터 시각",
            "외부 데이터 경과(초)",
            "시장 상태",
            "보호 사유",
            "인텔리전스 소스 상태",
            "자동매매 정책",
            "수량 배수",
            "청산 정책",
            "마지막 이벤트 ID",
            "시장 위험 모드",
            "주문 안정성 모드",
            "대기 주문 상태",
            "미체결 수량",
            "동기화 실패 사유",
        ]
        self.diagnostic_table.setColumnCount(len(cols))
        self.diagnostic_table.setHorizontalHeaderLabels(cols)
        diagnostic_header = self.diagnostic_table.horizontalHeader()
        diagnostic_vertical_header = self.diagnostic_table.verticalHeader()
        if diagnostic_header is not None:
            diagnostic_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        if diagnostic_vertical_header is not None:
            diagnostic_vertical_header.setVisible(False)
        self.diagnostic_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diagnostic_table.itemSelectionChanged.connect(self._on_diagnostic_selection_changed)
        layout.addWidget(self.diagnostic_table)

        self.diag_detail_panel = QPlainTextEdit()
        self.diag_detail_panel.setReadOnly(True)
        self.diag_detail_panel.setMaximumHeight(180)
        self.diag_detail_panel.setPlainText("선택된 종목이 없습니다.")
        layout.addWidget(self.diag_detail_panel)

        info = QLabel("주문/동기화 상태를 실시간으로 진단합니다. 이 화면은 읽기 전용입니다.")
        info.setWordWrap(True)
        layout.addWidget(info)
        return widget
    def _create_api_tab(self):
        """API/알림 설정 탭"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # API 인증
        group1 = QGroupBox("🔐 키움 REST API 인증")
        form1 = QFormLayout()
        self.input_app_key = QLineEdit()
        self.input_app_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_app_key.setPlaceholderText("키움 App Key")
        form1.addRow("앱 키:", self.input_app_key)
        self.input_secret = QLineEdit()
        self.input_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_secret.setPlaceholderText("키움 Secret Key")
        form1.addRow("시크릿 키:", self.input_secret)
        self.chk_mock = QCheckBox("모의투자 사용")
        form1.addRow("", self.chk_mock)
        group1.setLayout(form1)
        layout.addWidget(group1)

        # 텔레그램
        group2 = QGroupBox("📱 텔레그램 알림")
        form2 = QFormLayout()
        self.input_tg_token = QLineEdit()
        self.input_tg_token.setPlaceholderText("텔레그램 Bot Token")
        form2.addRow("봇 토큰:", self.input_tg_token)
        self.input_tg_chat = QLineEdit()
        self.input_tg_chat.setPlaceholderText("텔레그램 Chat ID")
        form2.addRow("챗 ID:", self.input_tg_chat)
        self.chk_use_telegram = QCheckBox("텔레그램 알림 사용")
        form2.addRow("", self.chk_use_telegram)
        group2.setLayout(form2)
        layout.addWidget(group2)

        group3 = QGroupBox("ℹ️ 안내")
        form3 = QFormLayout()
        info_auto_start = QLabel(
            "시장 인텔리전스 관련 설정은 [🧠 인텔리전스 설정] 탭에서 관리합니다.\n자동 실행과 앱 동작 설정은 [🛠 상세 설정 > 시스템]에서 변경합니다."
        )
        info_auto_start.setWordWrap(True)
        form3.addRow("", info_auto_start)

        group3.setLayout(form3)
        layout.addWidget(group3)

        btn_save = QPushButton("💾 전체 설정 저장")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)
        layout.addStretch()

        scroll.setWidget(content_widget)
        tab_layout.addWidget(scroll)

        return tab_widget
