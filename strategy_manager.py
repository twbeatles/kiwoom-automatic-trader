from config import Config

class StrategyManager:
    """매매 전략 로직 분리"""
    def __init__(self, trader):
        self.trader = trader

    def log(self, msg):
        self.trader.log(msg)

    # ------------------------------------------------------------------
    # RSI 계산 및 체크
    # ------------------------------------------------------------------
    def calculate_rsi(self, code, period=14):
        """RSI 계산 (종목별 저장된 가격 데이터 기반)"""
        if code not in self.trader.universe:
            return 50  # 기본값
        
        info = self.trader.universe[code]
        prices = info.get('price_history', [])
        
        if len(prices) < period + 1:
            return 50  # 데이터 부족
        
        # 가격 변화 계산
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

    def check_macd_condition(self, code):
        """MACD 조건 확인"""
        if not hasattr(self.trader, 'chk_use_macd') or not self.trader.chk_use_macd.isChecked():
            return True
        
        prices = self.trader.price_history.get(code, [])
        if len(prices) < 30:
            return True
        
        macd, signal, _ = self.calculate_macd(prices)
        if macd <= signal:
            self.log(f"[{self.trader.universe.get(code, {}).get('name', code)}] MACD {macd:.2f} <= Signal {signal:.2f} 진입 보류")
            return False
        return True

    # ------------------------------------------------------------------
    # 볼린저 밴드 체크
    # ------------------------------------------------------------------
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
        """볼린저 밴드 조건 확인"""
        if not hasattr(self.trader, 'chk_use_bb') or not self.trader.chk_use_bb.isChecked():
            return True
        
        prices = self.trader.universe.get(code, {}).get('price_history', [])
        current_price = self.trader.universe.get(code, {}).get('current', 0)
        
        if len(prices) < 20 or current_price == 0:
            return True
            
        k = self.trader.spin_bb_k.value()
        _, _, lower = self.calculate_bollinger(prices, k=k)
        
        # 밴드 하단보다 현재가가 낮으면(돌파) 매수 간주
        if current_price > lower:
            # self.log(f"[{code}] BB 하단 미달")
            return False
            
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
            # self.log(f"[{code}] P-DI({p_di:.1f}) <= M-DI({m_di:.1f})")
            return False
            
        # 조건 2: ADX 기준
        threshold = self.trader.spin_adx.value()
        if adx < threshold:
            # self.log(f"[{code}] ADX({adx:.1f}) < {threshold}")
            return False
            
        return True
