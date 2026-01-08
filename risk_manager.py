"""
Risk Manager for Kiwoom Pro Algo-Trader
리스크 관리 모듈 - 드로다운, 연속손실, 블랙리스트 관리
"""

import json
import logging
from datetime import timedelta
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List, Set, Any
from dataclasses import dataclass, field


@dataclass
class RiskSettings:
    """리스크 관리 설정"""
    # 드로다운 관리
    max_drawdown_percent: float = 10.0      # 최대 허용 드로다운 %
    drawdown_alert_percent: float = 5.0     # 드로다운 경고 %
    
    # 연속 손실 관리
    max_consecutive_losses: int = 5         # 최대 연속 손실 허용
    pause_after_losses: int = 3             # N회 연속 손실 시 일시정지
    pause_duration_minutes: int = 30        # 일시정지 시간 (분)
    
    # 종목별 관리
    max_loss_per_stock: float = 3.0         # 종목당 최대 손실 %
    blacklist_on_loss: bool = True          # 손절 시 블랙리스트 추가
    blacklist_duration_days: int = 1        # 블랙리스트 유지 기간 (일)
    
    # 데이터 파일
    data_file: str = "risk_data.json"


@dataclass
class RiskState:
    """리스크 상태 데이터"""
    # 드로다운
    peak_balance: float = 0.0               # 최고 잔고
    current_balance: float = 0.0            # 현재 잔고
    current_drawdown: float = 0.0           # 현재 드로다운 %
    max_drawdown_today: float = 0.0         # 오늘 최대 드로다운
    
    # 연속 손실
    consecutive_losses: int = 0             # 연속 손실 횟수
    consecutive_wins: int = 0               # 연속 이익 횟수
    is_paused: bool = False                 # 일시정지 상태
    pause_until: Optional[datetime] = None  # 일시정지 해제 시간
    
    # 오늘 통계
    today_trades: int = 0                   # 오늘 거래 횟수
    today_wins: int = 0                     # 오늘 이익 거래
    today_losses: int = 0                   # 오늘 손실 거래
    today_profit: float = 0.0               # 오늘 실현 손익
    
    # 블랙리스트
    blacklist: Dict[str, str] = field(default_factory=dict)  # {code: expiry_date}


