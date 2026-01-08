"""
Stock Screener for Kiwoom Pro Algo-Trader
기술적 조건 기반 종목 스크리닝
"""

import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum


class ConditionType(Enum):
    """스크리너 조건 유형"""
    # 이동평균
    MA_GOLDEN_CROSS = "ma_golden_cross"     # 골든크로스
    MA_DEAD_CROSS = "ma_dead_cross"         # 데드크로스
    ABOVE_MA = "above_ma"                   # 이동평균 위
    BELOW_MA = "below_ma"                   # 이동평균 아래
    
    # RSI
    RSI_OVERSOLD = "rsi_oversold"           # 과매도 (RSI < 30)
    RSI_OVERBOUGHT = "rsi_overbought"       # 과매수 (RSI > 70)
    RSI_RANGE = "rsi_range"                 # RSI 범위
    
    # 거래량
    VOLUME_SURGE = "volume_surge"           # 거래량 급등
    VOLUME_ABOVE_AVG = "volume_above_avg"   # 평균 거래량 이상
    
    # 변동성
    VOLATILITY_BREAKOUT = "volatility_breakout"  # 변동성 돌파
    ATR_BREAKOUT = "atr_breakout"           # ATR 돌파
    
    # 볼린저밴드
    BB_LOWER_TOUCH = "bb_lower_touch"       # 하단밴드 터치
    BB_UPPER_TOUCH = "bb_upper_touch"       # 상단밴드 터치
    BB_SQUEEZE = "bb_squeeze"               # 볼린저밴드 수축
    
    # 기타
    NEW_HIGH = "new_high"                   # 신고가
    NEW_LOW = "new_low"                     # 신저가
    PRICE_CHANGE = "price_change"           # 등락률


@dataclass
class ScreenerCondition:
    """스크리너 조건 정의"""
    condition_type: ConditionType
    params: Dict[str, Any] = None
    
    def __post_init__(self):
        self.params = self.params or {}


@dataclass 
class ScreenerResult:
    """스크리닝 결과"""
    code: str
    name: str
    current_price: int
    change_rate: float
    volume: int
    matched_conditions: List[str]
    score: float  # 조건 매칭 점수


