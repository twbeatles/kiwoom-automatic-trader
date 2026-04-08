from PyQt6.QtWidgets import QDialog, QPushButton, QTabWidget, QTextEdit, QVBoxLayout

from config import Config
from dark_theme import DARK_STYLESHEET


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