class RiskManager:
    """리스크 관리자"""
    
    def __init__(self, settings: Optional[RiskSettings] = None):
        self.settings = settings or RiskSettings()
        self.state = RiskState()
        self.logger = logging.getLogger('RiskManager')
        self._load_state()
    
    def _load_state(self):
        """저장된 상태 로드"""
        try:
            data_path = Path(self.settings.data_file)
            if data_path.exists():
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 오늘 날짜가 아니면 일일 통계 초기화
                saved_date = data.get("date", "")
                today = date.today().isoformat()
                
                if saved_date != today:
                    # 새로운 날 - 일일 통계 초기화
                    self.state.today_trades = 0
                    self.state.today_wins = 0
                    self.state.today_losses = 0
                    self.state.today_profit = 0.0
                    self.state.max_drawdown_today = 0.0
                    self.state.consecutive_losses = 0
                    self.state.consecutive_wins = 0
                    self.state.is_paused = False
                    self.state.pause_until = None
                else:
                    # 같은 날 - 상태 복원
                    self.state.consecutive_losses = data.get("consecutive_losses", 0)
                    self.state.consecutive_wins = data.get("consecutive_wins", 0)
                    self.state.today_trades = data.get("today_trades", 0)
                    self.state.today_wins = data.get("today_wins", 0)
                    self.state.today_losses = data.get("today_losses", 0)
                    self.state.today_profit = data.get("today_profit", 0.0)
                    self.state.max_drawdown_today = data.get("max_drawdown_today", 0.0)
                
                # 블랙리스트 로드 및 만료 제거
                self.state.blacklist = {}
                for code, expiry in data.get("blacklist", {}).items():
                    if expiry >= today:
                        self.state.blacklist[code] = expiry
                
                self.state.peak_balance = data.get("peak_balance", 0.0)
                
        except Exception as e:
            self.logger.warning(f"리스크 상태 로드 실패: {e}")
    
    def _save_state(self):
        """상태 저장"""
        try:
            data = {
                "date": date.today().isoformat(),
                "peak_balance": self.state.peak_balance,
                "consecutive_losses": self.state.consecutive_losses,
                "consecutive_wins": self.state.consecutive_wins,
                "today_trades": self.state.today_trades,
                "today_wins": self.state.today_wins,
                "today_losses": self.state.today_losses,
                "today_profit": self.state.today_profit,
                "max_drawdown_today": self.state.max_drawdown_today,
                "blacklist": self.state.blacklist,
            }
            with open(self.settings.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"리스크 상태 저장 실패: {e}")
    
    def update_balance(self, current_balance: float) -> Dict[str, Any]:
        """
        잔고 업데이트 및 드로다운 계산
        
        Returns:
            {
                'drawdown': float,
                'drawdown_alert': bool,
                'drawdown_exceeded': bool,
            }
        """
        self.state.current_balance = current_balance
        
        # 최고 잔고 업데이트
        if current_balance > self.state.peak_balance:
            self.state.peak_balance = current_balance
        
        # 드로다운 계산
        if self.state.peak_balance > 0:
            self.state.current_drawdown = (
                (self.state.peak_balance - current_balance) / self.state.peak_balance
            ) * 100
        else:
            self.state.current_drawdown = 0.0
        
        # 오늘 최대 드로다운 업데이트
        if self.state.current_drawdown > self.state.max_drawdown_today:
            self.state.max_drawdown_today = self.state.current_drawdown
        
        result = {
            'drawdown': self.state.current_drawdown,
            'drawdown_alert': self.state.current_drawdown >= self.settings.drawdown_alert_percent,
            'drawdown_exceeded': self.state.current_drawdown >= self.settings.max_drawdown_percent,
        }
        
        if result['drawdown_exceeded']:
            self.logger.warning(f"최대 드로다운 초과! {self.state.current_drawdown:.2f}%")
        elif result['drawdown_alert']:
            self.logger.info(f"드로다운 경고: {self.state.current_drawdown:.2f}%")
        
        self._save_state()
        return result
    
    def record_trade(self, profit: float, code: str = "") -> Dict[str, Any]:
        """
        거래 결과 기록
        
        Args:
            profit: 실현 손익
            code: 종목코드 (손절 시 블랙리스트용)
        
        Returns:
            {
                'consecutive_losses': int,
                'should_pause': bool,
                'blacklisted': bool,
            }
        """
        self.state.today_trades += 1
        self.state.today_profit += profit
        
        result = {
            'consecutive_losses': 0,
            'should_pause': False,
            'blacklisted': False,
        }
        
        if profit > 0:
            # 이익
            self.state.today_wins += 1
            self.state.consecutive_wins += 1
            self.state.consecutive_losses = 0
        else:
            # 손실
            self.state.today_losses += 1
            self.state.consecutive_losses += 1
            self.state.consecutive_wins = 0
            
            result['consecutive_losses'] = self.state.consecutive_losses
            
            # 연속 손실 시 일시정지
            if self.state.consecutive_losses >= self.settings.pause_after_losses:
                self.state.is_paused = True
                self.state.pause_until = datetime.now() + timedelta(
                    minutes=self.settings.pause_duration_minutes
                )
                result['should_pause'] = True
                self.logger.warning(
                    f"연속 {self.state.consecutive_losses}회 손실 - "
                    f"{self.settings.pause_duration_minutes}분 일시정지"
                )
            
            # 블랙리스트 추가
            if code and self.settings.blacklist_on_loss:
                self.add_to_blacklist(code)
                result['blacklisted'] = True
        
        self._save_state()
        return result
    
    def add_to_blacklist(self, code: str):
        """종목 블랙리스트 추가"""
        from datetime import timedelta
        expiry = (date.today() + timedelta(days=self.settings.blacklist_duration_days)).isoformat()
        self.state.blacklist[code] = expiry
        self.logger.info(f"블랙리스트 추가: {code} (만료: {expiry})")
        self._save_state()
    
    def remove_from_blacklist(self, code: str):
        """종목 블랙리스트 제거"""
        if code in self.state.blacklist:
            del self.state.blacklist[code]
            self._save_state()
            self.logger.info(f"블랙리스트 제거: {code}")
    
    def is_blacklisted(self, code: str) -> bool:
        """블랙리스트 여부 확인"""
        if code not in self.state.blacklist:
            return False
        
        # 만료 확인
        expiry = self.state.blacklist[code]
        if expiry < date.today().isoformat():
            del self.state.blacklist[code]
            self._save_state()
            return False
        
        return True
    
    def is_trading_allowed(self) -> tuple[bool, str]:
        """
        매매 허용 여부 확인
        
        Returns:
            (allowed: bool, reason: str)
        """
        # 일시정지 상태 확인
        if self.state.is_paused:
            if self.state.pause_until and datetime.now() >= self.state.pause_until:
                # 일시정지 해제
                self.state.is_paused = False
                self.state.pause_until = None
                self._save_state()
            else:
                remaining = ""
                if self.state.pause_until:
                    diff = (self.state.pause_until - datetime.now()).seconds // 60
                    remaining = f" ({diff}분 남음)"
                return False, f"연속 손실로 일시정지 중{remaining}"
        
        # 최대 드로다운 확인
        if self.state.current_drawdown >= self.settings.max_drawdown_percent:
            return False, f"최대 드로다운 초과 ({self.state.current_drawdown:.1f}%)"
        
        # 연속 손실 한도 확인
        if self.state.consecutive_losses >= self.settings.max_consecutive_losses:
            return False, f"연속 손실 한도 도달 ({self.state.consecutive_losses}회)"
        
        return True, ""
    
    def can_trade_stock(self, code: str) -> tuple[bool, str]:
        """
        특정 종목 매매 가능 여부
        
        Returns:
            (allowed: bool, reason: str)
        """
        # 전체 매매 허용 확인
        allowed, reason = self.is_trading_allowed()
        if not allowed:
            return False, reason
        
        # 블랙리스트 확인
        if self.is_blacklisted(code):
            return False, f"블랙리스트 종목 (손절 이력)"
        
        return True, ""
    
    def get_risk_adjusted_size(self, base_size: float) -> float:
        """
        리스크 조정 수량 계산
        
        연속 손실 시 수량 감소
        """
        if self.state.consecutive_losses == 0:
            return base_size
        
        # 연속 손실당 20% 감소 (최대 60% 감소)
        reduction = min(self.state.consecutive_losses * 0.2, 0.6)
        adjusted = base_size * (1 - reduction)
        
        self.logger.info(
            f"리스크 조정: {base_size:.0f} → {adjusted:.0f} "
            f"(연속손실 {self.state.consecutive_losses}회, -{reduction*100:.0f}%)"
        )
        return adjusted
    
    def get_status(self) -> Dict[str, Any]:
        """현재 리스크 상태 조회"""
        allowed, reason = self.is_trading_allowed()
        return {
            'current_drawdown': self.state.current_drawdown,
            'max_drawdown_today': self.state.max_drawdown_today,
            'consecutive_losses': self.state.consecutive_losses,
            'consecutive_wins': self.state.consecutive_wins,
            'today_trades': self.state.today_trades,
            'today_wins': self.state.today_wins,
            'today_losses': self.state.today_losses,
            'today_profit': self.state.today_profit,
            'is_paused': self.state.is_paused,
            'trading_allowed': allowed,
            'trading_blocked_reason': reason,
            'blacklist_count': len(self.state.blacklist),
            'blacklist': list(self.state.blacklist.keys()),
        }
    
    def reset_daily(self):
        """일일 통계 초기화"""
        self.state.today_trades = 0
        self.state.today_wins = 0
        self.state.today_losses = 0
        self.state.today_profit = 0.0
        self.state.max_drawdown_today = 0.0
        self.state.consecutive_losses = 0
        self.state.consecutive_wins = 0
        self.state.is_paused = False
        self.state.pause_until = None
        self._save_state()
        self.logger.info("일일 리스크 상태 초기화")
    
    def force_resume(self):
        """강제 매매 재개"""
        self.state.is_paused = False
        self.state.pause_until = None
        self.state.consecutive_losses = 0
        self._save_state()
        self.logger.info("매매 강제 재개")
    
    def save_state(self):
        """상태 저장 (public alias)"""
        self._save_state()
