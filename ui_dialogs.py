"""
Dialog confirmations and tooling for Kiwoom Pro Algo-Trader.
"""

import datetime
import json
import logging
import os

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QHeaderView,
)

from config import Config
from data.providers import StockMasterCacheProvider
from dark_theme import DARK_STYLESHEET
from profile_manager import ProfileManager


# ============================================================================
# 프리셋 관리 다이얼로그
# ============================================================================
class PresetDialog(QDialog):
    def __init__(self, parent=None, current_values=None):
        super().__init__(parent)
        self.logger = logging.getLogger("KiwoomTrader")
        self.current_values = current_values or {}
        self.presets = self._load_presets()
        self.selected_preset = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("📋 프리셋 관리")
        self.setFixedSize(600, 500)
        self.setStyleSheet(DARK_STYLESHEET)

        layout = QVBoxLayout(self)

        # 목록
        self.list_widget = QListWidget()
        self._refresh_list()
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(QLabel("저장된 프리셋:"))
        layout.addWidget(self.list_widget)

        # 상세정보
        self.detail_label = QLabel("프리셋을 선택하세요")
        self.detail_label.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        # 새 프리셋 저장
        save_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("새 프리셋 이름")
        save_layout.addWidget(self.name_input)
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save_preset)
        save_layout.addWidget(btn_save)
        layout.addLayout(save_layout)

        # 버튼
        btn_layout = QHBoxLayout()
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_preset)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_apply = QPushButton("✅ 적용")
        btn_apply.clicked.connect(self._apply_preset)
        btn_layout.addWidget(btn_apply)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _load_presets(self):
        presets = dict(Config.DEFAULT_PRESETS)
        try:
            if os.path.exists(Config.PRESETS_FILE):
                with open(Config.PRESETS_FILE, 'r', encoding='utf-8') as f:
                    presets.update(json.load(f))
        except json.JSONDecodeError as exc:
            self.logger.warning(f"프리셋 파싱 실패: {exc}")
            QMessageBox.warning(self, "프리셋 로드 실패", f"프리셋 파일 형식이 손상되었습니다.\n{exc}")
        except OSError as exc:
            self.logger.warning(f"프리셋 로드 실패: {exc}")
            QMessageBox.warning(self, "프리셋 로드 실패", f"프리셋 파일을 읽을 수 없습니다.\n{exc}")
        return presets

    def _save_presets(self):
        user = {k: v for k, v in self.presets.items() if k not in Config.DEFAULT_PRESETS}
        try:
            os.makedirs(os.path.dirname(Config.PRESETS_FILE), exist_ok=True)
            with open(Config.PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(user, f, ensure_ascii=False, indent=2)
        except (OSError, TypeError) as exc:
            self.logger.error(f"프리셋 저장 실패: {exc}")
            QMessageBox.warning(self, "프리셋 저장 실패", f"프리셋을 저장할 수 없습니다.\n{exc}")

    def _refresh_list(self):
        self.list_widget.clear()
        for key, preset in self.presets.items():
            prefix = "[기본] " if key in Config.DEFAULT_PRESETS else "[사용자] "
            item = QListWidgetItem(prefix + preset.get('name', key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list_widget.addItem(item)

    def _on_select(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        p = self.presets.get(key, {})
        self.detail_label.setText(f"<b>{p.get('name', key)}</b><br>{p.get('description', '')}<br><br>"
            f"K값: {p.get('k', '-')} | TS발동: {p.get('ts_start', '-')}% | 손절: {p.get('loss', '-')}%")

    def _save_preset(self):
        name = self.name_input.text().strip()
        if not name:
            return
        key = f"custom_{name.lower().replace(' ', '_')}"
        self.presets[key] = {"name": f"⭐ {name}", "description": f"사용자 정의 ({datetime.datetime.now():%Y-%m-%d})", **self.current_values}
        self._save_presets()
        self._refresh_list()
        self.name_input.clear()

    def _delete_preset(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key in Config.DEFAULT_PRESETS:
            QMessageBox.warning(self, "경고", "기본 프리셋은 삭제할 수 없습니다.")
            return
        del self.presets[key]
        self._save_presets()
        self._refresh_list()

    def _apply_preset(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_preset = self.presets.get(item.data(Qt.ItemDataRole.UserRole))
            self.accept()


# ============================================================================
# 도움말 다이얼로그
# ============================================================================
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📚 도움말")
        self.setFixedSize(700, 600)
        self.setStyleSheet(DARK_STYLESHEET)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        for key, title in [("quick_start", "🚀 빠른 시작"), ("strategy", "📈 전략"), ("faq", "❓ FAQ")]:
            text = QTextEdit()
            text.setReadOnly(True)
            text.setHtml(f"<div style='font-size:13px'>{Config.HELP_CONTENT.get(key, '')}</div>")
            tabs.addTab(text, title)

        layout.addWidget(tabs)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.close)
        layout.addWidget(btn)


# ============================================================================
# 종목 검색 다이얼로그 (v4.3 신규)
# ============================================================================
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

        # Title Label
        title = QLabel("종목 검색")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff; margin-bottom: 10px;")
        layout.addWidget(title)

        # Search Input
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

        # Result Table
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["선택", "종목코드", "종목명", "현재가", "출처"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setStyleSheet("""
            QTableWidget { border: 1px solid #30363d; border-radius: 8px; }
            QHeaderView::section { background: #161b22; padding: 8px; border: none; }
        """)
        layout.addWidget(self.result_table)
        self.search_status = QLabel("6자리 코드는 API 확인, 종목명은 로컬 캐시에서 검색합니다.")
        self.search_status.setWordWrap(True)
        layout.addWidget(self.search_status)

        # Bottom Buttons
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
            if chk and chk.isChecked():
                code_item = self.result_table.item(i, 1)
                if code_item:
                    self.selected_codes.append(code_item.text())
        self.accept()


# ============================================================================
# 수동 주문 다이얼로그 (v4.3 신규)
# ============================================================================
class ManualOrderDialog(QDialog):
    """수동 매수/매도 주문"""
    def __init__(self, parent=None, rest_client=None, account=""):
        super().__init__(parent)
        self.rest_client = rest_client
        self.account = account
        self.order_result = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("📝 수동 주문")
        self.setFixedSize(450, 420)
        self.setStyleSheet("background-color: #0d1117; color: #e6edf3;")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("신규 주문")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #e6edf3; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Code
        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("예: 005930")
        self.input_code.setMinimumHeight(36)
        form.addRow("종목코드:", self.input_code)

        # Type
        self.combo_type = QComboBox()
        self.combo_type.addItems(["매수", "매도"])
        self.combo_type.setMinimumHeight(36)
        self.combo_type.setStyleSheet("QComboBox { padding: 5px; }")
        form.addRow("주문유형:", self.combo_type)

        # Quantity
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 100000)
        self.spin_qty.setValue(1)
        self.spin_qty.setMinimumHeight(36)
        form.addRow("주문수량:", self.spin_qty)

        # Price Type
        self.combo_price_type = QComboBox()
        self.combo_price_type.addItems(["시장가", "지정가"])
        self.combo_price_type.setMinimumHeight(36)
        self.combo_price_type.currentIndexChanged.connect(self._on_price_type_changed)
        form.addRow("가격구분:", self.combo_price_type)

        # Price
        self.spin_price = QSpinBox()
        self.spin_price.setRange(0, 10000000)
        self.spin_price.setValue(0)
        self.spin_price.setEnabled(False)
        self.spin_price.setMinimumHeight(36)
        form.addRow("주문가격:", self.spin_price)

        layout.addLayout(form)

        # Warning
        self.lbl_warning = QLabel("⚠️ 주문이 즉시 전송됩니다. 확인해주세요.")
        self.lbl_warning.setStyleSheet("""
            color: #d29922; font-size: 12px; font-weight: bold;
            background: rgba(210, 153, 34, 0.1); border-radius: 6px; padding: 10px;
        """)
        self.lbl_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_warning)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_close = QPushButton("취소")
        btn_close.setMinimumHeight(45)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        
        btn_order = QPushButton("⚡ 주문 실행")
        btn_order.setMinimumHeight(45)
        btn_order.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_order.setObjectName("orderBtn") # Special styling opportunity
        btn_order.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d32f2f, stop:1 #b71c1c);
                color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 14px;
            }
            QPushButton:hover { background: #e53935; }
            QPushButton:pressed { background: #b71c1c; }
        """)
        btn_order.clicked.connect(self._execute_order)
        
        btn_layout.addWidget(btn_close)
        btn_layout.addWidget(btn_order)
        layout.addLayout(btn_layout)

    def _on_price_type_changed(self, idx):
        self.spin_price.setEnabled(idx == 1)  # 지정가일 때만 활성화

    def _execute_order(self):
        code = self.input_code.text().strip()
        if not code or len(code) != 6:
            QMessageBox.warning(self, "경고", "올바른 종목코드를 입력하세요.")
            return

        confirm = QMessageBox.question(self, "주문 확인",
            f"종목: {code}\n유형: {self.combo_type.currentText()}\n"
            f"수량: {self.spin_qty.value()}주\n\n실행하시겠습니까?")

        if confirm == QMessageBox.StandardButton.Yes:
            self.order_result = {
                'code': code,
                'type': self.combo_type.currentText(),
                'qty': self.spin_qty.value(),
                'price_type': self.combo_price_type.currentText(),
                'price': self.spin_price.value() if self.combo_price_type.currentIndex() == 1 else 0
            }
            self.accept()


# ============================================================================
# 프로필 관리 다이얼로그 (v4.3 신규)
# ============================================================================
class ProfileManagerDialog(QDialog):
    """설정 프로필 관리"""
    def __init__(self, parent=None, profile_manager=None, current_settings=None):
        super().__init__(parent)
        self.pm = profile_manager or ProfileManager()
        self.current_settings = current_settings or {}
        self.selected_settings = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("👤 프로필 관리")
        self.setFixedSize(550, 450)

        layout = QVBoxLayout(self)

        # 프로필 목록
        self.list_widget = QListWidget()
        self._refresh_list()
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(QLabel("저장된 프로필:"))
        layout.addWidget(self.list_widget)

        # 상세 정보
        self.detail_label = QLabel("프로필을 선택하세요")
        self.detail_label.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        # 새 프로필 저장
        save_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("새 프로필 이름")
        save_layout.addWidget(self.name_input)
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save_profile)
        save_layout.addWidget(btn_save)
        layout.addLayout(save_layout)

        # 버튼
        btn_layout = QHBoxLayout()
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_profile)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_apply = QPushButton("✅ 적용")
        btn_apply.clicked.connect(self._apply_profile)
        btn_layout.addWidget(btn_apply)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _refresh_list(self):
        self.list_widget.clear()
        for name in self.pm.get_profile_names():
            info = self.pm.get_profile_info(name)
            item = QListWidgetItem(f"👤 {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)

    def _on_select(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        info = self.pm.get_profile_info(name)
        if info:
            self.detail_label.setText(
                f"<b>{info['name']}</b><br>"
                f"설명: {info['description']}<br>"
                f"생성: {info['created'][:10] if info['created'] else '-'}<br>"
                f"수정: {info['updated'][:10] if info['updated'] else '-'}"
            )

    def _save_profile(self):
        name = self.name_input.text().strip()
        if not name:
            return
        self.pm.save_profile(name, self.current_settings, "사용자 정의 프로필")
        self._refresh_list()
        self.name_input.clear()
        QMessageBox.information(self, "알림", f"프로필 '{name}' 저장됨")

    def _delete_profile(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "확인", f"'{name}' 프로필을 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.pm.delete_profile(name)
            self._refresh_list()
            self.detail_label.setText("프로필을 선택하세요")

    def _apply_profile(self):
        item = self.list_widget.currentItem()
        if item:
            name = item.data(Qt.ItemDataRole.UserRole)
            self.selected_settings = self.pm.load_profile(name)
            self.accept()


# ============================================================================
# 예약 매매 다이얼로그 (v4.3 신규)
# ============================================================================
class ScheduleDialog(QDialog):
    """예약 매매 설정"""
    def __init__(self, parent=None, current_schedule=None):
        super().__init__(parent)
        self.schedule = current_schedule or {}
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("⏰ 예약 매매 설정")
        self.setFixedSize(350, 250)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # 활성화 체크
        self.chk_enabled = QCheckBox("예약 매매 활성화")
        self.chk_enabled.setChecked(self.schedule.get('enabled', False))
        form.addRow("", self.chk_enabled)

        # 시작 시간
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm")
        start = self.schedule.get('start', '09:00')
        self.time_start.setTime(QTime.fromString(start, "HH:mm"))
        form.addRow("시작 시간:", self.time_start)

        # 종료 시간
        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat("HH:mm")
        end = self.schedule.get('end', '15:19')
        self.time_end.setTime(QTime.fromString(end, "HH:mm"))
        form.addRow("종료 시간:", self.time_end)

        # 자동 청산
        self.chk_liquidate = QCheckBox("종료 시 자동 청산")
        self.chk_liquidate.setChecked(self.schedule.get('liquidate', True))
        form.addRow("", self.chk_liquidate)

        layout.addLayout(form)
        layout.addStretch()

        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        btn_close = QPushButton("취소")
        btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _save(self):
        self.schedule = {
            'enabled': self.chk_enabled.isChecked(),
            'start': self.time_start.time().toString("HH:mm"),
            'end': self.time_end.time().toString("HH:mm"),
            'liquidate': self.chk_liquidate.isChecked()
        }
        self.accept()
