"""
Sound Notifier for Kiwoom Pro Algo-Trader
사운드 알림 시스템
"""

import threading
import queue
import os
from typing import Optional
from pathlib import Path

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


class SoundNotifier:
    """비동기 사운드 알림 클래스"""
    
    # 기본 시스템 사운드 (Windows)
    SOUND_BUY = "SystemAsterisk"      # 매수
    SOUND_SELL = "SystemExclamation"  # 매도
    SOUND_ERROR = "SystemHand"         # 에러
    SOUND_WARNING = "SystemQuestion"   # 경고
    SOUND_SUCCESS = "SystemNotification"  # 성공
    
    # 커스텀 사운드 빈도 (Hz)
    FREQ_BUY = 800
    FREQ_SELL = 600
    FREQ_ERROR = 400
    FREQ_PROFIT = 1000
    FREQ_LOSS = 300
    
    def __init__(self, enabled: bool = True, use_custom: bool = False):
        """
        Args:
            enabled: 사운드 활성화 여부
            use_custom: 커스텀 비프음 사용 여부 (False면 시스템 사운드)
        """
        self.enabled = enabled and HAS_WINSOUND
        self.use_custom = use_custom
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = False
        
        if self.enabled:
            self._start_worker()
    
    def _start_worker(self):
        """백그라운드 사운드 재생 스레드 시작"""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
    
    def _worker(self):
        """사운드 재생 워커"""
        while not self._stop:
            try:
                sound_type = self._queue.get(timeout=1)
                if sound_type is None:
                    break
                self._play_sound(sound_type)
            except queue.Empty:
                continue
            except Exception:
                pass  # 사운드 재생 실패 무시
    
    def _play_sound(self, sound_type: str):
        """실제 사운드 재생"""
        if not self.enabled or not HAS_WINSOUND:
            return
        
        try:
            if self.use_custom:
                # 커스텀 비프음
                freq_map = {
                    'buy': self.FREQ_BUY,
                    'sell': self.FREQ_SELL,
                    'error': self.FREQ_ERROR,
                    'warning': self.FREQ_ERROR,
                    'profit': self.FREQ_PROFIT,
                    'loss': self.FREQ_LOSS,
                    'success': self.FREQ_PROFIT,
                }
                freq = freq_map.get(sound_type, 600)
                duration = 150 if sound_type in ['buy', 'sell'] else 300
                winsound.Beep(freq, duration)
            else:
                # 시스템 사운드
                sound_map = {
                    'buy': self.SOUND_BUY,
                    'sell': self.SOUND_SELL,
                    'error': self.SOUND_ERROR,
                    'warning': self.SOUND_WARNING,
                    'profit': self.SOUND_SUCCESS,
                    'loss': self.SOUND_ERROR,
                    'success': self.SOUND_SUCCESS,
                }
                sound = sound_map.get(sound_type, self.SOUND_SUCCESS)
                winsound.PlaySound(sound, winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass
    
    def play(self, sound_type: str):
        """비동기 사운드 재생 (큐에 추가)
        
        Args:
            sound_type: 'buy', 'sell', 'error', 'warning', 'profit', 'loss', 'success'
        """
        if self.enabled:
            self._queue.put(sound_type)
    
    def play_buy(self):
        """매수 사운드"""
        self.play('buy')
    
    def play_sell(self):
        """매도 사운드"""
        self.play('sell')
    
    def play_profit(self):
        """수익 사운드"""
        self.play('profit')
    
    def play_loss(self):
        """손실 사운드"""
        self.play('loss')
    
    def play_error(self):
        """에러 사운드"""
        self.play('error')
    
    def play_warning(self):
        """경고 사운드"""
        self.play('warning')
    
    def play_success(self):
        """성공 사운드"""
        self.play('success')
    
    def set_enabled(self, enabled: bool):
        """사운드 활성화/비활성화"""
        self.enabled = enabled and HAS_WINSOUND
        if self.enabled and not self._thread:
            self._start_worker()
    
    def set_custom_mode(self, use_custom: bool):
        """커스텀 사운드 모드 설정"""
        self.use_custom = use_custom
    
    def stop(self):
        """워커 종료"""
        self._stop = True
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)
