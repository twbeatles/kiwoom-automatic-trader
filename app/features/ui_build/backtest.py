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


class UIBuildBacktestMixin(TraderMixinBase):
    def _select_backtest_bars_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "백테스트 가격 CSV 선택", "", "CSV (*.csv)")
        if filename and hasattr(self, "input_backtest_bars_path"):
            self.input_backtest_bars_path.setText(filename)
    def _select_backtest_intel_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "인텔리전스 JSONL 선택", "", "JSONL (*.jsonl);;JSON (*.json);;All Files (*)")
        if filename and hasattr(self, "input_backtest_intel_path"):
            self.input_backtest_intel_path.setText(filename)
    def _backtest_config_values_from_ui(self):
        cfg = getattr(self, "config", None)
        values = dict(getattr(cfg, "backtest_config", {}) if cfg is not None else {})
        if hasattr(self, "combo_backtest_timeframe"):
            values["timeframe"] = self.combo_backtest_timeframe.currentData() or self.combo_backtest_timeframe.currentText()
        if hasattr(self, "spin_backtest_commission"):
            values["commission_bps"] = float(self.spin_backtest_commission.value())
        if hasattr(self, "spin_backtest_slippage"):
            values["slippage_bps"] = float(self.spin_backtest_slippage.value())
        return values
    def _run_backtest_from_ui(self):
        if hasattr(self, "chk_feature_backtest") and not self.chk_feature_backtest.isChecked():
            QMessageBox.warning(self, "경고", "백테스트 기능이 비활성화되어 있습니다.")
            return
        bars_path = str(self.input_backtest_bars_path.text()).strip() if hasattr(self, "input_backtest_bars_path") else ""
        intel_path = str(self.input_backtest_intel_path.text()).strip() if hasattr(self, "input_backtest_intel_path") else ""
        if not bars_path:
            QMessageBox.warning(self, "경고", "백테스트 가격 CSV를 선택해주세요.")
            return
        if hasattr(self, "btn_run_backtest"):
            self.btn_run_backtest.setEnabled(False)
        if hasattr(self, "btn_save_backtest"):
            self.btn_save_backtest.setEnabled(False)
        if hasattr(self, "lbl_backtest_status"):
            self.lbl_backtest_status.setText("실행 중...")

        worker = Worker(
            run_backtest_from_files,
            bars_path,
            intel_path or None,
            self._backtest_config_values_from_ui(),
        )
        worker.signals.result.connect(self._on_backtest_result)
        worker.signals.error.connect(self._on_backtest_error)
        self.threadpool.start(worker)
    def _on_backtest_result(self, result):
        self._last_backtest_result = result
        if hasattr(self, "btn_run_backtest"):
            self.btn_run_backtest.setEnabled(True)
        if hasattr(self, "btn_save_backtest"):
            self.btn_save_backtest.setEnabled(True)
        if hasattr(self, "lbl_backtest_status"):
            self.lbl_backtest_status.setText("완료")
        if hasattr(self, "backtest_metrics_table"):
            rows = metric_rows(result)
            self.backtest_metrics_table.setRowCount(len(rows))
            for row_idx, (name, value) in enumerate(rows):
                self.backtest_metrics_table.setItem(row_idx, 0, QTableWidgetItem(name))
                self.backtest_metrics_table.setItem(row_idx, 1, QTableWidgetItem(value))
        if hasattr(self, "backtest_trades_table"):
            trades = list(getattr(result, "trades", []) or [])[-50:]
            self.backtest_trades_table.setRowCount(len(trades))
            for row_idx, trade in enumerate(trades):
                values = [
                    trade.get("ts", ""),
                    trade.get("symbol", ""),
                    trade.get("side", ""),
                    f"{float(trade.get('price', 0.0) or 0.0):.2f}",
                    f"{float(trade.get('qty', 0.0) or 0.0):.4f}",
                ]
                for col_idx, value in enumerate(values):
                    self.backtest_trades_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        if hasattr(self, "log"):
            self.log(f"백테스트 완료: trades={len(getattr(result, 'trades', []) or [])}")
    def _on_backtest_error(self, error):
        if hasattr(self, "btn_run_backtest"):
            self.btn_run_backtest.setEnabled(True)
        if hasattr(self, "lbl_backtest_status"):
            self.lbl_backtest_status.setText("실패")
        if hasattr(self, "log"):
            self.log(f"백테스트 실패: {error}")
        QMessageBox.warning(self, "백테스트 실패", str(error))
    def _save_backtest_result(self):
        result = getattr(self, "_last_backtest_result", None)
        if result is None:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "백테스트 결과 저장", "backtest_result.json", "JSON (*.json)")
        if not filename:
            return
        with open(filename, "w", encoding="utf-8") as handle:
            json.dump(backtest_result_to_dict(result), handle, ensure_ascii=False, indent=2)
        if hasattr(self, "log"):
            self.log(f"백테스트 결과 저장: {filename}")
