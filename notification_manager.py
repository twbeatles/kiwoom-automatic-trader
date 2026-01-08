"""
Notification Manager for Kiwoom Pro Algo-Trader
사운드 알림 및 Windows 데스크톱 알림 관리
"""

import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Windows 사운드
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# 데스크톱 알림
try:
    from plyer import notification as plyer_notify
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False


class NotificationType(Enum):
    """알림 유형"""
    BUY = "buy"           # 매수 체결
    SELL = "sell"         # 매도 체결
    PROFIT = "profit"     # 익절
    LOSS = "loss"         # 손절
    ALERT = "alert"       # 일반 알림
    ERROR = "error"       # 오류
    TARGET = "target"     # 목표가 도달


@dataclass
class NotificationSettings:
    """알림 설정"""
    sound_enabled: bool = True
    toast_enabled: bool = True
    
    # 이벤트별 알림 ON/OFF
    on_buy: bool = True
    on_sell: bool = True
    on_profit: bool = True
    on_loss: bool = True
    on_target: bool = True
    on_error: bool = True
    
    # 사운드 파일 경로
    sound_dir: str = "sounds"


class NotificationManager:
    """알림 관리자 - 사운드 및 데스크톱 알림"""
    
    # 기본 사운드 주파수/지속시간 (winsound.Beep 용)
    DEFAULT_SOUNDS = {
        NotificationType.BUY: (800, 200),      # 높은 톤, 짧게
        NotificationType.SELL: (600, 200),     # 중간 톤
        NotificationType.PROFIT: (1000, 300),  # 높은 톤, 길게
        NotificationType.LOSS: (400, 400),     # 낮은 톤, 길게
        NotificationType.ALERT: (700, 150),    # 중간
        NotificationType.ERROR: (300, 500),    # 낮은 톤, 매우 길게
        NotificationType.TARGET: (900, 250),   # 높은 톤
    }
    
    # 알림 아이콘 이모지
    ICONS = {
        NotificationType.BUY: "🛒",
        NotificationType.SELL: "💰",
        NotificationType.PROFIT: "📈",
        NotificationType.LOSS: "📉",
        NotificationType.ALERT: "🔔",
        NotificationType.ERROR: "❌",
        NotificationType.TARGET: "🎯",
    }
    
    def __init__(self, settings: Optional[NotificationSettings] = None):
        self.settings = settings or NotificationSettings()
        self.logger = logging.getLogger('Notification')
        self._sound_cache: Dict[str, str] = {}
        self._init_sounds()
    
    def _init_sounds(self):
        """사운드 파일 초기화"""
        sound_dir = Path(self.settings.sound_dir)
        if sound_dir.exists():
            for wav_file in sound_dir.glob("*.wav"):
                name = wav_file.stem.lower()
                self._sound_cache[name] = str(wav_file.absolute())
    
    def _should_notify(self, event_type: NotificationType) -> bool:
        """이벤트 유형에 따라 알림 여부 결정"""
        mapping = {
            NotificationType.BUY: self.settings.on_buy,
            NotificationType.SELL: self.settings.on_sell,
            NotificationType.PROFIT: self.settings.on_profit,
            NotificationType.LOSS: self.settings.on_loss,
            NotificationType.TARGET: self.settings.on_target,
            NotificationType.ERROR: self.settings.on_error,
            NotificationType.ALERT: True,  # 항상 허용
        }
        return mapping.get(event_type, True)
    
    def play_sound(self, event_type: NotificationType):
        """
        사운드 재생 (비동기)
        
        Args:
            event_type: 알림 유형
        """
        if not self.settings.sound_enabled:
            return
        
        if not HAS_WINSOUND:
            self.logger.warning("winsound 모듈 없음 - 사운드 비활성화")
            return
        
        def _play():
            try:
                # 커스텀 WAV 파일이 있으면 사용
                sound_name = event_type.value
                if sound_name in self._sound_cache:
                    winsound.PlaySound(
                        self._sound_cache[sound_name],
                        winsound.SND_FILENAME | winsound.SND_ASYNC
                    )
                else:
                    # 기본 비프음
                    freq, duration = self.DEFAULT_SOUNDS.get(
                        event_type, (600, 200)
                    )
                    winsound.Beep(freq, duration)
            except Exception as e:
                self.logger.warning(f"사운드 재생 실패: {e}")
        
        # 비동기 재생 (UI 블로킹 방지)
        threading.Thread(target=_play, daemon=True).start()
    
    def show_toast(self, title: str, message: str, event_type: NotificationType = NotificationType.ALERT):
        """
        Windows 토스트 알림 표시
        
        Args:
            title: 알림 제목
            message: 알림 내용
            event_type: 알림 유형 (아이콘 결정)
        """
        if not self.settings.toast_enabled:
            return
        
        if not HAS_PLYER:
            self.logger.debug("plyer 없음 - 토스트 비활성화")
            return
        
        def _show():
            try:
                icon = self.ICONS.get(event_type, "🔔")
                plyer_notify.notify(
                    title=f"{icon} {title}",
                    message=message,
                    app_name="Kiwoom Trader",
                    timeout=5
                )
            except Exception as e:
                self.logger.warning(f"토스트 알림 실패: {e}")
        
        # 비동기 표시
        threading.Thread(target=_show, daemon=True).start()
    
    def notify(self, event_type: NotificationType, data: Dict[str, Any]):
        """
        통합 알림 (사운드 + 토스트)
        
        Args:
            event_type: 알림 유형
            data: 알림 데이터
                - title: 제목 (optional)
                - message: 메시지
                - code: 종목코드 (optional)
                - name: 종목명 (optional)
                - price: 가격 (optional)
                - quantity: 수량 (optional)
                - profit: 손익 (optional)
        """
        if not self._should_notify(event_type):
            return
        
        # 제목 생성
        icon = self.ICONS.get(event_type, "🔔")
        title = data.get("title", "")
        if not title:
            type_names = {
                NotificationType.BUY: "매수 체결",
                NotificationType.SELL: "매도 체결",
                NotificationType.PROFIT: "익절 완료",
                NotificationType.LOSS: "손절 발생",
                NotificationType.TARGET: "목표가 도달",
                NotificationType.ALERT: "알림",
                NotificationType.ERROR: "오류",
            }
            title = type_names.get(event_type, "알림")
        
        # 메시지 생성
        message = data.get("message", "")
        if not message:
            parts = []
            if data.get("name"):
                parts.append(f"{data['name']}")
            if data.get("price"):
                parts.append(f"{data['price']:,}원")
            if data.get("quantity"):
                parts.append(f"{data['quantity']}주")
            if data.get("profit") is not None:
                profit = data['profit']
                parts.append(f"손익: {profit:+,}원")
            message = " | ".join(parts) if parts else "거래가 발생했습니다."
        
        # 사운드 재생
        self.play_sound(event_type)
        
        # 토스트 알림
        self.show_toast(title, message, event_type)
        
        self.logger.info(f"알림 발송: [{event_type.value}] {title} - {message}")
    
    def notify_buy(self, code: str, name: str, price: int, quantity: int):
        """매수 체결 알림"""
        self.notify(NotificationType.BUY, {
            "code": code,
            "name": name,
            "price": price,
            "quantity": quantity,
        })
    
    def notify_sell(self, code: str, name: str, price: int, quantity: int, profit: int):
        """매도 체결 알림"""
        event_type = NotificationType.PROFIT if profit > 0 else NotificationType.LOSS
        self.notify(event_type, {
            "code": code,
            "name": name,
            "price": price,
            "quantity": quantity,
            "profit": profit,
        })
    
    def notify_target_reached(self, code: str, name: str, target_price: int, current_price: int):
        """목표가 도달 알림"""
        self.notify(NotificationType.TARGET, {
            "code": code,
            "name": name,
            "message": f"{name} 목표가 {target_price:,}원 도달! (현재 {current_price:,}원)",
        })
    
    def notify_error(self, message: str):
        """오류 알림"""
        self.notify(NotificationType.ERROR, {
            "title": "오류 발생",
            "message": message,
        })
    
    def update_settings(self, settings: NotificationSettings):
        """설정 업데이트"""
        self.settings = settings
