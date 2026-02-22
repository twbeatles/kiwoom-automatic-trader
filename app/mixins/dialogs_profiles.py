"""Dialogs/profiles mixin for KiwoomProTrader."""

import json
import re
from pathlib import Path

from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

from app.support.worker import Worker
from config import Config
from dark_theme import DARK_STYLESHEET
from light_theme import LIGHT_STYLESHEET
from ui_dialogs import (
    ManualOrderDialog,
    PresetDialog,
    ProfileManagerDialog,
    ScheduleDialog,
    StockSearchDialog,
)

class DialogsProfilesMixin:
    def _open_presets(self):
        current = {"k": self.spin_k.value(), "ts_start": self.spin_ts_start.value(),
                   "ts_stop": self.spin_ts_stop.value(), "loss": self.spin_loss.value(),
                   "betting": self.spin_betting.value()}
        dialog = PresetDialog(self, current)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_preset:
            p = dialog.selected_preset
            self.spin_k.setValue(p.get("k", 0.5))
            self.spin_ts_start.setValue(p.get("ts_start", 3.0))
            self.spin_ts_stop.setValue(p.get("ts_stop", 1.5))
            self.spin_loss.setValue(p.get("loss", 2.0))
            self.spin_betting.setValue(p.get("betting", 10.0))
            self.log(f"📋 프리셋 적용: {p.get('name', 'Unknown')}")

    def _load_favorites(self):
        """즐겨찾기 그룹 로드"""
        try:
            fav_file = Path(Config.DATA_DIR) / "favorites.json"
            if fav_file.exists():
                with open(fav_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
                for name in self.favorites.keys():
                    self.combo_favorites.addItem(f"⭐ {name}")
            else:
                self.favorites = {}
        except Exception:
            self.favorites = {}

    def _on_favorite_selected(self, index):
        """즐겨찾기 선택 시"""
        if index <= 0:
            return
        name = self.combo_favorites.currentText().replace("⭐ ", "")
        if name in self.favorites:
            codes = self.favorites[name]
            self.input_codes.setText(",".join(codes))
            self.log(f"⭐ 즐겨찾기 적용: {name} ({len(codes)}개)")

    def _save_favorite(self):
        """현재 종목을 즐겨찾기에 저장"""
        codes = [c.strip() for c in self.input_codes.text().split(",") if c.strip()]
        if not codes:
            QMessageBox.warning(self, "경고", "저장할 종목이 없습니다.")
            return
        
        name, ok = QInputDialog.getText(self, "즐겨찾기 저장", "그룹 이름:")
        if ok and name:
            self.favorites[name] = codes
            # 콤보박스에 추가 (중복 확인)
            existing = [self.combo_favorites.itemText(i) for i in range(self.combo_favorites.count())]
            if f"⭐ {name}" not in existing:
                self.combo_favorites.addItem(f"⭐ {name}")
            
            # 파일 저장
            try:
                fav_file = Path(Config.DATA_DIR) / "favorites.json"
                fav_file.parent.mkdir(parents=True, exist_ok=True)
                with open(fav_file, 'w', encoding='utf-8') as f:
                    json.dump(self.favorites, f, ensure_ascii=False, indent=2)
                self.log(f"⭐ 즐겨찾기 저장: {name} ({len(codes)}개)")
            except Exception as e:
                self.log(f"❌ 즐겨찾기 저장 실패: {e}")

    def _drag_enter_codes(self, event):
        """드래그 진입 이벤트"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _drop_codes(self, event):
        """드롭 이벤트 - 텍스트에서 종목코드 추출"""
        text = event.mimeData().text()
        # 숫자 6자리 패턴 추출 (종목코드)
        codes = re.findall(r'\b\d{6}\b', text)
        if codes:
            current = self.input_codes.text()
            if current:
                new_codes = current + "," + ",".join(codes)
            else:
                new_codes = ",".join(codes)
            self.input_codes.setText(new_codes)
            self.log(f"📥 드롭으로 종목 추가: {','.join(codes)}")
        event.acceptProposedAction()

    def _open_stock_search(self):
        """종목 검색 다이얼로그 열기"""
        dialog = StockSearchDialog(self, self.rest_client)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_codes:
            current = self.input_codes.text().strip()
            if current:
                new_codes = current + "," + ",".join(dialog.selected_codes)
            else:
                new_codes = ",".join(dialog.selected_codes)
            self.input_codes.setText(new_codes)
            self.log(f"🔍 종목 추가: {', '.join(dialog.selected_codes)}")

    def _open_manual_order(self):
        """수동 주문 다이얼로그 열기"""
        if not self.is_connected:
            QMessageBox.warning(self, "경고", "먼저 API에 연결하세요.")
            return
        
        dialog = ManualOrderDialog(self, self.rest_client, self.current_account)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.order_result:
            order = dialog.order_result
            self.log(f"📝 수동 주문 요청: {order['type']} {order['code']} {order['qty']}주")
            
            # 실제 주문 실행 (Worker 사용)
            code = order['code']
            qty = order['qty']
            price = order.get('price', 0)
            order_type = order['type']
            price_type = order.get('price_type', '시장가')
            
            # API 호출 함수 선택
            if order_type == '매수':
                if price_type == '시장가':
                    func = self.rest_client.buy_market
                    args = (self.current_account, code, qty)
                else:
                    func = self.rest_client.buy_limit
                    args = (self.current_account, code, qty, price)
            else:  # 매도
                if price_type == '시장가':
                    func = self.rest_client.sell_market
                    args = (self.current_account, code, qty)
                else:
                    func = self.rest_client.sell_limit
                    args = (self.current_account, code, qty, price)

            worker = Worker(func, *args)
            worker.signals.result.connect(lambda res: self._on_manual_order_result(res, order_type, code))
            worker.signals.error.connect(lambda e: self.log(f"❌ 수동 주문 오류: {e}"))
            self.threadpool.start(worker)

    def _on_manual_order_result(self, result, order_type, code):
        """수동 주문 결과 처리"""
        if result.success:
            self.log(f"✅ 수동 주문 성공: {order_type} {code} (주문번호 {result.order_no})")
            if order_type == '매수':
                self._set_pending_order(code, 'buy', '수동주문')
            else:
                self._set_pending_order(code, 'sell', '수동주문')
            self._sync_position_from_account(code)
        else:
            self.log(f"❌ 수동 주문 실패: {result.message}")
            self._clear_pending_order(code)

    def _open_profile_manager(self):
        """프로필 관리 다이얼로그 열기"""
        current_settings = self._get_current_settings()
        dialog = ProfileManagerDialog(self, self.profile_manager, current_settings)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_settings:
            self._apply_settings(dialog.selected_settings)
            self.log(f"👤 프로필 적용됨")

    def _get_current_settings(self):
        """현재 설정 딕셔너리 반환"""
        return {
            "betting": self.spin_betting.value(),
            "k_value": self.spin_k.value(),
            "ts_start": self.spin_ts_start.value(),
            "ts_stop": self.spin_ts_stop.value(),
            "loss_cut": self.spin_loss.value(),
            "max_holdings": self.spin_max_holdings.value(),
            "max_loss": self.spin_max_loss.value(),
            "max_daily_loss": self.spin_max_loss.value(),
            "use_rsi": self.chk_use_rsi.isChecked(),
            "rsi_upper": self.spin_rsi_upper.value(),
            "rsi_period": self.spin_rsi_period.value(),
            "use_macd": self.chk_use_macd.isChecked(),
            "use_bb": self.chk_use_bb.isChecked(),
            "bb_k": self.spin_bb_k.value(),
            "use_dmi": self.chk_use_dmi.isChecked(),
            "adx": self.spin_adx.value(),
            "use_volume": self.chk_use_volume.isChecked(),
            "volume_mult": self.spin_volume_mult.value(),
            "use_risk": self.chk_use_risk.isChecked(),
            "codes": self.input_codes.text(),
            "use_ma": self.chk_use_ma.isChecked(),
            "ma_short": self.spin_ma_short.value(),
            "ma_long": self.spin_ma_long.value(),
            "use_time_strategy": self.chk_use_time_strategy.isChecked(),
            "use_atr_sizing": self.chk_use_atr_sizing.isChecked(),
            "risk_percent": self.spin_risk_percent.value(),
            "use_split": self.chk_use_split.isChecked(),
            "split_count": self.spin_split_count.value(),
            "split_percent": self.spin_split_percent.value(),
            "use_stoch_rsi": self.chk_use_stoch_rsi.isChecked(),
            "stoch_upper": self.spin_stoch_upper.value(),
            "stoch_lower": self.spin_stoch_lower.value(),
            "use_mtf": self.chk_use_mtf.isChecked(),
            "use_partial_profit": self.chk_use_partial_profit.isChecked(),
            "use_gap": self.chk_use_gap.isChecked(),
            "use_dynamic_sizing": self.chk_use_dynamic_sizing.isChecked(),
            "use_market_limit": self.chk_use_market_limit.isChecked(),
            "market_limit": self.spin_market_limit.value(),
            "use_sector_limit": self.chk_use_sector_limit.isChecked(),
            "sector_limit": self.spin_sector_limit.value(),
            "use_atr_stop": self.chk_use_atr_stop.isChecked(),
            "atr_mult": self.spin_atr_mult.value(),
            "use_liquidity": self.chk_use_liquidity.isChecked(),
            "min_value": self.spin_min_value.value(),
            "use_spread": self.chk_use_spread.isChecked(),
            "spread_max": self.spin_spread_max.value(),
            "use_breakout_confirm": self.chk_use_breakout_confirm.isChecked(),
            "breakout_ticks": self.spin_breakout_ticks.value(),
            "use_cooldown": self.chk_use_cooldown.isChecked(),
            "cooldown_min": self.spin_cooldown_min.value(),
            "use_time_stop": self.chk_use_time_stop.isChecked(),
            "time_stop_min": self.spin_time_stop_min.value(),
            "use_entry_scoring": self.chk_use_entry_score.isChecked(),
            "entry_score_threshold": self.spin_entry_score_threshold.value(),
            "strategy_pack": dict(getattr(self.config, "strategy_pack", {})) if hasattr(self, "config") else {},
            "strategy_params": dict(getattr(self.config, "strategy_params", {})) if hasattr(self, "config") else {},
            "portfolio_mode": self.combo_portfolio_mode.currentText() if hasattr(self, "combo_portfolio_mode") else "single_strategy",
            "short_enabled": self.chk_short_enabled.isChecked() if hasattr(self, "chk_short_enabled") else False,
            "asset_scope": self.combo_asset_scope.currentText() if hasattr(self, "combo_asset_scope") else "kr_stock_live",
            "execution_policy": self.combo_execution_policy.currentText() if hasattr(self, "combo_execution_policy") else "market",
            "backtest_config": {
                "timeframe": self.combo_backtest_timeframe.currentText() if hasattr(self, "combo_backtest_timeframe") else "1d",
                "lookback_days": self.spin_backtest_lookback.value() if hasattr(self, "spin_backtest_lookback") else 365,
                "commission_bps": self.spin_backtest_commission.value() if hasattr(self, "spin_backtest_commission") else 5.0,
                "slippage_bps": self.spin_backtest_slippage.value() if hasattr(self, "spin_backtest_slippage") else 3.0,
            },
            "feature_flags": {
                "use_modular_strategy_pack": self.chk_feature_modular_pack.isChecked() if hasattr(self, "chk_feature_modular_pack") else True,
                "enable_backtest": self.chk_feature_backtest.isChecked() if hasattr(self, "chk_feature_backtest") else True,
                "enable_external_data": self.chk_feature_external_data.isChecked() if hasattr(self, "chk_feature_external_data") else True,
            },
            "schedule": dict(self.schedule),
            "theme": self.current_theme,
        }

    def _apply_settings(self, settings):
        """설정 딕셔너리 적용"""
        if 'betting' in settings:
            self.spin_betting.setValue(settings['betting'])
        if 'k_value' in settings:
            self.spin_k.setValue(settings['k_value'])
        if 'ts_start' in settings:
            self.spin_ts_start.setValue(settings['ts_start'])
        if 'ts_stop' in settings:
            self.spin_ts_stop.setValue(settings['ts_stop'])
        if 'loss_cut' in settings:
            self.spin_loss.setValue(settings['loss_cut'])
        if 'max_holdings' in settings:
            self.spin_max_holdings.setValue(settings['max_holdings'])
        if 'max_loss' in settings:
            self.spin_max_loss.setValue(settings['max_loss'])
        elif 'max_daily_loss' in settings:
            self.spin_max_loss.setValue(settings['max_daily_loss'])
        if 'codes' in settings:
            self.input_codes.setText(settings['codes'])
        if 'use_rsi' in settings:
            self.chk_use_rsi.setChecked(settings['use_rsi'])
        if 'rsi_upper' in settings:
            self.spin_rsi_upper.setValue(settings['rsi_upper'])
        if 'rsi_period' in settings:
            self.spin_rsi_period.setValue(settings['rsi_period'])
        if 'use_macd' in settings:
            self.chk_use_macd.setChecked(settings['use_macd'])
        if 'use_bb' in settings:
            self.chk_use_bb.setChecked(settings['use_bb'])
        if 'bb_k' in settings:
            self.spin_bb_k.setValue(settings['bb_k'])
        if 'use_dmi' in settings:
            self.chk_use_dmi.setChecked(settings['use_dmi'])
        if 'adx' in settings:
            self.spin_adx.setValue(settings['adx'])
        if 'use_volume' in settings:
            self.chk_use_volume.setChecked(settings['use_volume'])
        if 'volume_mult' in settings:
            self.spin_volume_mult.setValue(settings['volume_mult'])
        if 'use_risk' in settings:
            self.chk_use_risk.setChecked(settings['use_risk'])
        if 'use_ma' in settings:
            self.chk_use_ma.setChecked(settings['use_ma'])
        if 'ma_short' in settings:
            self.spin_ma_short.setValue(settings['ma_short'])
        if 'ma_long' in settings:
            self.spin_ma_long.setValue(settings['ma_long'])
        if 'use_time_strategy' in settings:
            self.chk_use_time_strategy.setChecked(settings['use_time_strategy'])
        if 'use_atr_sizing' in settings:
            self.chk_use_atr_sizing.setChecked(settings['use_atr_sizing'])
        if 'risk_percent' in settings:
            self.spin_risk_percent.setValue(settings['risk_percent'])
        if 'use_split' in settings:
            self.chk_use_split.setChecked(settings['use_split'])
        if 'split_count' in settings:
            self.spin_split_count.setValue(settings['split_count'])
        if 'split_percent' in settings:
            self.spin_split_percent.setValue(settings['split_percent'])
        if 'use_stoch_rsi' in settings:
            self.chk_use_stoch_rsi.setChecked(settings['use_stoch_rsi'])
        if 'stoch_upper' in settings:
            self.spin_stoch_upper.setValue(settings['stoch_upper'])
        if 'stoch_lower' in settings:
            self.spin_stoch_lower.setValue(settings['stoch_lower'])
        if 'use_mtf' in settings:
            self.chk_use_mtf.setChecked(settings['use_mtf'])
        if 'use_partial_profit' in settings:
            self.chk_use_partial_profit.setChecked(settings['use_partial_profit'])
        if 'use_gap' in settings:
            self.chk_use_gap.setChecked(settings['use_gap'])
        if 'use_dynamic_sizing' in settings:
            self.chk_use_dynamic_sizing.setChecked(settings['use_dynamic_sizing'])
        if 'use_market_limit' in settings:
            self.chk_use_market_limit.setChecked(settings['use_market_limit'])
        if 'market_limit' in settings:
            self.spin_market_limit.setValue(settings['market_limit'])
        if 'use_sector_limit' in settings:
            self.chk_use_sector_limit.setChecked(settings['use_sector_limit'])
        if 'sector_limit' in settings:
            self.spin_sector_limit.setValue(settings['sector_limit'])
        if 'use_atr_stop' in settings:
            self.chk_use_atr_stop.setChecked(settings['use_atr_stop'])
        if 'atr_mult' in settings:
            self.spin_atr_mult.setValue(settings['atr_mult'])
        if 'use_liquidity' in settings:
            self.chk_use_liquidity.setChecked(settings['use_liquidity'])
        if 'min_value' in settings:
            self.spin_min_value.setValue(settings['min_value'])
        if 'use_spread' in settings:
            self.chk_use_spread.setChecked(settings['use_spread'])
        if 'spread_max' in settings:
            self.spin_spread_max.setValue(settings['spread_max'])
        if 'use_breakout_confirm' in settings:
            self.chk_use_breakout_confirm.setChecked(settings['use_breakout_confirm'])
        if 'breakout_ticks' in settings:
            self.spin_breakout_ticks.setValue(settings['breakout_ticks'])
        if 'use_cooldown' in settings:
            self.chk_use_cooldown.setChecked(settings['use_cooldown'])
        if 'cooldown_min' in settings:
            self.spin_cooldown_min.setValue(settings['cooldown_min'])
        if 'use_time_stop' in settings:
            self.chk_use_time_stop.setChecked(settings['use_time_stop'])
        if 'time_stop_min' in settings:
            self.spin_time_stop_min.setValue(settings['time_stop_min'])
        if 'use_entry_scoring' in settings:
            self.chk_use_entry_score.setChecked(settings['use_entry_scoring'])
        if 'entry_score_threshold' in settings:
            self.spin_entry_score_threshold.setValue(settings['entry_score_threshold'])
        if 'portfolio_mode' in settings and hasattr(self, "combo_portfolio_mode"):
            self.combo_portfolio_mode.setCurrentText(str(settings['portfolio_mode']))
        if 'short_enabled' in settings and hasattr(self, "chk_short_enabled"):
            self.chk_short_enabled.setChecked(bool(settings['short_enabled']))
        if 'asset_scope' in settings and hasattr(self, "combo_asset_scope"):
            self.combo_asset_scope.setCurrentText(str(settings['asset_scope']))
        if 'execution_policy' in settings and hasattr(self, "combo_execution_policy"):
            self.combo_execution_policy.setCurrentText(str(settings['execution_policy']))
        if isinstance(settings.get('strategy_pack'), dict):
            if hasattr(self, "combo_strategy_pack"):
                self.combo_strategy_pack.setCurrentText(str(settings['strategy_pack'].get('primary_strategy', 'volatility_breakout')))
            if hasattr(self, "config"):
                self.config.strategy_pack = dict(settings['strategy_pack'])
        if isinstance(settings.get('strategy_params'), dict) and hasattr(self, "config"):
            self.config.strategy_params = dict(settings['strategy_params'])
        if isinstance(settings.get('backtest_config'), dict):
            bt = settings['backtest_config']
            if hasattr(self, "combo_backtest_timeframe"):
                self.combo_backtest_timeframe.setCurrentText(str(bt.get('timeframe', '1d')))
            if hasattr(self, "spin_backtest_lookback"):
                self.spin_backtest_lookback.setValue(int(bt.get('lookback_days', 365)))
            if hasattr(self, "spin_backtest_commission"):
                self.spin_backtest_commission.setValue(float(bt.get('commission_bps', 5.0)))
            if hasattr(self, "spin_backtest_slippage"):
                self.spin_backtest_slippage.setValue(float(bt.get('slippage_bps', 3.0)))
            if hasattr(self, "config"):
                self.config.backtest_config = dict(bt)
        if isinstance(settings.get('feature_flags'), dict):
            flags = settings['feature_flags']
            if hasattr(self, "chk_feature_modular_pack"):
                self.chk_feature_modular_pack.setChecked(bool(flags.get('use_modular_strategy_pack', True)))
            if hasattr(self, "chk_feature_backtest"):
                self.chk_feature_backtest.setChecked(bool(flags.get('enable_backtest', True)))
            if hasattr(self, "chk_feature_external_data"):
                self.chk_feature_external_data.setChecked(bool(flags.get('enable_external_data', True)))
            if hasattr(self, "config"):
                self.config.feature_flags = dict(flags)
        if 'schedule' in settings and isinstance(settings['schedule'], dict):
            self.schedule = settings['schedule']
        if settings.get('theme') in ('dark', 'light'):
            if settings['theme'] != self.current_theme:
                self.current_theme = settings['theme']
                self.setStyleSheet(LIGHT_STYLESHEET if self.current_theme == 'light' else DARK_STYLESHEET)

    def _open_schedule(self):
        """예약 매매 다이얼로그 열기"""
        dialog = ScheduleDialog(self, self.schedule)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.schedule = dialog.schedule
            if self.schedule.get('enabled'):
                self.log(f"⏰ 예약 매매 설정: {self.schedule['start']} ~ {self.schedule['end']}")
            else:
                self.log("⏰ 예약 매매 비활성화")

