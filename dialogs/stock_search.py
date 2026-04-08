from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from data.providers import StockMasterCacheProvider


class StockSearchDialog(QDialog):
    """종목명으로 종목코드 검색"""

    def __init__(self, parent=None, rest_client=None):
        super().__init__(parent)
        self.rest_client = rest_client
        self.cache_provider = StockMasterCacheProvider()
        self.selected_codes = []
        self._last_results = []
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("🔍 종목 검색")
        self.setFixedSize(600, 500)
        self.setStyleSheet("background-color: #0d1117; color: #e6edf3;")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("종목 검색")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff; margin-bottom: 10px;")
        layout.addWidget(title)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("종목명 또는 종목코드를 입력하세요...")
        self.search_input.setMinimumHeight(40)
        self.search_input.setStyleSheet("border-radius: 8px; font-size: 14px;")
        self.search_input.returnPressed.connect(self._search)

        btn_search = QPushButton("검색")
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.setMinimumHeight(40)
        btn_search.clicked.connect(self._search)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_search)
        layout.addLayout(search_layout)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["선택", "종목코드", "종목명", "현재가", "출처"])
        result_header = self.result_table.horizontalHeader()
        if result_header is not None:
            result_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        result_vertical_header = self.result_table.verticalHeader()
        if result_vertical_header is not None:
            result_vertical_header.setVisible(False)
        self.result_table.setStyleSheet(
            """
            QTableWidget { border: 1px solid #30363d; border-radius: 8px; }
            QHeaderView::section { background: #161b22; padding: 8px; border: none; }
            """
        )
        layout.addWidget(self.result_table)
        self.search_status = QLabel("6자리 코드는 API 확인, 종목명은 로컬 캐시에서 검색합니다.")
        self.search_status.setWordWrap(True)
        layout.addWidget(self.search_status)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_apply = QPushButton("✅ 선택 적용")
        btn_apply.setMinimumHeight(36)
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.clicked.connect(self._apply)

        btn_close = QPushButton("닫기")
        btn_close.setMinimumHeight(36)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)

        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _search(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            return

        results = []
        status_parts = []

        if len(keyword) == 6 and keyword.isdigit():
            api_row = self._search_code_via_api(keyword)
            if api_row:
                results.append(api_row)
                status_parts.append("API 확인 결과 1건")
            else:
                status_parts.append("API 확인 결과 없음")
            cached_rows = self.cache_provider.search(keyword, limit=20)
            if cached_rows:
                status_parts.append(f"캐시 검색 {len(cached_rows)}건")
                results.extend(cached_rows)
        else:
            cached_rows = self.cache_provider.search(keyword, limit=100)
            results.extend(cached_rows)
            status_parts.append(f"캐시 검색 {len(cached_rows)}건")

        deduped = []
        seen = set()
        for row in results:
            code = str(row.get("code", "")).strip()
            if not code or code in seen:
                continue
            seen.add(code)
            deduped.append(row)

        self._last_results = deduped
        self._render_results(deduped)
        self.search_status.setText(" | ".join(status_parts) if status_parts else "검색 결과 없음")

    def _search_code_via_api(self, code: str):
        if not self.rest_client:
            return None
        try:
            quote = self.rest_client.get_stock_quote(code)
        except Exception:
            return None

        if not quote:
            return None

        name = str(getattr(quote, "name", "") or code)
        market = str(getattr(quote, "market_type", "") or "UNKNOWN")
        current_price = int(getattr(quote, "current_price", 0) or 0)
        self.cache_provider.upsert(code, name, market, current_price)
        return {
            "code": code,
            "name": name,
            "market": market,
            "current_price": current_price,
            "source": "api",
        }

    def _render_results(self, rows):
        self.result_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            code = str(row.get("code", ""))
            name = str(row.get("name", code))
            current_price = int(row.get("current_price", 0) or 0)
            source = str(row.get("source", "cache"))

            chk = QCheckBox()
            self.result_table.setCellWidget(i, 0, chk)
            self.result_table.setItem(i, 1, QTableWidgetItem(code))
            self.result_table.setItem(i, 2, QTableWidgetItem(name))
            self.result_table.setItem(i, 3, QTableWidgetItem(f"{current_price:,}" if current_price > 0 else "-"))
            self.result_table.setItem(i, 4, QTableWidgetItem("API 확인" if source == "api" else "캐시"))

    def _apply(self):
        self.selected_codes = []
        for i in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(i, 0)
            if isinstance(chk, QCheckBox) and chk.isChecked():
                code_item = self.result_table.item(i, 1)
                if code_item:
                    self.selected_codes.append(code_item.text())
        self.accept()
