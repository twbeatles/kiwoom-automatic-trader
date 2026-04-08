from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


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

        header = QLabel("신규 주문")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #e6edf3; margin-bottom: 10px;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("예: 005930")
        self.input_code.setMinimumHeight(36)
        form.addRow("종목코드:", self.input_code)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["매수", "매도"])
        self.combo_type.setMinimumHeight(36)
        self.combo_type.setStyleSheet("QComboBox { padding: 5px; }")
        form.addRow("주문유형:", self.combo_type)

        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 100000)
        self.spin_qty.setValue(1)
        self.spin_qty.setMinimumHeight(36)
        form.addRow("주문수량:", self.spin_qty)

        self.combo_price_type = QComboBox()
        self.combo_price_type.addItems(["시장가", "지정가"])
        self.combo_price_type.setMinimumHeight(36)
        self.combo_price_type.currentIndexChanged.connect(self._on_price_type_changed)
        form.addRow("가격구분:", self.combo_price_type)

        self.spin_price = QSpinBox()
        self.spin_price.setRange(0, 10000000)
        self.spin_price.setValue(0)
        self.spin_price.setEnabled(False)
        self.spin_price.setMinimumHeight(36)
        form.addRow("주문가격:", self.spin_price)

        layout.addLayout(form)

        self.lbl_warning = QLabel("⚠️ 주문이 즉시 전송됩니다. 확인해주세요.")
        self.lbl_warning.setStyleSheet(
            """
            color: #d29922; font-size: 12px; font-weight: bold;
            background: rgba(210, 153, 34, 0.1); border-radius: 6px; padding: 10px;
            """
        )
        self.lbl_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_warning)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_close = QPushButton("취소")
        btn_close.setMinimumHeight(45)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)

        btn_order = QPushButton("⚡ 주문 실행")
        btn_order.setMinimumHeight(45)
        btn_order.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_order.setObjectName("orderBtn")
        btn_order.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d32f2f, stop:1 #b71c1c);
                color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 14px;
            }
            QPushButton:hover { background: #e53935; }
            QPushButton:pressed { background: #b71c1c; }
            """
        )
        btn_order.clicked.connect(self._execute_order)

        btn_layout.addWidget(btn_close)
        btn_layout.addWidget(btn_order)
        layout.addLayout(btn_layout)

    def _on_price_type_changed(self, idx):
        self.spin_price.setEnabled(idx == 1)

    def _execute_order(self):
        code = self.input_code.text().strip()
        if not code or len(code) != 6 or not code.isdigit():
            QMessageBox.warning(self, "경고", "종목코드는 6자리 숫자여야 합니다.")
            return
        if self.combo_price_type.currentIndex() == 1 and self.spin_price.value() <= 0:
            QMessageBox.warning(self, "경고", "지정가 주문은 1원 이상의 가격이 필요합니다.")
            return

        confirm = QMessageBox.question(
            self,
            "주문 확인",
            f"종목: {code}\n유형: {self.combo_type.currentText()}\n"
            f"수량: {self.spin_qty.value()}주\n\n실행하시겠습니까?",
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self.order_result = {
                "code": code,
                "type": self.combo_type.currentText(),
                "qty": self.spin_qty.value(),
                "price_type": self.combo_price_type.currentText(),
                "price": self.spin_price.value() if self.combo_price_type.currentIndex() == 1 else 0,
            }
            self.accept()
