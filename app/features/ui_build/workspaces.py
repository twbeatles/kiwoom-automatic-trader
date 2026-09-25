"""5-workspace trade IA for KiwoomProTrader (P1).

13개의 최상위 탭을 5개 워크스페이스로 묶는 구성 레이어다. 기존 탭 빌더
(_create_strategy_tab, _create_chart_tab 등)는 그대로 재사용하므로 조회
로직(Worker 비동기)과 위젯 속성 이름은 그대로 유지된다. 매매 로직 변경 없음.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.mixins._typing import TraderMixinBase


# 최상위 워크스페이스 라벨 (표시 순서 고정)
WORKSPACE_TRADE = "⚡ 매매"
WORKSPACE_EXPLORE = "📊 종목 탐색"
WORKSPACE_PORTFOLIO = "💼 포트폴리오"
WORKSPACE_INTEL = "🧠 인텔리전스"
WORKSPACE_SYSTEM = "⚙ 시스템"

WORKSPACE_LABELS = (
    WORKSPACE_TRADE,
    WORKSPACE_EXPLORE,
    WORKSPACE_PORTFOLIO,
    WORKSPACE_INTEL,
    WORKSPACE_SYSTEM,
)


class UIBuildWorkspacesMixin(TraderMixinBase):
    """5-워크스페이스 탭 구성 + 우측 주문 티켓 도크."""

    def _create_workspace_tabs(self):
        tabs = QTabWidget()
        self.main_tabs = tabs
        tabs.setObjectName("workspace_tabs")
        tabs.addTab(self._create_trade_workspace(), WORKSPACE_TRADE)
        tabs.addTab(self._create_explore_workspace(), WORKSPACE_EXPLORE)
        tabs.addTab(self._create_portfolio_workspace(), WORKSPACE_PORTFOLIO)
        tabs.addTab(self._create_intel_workspace(), WORKSPACE_INTEL)
        tabs.addTab(self._create_system_workspace(), WORKSPACE_SYSTEM)
        return tabs

    def _goto_workspace(self, index):
        tabs = getattr(self, "main_tabs", None)
        if tabs is not None and 0 <= int(index) < tabs.count():
            tabs.setCurrentIndex(int(index))

    # -- 워크스페이스 -----------------------------------------------

    def _create_trade_workspace(self):
        """⚡ 매매: 핵심 설정 + 우측 주문 티켓 안내는 도크로 분리."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("주문은 우측 주문 티켓(📝) 또는 매매 메뉴 > 수동 주문(Ctrl+O)에서 실행합니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b949e; padding: 4px 2px;")
        layout.addWidget(hint)
        layout.addWidget(self._create_strategy_tab())
        return widget

    def _create_explore_workspace(self):
        """📊 종목 탐색: 통합 관심리스트(조건+순위+검색) + 차트 + 호가."""
        sub = QTabWidget()
        sub.addTab(self._create_unified_watchlist(), "🔎 관심(조건+순위)")
        sub.addTab(self._create_chart_tab(), "📈 차트")
        sub.addTab(self._create_orderbook_tab(), "📋 호가")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(sub)
        self.explore_tabs = sub
        return widget

    def _create_unified_watchlist(self):
        """조건검색 + 순위 + 종목검색을 한 화면에 묶은 관심리스트."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("관심 종목을 조건·순위·검색에서 모아봅니다."))
        search_row.addStretch()
        btn_search = QPushButton("🔍 종목검색")
        btn_search.clicked.connect(self._open_stock_search)
        search_row.addWidget(btn_search)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)
        condition_group = QGroupBox("🔍 조건검색")
        condition_layout = QVBoxLayout(condition_group)
        condition_layout.addWidget(self._create_condition_tab())
        ranking_group = QGroupBox("🏆 순위")
        ranking_layout = QVBoxLayout(ranking_group)
        ranking_layout.addWidget(self._create_ranking_tab())
        splitter.addWidget(condition_group)
        splitter.addWidget(ranking_group)
        splitter.setSizes([300, 300])
        layout.addWidget(splitter)
        return widget

    def _create_portfolio_workspace(self):
        """💼 포트폴리오: 통계 + 거래 내역."""
        sub = QTabWidget()
        sub.addTab(self._create_stats_tab(), "📊 통계")
        sub.addTab(self._create_history_tab(), "📝 내역")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(sub)
        return widget

    def _create_intel_workspace(self):
        """🧠 인텔리전스: 설정 + 현황 + 리플레이."""
        sub = QTabWidget()
        if hasattr(self, "_create_market_intelligence_settings_tab"):
            sub.addTab(self._create_market_intelligence_settings_tab(), "🧠 인텔리전스 설정")
        if hasattr(self, "_create_market_intelligence_tab"):
            sub.addTab(self._create_market_intelligence_tab(), "🧠 인텔리전스 현황")
        if hasattr(self, "_create_market_replay_tab"):
            sub.addTab(self._create_market_replay_tab(), "📼 인텔리전스 리플레이")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(sub)
        return widget

    def _create_system_workspace(self):
        """⚙ 시스템: 상세 설정 + API/알림 + 시스템 진단."""
        sub = QTabWidget()
        sub.addTab(self._create_advanced_tab(), "🛠 상세 설정")
        api_tab = self._create_api_tab()
        api_tab.setObjectName("api_tab")
        sub.addTab(api_tab, "🔐 API/알림")
        sub.addTab(self._create_diagnostics_tab(), "🩺 시스템 진단")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(sub)
        self.system_tabs = sub
        return widget

    # -- 우측 주문 티켓 도크 ------------------------------------------

    def _create_order_dock(self):
        """우측 레일 주문 티켓 도크 (모든 워크스페이스에서 상시 노출)."""
        dock = QDockWidget("📝 주문 티켓", self)
        dock.setObjectName("order_ticket_dock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        dock.setWidget(self._create_order_ticket())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.order_ticket_dock = dock
        return dock

    def _create_order_ticket(self):
        box = QGroupBox("📝 주문 티켓")
        form = QFormLayout(box)

        self.ticket_code = QLineEdit()
        self.ticket_code.setPlaceholderText("예: 005930")
        self.ticket_code.setMaxLength(6)
        form.addRow("종목코드:", self.ticket_code)

        self.ticket_side = QComboBox()
        self.ticket_side.addItems(["매수", "매도"])
        form.addRow("주문유형:", self.ticket_side)

        self.ticket_qty = QSpinBox()
        self.ticket_qty.setRange(1, 100000)
        self.ticket_qty.setValue(1)
        form.addRow("주문수량:", self.ticket_qty)

        self.ticket_price_type = QComboBox()
        self.ticket_price_type.addItems(["시장가", "지정가"])
        self.ticket_price_type.currentIndexChanged.connect(self._on_ticket_price_type_changed)
        form.addRow("가격구분:", self.ticket_price_type)

        self.ticket_price = QSpinBox()
        self.ticket_price.setRange(0, 10000000)
        self.ticket_price.setValue(0)
        self.ticket_price.setEnabled(False)
        form.addRow("주문가격:", self.ticket_price)

        btn_submit = QPushButton("⚡ 주문 실행")
        btn_submit.setObjectName("orderBtn")
        btn_submit.setMinimumHeight(40)
        btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_submit.clicked.connect(self._submit_order_ticket)
        form.addRow(btn_submit)

        btn_dialog = QPushButton("📝 수동 주문 창 열기")
        btn_dialog.clicked.connect(self._open_manual_order)
        form.addRow(btn_dialog)

        hint = QLabel("실행 전 _validate_manual_order_request 검증을 항상 통과합니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b949e;")
        form.addRow(hint)
        return box

    def _toggle_order_ticket(self):
        dock = getattr(self, "order_ticket_dock", None)
        if dock is not None:
            dock.setVisible(not dock.isVisible())

    def _on_ticket_price_type_changed(self, idx):
        price = getattr(self, "ticket_price", None)
        if price is not None:
            price.setEnabled(idx == 1)

    def _submit_order_ticket(self):
        """티켓 주문을 수동 주문과 동일한 choke point로 실행한다."""
        if not getattr(self, "is_connected", False):
            self.log("먼저 API에 연결하세요.")
            return
        if not getattr(self, "current_account", ""):
            self.log("주문 가능한 계좌를 먼저 선택하세요.")
            return
        order = {
            "code": self.ticket_code.text().strip(),
            "type": self.ticket_side.currentText(),
            "qty": int(self.ticket_qty.value()),
            "price_type": self.ticket_price_type.currentText(),
            "price": int(self.ticket_price.value())
            if self.ticket_price_type.currentIndex() == 1
            else 0,
        }
        # 단일 검증 choke point (수동 주문 다이얼로그와 동일)
        if not self._validate_manual_order_request(order):
            return
        order["validated"] = True
        self.log(f"📝 주문 티켓 요청: {order['type']} {order['code']} {order['qty']}주")
        dispatcher = getattr(self, "_dispatch_manual_order", None)
        if callable(dispatcher):
            dispatcher(order)
