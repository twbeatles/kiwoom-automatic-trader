"""Kiwoom Pro Algo-Trader entrypoint wrapper."""

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from app.core.window import KiwoomProTrader
from app.support.ui_scale import configure_high_dpi_scaling


def main():
    # Fractional OS scales (125%/150%/175%) must be honoured before the
    # QApplication exists; otherwise HiDPI displays render a tiny/dense UI.
    configure_high_dpi_scaling()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    def exception_handler(exc_type, exc_value, exc_tb):
        import traceback

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger("Main").critical(f"치명적 오류:\n{error_msg}")
        QMessageBox.critical(
            None,
            "오류 발생",
            f"프로그램 오류가 발생했습니다.\n\n{exc_type.__name__}: {exc_value}\n\n자세한 내용은 로그를 확인하세요.",
        )

    sys.excepthook = exception_handler

    try:
        window = KiwoomProTrader()
        window.show()
        sys.exit(app.exec())
    except Exception as exc:
        QMessageBox.critical(None, "시작 오류", f"프로그램 시작 실패:\n{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
