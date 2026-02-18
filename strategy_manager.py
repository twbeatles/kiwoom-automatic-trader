"""
Strategy Manager v4.3
매매 전략 로직 - 확장된 기능 포함
"""

from config import Config
import datetime
import time
from typing import Tuple, Optional, List, Dict, Any
from strategies import StrategyContext, StrategyPackEngine


class StrategyManager:
    """매매 전략 로직 분리"""
    
    def __init__(self, trader, config=None):
        self.trader = trader
        self.config = config  # TradingConfig (v4.5 아키텍처 개선)
        # 연속 손실 추적 (Anti-Martingale용)
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        # 섹터별 투자 추적
        self.sector_investments: Dict[str, float] = {}
        # 시장별 투자 추적
        self.market_investments = {'kospi': 0, 'kosdaq': 0}
        self._decision_cache: Dict[str, Dict[str, Any]] = {}
        self.pack_engine = StrategyPackEngine(self)

    def log(self, msg):
        self.trader.log(msg)

    # ==================================================================
    # 스토캐스틱 RSI (신규)
    # ==================================================================
    def calculate_stochastic_rsi(self, code, rsi_period=14, stoch_period=14, 
                                   k_period=3, d_period=3) -> Tuple[float, float]:
        """스토캐스틱 RSI 계산
        
        Returns:
            (K값, D값) 튜플
        """
        if code not in self.trader.universe:
            return 50, 50
        
        info = self.trader.universe[code]
        prices = info.get('price_history', [])
        
        if len(prices) < rsi_period + stoch_period:
            return 50, 50
        
        # RSI 값들 계산
        rsi_values = []
        for i in range(stoch_period + k_period + d_period):
            end_idx = len(prices) - i
            start_idx = max(0, end_idx - rsi_period - 1)
            sub_prices = prices[start_idx:end_idx]
            if len(sub_prices) >= rsi_period + 1:
                rsi = self._calculate_rsi_from_prices(sub_prices, rsi_period)
                rsi_values.insert(0, rsi)
        
        if len(rsi_values) < stoch_period:
            return 50, 50
        
        # Stochastic RSI 계산
        stoch_k_values = []
        for i in range(len(rsi_values) - stoch_period + 1):
            window = rsi_values[i:i + stoch_period]
            min_rsi = min(window)
            max_rsi = max(window)
            if max_rsi - min_rsi > 0:
                stoch = (window[-1] - min_rsi) / (max_rsi - min_rsi) * 100
            else:
                stoch = 50
            stoch_k_values.append(stoch)
        
        if len(stoch_k_values) < k_period:
            return 50, 50
        
        # %K (SMA of Stoch RSI)
        k_value = sum(stoch_k_values[-k_period:]) / k_period
        
        # %D (SMA of %K)
        if len(stoch_k_values) >= k_period + d_period - 1:
            k_smooth = []
            for i in range(d_period):
                idx = len(stoch_k_values) - d_period + i - k_period + 1
                if idx >= 0:
                    k_smooth.append(sum(stoch_k_values[idx:idx + k_period]) / k_period)
            d_value = sum(k_smooth) / len(k_smooth) if k_smooth else k_value
        else:
            d_value = k_value
        
        return k_value, d_value
    
    def _calculate_rsi_from_prices(self, prices, period):
        """가격 리스트에서 RSI 계산"""
        if len(prices) < period + 1:
            return 50
        
        gains = []
        losses = []
        for i in range(1, period + 1):
            change = prices[-(i)] - prices[-(i+1)] if i + 1 <= len(prices) else 0
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    
    def check_stochastic_rsi_condition(self, code) -> bool:
        """스토캐스틱 RSI 조건 확인"""
        if self.config:
            if not self.config.use_stoch_rsi:
                return True
            upper_limit = self.config.stoch_upper
        else:
            if not hasattr(self.trader, 'chk_use_stoch_rsi') or not self.trader.chk_use_stoch_rsi.isChecked():
                return True
            upper = getattr(self.trader, 'spin_stoch_upper', None)
            upper_limit = upper.value() if upper else 80
        
        k, d = self.calculate_stochastic_rsi(code)
        
        # 과매수 시 진입 보류
        if k >= upper_limit:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] StochRSI K={k:.1f} >= {upper_limit} (과매수) 진입 보류")
            return False
        
        return True

    # ==================================================================
    # 다중 시간프레임 분석 (MTF) (신규)
    # ==================================================================
    def check_mtf_condition(self, code) -> bool:
        """다중 시간프레임 조건 확인
        일봉과 분봉의 추세가 일치할 때만 진입
        """
        if self.config:
            if not self.config.use_mtf:
                return True
        else:
            if not hasattr(self.trader, 'chk_use_mtf') or not self.trader.chk_use_mtf.isChecked():
                return True
        
        info = self.trader.universe.get(code, {})
        
        # 일봉 추세 (MA 기반)
        daily_prices = info.get('daily_prices', info.get('price_history', []))
        daily_trend = self._get_trend(daily_prices, 20)
        
        # 분봉 추세 (현재 가격 기반)
        minute_prices = info.get('minute_prices', info.get('price_history', []))
        minute_trend = self._get_trend(minute_prices, 10)
        
        # 둘 다 상승 추세일 때만 진입
        if daily_trend != 'up' or minute_trend != 'up':
            self.log(f"[{info.get('name', code)}] MTF 불일치: 일봉={daily_trend}, 분봉={minute_trend}")
            return False
        
        return True
    
    def _get_trend(self, prices, period) -> str:
        """추세 판단"""
        if len(prices) < period:
            return 'neutral'
        
        short_ma = sum(prices[-5:]) / 5 if len(prices) >= 5 else prices[-1]
        long_ma = sum(prices[-period:]) / period
        current = prices[-1]
        
        if current > long_ma and short_ma > long_ma:
            return 'up'
        elif current < long_ma and short_ma < long_ma:
            return 'down'
        return 'neutral'

    # ==================================================================
    # 단계별 익절 (Partial Take Profit) (신규)
    # ==================================================================
    def calculate_partial_take_profit(self, code, current_profit_rate: float) -> Optional[Dict]:
        """단계별 익절 계산
        
        Args:
            code: 종목코드
            current_profit_rate: 현재 수익률 (%)
        
        Returns:
            {'sell_ratio': 매도비율, 'level': 단계} 또는 None
        """
        if self.config:
            if not self.config.use_partial_profit:
                return None
        else:
            if not hasattr(self.trader, 'chk_use_partial_profit') or \
               not self.trader.chk_use_partial_profit.isChecked():
                return None
        
        info = self.trader.universe.get(code, {})
        executed_levels = info.get('partial_profit_levels', set())
        
        for i, level in enumerate(Config.PARTIAL_TAKE_PROFIT):
            if i not in executed_levels and current_profit_rate >= level['rate']:
                return {
                    'sell_ratio': level['sell_ratio'],
                    'level': i,
                    'rate': level['rate']
                }
        
        return None
    
    def mark_partial_profit_executed(self, code, level: int):
        """단계별 익절 실행 표시"""
        if code in self.trader.universe:
            if 'partial_profit_levels' not in self.trader.universe[code]:
                self.trader.universe[code]['partial_profit_levels'] = set()
            self.trader.universe[code]['partial_profit_levels'].add(level)

    # ==================================================================
    # 진입 점수 시스템 (신규)
    # ==================================================================
    def calculate_entry_score(self, code) -> Tuple[int, Dict[str, int]]:
        """진입 점수 계산
        
        Returns:
            (총점, {지표별 점수}) 튜플
        """
        scores = {}
        info = self.trader.universe.get(code, {})
        prices = info.get('price_history', [])
        current = info.get('current', 0)
        target = info.get('target', 0)
        
        # 1. 목표가 돌파 점수
        if target > 0 and current >= target:
            scores['target_break'] = Config.ENTRY_WEIGHTS.get('target_break', 20)
        else:
            scores['target_break'] = 0
        
        # 2. 이동평균 필터 점수
        if len(prices) >= 20:
            ma20 = sum(prices[-20:]) / 20
            ma5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else current
            if current > ma20 and ma5 > ma20:
                scores['ma_filter'] = Config.ENTRY_WEIGHTS.get('ma_filter', 15)
            else:
                scores['ma_filter'] = 0
        else:
            scores['ma_filter'] = Config.ENTRY_WEIGHTS.get('ma_filter', 15) // 2
        
        # 3. RSI 최적 영역 점수
        rsi = self.calculate_rsi(code, 14)
        if 30 <= rsi <= 60:  # 최적 진입 영역
            scores['rsi_optimal'] = Config.ENTRY_WEIGHTS.get('rsi_optimal', 20)
        elif rsi < 70:
            scores['rsi_optimal'] = Config.ENTRY_WEIGHTS.get('rsi_optimal', 20) // 2
        else:
            scores['rsi_optimal'] = 0
        
        # 4. MACD 골든크로스 점수
        macd, signal, _ = self.calculate_macd(prices)
        if macd > signal:
            scores['macd_golden'] = Config.ENTRY_WEIGHTS.get('macd_golden', 20)
        else:
            scores['macd_golden'] = 0
        
        # 5. 거래량 확인 점수
        current_volume = info.get('current_volume', 0)
        avg_volume = info.get('avg_volume_5', 0)
        if avg_volume > 0 and current_volume >= avg_volume * 1.2:
            scores['volume_confirm'] = Config.ENTRY_WEIGHTS.get('volume_confirm', 15)
        elif avg_volume > 0 and current_volume >= avg_volume:
            scores['volume_confirm'] = Config.ENTRY_WEIGHTS.get('volume_confirm', 15) // 2
        else:
            scores['volume_confirm'] = 0
        
        # 6. 볼린저 밴드 위치 점수
        if len(prices) >= 20:
            upper, middle, lower = self.calculate_bollinger(prices)
            if lower <= current <= middle:
                scores['bb_position'] = Config.ENTRY_WEIGHTS.get('bb_position', 10)
            elif current < lower:
                scores['bb_position'] = Config.ENTRY_WEIGHTS.get('bb_position', 10) // 2
            else:
                scores['bb_position'] = 0
        else:
            scores['bb_position'] = 0
        
        total = sum(scores.values())
        return total, scores
    
    def check_entry_score_condition(self, code) -> Tuple[bool, int]:
        """진입 점수 조건 확인
        
        Returns:
            (통과여부, 점수) 튜플
        """
        if self.config:
            if not self.config.use_entry_scoring:
                return True, 100
            threshold = int(self.config.entry_score_threshold)
        else:
            use_entry = hasattr(self.trader, 'chk_use_entry_score') and self.trader.chk_use_entry_score.isChecked()
            if not use_entry:
                return True, 100
            threshold_spin = getattr(self.trader, 'spin_entry_score_threshold', None)
            threshold = int(threshold_spin.value()) if threshold_spin else Config.ENTRY_SCORE_THRESHOLD

        total, details = self.calculate_entry_score(code)
        
        if total < threshold:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] 진입점수 {total}/{threshold} 미달: {details}")
            return False, total
        
        return True, total

    # ==================================================================
    # 갭 분석 (신규)
    # ==================================================================
    def analyze_gap(self, code) -> Tuple[str, float]:
        """갭 분석
        
        Returns:
            (갭 유형, 갭 비율%) 튜플
            갭 유형: 'gap_up', 'gap_down', 'no_gap'
        """
        info = self.trader.universe.get(code, {})
        today_open = info.get('open', 0)
        prev_close = info.get('prev_close', 0)
        
        if prev_close == 0 or today_open == 0:
            return 'no_gap', 0
        
        gap_ratio = (today_open - prev_close) / prev_close * 100
        
        gap_threshold = getattr(Config, 'GAP_THRESHOLD', 2.0)
        
        if gap_ratio >= gap_threshold:
            return 'gap_up', gap_ratio
        elif gap_ratio <= -gap_threshold:
            return 'gap_down', gap_ratio
        else:
            return 'no_gap', gap_ratio
    
    def check_gap_condition(self, code) -> bool:
        """갭 조건 확인"""
        if self.config:
            if not self.config.use_gap:
                return True
        else:
            if not hasattr(self.trader, 'chk_use_gap') or not self.trader.chk_use_gap.isChecked():
                return True
        
        gap_type, gap_ratio = self.analyze_gap(code)
        
        # 갭 상승 시 더 보수적인 진입 (K값 조정됨)
        if gap_type == 'gap_up':
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] ⚡ 갭상승 {gap_ratio:.1f}% 감지 - 보수적 진입")
            # 갭 상승이 너무 크면 진입 보류
            if gap_ratio > 5.0:
                return False
        
        return True
    
    def get_gap_adjusted_k(self, code) -> float:
        """갭에 따른 조정된 K값 반환"""
        if self.config:
            base_k = self.config.k_value
        else:
            base_k = self.trader.spin_k.value()
            
        gap_type, gap_ratio = self.analyze_gap(code)
        
        if gap_type == 'gap_up':
            # 갭 상승 시 K값 감소 (더 보수적)
            adjustment = min(0.2, gap_ratio / 100)
            return max(0.2, base_k - adjustment)
        elif gap_type == 'gap_down':
            # 갭 하락 시 K값 증가 (더 공격적)
            adjustment = min(0.15, abs(gap_ratio) / 100)
            return min(0.8, base_k + adjustment)
        
        return base_k

    # ==================================================================
    # 동적 포지션 사이징 (Anti-Martingale) (신규)
    # ==================================================================
    def calculate_dynamic_position_size(self, code) -> int:
        """동적 포지션 크기 계산 (Anti-Martingale)
        
        연속 손실 시 포지션 축소, 연속 이익 시 포지션 확대
        """
        info = self.trader.universe.get(code, {})
        current_price = info.get('current', 0)
        
        if current_price <= 0:
            return 0
        
        # 기본 투자금
        if self.config:
             base_invest = self.trader.deposit * (self.config.betting_ratio / 100)
             use_dynamic = self.config.use_dynamic_sizing
        else:
            base_invest = self.trader.deposit * (self.trader.spin_betting.value() / 100)
            use_dynamic = hasattr(self.trader, 'chk_use_dynamic_sizing') and \
                          self.trader.chk_use_dynamic_sizing.isChecked()
        
        # 동적 사이징 활성화 체크
        if not use_dynamic:
            return max(0, int(base_invest / current_price))
        
        # Anti-Martingale 적용
        if self.consecutive_losses >= 3:
            # 연속 3회 이상 손실 시 50% 축소
            adjusted_invest = base_invest * 0.5
            self.log(f"[동적사이징] 연속 {self.consecutive_losses}회 손실 - 투자금 50% 축소")
        elif self.consecutive_losses >= 2:
            # 연속 2회 손실 시 25% 축소
            adjusted_invest = base_invest * 0.75
        elif self.consecutive_wins >= 3:
            # 연속 3회 이상 이익 시 25% 확대
            adjusted_invest = base_invest * 1.25
            self.log(f"[동적사이징] 연속 {self.consecutive_wins}회 이익 - 투자금 25% 확대")
        elif self.consecutive_wins >= 2:
            # 연속 2회 이익 시 10% 확대
            adjusted_invest = base_invest * 1.1
        else:
            adjusted_invest = base_invest
        
        # 최대/최소 제한
        max_invest = self.trader.deposit * 0.2  # 최대 20%
        min_invest = self.trader.deposit * 0.02  # 최소 2%
        adjusted_invest = max(min_invest, min(max_invest, adjusted_invest))
        
        return max(0, int(adjusted_invest / current_price))
    
    def update_consecutive_results(self, is_profit: bool):
        """연속 손익 결과 업데이트"""
        if is_profit:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

    # ==================================================================
    # 자산군 분산 (신규)
    # ==================================================================
    def check_market_diversification(self, code) -> bool:
        """시장별 분산 조건 확인"""
        if self.config:
            if not self.config.use_market_limit:
                 return True
            max_val = self.config.market_limit
        else:
            if not hasattr(self.trader, 'chk_use_market_limit') or \
               not self.trader.chk_use_market_limit.isChecked():
                return True
            max_ratio_spin = getattr(self.trader, 'spin_market_limit', None)
            max_val = max_ratio_spin.value() if max_ratio_spin else 70
        
        market = self._get_stock_market(code)
        current_allocation = self.market_investments.get(market, 0)
        
        # 한 시장에 최대 70% 제한
        max_ratio = max_val / 100
        
        total_invested = sum(self.market_investments.values())
        if total_invested > 0:
            market_ratio = current_allocation / total_invested
            if market_ratio >= max_ratio:
                self.log(f"[분산관리] {market.upper()} 비중 {market_ratio*100:.0f}% >= {max_ratio*100:.0f}% 진입 보류")
                return False
        
        return True
    
    def _get_stock_market(self, code) -> str:
        """종목의 시장 구분 반환"""
        info = self.trader.universe.get(code, {})
        if 'market_type' in info and info['market_type'] != 'unknown':
            return info['market_type'].lower()
        if code.startswith('0') or code.startswith('1') or code.startswith('2'):
            return 'kospi'
        return 'kosdaq'
    
    def update_market_investment(self, code, amount, is_buy=True):
        """시장별 투자금 업데이트"""
        market = self._get_stock_market(code)
        if is_buy:
            self.market_investments[market] = self.market_investments.get(market, 0) + amount
        else:
            self.market_investments[market] = max(0, self.market_investments.get(market, 0) - amount)

    # ==================================================================
    # 섹터 제한 (신규)
    # ==================================================================
    def check_sector_limit(self, code) -> bool:
        """섹터별 투자 제한 확인"""
        if self.config:
            if not self.config.use_sector_limit:
                return True
            max_val = self.config.sector_limit
        else:
            if not hasattr(self.trader, 'chk_use_sector_limit') or \
               not self.trader.chk_use_sector_limit.isChecked():
                return True
            max_amt = getattr(self.trader, 'spin_sector_limit', None)
            max_val = max_amt.value() if max_amt else 30
        
        sector = self._get_stock_sector(code)
        current_allocation = self.sector_investments.get(sector, 0)
        
        # 한 섹터에 최대 투자금 제한
        max_sector_invest = self.trader.deposit * (max_val / 100)
        
        if current_allocation >= max_sector_invest:
            self.log(f"[섹터관리] {sector} 섹터 한도 도달 ({current_allocation:,.0f}원)")
            return False
        
        return True
    
    def _get_stock_sector(self, code) -> str:
        """종목의 섹터 반환 (실제로는 API 조회 필요)"""
        info = self.trader.universe.get(code, {})
        return info.get('sector', '기타')
    
    def update_sector_investment(self, code, amount, is_buy=True):
        """섹터별 투자금 업데이트"""
        sector = self._get_stock_sector(code)
        if is_buy:
            self.sector_investments[sector] = self.sector_investments.get(sector, 0) + amount
        else:
            self.sector_investments[sector] = max(0, self.sector_investments.get(sector, 0) - amount)

    # ==================================================================
    # 변동성 기반 손절 (ATR Stop) (신규)
    # ==================================================================
    def calculate_atr_stop_loss(self, code, multiplier=2.0) -> float:
        """ATR 기반 손절가 계산
        
        Args:
            code: 종목코드
            multiplier: ATR 배수
        
        Returns:
            손절가
        """
        info = self.trader.universe.get(code, {})
        current_price = info.get('current', 0)
        buy_price = info.get('buy_price', 0)
        
        if current_price <= 0 or buy_price <= 0:
            return 0
        
        high_list = info.get('high_history', [])
        low_list = info.get('low_history', [])
        close_list = info.get('price_history', [])
        
        atr = self.calculate_atr(high_list, low_list, close_list, period=14)
        
        if atr <= 0:
            # ATR 계산 불가 시 고정 손절 사용
            loss_cut = self.config.loss_cut if self.config else self.trader.spin_loss.value()
            return buy_price * (1 - loss_cut / 100)
        
        # ATR 기반 손절가 = 매입가 - (ATR * 배수)
        stop_price = buy_price - (atr * multiplier)
        
        return max(0, stop_price)
    
    def check_atr_stop_loss(self, code) -> Tuple[bool, float]:
        """ATR 손절 조건 확인
        
        Returns:
            (손절 필요 여부, 손절가)
        """
        if self.config:
            if not self.config.use_atr_stop:
                return False, 0
            mult = self.config.atr_mult
        else:
            if not hasattr(self.trader, 'chk_use_atr_stop') or \
               not self.trader.chk_use_atr_stop.isChecked():
                return False, 0
            multiplier = getattr(self.trader, 'spin_atr_mult', None)
            mult = multiplier.value() if multiplier else 2.0
        
        info = self.trader.universe.get(code, {})
        current_price = info.get('current', 0)
        
        stop_price = self.calculate_atr_stop_loss(code, mult)
        
        if stop_price > 0 and current_price <= stop_price:
            self.log(f"[{info.get('name', code)}] ATR 손절 발동: 현재가 {current_price:,} <= 손절가 {stop_price:,.0f}")
            return True, stop_price
        
        return False, stop_price

    # ==================================================================
    # 기존 전략 함수들 (유지)
    # ==================================================================
    def calculate_rsi(self, code, period=14):
        """RSI 계산 (종목별 저장된 가격 데이터 기반)"""
        if code not in self.trader.universe:
            return 50
        
        info = self.trader.universe[code]
        prices = info.get('price_history', [])
        
        if len(prices) < period + 1:
            return 50
        
        gains = []
        losses = []
        
        for i in range(1, period + 1):
            change = prices[-(i)] - prices[-(i+1)]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def check_rsi_condition(self, code):
        """RSI 조건 확인"""
        if self.config:
            if not self.config.use_rsi:
                return True
            rsi_period = self.config.rsi_period
            upper_limit = self.config.rsi_upper
        else:
            if not self.trader.chk_use_rsi.isChecked():
                return True
            rsi_period = self.trader.spin_rsi_period.value()
            upper_limit = self.trader.spin_rsi_upper.value()
        
        rsi = self.calculate_rsi(code, rsi_period)
        
        if rsi >= upper_limit:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] RSI {rsi:.1f} >= {upper_limit} (과매수) 진입 보류")
            return False
        
        return True

    def check_volume_condition(self, code):
        """거래량 조건 확인"""
        if self.config:
            if not self.config.use_volume:
                return True
            required_mult = self.config.volume_mult
        else:
            if not self.trader.chk_use_volume.isChecked():
                return True
            required_mult = self.trader.spin_volume_mult.value()
        
        if code not in self.trader.universe:
            return True
        
        info = self.trader.universe[code]
        current_volume = info.get('current_volume', 0)
        avg_volume = info.get('avg_volume_20', 0) or info.get('avg_volume_5', 0)
        
        if avg_volume == 0:
            return True
        
        actual_mult = current_volume / avg_volume
        
        if actual_mult < required_mult:
            return False
        
        return True

    # ==================================================================
    # 유동성/스프레드 필터 (v4.3 신규)
    # ==================================================================
    def check_liquidity_condition(self, code) -> bool:
        """유동성 조건 확인 (20일 평균 거래대금)"""
        if self.config:
            if not self.config.use_liquidity:
                return True
            min_value = self.config.min_avg_value * 100_000_000
        else:
            if not hasattr(self.trader, 'chk_use_liquidity') or not self.trader.chk_use_liquidity.isChecked():
                return True
            min_value = Config.DEFAULT_MIN_AVG_VALUE
            min_value_spin = getattr(self.trader, 'spin_min_value', None)
            if min_value_spin:
                min_value = int(min_value_spin.value() * 100_000_000)

        info = self.trader.universe.get(code, {})
        avg_value = info.get('avg_value_20', 0)

        if avg_value <= 0:
            return True

        if avg_value < min_value:
            self.log(f"[{info.get('name', code)}] 유동성 부족: 평균 거래대금 {avg_value:,.0f}원 < 기준 {min_value:,.0f}원")
            return False

        return True

    def check_spread_condition(self, code) -> bool:
        """스프레드 조건 확인"""
        if self.config:
            if not self.config.use_spread:
                return True
            max_spread = self.config.max_spread
        else:
            if not hasattr(self.trader, 'chk_use_spread') or not self.trader.chk_use_spread.isChecked():
                return True
            max_spread_spin = getattr(self.trader, 'spin_spread_max', None)
            max_spread = max_spread_spin.value() if max_spread_spin else Config.DEFAULT_MAX_SPREAD_PCT

        info = self.trader.universe.get(code, {})
        ask = info.get('ask_price', 0)
        bid = info.get('bid_price', 0)

        if ask <= 0 or bid <= 0:
            return True

        mid = (ask + bid) / 2
        if mid <= 0:
            return True

        spread_pct = (ask - bid) / mid * 100

        if spread_pct > max_spread:
            self.log(f"[{info.get('name', code)}] 스프레드 {spread_pct:.2f}% > {max_spread:.2f}% 진입 보류")
            return False

        return True

    def calculate_macd(self, prices):
        """MACD 계산 (단순 구현)"""
        if len(prices) < Config.DEFAULT_MACD_SLOW + Config.DEFAULT_MACD_SIGNAL:
            return 0, 0, 0
        
        def ema(data, period):
            multiplier = 2 / (period + 1)
            result = [data[0]]
            for i in range(1, len(data)):
                result.append((data[i] - result[-1]) * multiplier + result[-1])
            return result
        
        ema_fast = ema(prices, Config.DEFAULT_MACD_FAST)
        ema_slow = ema(prices, Config.DEFAULT_MACD_SLOW)
        macd = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal = ema(macd, Config.DEFAULT_MACD_SIGNAL)
        histogram = macd[-1] - signal[-1]
        return macd[-1], signal[-1], histogram

    def check_macd_condition(self, code):
        """MACD 조건 확인"""
        if self.config:
            if not self.config.use_macd:
                return True
        else:
            if not hasattr(self.trader, 'chk_use_macd') or not self.trader.chk_use_macd.isChecked():
                return True
        
        info = self.trader.universe.get(code, {})
        prices = info.get('price_history', [])
        if len(prices) < 30:
            return True
        
        macd, signal, _ = self.calculate_macd(prices)
        if macd <= signal:
            self.log(f"[{info.get('name', code)}] MACD {macd:.2f} <= Signal {signal:.2f} 진입 보류")
            return False
        return True

    def calculate_bollinger(self, prices, k=2.0, period=20):
        """볼린저 밴드 계산"""
        if len(prices) < period:
            return 0, 0, 0
        
        subset = prices[-period:]
        avg = sum(subset) / period
        variance = sum((x - avg) ** 2 for x in subset) / period
        std_dev = variance ** 0.5
        
        upper = avg + (std_dev * k)
        lower = avg - (std_dev * k)
        return upper, avg, lower

    def check_bollinger_condition(self, code):
        """볼린저 밴드 조건 확인
        
        하단 밴드 근처에서 매수 기회로 판단 (과매도 상태)
        상단 밴드 이상에서는 진입 보류 (과매수 상태)
        """
        if self.config:
            if not self.config.use_bb:
                return True
            k = self.config.bb_k
        else:
            if not hasattr(self.trader, 'chk_use_bb') or not self.trader.chk_use_bb.isChecked():
                return True
            k = self.trader.spin_bb_k.value()
        
        prices = self.trader.universe.get(code, {}).get('price_history', [])
        current_price = self.trader.universe.get(code, {}).get('current', 0)
        
        if len(prices) < 20 or current_price == 0:
            return True
            
        upper, middle, lower = self.calculate_bollinger(prices, k=k)
        
        # 상단 밴드 이상이면 과매수 → 진입 보류
        if current_price >= upper:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] 볼린저 상단 돌파 ({current_price:,} >= {upper:,.0f}) 진입 보류")
            return False
        
        # 하단~중단 사이 또는 하단 이하면 매수 유효
        return True

    def calculate_atr(self, high_list, low_list, close_list, period=14):
        """ATR(Average True Range) 계산"""
        if len(high_list) < period + 1:
            return 0
            
        tr_list = []
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i-1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
        if len(tr_list) < period:
            return 0
            
        atr = sum(tr_list[-period:]) / period
        return atr

    def calculate_dmi(self, high_list, low_list, close_list, period=14):
        """DMI(P-DI, M-DI, ADX) 계산"""
        if len(high_list) < period + 1:
            return 0, 0, 0
            
        tr_list = []
        p_dm_list = []
        m_dm_list = []
        
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i-1]
            
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
            prev_h = high_list[i-1]
            prev_l = low_list[i-1]
            
            up_move = h - prev_h
            down_move = prev_l - l
            
            if up_move > down_move and up_move > 0:
                p_dm_list.append(up_move)
            else:
                p_dm_list.append(0)
                
            if down_move > up_move and down_move > 0:
                m_dm_list.append(down_move)
            else:
                m_dm_list.append(0)
        
        if len(tr_list) < period:
            return 0, 0, 0
            
        tr_sum = sum(tr_list[-period:])
        p_dm_sum = sum(p_dm_list[-period:])
        m_dm_sum = sum(m_dm_list[-period:])
        
        if tr_sum == 0:
            return 0, 0, 0
            
        p_di = (p_dm_sum / tr_sum) * 100
        m_di = (m_dm_sum / tr_sum) * 100
        
        dx = abs(p_di - m_di) / (p_di + m_di) * 100 if (p_di + m_di) > 0 else 0
        adx = dx
        
        return p_di, m_di, adx

    def check_dmi_condition(self, code):
        """DMI/ADX 조건 확인"""
        if self.config:
            if not self.config.use_dmi:
                return True
            threshold = self.config.adx_threshold
        else:
            if not hasattr(self.trader, 'chk_use_dmi') or not self.trader.chk_use_dmi.isChecked():
                return True
            threshold = self.trader.spin_adx.value()
            
        info = self.trader.universe.get(code, {})
        high_list = info.get('high_history', [])
        low_list = info.get('low_history', [])
        close_list = info.get('price_history', [])
        
        if len(high_list) < 20:
            return True
            
        p_di, m_di, adx = self.calculate_dmi(high_list, low_list, close_list)
        
        if p_di <= m_di:
            return False
            
        if adx < threshold:
            return False
            
        return True

    def calculate_ma(self, prices, period, ma_type='SMA'):
        """이동평균 계산"""
        if len(prices) < period:
            return None
        
        if ma_type == 'SMA':
            return sum(prices[-period:]) / period
        elif ma_type == 'EMA':
            multiplier = 2 / (period + 1)
            ema = prices[0]
            for price in prices[1:]:
                ema = (price - ema) * multiplier + ema
            return ema
        return None
    
    def check_ma_crossover(self, code, short_period=5, long_period=20):
        """이동평균 골든크로스/데드크로스 확인"""
        if self.config:
            if not self.config.use_ma:
                return None
            short_period = self.config.ma_short
            long_period = self.config.ma_long
        else:
            if not hasattr(self.trader, 'chk_use_ma') or not self.trader.chk_use_ma.isChecked():
                return None
            short_period = Config.DEFAULT_MA_SHORT # Or from spinbox if exists, but assuming defaults for now or previously defined values
            # Assuming standard defaults if UI widgets missing or standard usage
        
        info = self.trader.universe.get(code, {})
        prices = info.get('price_history', [])
        
        if len(prices) < long_period + 2:
            return None
        
        short_ma_now = self.calculate_ma(prices, short_period)
        long_ma_now = self.calculate_ma(prices, long_period)
        short_ma_prev = self.calculate_ma(prices[:-1], short_period)
        long_ma_prev = self.calculate_ma(prices[:-1], long_period)
        
        if None in [short_ma_now, long_ma_now, short_ma_prev, long_ma_prev]:
            return None
        
        if short_ma_prev <= long_ma_prev and short_ma_now > long_ma_now:
            self.log(f"[{info.get('name', code)}] 🌟 골든크로스 발생 (MA{short_period}>{long_period})")
            return 'golden'
        
        if short_ma_prev >= long_ma_prev and short_ma_now < long_ma_now:
            self.log(f"[{info.get('name', code)}] ☠️ 데드크로스 발생 (MA{short_period}<{long_period})")
            return 'dead'
        
        return None

    def calculate_position_size(self, code, risk_percent=1.0, atr_multiplier=2.0):
        """ATR 기반 포지션 크기 계산"""
        info = self.trader.universe.get(code, {})
        high_list = info.get('high_history', [])
        low_list = info.get('low_history', [])
        close_list = info.get('price_history', [])
        
        if len(high_list) < 15 or len(low_list) < 15 or len(close_list) < 15:
            return self._default_position_size(code)
        
        atr = self.calculate_atr(high_list, low_list, close_list, period=14)
        if atr <= 0:
            return self._default_position_size(code)
        
        current_price = info.get('current', 0)
        if current_price <= 0:
            return 0
        
        stop_loss_amount = atr * atr_multiplier
        risk_amount = self.trader.deposit * (risk_percent / 100)
        
        if stop_loss_amount > 0:
            position_size = int(risk_amount / stop_loss_amount)
        else:
            position_size = 0
        
        max_invest = self.trader.deposit * (self.config.betting_ratio / 100) if self.config else self.trader.deposit * (self.trader.spin_betting.value() / 100)
        max_quantity = int(max_invest / current_price) if current_price > 0 else 0
        
        final_size = min(position_size, max_quantity)
        
        if final_size > 0:
            self.log(f"[{info.get('name', code)}] ATR 사이징: ATR={atr:.0f}, 적정수량={final_size}주")
        
        return max(0, final_size)
    
    def _default_position_size(self, code):
        """기본 포지션 크기 계산"""
        info = self.trader.universe.get(code, {})
        current_price = info.get('current', 0)
        if current_price <= 0:
            return 0
        
        if self.config:
            invest_amount = self.trader.deposit * (self.config.betting_ratio / 100)
        else:
            invest_amount = self.trader.deposit * (self.trader.spin_betting.value() / 100)
        return max(0, int(invest_amount / current_price))

    def get_time_based_k_value(self):
        """시간대별 K값 반환"""
        now = datetime.datetime.now()
        hour, minute = now.hour, now.minute
        time_val = hour * 60 + minute
        
        base_k = self.config.k_value if self.config else self.trader.spin_k.value()
        
        if time_val < 9 * 60 + 30:
            adjusted_k = base_k * 1.4
            phase = "공격적"
        elif time_val < 14 * 60 + 30:
            adjusted_k = base_k * 1.0
            phase = "기본"
        else:
            adjusted_k = base_k * 0.6
            phase = "보수적"
        
        return adjusted_k, phase
    
    def calculate_target_price(self, code):
        """시간대 적용 목표가 계산"""
        info = self.trader.universe.get(code, {})
        prev_high = info.get('prev_high', 0) or info.get('high', 0)
        prev_low = info.get('prev_low', 0) or info.get('low', 0)
        today_open = info.get('open', 0)
        
        if prev_high == 0 or prev_low == 0 or today_open == 0:
            return 0
        
        # 갭 조정 K값 사용
        if self.config and self.config.use_gap:
            k_value = self.get_gap_adjusted_k(code)
        elif self.config and self.config.use_time_strategy:
            k_value, _ = self.get_time_based_k_value()
        else:
            k_value = self.config.k_value if self.config else self.trader.spin_k.value()
        
        target = today_open + (prev_high - prev_low) * k_value
        
        return target

    def get_split_orders(self, total_quantity, current_price, order_type='buy'):
        """분할 주문 생성"""
        if self.config:
            if not self.config.use_split:
                return [(total_quantity, current_price)]
            split_count = self.config.split_count
            split_percent = self.config.split_percent
        else:
            return [(total_quantity, current_price)]
        
        if split_count <= 1 or total_quantity < split_count:
            return [(total_quantity, current_price)]
        
        orders = []
        remaining = total_quantity
        
        for i in range(split_count):
            if i == split_count - 1:
                qty = remaining
            else:
                qty = total_quantity // split_count
                remaining -= qty
            
            if order_type == 'buy':
                price_adj = 1 - (split_percent / 100) * i
            else:
                price_adj = 1 + (split_percent / 100) * i
            
            adjusted_price = int(current_price * price_adj)
            orders.append((qty, adjusted_price))
        
        return orders

    def _evaluate_with_strategy_pack(
        self, code: str, now_ts: float
    ) -> Optional[Tuple[bool, Dict[str, bool], Dict[str, float]]]:
        """모듈형 전략팩 엔진 평가 경로 (실패 시 None 반환)."""
        cfg = self.config
        if not cfg:
            return None

        flags = getattr(cfg, "feature_flags", {}) or {}
        if not flags.get("use_modular_strategy_pack", True):
            return None

        info = self.trader.universe.get(code)
        if not info:
            return None

        try:
            context = StrategyContext(
                code=code,
                now_ts=now_ts,
                info=info,
                config=cfg,
                portfolio_state={
                    "holding_or_pending_count": int(getattr(self.trader, "_holding_or_pending_count", 0)),
                    "daily_realized_profit": float(getattr(self.trader, "total_realized_profit", 0)),
                },
            )
            pack_result = self.pack_engine.evaluate(context)
            return pack_result.passed, dict(pack_result.conditions), dict(pack_result.metrics)
        except Exception as exc:
            self.log(f"[전략팩] 평가 실패, 레거시 엔진으로 폴백: {exc}")
            return None

    # ==================================================================
    # 종합 매수 조건 체크 (확장)
    # ==================================================================
    def evaluate_buy_conditions(
        self, code: str, now_ts: Optional[float] = None
    ) -> Tuple[bool, Dict[str, bool], Dict[str, float]]:
        """모든 매수 조건을 단일 스냅샷 기준으로 평가한다."""
        now_ts = now_ts if now_ts is not None else time.time()
        cache_window_sec = Config.DECISION_CACHE_MS / 1000.0
        cache_item = self._decision_cache.get(code)
        if cache_item and (now_ts - cache_item.get("ts", 0.0)) < cache_window_sec:
            return cache_item["result"]

        pack_result = self._evaluate_with_strategy_pack(code, now_ts)
        if pack_result is not None:
            self._decision_cache[code] = {"ts": now_ts, "result": pack_result}
            return pack_result

        info = self.trader.universe.get(code, {})
        prices = info.get("price_history", [])
        high_list = info.get("high_history", [])
        low_list = info.get("low_history", [])
        daily_prices = info.get("daily_prices", prices)
        minute_prices = info.get("minute_prices", prices)
        current = float(info.get("current", 0) or 0)
        target = float(info.get("target", 0) or 0)

        cooldown_map = getattr(self.trader, "_log_cooldown_map", None)
        if cooldown_map is None:
            cooldown_map = {}
            self.trader._log_cooldown_map = cooldown_map

        def log_once(key: str, message: str):
            cache_key = f"{code}:{key}"
            last_ts = cooldown_map.get(cache_key, 0.0)
            if now_ts - last_ts >= Config.LOG_DEDUP_SEC:
                self.log(message)
                cooldown_map[cache_key] = now_ts

        cfg = self.config
        if cfg:
            use_rsi = bool(cfg.use_rsi)
            rsi_period = int(cfg.rsi_period)
            rsi_upper = float(cfg.rsi_upper)
            use_volume = bool(cfg.use_volume)
            volume_mult = float(cfg.volume_mult)
            use_liquidity = bool(cfg.use_liquidity)
            min_value = float(cfg.min_avg_value) * 100_000_000
            use_spread = bool(cfg.use_spread)
            max_spread = float(cfg.max_spread)
            use_macd = bool(cfg.use_macd)
            use_bb = bool(cfg.use_bb)
            bb_k = float(cfg.bb_k)
            use_dmi = bool(cfg.use_dmi)
            adx_threshold = float(cfg.adx_threshold)
            use_stoch_rsi = bool(cfg.use_stoch_rsi)
            stoch_upper = float(cfg.stoch_upper)
            use_mtf = bool(cfg.use_mtf)
            use_gap = bool(cfg.use_gap)
            use_entry_scoring = bool(cfg.use_entry_scoring)
            entry_threshold = int(cfg.entry_score_threshold)
        else:
            use_rsi = bool(getattr(self.trader, "chk_use_rsi", None) and self.trader.chk_use_rsi.isChecked())
            rsi_period = int(self.trader.spin_rsi_period.value()) if hasattr(self.trader, "spin_rsi_period") else 14
            rsi_upper = float(self.trader.spin_rsi_upper.value()) if hasattr(self.trader, "spin_rsi_upper") else 70
            use_volume = bool(getattr(self.trader, "chk_use_volume", None) and self.trader.chk_use_volume.isChecked())
            volume_mult = float(self.trader.spin_volume_mult.value()) if hasattr(self.trader, "spin_volume_mult") else 1.5
            use_liquidity = bool(getattr(self.trader, "chk_use_liquidity", None) and self.trader.chk_use_liquidity.isChecked())
            min_value = (
                float(self.trader.spin_min_value.value()) * 100_000_000
                if hasattr(self.trader, "spin_min_value")
                else float(Config.DEFAULT_MIN_AVG_VALUE)
            )
            use_spread = bool(getattr(self.trader, "chk_use_spread", None) and self.trader.chk_use_spread.isChecked())
            max_spread = (
                float(self.trader.spin_spread_max.value())
                if hasattr(self.trader, "spin_spread_max")
                else float(Config.DEFAULT_MAX_SPREAD_PCT)
            )
            use_macd = bool(getattr(self.trader, "chk_use_macd", None) and self.trader.chk_use_macd.isChecked())
            use_bb = bool(getattr(self.trader, "chk_use_bb", None) and self.trader.chk_use_bb.isChecked())
            bb_k = float(self.trader.spin_bb_k.value()) if hasattr(self.trader, "spin_bb_k") else 2.0
            use_dmi = bool(getattr(self.trader, "chk_use_dmi", None) and self.trader.chk_use_dmi.isChecked())
            adx_threshold = float(self.trader.spin_adx.value()) if hasattr(self.trader, "spin_adx") else 25
            use_stoch_rsi = bool(
                getattr(self.trader, "chk_use_stoch_rsi", None) and self.trader.chk_use_stoch_rsi.isChecked()
            )
            stoch_upper = float(self.trader.spin_stoch_upper.value()) if hasattr(self.trader, "spin_stoch_upper") else 80
            use_mtf = bool(getattr(self.trader, "chk_use_mtf", None) and self.trader.chk_use_mtf.isChecked())
            use_gap = bool(getattr(self.trader, "chk_use_gap", None) and self.trader.chk_use_gap.isChecked())
            use_entry_scoring = bool(
                getattr(self.trader, "chk_use_entry_score", None) and self.trader.chk_use_entry_score.isChecked()
            )
            entry_threshold = (
                int(self.trader.spin_entry_score_threshold.value())
                if hasattr(self.trader, "spin_entry_score_threshold")
                else int(Config.ENTRY_SCORE_THRESHOLD)
            )

        metrics: Dict[str, float] = {
            "rsi": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "bb_upper": 0.0,
            "bb_middle": 0.0,
            "bb_lower": 0.0,
            "dmi_pdi": 0.0,
            "dmi_mdi": 0.0,
            "dmi_adx": 0.0,
            "stoch_k": 50.0,
            "stoch_d": 50.0,
            "spread_pct": 0.0,
            "entry_score": 100.0,
            "gap_ratio": 0.0,
        }
        conditions: Dict[str, bool] = {}

        rsi = self.calculate_rsi(code, rsi_period)
        metrics["rsi"] = float(rsi)
        conditions["rsi"] = (not use_rsi) or (rsi < rsi_upper)
        if use_rsi and not conditions["rsi"]:
            log_once("rsi", f"[{info.get('name', code)}] RSI {rsi:.1f} >= {rsi_upper:.0f} (과매수) 진입 보류")

        avg_volume = float(info.get("avg_volume_20", 0) or info.get("avg_volume_5", 0) or 0)
        current_volume = float(info.get("current_volume", 0) or 0)
        conditions["volume"] = (not use_volume) or (avg_volume <= 0) or (current_volume / avg_volume >= volume_mult)

        avg_value = float(info.get("avg_value_20", 0) or 0)
        conditions["liquidity"] = (not use_liquidity) or (avg_value <= 0) or (avg_value >= min_value)
        if use_liquidity and not conditions["liquidity"]:
            log_once(
                "liquidity",
                f"[{info.get('name', code)}] 유동성 부족: 평균 거래대금 {avg_value:,.0f}원 < 기준 {min_value:,.0f}원",
            )

        ask = float(info.get("ask_price", 0) or 0)
        bid = float(info.get("bid_price", 0) or 0)
        if ask > 0 and bid > 0 and (ask + bid) > 0:
            mid = (ask + bid) / 2.0
            spread_pct = (ask - bid) / mid * 100.0
        else:
            spread_pct = 0.0
        metrics["spread_pct"] = spread_pct
        conditions["spread"] = (not use_spread) or (spread_pct <= 0) or (spread_pct <= max_spread)
        if use_spread and not conditions["spread"]:
            log_once("spread", f"[{info.get('name', code)}] 스프레드 {spread_pct:.2f}% > {max_spread:.2f}% 진입 보류")

        if len(prices) >= 30:
            macd, signal, _ = self.calculate_macd(prices)
        else:
            macd, signal = 0.0, 0.0
        metrics["macd"] = float(macd)
        metrics["macd_signal"] = float(signal)
        conditions["macd"] = (not use_macd) or (len(prices) < 30) or (macd > signal)
        if use_macd and not conditions["macd"]:
            log_once("macd", f"[{info.get('name', code)}] MACD {macd:.2f} <= Signal {signal:.2f} 진입 보류")

        if len(prices) >= 20 and current > 0:
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger(prices, k=bb_k)
        else:
            bb_upper, bb_middle, bb_lower = 0.0, 0.0, 0.0
        metrics["bb_upper"] = float(bb_upper)
        metrics["bb_middle"] = float(bb_middle)
        metrics["bb_lower"] = float(bb_lower)
        conditions["bollinger"] = (not use_bb) or (bb_upper <= 0) or (current < bb_upper)
        if use_bb and not conditions["bollinger"]:
            log_once("bb", f"[{info.get('name', code)}] 볼린저 상단 돌파 ({int(current):,} >= {bb_upper:,.0f}) 진입 보류")

        if len(high_list) >= 20:
            p_di, m_di, adx = self.calculate_dmi(high_list, low_list, prices)
        else:
            p_di, m_di, adx = 0.0, 0.0, 0.0
        metrics["dmi_pdi"] = float(p_di)
        metrics["dmi_mdi"] = float(m_di)
        metrics["dmi_adx"] = float(adx)
        conditions["dmi"] = (not use_dmi) or (len(high_list) < 20) or (p_di > m_di and adx >= adx_threshold)

        if use_stoch_rsi:
            stoch_k, stoch_d = self.calculate_stochastic_rsi(code)
        else:
            stoch_k, stoch_d = 50.0, 50.0
        metrics["stoch_k"] = float(stoch_k)
        metrics["stoch_d"] = float(stoch_d)
        conditions["stoch_rsi"] = (not use_stoch_rsi) or (stoch_k < stoch_upper)
        if use_stoch_rsi and not conditions["stoch_rsi"]:
            log_once("stoch", f"[{info.get('name', code)}] StochRSI K={stoch_k:.1f} >= {stoch_upper:.0f} (과매수) 진입 보류")

        daily_trend = self._get_trend(daily_prices, 20)
        minute_trend = self._get_trend(minute_prices, 10)
        conditions["mtf"] = (not use_mtf) or (daily_trend == "up" and minute_trend == "up")
        if use_mtf and not conditions["mtf"]:
            log_once("mtf", f"[{info.get('name', code)}] MTF 불일치: 일봉={daily_trend}, 분봉={minute_trend}")

        if use_gap:
            gap_type, gap_ratio = self.analyze_gap(code)
        else:
            gap_type, gap_ratio = "no_gap", 0.0
        metrics["gap_ratio"] = float(gap_ratio)
        conditions["gap"] = (not use_gap) or not (gap_type == "gap_up" and gap_ratio > 5.0)

        conditions["market_div"] = self.check_market_diversification(code)
        conditions["sector"] = self.check_sector_limit(code)

        ma_signal = self.check_ma_crossover(code)
        conditions["ma_cross"] = ma_signal != "dead"

        if use_entry_scoring:
            scores: Dict[str, int] = {}
            scores["target_break"] = Config.ENTRY_WEIGHTS.get("target_break", 20) if target > 0 and current >= target else 0

            if len(prices) >= 20:
                ma20 = sum(prices[-20:]) / 20
                ma5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else current
                scores["ma_filter"] = Config.ENTRY_WEIGHTS.get("ma_filter", 15) if current > ma20 and ma5 > ma20 else 0
            else:
                scores["ma_filter"] = Config.ENTRY_WEIGHTS.get("ma_filter", 15) // 2

            if 30 <= rsi <= 60:
                scores["rsi_optimal"] = Config.ENTRY_WEIGHTS.get("rsi_optimal", 20)
            elif rsi < 70:
                scores["rsi_optimal"] = Config.ENTRY_WEIGHTS.get("rsi_optimal", 20) // 2
            else:
                scores["rsi_optimal"] = 0

            scores["macd_golden"] = Config.ENTRY_WEIGHTS.get("macd_golden", 20) if macd > signal else 0

            avg_volume_5 = float(info.get("avg_volume_5", 0) or 0)
            if avg_volume_5 > 0 and current_volume >= avg_volume_5 * 1.2:
                scores["volume_confirm"] = Config.ENTRY_WEIGHTS.get("volume_confirm", 15)
            elif avg_volume_5 > 0 and current_volume >= avg_volume_5:
                scores["volume_confirm"] = Config.ENTRY_WEIGHTS.get("volume_confirm", 15) // 2
            else:
                scores["volume_confirm"] = 0

            if bb_upper > 0 and bb_lower <= current <= bb_middle:
                scores["bb_position"] = Config.ENTRY_WEIGHTS.get("bb_position", 10)
            elif bb_upper > 0 and current < bb_lower:
                scores["bb_position"] = Config.ENTRY_WEIGHTS.get("bb_position", 10) // 2
            else:
                scores["bb_position"] = 0

            entry_score = sum(scores.values())
            metrics["entry_score"] = float(entry_score)
            conditions["entry_score"] = entry_score >= entry_threshold
            if not conditions["entry_score"]:
                log_once(
                    "entry_score",
                    f"[{info.get('name', code)}] 진입점수 {entry_score}/{entry_threshold} 미달: {scores}",
                )
        else:
            conditions["entry_score"] = True
            metrics["entry_score"] = 100.0

        result = (all(conditions.values()), conditions, metrics)
        self._decision_cache[code] = {"ts": now_ts, "result": result}
        return result

    def check_all_buy_conditions(self, code) -> Tuple[bool, Dict[str, bool]]:
        """모든 매수 조건 확인 (하위호환 래퍼)."""
        passed, conditions, _ = self.evaluate_buy_conditions(code)
        return passed, conditions
    
    def reset_tracking(self):
        """추적 데이터 초기화"""
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.sector_investments.clear()
        self.market_investments = {'kospi': 0, 'kosdaq': 0}
        self._decision_cache.clear()

