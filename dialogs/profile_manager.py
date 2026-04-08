from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from profile_manager import ProfileManager


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

        self.list_widget = QListWidget()
        self._refresh_list()
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(QLabel("저장된 프로필:"))
        layout.addWidget(self.list_widget)

        self.detail_label = QLabel("프로필을 선택하세요")
        self.detail_label.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        save_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("새 프로필 이름")
        save_layout.addWidget(self.name_input)
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save_profile)
        save_layout.addWidget(btn_save)
        layout.addLayout(save_layout)

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
            self.pm.get_profile_info(name)
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
