"""Favorites/codes dialogs (SRP: favorites I/O + code drop/search only)."""

import json
import re
from pathlib import Path

from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

from config import Config
from app.mixins._typing import TraderMixinBase
from ui_dialogs import StockSearchDialog


class FavoritesMixin(TraderMixinBase):
    """Favorites/codes dialogs (SRP: favorites I/O + code drop/search only)."""

    def _load_favorites(self):
        """즐겨찾기 그룹 로드"""
        fav_file = Path(Config.DATA_DIR) / "favorites.json"
        try:
            if fav_file.exists():
                with open(fav_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
                for name in self.favorites.keys():
                    self.combo_favorites.addItem(f"⭐ {name}")
            else:
                self.favorites = {}
        except Exception as exc:
            self.logger.warning(f"즐겨찾기 파일 로드 실패 (기존 데이터 백업 시도): {exc}")
            try:
                if fav_file.exists():
                    bak_file = fav_file.with_suffix(".json.bak")
                    import shutil
                    shutil.copy2(fav_file, bak_file)
                    self.logger.info(f"손상 가능성이 있는 즐겨찾기 백업 저장: {bak_file}")
            except Exception:
                pass
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
