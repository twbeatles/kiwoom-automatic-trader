import datetime
import json
import logging
import os

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

from config import Config
from dark_theme import DARK_STYLESHEET


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

        self.list_widget = QListWidget()
        self._refresh_list()
        self.list_widget.itemClicked.connect(self._on_select)
        layout.addWidget(QLabel("저장된 프리셋:"))
        layout.addWidget(self.list_widget)

        self.detail_label = QLabel("프리셋을 선택하세요")
        self.detail_label.setStyleSheet("padding: 10px; background: #16213e; border-radius: 5px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        save_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("새 프리셋 이름")
        save_layout.addWidget(self.name_input)
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save_preset)
        save_layout.addWidget(btn_save)
        layout.addLayout(save_layout)

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
                with open(Config.PRESETS_FILE, "r", encoding="utf-8") as f:
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
            with open(Config.PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(user, f, ensure_ascii=False, indent=2)
        except (OSError, TypeError) as exc:
            self.logger.error(f"프리셋 저장 실패: {exc}")
            QMessageBox.warning(self, "프리셋 저장 실패", f"프리셋을 저장할 수 없습니다.\n{exc}")

    def _refresh_list(self):
        self.list_widget.clear()
        for key, preset in self.presets.items():
            prefix = "[기본] " if key in Config.DEFAULT_PRESETS else "[사용자] "
            item = QListWidgetItem(prefix + preset.get("name", key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list_widget.addItem(item)

    def _on_select(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        preset = self.presets.get(key, {})
        self.detail_label.setText(
            f"<b>{preset.get('name', key)}</b><br>{preset.get('description', '')}<br><br>"
            f"K값: {preset.get('k', '-')} | TS발동: {preset.get('ts_start', '-')}% | 손절: {preset.get('loss', '-')}%"
        )

    def _save_preset(self):
        name = self.name_input.text().strip()
        if not name:
            return
        key = f"custom_{name.lower().replace(' ', '_')}"
        self.presets[key] = {
            "name": f"⭐ {name}",
            "description": f"사용자 정의 ({datetime.datetime.now():%Y-%m-%d})",
            **self.current_values,
        }
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