class StockScreener:
    """종목 스크리너"""
    
    def __init__(self, rest_client=None, strategy_manager=None):
        """
        Args:
            rest_client: KiwoomRESTClient 인스턴스
            strategy_manager: StrategyManager 인스턴스
        """
        self.rest_client = rest_client
        self.strategy = strategy_manager
        self.logger = logging.getLogger('Screener')
        
        # 가격 데이터 캐시
        self._price_cache: Dict[str, Dict] = {}
        
    def set_clients(self, rest_client, strategy_manager=None):
        """클라이언트 설정"""
        self.rest_client = rest_client
        self.strategy = strategy_manager
    
    def _get_price_data(self, code: str) -> Optional[Dict]:
        """가격 데이터 조회 (캐시 사용)"""
        if code in self._price_cache:
            return self._price_cache[code]
        
        if not self.rest_client:
            return None
            
        try:
            quote = self.rest_client.get_stock_quote(code)
            if quote:
                data = {
                    'name': quote.name,
                    'current': quote.current_price,
                    'open': quote.open_price,
                    'high': quote.high_price,
                    'low': quote.low_price,
                    'prev_close': quote.prev_close,
                    'volume': quote.volume,
                    'change_rate': ((quote.current_price - quote.prev_close) / quote.prev_close * 100) if quote.prev_close else 0,
                }
                self._price_cache[code] = data
                return data
        except Exception as e:
            self.logger.warning(f"{code} 시세 조회 실패: {e}")
        
        return None
    
    def _get_daily_data(self, code: str, count: int = 60) -> Optional[List[Dict]]:
        """일봉 데이터 조회"""
        if not self.rest_client:
            return None
            
        try:
            candles = self.rest_client.get_daily_chart(code, count)
            if candles:
                return [{
                    'date': c.date,
                    'open': c.open_price,
                    'high': c.high_price,
                    'low': c.low_price,
                    'close': c.close_price,
                    'volume': c.volume,
                } for c in candles]
        except Exception as e:
            self.logger.warning(f"{code} 일봉 조회 실패: {e}")
        
        return None
    
    def _calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        """이동평균 계산"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """RSI 계산"""
        if len(prices) < period + 1:
            return None
            
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        if len(gains) < period:
            return None
            
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_bollinger(self, prices: List[float], period: int = 20, std_mult: float = 2.0) -> Optional[Dict]:
        """볼린저밴드 계산"""
        if len(prices) < period:
            return None
            
        recent = prices[-period:]
        middle = sum(recent) / period
        
        variance = sum((p - middle) ** 2 for p in recent) / period
        std = variance ** 0.5
        
        return {
            'upper': middle + std_mult * std,
            'middle': middle,
            'lower': middle - std_mult * std,
            'width': (std_mult * std * 2) / middle * 100,  # 밴드 폭 %
        }
    
    def _check_condition(self, code: str, condition: ScreenerCondition, daily_data: List[Dict]) -> bool:
        """단일 조건 체크"""
        if not daily_data:
            return False
        
        closes = [d['close'] for d in daily_data]
        volumes = [d['volume'] for d in daily_data]
        highs = [d['high'] for d in daily_data]
        lows = [d['low'] for d in daily_data]
        
        ctype = condition.condition_type
        params = condition.params
        
        try:
            # === 이동평균 조건 ===
            if ctype == ConditionType.MA_GOLDEN_CROSS:
                short_period = params.get('short', 5)
                long_period = params.get('long', 20)
                
                if len(closes) < long_period + 2:
                    return False
                
                # 현재와 전일 MA
                ma_short_now = self._calculate_ma(closes[:-1], short_period)
                ma_long_now = self._calculate_ma(closes[:-1], long_period)
                ma_short_prev = self._calculate_ma(closes[:-2], short_period)
                ma_long_prev = self._calculate_ma(closes[:-2], long_period)
                
                if all([ma_short_now, ma_long_now, ma_short_prev, ma_long_prev]):
                    # 전일 데드크로스 상태 → 오늘 골든크로스
                    return ma_short_prev <= ma_long_prev and ma_short_now > ma_long_now
                return False
            
            elif ctype == ConditionType.MA_DEAD_CROSS:
                short_period = params.get('short', 5)
                long_period = params.get('long', 20)
                
                if len(closes) < long_period + 2:
                    return False
                
                ma_short_now = self._calculate_ma(closes[:-1], short_period)
                ma_long_now = self._calculate_ma(closes[:-1], long_period)
                ma_short_prev = self._calculate_ma(closes[:-2], short_period)
                ma_long_prev = self._calculate_ma(closes[:-2], long_period)
                
                if all([ma_short_now, ma_long_now, ma_short_prev, ma_long_prev]):
                    return ma_short_prev >= ma_long_prev and ma_short_now < ma_long_now
                return False
            
            elif ctype == ConditionType.ABOVE_MA:
                period = params.get('period', 20)
                ma = self._calculate_ma(closes, period)
                if ma:
                    return closes[-1] > ma
                return False
            
            elif ctype == ConditionType.BELOW_MA:
                period = params.get('period', 20)
                ma = self._calculate_ma(closes, period)
                if ma:
                    return closes[-1] < ma
                return False
            
            # === RSI 조건 ===
            elif ctype == ConditionType.RSI_OVERSOLD:
                threshold = params.get('threshold', 30)
                rsi = self._calculate_rsi(closes)
                if rsi is not None:
                    return rsi < threshold
                return False
            
            elif ctype == ConditionType.RSI_OVERBOUGHT:
                threshold = params.get('threshold', 70)
                rsi = self._calculate_rsi(closes)
                if rsi is not None:
                    return rsi > threshold
                return False
            
            elif ctype == ConditionType.RSI_RANGE:
                low = params.get('low', 30)
                high = params.get('high', 70)
                rsi = self._calculate_rsi(closes)
                if rsi is not None:
                    return low <= rsi <= high
                return False
            
            # === 거래량 조건 ===
            elif ctype == ConditionType.VOLUME_SURGE:
                multiplier = params.get('multiplier', 2.0)
                period = params.get('period', 20)
                
                if len(volumes) < period + 1:
                    return False
                
                avg_volume = sum(volumes[-period-1:-1]) / period
                return volumes[-1] > avg_volume * multiplier
            
            elif ctype == ConditionType.VOLUME_ABOVE_AVG:
                period = params.get('period', 20)
                
                if len(volumes) < period + 1:
                    return False
                
                avg_volume = sum(volumes[-period-1:-1]) / period
                return volumes[-1] > avg_volume
            
            # === 변동성 조건 ===
            elif ctype == ConditionType.VOLATILITY_BREAKOUT:
                k = params.get('k', 0.5)
                
                if len(daily_data) < 2:
                    return False
                
                prev = daily_data[-2]
                today = daily_data[-1]
                
                volatility = prev['high'] - prev['low']
                target = today['open'] + volatility * k
                
                return today['close'] > target
            
            # === 볼린저밴드 조건 ===
            elif ctype == ConditionType.BB_LOWER_TOUCH:
                bb = self._calculate_bollinger(closes)
                if bb:
                    return closes[-1] <= bb['lower']
                return False
            
            elif ctype == ConditionType.BB_UPPER_TOUCH:
                bb = self._calculate_bollinger(closes)
                if bb:
                    return closes[-1] >= bb['upper']
                return False
            
            elif ctype == ConditionType.BB_SQUEEZE:
                threshold = params.get('threshold', 5.0)  # 밴드 폭 %
                bb = self._calculate_bollinger(closes)
                if bb:
                    return bb['width'] < threshold
                return False
            
            # === 기타 조건 ===
            elif ctype == ConditionType.NEW_HIGH:
                period = params.get('period', 52)  # 52주 신고가
                if len(highs) >= period:
                    return highs[-1] >= max(highs[-period:])
                return False
            
            elif ctype == ConditionType.NEW_LOW:
                period = params.get('period', 52)
                if len(lows) >= period:
                    return lows[-1] <= min(lows[-period:])
                return False
            
            elif ctype == ConditionType.PRICE_CHANGE:
                min_change = params.get('min', 0)
                max_change = params.get('max', 100)
                
                if len(closes) < 2:
                    return False
                
                change = (closes[-1] - closes[-2]) / closes[-2] * 100
                return min_change <= change <= max_change
        
        except Exception as e:
            self.logger.warning(f"{code} 조건 체크 오류 ({ctype.value}): {e}")
        
        return False
    
    def scan(self, codes: List[str], conditions: List[ScreenerCondition], 
             require_all: bool = False) -> List[ScreenerResult]:
        """
        종목 스캔 실행
        
        Args:
            codes: 스캔할 종목코드 리스트
            conditions: 스크리닝 조건 리스트
            require_all: True면 모든 조건 충족, False면 하나라도 충족
        
        Returns:
            매칭된 종목 결과 리스트 (점수순 정렬)
        """
        self._price_cache.clear()
        results = []
        
        for code in codes:
            try:
                # 가격 데이터 조회
                price_data = self._get_price_data(code)
                if not price_data:
                    continue
                
                # 일봉 데이터 조회
                daily_data = self._get_daily_data(code)
                if not daily_data:
                    continue
                
                # 조건 체크
                matched = []
                for cond in conditions:
                    if self._check_condition(code, cond, daily_data):
                        matched.append(cond.condition_type.value)
                
                # 결과 판정
                if require_all:
                    if len(matched) < len(conditions):
                        continue
                else:
                    if not matched:
                        continue
                
                # 점수 계산 (매칭 조건 비율)
                score = len(matched) / len(conditions) * 100
                
                results.append(ScreenerResult(
                    code=code,
                    name=price_data['name'],
                    current_price=price_data['current'],
                    change_rate=price_data['change_rate'],
                    volume=price_data['volume'],
                    matched_conditions=matched,
                    score=score,
                ))
                
            except Exception as e:
                self.logger.warning(f"{code} 스캔 오류: {e}")
        
        # 점수순 정렬
        results.sort(key=lambda x: x.score, reverse=True)
        
        self.logger.info(f"스캔 완료: {len(codes)}개 중 {len(results)}개 매칭")
        return results
    
    def scan_golden_cross(self, codes: List[str], short: int = 5, long: int = 20) -> List[ScreenerResult]:
        """골든크로스 종목 스캔"""
        return self.scan(codes, [
            ScreenerCondition(ConditionType.MA_GOLDEN_CROSS, {'short': short, 'long': long})
        ])
    
    def scan_rsi_oversold(self, codes: List[str], threshold: int = 30) -> List[ScreenerResult]:
        """RSI 과매도 종목 스캔"""
        return self.scan(codes, [
            ScreenerCondition(ConditionType.RSI_OVERSOLD, {'threshold': threshold})
        ])
    
    def scan_volume_surge(self, codes: List[str], multiplier: float = 2.0) -> List[ScreenerResult]:
        """거래량 급등 종목 스캔"""
        return self.scan(codes, [
            ScreenerCondition(ConditionType.VOLUME_SURGE, {'multiplier': multiplier})
        ])
    
    def scan_volatility_breakout(self, codes: List[str], k: float = 0.5) -> List[ScreenerResult]:
        """변동성 돌파 종목 스캔"""
        return self.scan(codes, [
            ScreenerCondition(ConditionType.VOLATILITY_BREAKOUT, {'k': k})
        ])
    
    def scan_bb_oversold(self, codes: List[str]) -> List[ScreenerResult]:
        """볼린저밴드 하단 터치 종목 스캔"""
        return self.scan(codes, [
            ScreenerCondition(ConditionType.BB_LOWER_TOUCH)
        ])
    
    def create_preset_conditions(self, preset: str) -> List[ScreenerCondition]:
        """프리셋 조건 생성"""
        presets = {
            'aggressive': [
                ScreenerCondition(ConditionType.VOLATILITY_BREAKOUT, {'k': 0.6}),
                ScreenerCondition(ConditionType.VOLUME_SURGE, {'multiplier': 2.0}),
            ],
            'value': [
                ScreenerCondition(ConditionType.RSI_OVERSOLD, {'threshold': 30}),
                ScreenerCondition(ConditionType.BB_LOWER_TOUCH),
            ],
            'momentum': [
                ScreenerCondition(ConditionType.MA_GOLDEN_CROSS, {'short': 5, 'long': 20}),
                ScreenerCondition(ConditionType.VOLUME_ABOVE_AVG),
            ],
            'breakout': [
                ScreenerCondition(ConditionType.NEW_HIGH, {'period': 20}),
                ScreenerCondition(ConditionType.VOLUME_SURGE, {'multiplier': 1.5}),
            ],
        }
        return presets.get(preset, [])
