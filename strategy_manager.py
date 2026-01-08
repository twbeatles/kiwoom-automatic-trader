"""
Strategy Manager for Kiwoom Pro Algo-Trader
매매 전략 로직 및 기술적 지표 계산
"""

from typing import Optional, Tuple, List, Dict, Any
from config import Config

# ============================================================================
# 상수 정의 (매직 넘버 제거)
# ============================================================================
DEFAULT_RSI_VALUE = 50          # 데이터 부족 시 기본 RSI
DEFAULT_RSI_PERIOD = 14         # RSI 기본 기간
DEFAULT_BB_PERIOD = 20          # 볼린저밴드 기본 기간
DEFAULT_BB_K = 2.0              # 볼린저밴드 표준편차 배수
DEFAULT_ATR_PERIOD = 14         # ATR 기본 기간
DEFAULT_DMI_PERIOD = 14         # DMI 기본 기간
MIN_DATA_POINTS = 15            # 최소 데이터 포인트
GOLDEN_CROSS = 'golden'
DEAD_CROSS = 'dead'


class StrategyManager:
    """매매 전략 로직 분리"""
    
    def __init__(self, trader):
        self.trader = trader

    def log(self, msg):
        self.trader.log(msg)

    # ------------------------------------------------------------------
    # RSI 계산 및 체크
    # ------------------------------------------------------------------
    def calculate_rsi(self, code: str, period: int = DEFAULT_RSI_PERIOD) -> float:
        """
        RSI 계산 (종목별 저장된 가격 데이터 기반)
        
        Args:
            code: 종목코드
            period: RSI 기간 (기본 14)
        
        Returns:
            RSI 값 (0-100)
        """
        if code not in self.trader.universe:
            return DEFAULT_RSI_VALUE
        
        info = self.trader.universe[code]
        prices = info.get('price_history', [])
        
        # 데이터 유효성 검사
        if not prices or len(prices) < period + 1:
            return DEFAULT_RSI_VALUE
        
        if period <= 0:
            return DEFAULT_RSI_VALUE
        
        # 가격 변화 계산
        gains = []
        losses = []
        
        try:
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
            
            # 0 나누기 방지
            if avg_loss == 0:
                return 100.0 if avg_gain > 0 else DEFAULT_RSI_VALUE
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return max(0.0, min(100.0, rsi))  # 범위 제한
        
        except (IndexError, ZeroDivisionError, TypeError) as e:
            self.log(f"RSI 계산 오류 ({code}): {e}")
            return DEFAULT_RSI_VALUE
    
    def check_rsi_condition(self, code):
        """RSI 조건 확인"""
        if not self.trader.chk_use_rsi.isChecked():
            return True
        
        rsi = self.calculate_rsi(code, self.trader.spin_rsi_period.value())
        upper_limit = self.trader.spin_rsi_upper.value()
        
        if rsi >= upper_limit:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] RSI {rsi:.1f} >= {upper_limit} (과매수) 진입 보류")
            return False
        
        return True

    # ------------------------------------------------------------------
    # 거래량 체크
    # ------------------------------------------------------------------
    def check_volume_condition(self, code):
        """거래량 조건 확인"""
        if not self.trader.chk_use_volume.isChecked():
            return True
        
        if code not in self.trader.universe:
            return True
        
        info = self.trader.universe[code]
        current_volume = info.get('current_volume', 0)
        avg_volume = info.get('avg_volume_5', 0)
        
        if avg_volume == 0:
            return True
        
        required_mult = self.trader.spin_volume_mult.value()
        actual_mult = current_volume / avg_volume
        
        if actual_mult < required_mult:
            return False
        
        return True

    # ------------------------------------------------------------------
    # MACD 계산 및 체크
    # ------------------------------------------------------------------
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

    def check_macd_condition(self, code: str) -> bool:
        """MACD 조건 확인"""
        # UI 위젯이 없으면 기본값 반환
        chk_use_macd = getattr(self.trader, 'chk_use_macd', None)
        if chk_use_macd is None or not chk_use_macd.isChecked():
            return True
        
        prices = self.trader.price_history.get(code, [])
        if len(prices) < 30:
            return True
        
        try:
            macd, signal, _ = self.calculate_macd(prices)
            if macd <= signal:
                name = self.trader.universe.get(code, {}).get('name', code)
                self.log(f"[{name}] MACD {macd:.2f} <= Signal {signal:.2f} 진입 보류")
                return False
        except Exception as e:
            self.log(f"MACD 조건 확인 오류 ({code}): {e}")
        return True

    # ------------------------------------------------------------------
    # 볼린저 밴드 체크
    # ------------------------------------------------------------------
    def calculate_bollinger(self, prices: List[float], k: float = DEFAULT_BB_K, 
                           period: int = DEFAULT_BB_PERIOD) -> Tuple[float, float, float]:
        """
        볼린저 밴드 계산
        
        Args:
            prices: 가격 리스트
            k: 표준편차 배수 (기본 2.0)
            period: 기간 (기본 20)
        
        Returns:
            (upper, middle, lower) 밴드 값
        """
        if not prices or len(prices) < period or period <= 0:
            return 0.0, 0.0, 0.0
        
        try:
            subset = prices[-period:]
            avg = sum(subset) / period
            variance = sum((x - avg) ** 2 for x in subset) / period
            std_dev = variance ** 0.5
            
            upper = avg + (std_dev * k)
            lower = avg - (std_dev * k)
            return upper, avg, lower
        except (TypeError, ZeroDivisionError) as e:
            return 0.0, 0.0, 0.0

    def check_bollinger_condition(self, code: str) -> bool:
        """볼린저 밴드 조건 확인"""
        chk_use_bb = getattr(self.trader, 'chk_use_bb', None)
        if chk_use_bb is None or not chk_use_bb.isChecked():
            return True
        
        info = self.trader.universe.get(code, {})
        prices = info.get('price_history', [])
        current_price = info.get('current', 0)
        
        if len(prices) < DEFAULT_BB_PERIOD or current_price <= 0:
            return True
        
        try:
            spin_bb_k = getattr(self.trader, 'spin_bb_k', None)
            k = spin_bb_k.value() if spin_bb_k else DEFAULT_BB_K
            _, _, lower = self.calculate_bollinger(prices, k=k)
            
            # 밴드 하단보다 현재가가 낮으면(돌파) 매수 간주
            if current_price > lower:
                return False
        except Exception:
            pass
        
        return True

    # ------------------------------------------------------------------
    # ATR 및 DMI 체크
    # ------------------------------------------------------------------
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
            
        # Simple SMA for ATR
        atr = sum(tr_list[-period:]) / period
        return atr

    def calculate_dmi(self, high_list, low_list, close_list, period=14):
        """DMI(P-DI, M-DI, ADX) 계산"""
        if len(high_list) < period + 1:
            return 0, 0, 0
            
        # 1. TR, DM+ , DM- 계산
        tr_list = []
        p_dm_list = []
        m_dm_list = []
        
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i-1]
            
            # TR = Max(|High-Low|, |High-PrevClose|, |Low-PrevClose|)
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
            
            # DM
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
        
        # 2. Smooth Values (Wilder's Smoothing usually, but here simple SMA or EMA for simplicity)
        # Using simple SMA for period
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
        adx = dx # For strict ADX, need smoothing of DX. Here using simple DX for approximation.
        
        return p_di, m_di, adx

    def check_dmi_condition(self, code):
        """DMI/ADX 조건 확인"""
        if not hasattr(self.trader, 'chk_use_dmi') or not self.trader.chk_use_dmi.isChecked():
            return True
            
        info = self.trader.universe.get(code, {})
        high_list = info.get('high_history', [])
        low_list = info.get('low_history', [])
        close_list = info.get('price_history', [])
        
        if len(high_list) < 20:
            return True
            
        p_di, m_di, adx = self.calculate_dmi(high_list, low_list, close_list)
        
        # 조건 1: P-DI > M-DI (상승 추세)
        if p_di <= m_di:
            return False
            
        # 조건 2: ADX 기준
        threshold = self.trader.spin_adx.value()
        if adx < threshold:
            return False
            
        return True

    # ------------------------------------------------------------------
    # 이동평균 크로스오버 (신규)
    # ------------------------------------------------------------------
    def calculate_ma(self, prices, period, ma_type='SMA'):
        """이동평균 계산
        Args:
            prices: 가격 리스트
            period: 기간
            ma_type: 'SMA' 또는 'EMA'
        """
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
        """이동평균 골든크로스/데드크로스 확인
        Returns:
            'golden': 골든크로스 (매수 신호)
            'dead': 데드크로스 (매도 신호)
            None: 신호 없음
        """
        if not hasattr(self.trader, 'chk_use_ma') or not self.trader.chk_use_ma.isChecked():
            return None
            
        info = self.trader.universe.get(code, {})
        prices = info.get('price_history', [])
        
        if len(prices) < long_period + 2:
            return None
        
        # 현재와 이전 MA 계산
        short_ma_now = self.calculate_ma(prices, short_period)
        long_ma_now = self.calculate_ma(prices, long_period)
        short_ma_prev = self.calculate_ma(prices[:-1], short_period)
        long_ma_prev = self.calculate_ma(prices[:-1], long_period)
        
        if None in [short_ma_now, long_ma_now, short_ma_prev, long_ma_prev]:
            return None
        
        # 골든크로스: 단기MA가 장기MA를 상향 돌파
        if short_ma_prev <= long_ma_prev and short_ma_now > long_ma_now:
            self.log(f"[{info.get('name', code)}] 🌟 골든크로스 발생 (MA{short_period}>{long_period})")
            return 'golden'
        
        # 데드크로스: 단기MA가 장기MA를 하향 돌파
        if short_ma_prev >= long_ma_prev and short_ma_now < long_ma_now:
            self.log(f"[{info.get('name', code)}] ☠️ 데드크로스 발생 (MA{short_period}<{long_period})")
            return 'dead'
        
        return None

    # ------------------------------------------------------------------
    # ATR 기반 포지션 사이징 (신규)
    # ------------------------------------------------------------------
    def calculate_position_size(self, code, risk_percent=1.0, atr_multiplier=2.0):
        """ATR 기반 포지션 크기 계산
        Args:
            code: 종목코드
            risk_percent: 계좌 대비 위험 비율 (%)
            atr_multiplier: ATR 배수 (손절폭)
        Returns:
            적정 수량
        """
        info = self.trader.universe.get(code, {})
        high_list = info.get('high_history', [])
        low_list = info.get('low_history', [])
        close_list = info.get('price_history', [])
        
        if len(high_list) < 15 or len(low_list) < 15 or len(close_list) < 15:
            # 데이터 부족시 기본 계산
            return self._default_position_size(code)
        
        atr = self.calculate_atr(high_list, low_list, close_list, period=14)
        if atr <= 0:
            return self._default_position_size(code)
        
        current_price = info.get('current', 0)
        if current_price <= 0:
            return 0
        
        # 손절폭 = ATR * 배수
        stop_loss_amount = atr * atr_multiplier
        
        # 위험 금액 = 예수금 * 위험비율%
        risk_amount = self.trader.deposit * (risk_percent / 100)
        
        # 적정 수량 = 위험금액 / 손절폭
        if stop_loss_amount > 0:
            position_size = int(risk_amount / stop_loss_amount)
        else:
            position_size = 0
        
        # 최대 투자금 제한 적용
        max_invest = self.trader.deposit * (self.trader.spin_betting.value() / 100)
        max_quantity = int(max_invest / current_price) if current_price > 0 else 0
        
        final_size = min(position_size, max_quantity)
        
        if final_size > 0:
            self.log(f"[{info.get('name', code)}] ATR 사이징: ATR={atr:.0f}, 적정수량={final_size}주")
        
        return max(1, final_size)
    
    def _default_position_size(self, code):
        """기본 포지션 크기 계산 (ATR 데이터 부족시)"""
        info = self.trader.universe.get(code, {})
        current_price = info.get('current', 0)
        if current_price <= 0:
            return 0
        
        invest_amount = self.trader.deposit * (self.trader.spin_betting.value() / 100)
        return max(1, int(invest_amount / current_price))

    # ------------------------------------------------------------------
    # 시간대별 전략 파라미터 (신규)
    # ------------------------------------------------------------------
    def get_time_based_k_value(self):
        """시간대별 K값 반환
        - 09:00-09:30: 공격적 (K * 1.4)
        - 09:30-14:30: 기본 (K * 1.0)
        - 14:30-15:20: 보수적 (K * 0.6)
        """
        import datetime
        now = datetime.datetime.now()
        hour, minute = now.hour, now.minute
        time_val = hour * 60 + minute
        
        base_k = self.trader.spin_k.value()
        
        # 시간대별 조정
        if time_val < 9 * 60 + 30:  # 09:00-09:30 (공격적)
            adjusted_k = base_k * 1.4
            phase = "공격적"
        elif time_val < 14 * 60 + 30:  # 09:30-14:30 (기본)
            adjusted_k = base_k * 1.0
            phase = "기본"
        else:  # 14:30-15:20 (보수적)
            adjusted_k = base_k * 0.6
            phase = "보수적"
        
        return adjusted_k, phase
    
    def calculate_target_price(self, code):
        """시간대 적용 목표가 계산"""
        info = self.trader.universe.get(code, {})
        prev_high = info.get('high', 0)
        prev_low = info.get('low', 0)
        today_open = info.get('open', 0)
        
        if prev_high == 0 or prev_low == 0 or today_open == 0:
            return 0
        
        # 시간대별 K값 적용
        if hasattr(self.trader, 'chk_use_time_strategy') and self.trader.chk_use_time_strategy.isChecked():
            k_value, phase = self.get_time_based_k_value()
        else:
            k_value = self.trader.spin_k.value()
            phase = "기본"
        
        target = today_open + (prev_high - prev_low) * k_value
        
        return target

    # ------------------------------------------------------------------
    # 분할 매수/매도 (신규)
    # ------------------------------------------------------------------
    def get_split_orders(self, total_quantity, current_price, order_type='buy'):
        """분할 주문 생성
        Args:
            total_quantity: 총 수량
            current_price: 현재가
            order_type: 'buy' 또는 'sell'
        Returns:
            [(수량, 가격), ...] 리스트
        """
        if not hasattr(self.trader, 'chk_use_split') or not self.trader.chk_use_split.isChecked():
            return [(total_quantity, current_price)]
        
        split_count = getattr(self.trader, 'spin_split_count', None)
        split_count = split_count.value() if split_count else 3
        
        split_percent = getattr(self.trader, 'spin_split_percent', None)
        split_percent = split_percent.value() if split_percent else 0.5
        
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
            
            # 가격 조정
            if order_type == 'buy':
                price_adj = 1 - (split_percent / 100) * i
            else:
                price_adj = 1 + (split_percent / 100) * i
            
            adjusted_price = int(current_price * price_adj)
            orders.append((qty, adjusted_price))
        
        return orders

    # ------------------------------------------------------------------
    # 종합 매수 조건 체크
    # ------------------------------------------------------------------
    def check_all_buy_conditions(self, code):
        """모든 매수 조건 확인"""
        conditions = {
            'rsi': self.check_rsi_condition(code),
            'volume': self.check_volume_condition(code),
            'macd': self.check_macd_condition(code),
            'bollinger': self.check_bollinger_condition(code),
            'dmi': self.check_dmi_condition(code),
        }
        
        # MA 크로스오버 체크 (골든크로스만 매수)
        ma_signal = self.check_ma_crossover(code)
        if ma_signal == 'dead':
            conditions['ma_cross'] = False
        else:
            conditions['ma_cross'] = True
        
        return all(conditions.values()), conditions

