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


class UIBuildMarketTabsMixin(TraderMixinBase):
    def _create_chart_tab(self):
        """📈 차트 시각화 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 종목 선택
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("종목코드:"))
        self.chart_code_input = QLineEdit("005930")
        self.chart_code_input.setMaximumWidth(100)
        ctrl_layout.addWidget(self.chart_code_input)

        self.chart_type_combo = NoScrollComboBox()
        self.chart_type_combo.addItems(["일봉", "주봉", "1분봉", "5분봉", "15분봉", "30분봉", "60분봉"])
        ctrl_layout.addWidget(self.chart_type_combo)

        btn_load = QPushButton("🔄 차트 조회")
        btn_load.clicked.connect(self._load_chart)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # 차트 영역 (테이블로 대체 - pyqtgraph 없을 시)
        self.chart_table = QTableWidget()
        self.chart_table.setColumnCount(6)
        self.chart_table.setHorizontalHeaderLabels(["날짜", "시가", "고가", "저가", "종가", "거래량"])
        chart_header = self.chart_table.horizontalHeader()
        if chart_header is not None:
            chart_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.chart_table)

        # 차트 정보
        self.chart_info = QLabel("차트를 조회하세요")
        self.chart_info.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        layout.addWidget(self.chart_info)

        return widget
    def _create_orderbook_tab(self):
        """📋 호가창 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 종목 선택
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("종목코드:"))
        self.hoga_code_input = QLineEdit("005930")
        self.hoga_code_input.setMaximumWidth(100)
        ctrl_layout.addWidget(self.hoga_code_input)

        btn_load = QPushButton("🔄 호가 조회")
        btn_load.clicked.connect(self._load_orderbook)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # 호가 테이블 그룹
        hoga_group = QGroupBox("10단 호가")
        hoga_layout = QHBoxLayout()
        hoga_layout.setSpacing(10)

        # 매도 호가 테이블
        self.ask_table = QTableWidget(10, 2)
        self.ask_table.setHorizontalHeaderLabels(["매도호가", "잔량"])
        ask_vertical_header = self.ask_table.verticalHeader()
        ask_horizontal_header = self.ask_table.horizontalHeader()
        if ask_vertical_header is not None:
            ask_vertical_header.setVisible(False)  # 행 번호 숨김
        if ask_horizontal_header is not None:
            ask_horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ask_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ask_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ask_table.setFixedHeight(320)
        for i in range(10):
            self.ask_table.setRowHeight(i, 28)
        hoga_layout.addWidget(self.ask_table)

        # 매수 호가 테이블
        self.bid_table = QTableWidget(10, 2)
        self.bid_table.setHorizontalHeaderLabels(["매수호가", "잔량"])
        bid_vertical_header = self.bid_table.verticalHeader()
        bid_horizontal_header = self.bid_table.horizontalHeader()
        if bid_vertical_header is not None:
            bid_vertical_header.setVisible(False)  # 행 번호 숨김
        if bid_horizontal_header is not None:
            bid_horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bid_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bid_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.bid_table.setFixedHeight(320)
        for i in range(10):
            self.bid_table.setRowHeight(i, 28)
        hoga_layout.addWidget(self.bid_table)

        hoga_group.setLayout(hoga_layout)
        layout.addWidget(hoga_group)

        # 총 잔량 표시
        self.hoga_info = QLabel("총 매도잔량: - | 총 매수잔량: -")
        self.hoga_info.setStyleSheet("font-weight: bold; padding: 10px; font-size: 14px;")
        layout.addWidget(self.hoga_info)

        layout.addStretch()
        return widget
    def _create_condition_tab(self):
        """🔍 조건검색 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 조건식 선택
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("조건식:"))
        self.condition_combo = NoScrollComboBox()
        self.condition_combo.setMinimumWidth(200)
        ctrl_layout.addWidget(self.condition_combo)

        btn_refresh = QPushButton("🔄 목록 갱신")
        btn_refresh.clicked.connect(self._load_conditions)
        ctrl_layout.addWidget(btn_refresh)

        btn_search = QPushButton("🔍 검색 실행")
        btn_search.clicked.connect(self._execute_condition)
        ctrl_layout.addWidget(btn_search)

        btn_apply = QPushButton("📌 종목 적용")
        btn_apply.clicked.connect(self._apply_condition_result)
        ctrl_layout.addWidget(btn_apply)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # 검색 결과
        self.condition_table = QTableWidget()
        self.condition_table.setColumnCount(5)
        self.condition_table.setHorizontalHeaderLabels(["종목코드", "종목명", "현재가", "등락률", "거래량"])
        condition_header = self.condition_table.horizontalHeader()
        if condition_header is not None:
            condition_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.condition_table)

        self.condition_info = QLabel("조건검색 결과가 여기에 표시됩니다")
        layout.addWidget(self.condition_info)

        return widget
    def _create_ranking_tab(self):
        """🏆 순위 정보 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 순위 유형 선택
        ctrl_layout = QHBoxLayout()
        self.ranking_type = NoScrollComboBox()
        self.ranking_type.addItems(["거래량 상위", "상승률 상위", "하락률 상위"])
        ctrl_layout.addWidget(self.ranking_type)

        self.ranking_market = NoScrollComboBox()
        self.ranking_market.addItems(["전체", "코스피", "코스닥"])
        ctrl_layout.addWidget(self.ranking_market)

        btn_load = QPushButton("🔄 순위 조회")
        btn_load.clicked.connect(self._load_ranking)
        ctrl_layout.addWidget(btn_load)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # 순위 테이블
        self.ranking_table = QTableWidget()
        self.ranking_table.setColumnCount(6)
        self.ranking_table.setHorizontalHeaderLabels(["순위", "종목코드", "종목명", "현재가", "등락률", "거래량"])
        ranking_header = self.ranking_table.horizontalHeader()
        if ranking_header is not None:
            ranking_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ranking_table)

        return widget
