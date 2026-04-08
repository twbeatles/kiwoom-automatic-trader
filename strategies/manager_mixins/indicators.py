from typing import Tuple

from config import Config


class StrategyManagerIndicatorMixin:
    def calculate_atr_stop_loss(self, code, multiplier=2.0) -> float:
        info = self.trader.universe.get(code, {})
        current_price = info.get("current", 0)
        buy_price = info.get("buy_price", 0)

        if current_price <= 0 or buy_price <= 0:
            return 0

        high_list = info.get("high_history", [])
        low_list = info.get("low_history", [])
        close_list = info.get("price_history", [])

        atr = self.calculate_atr(high_list, low_list, close_list, period=14)
        if atr <= 0:
            loss_cut = self.config.loss_cut if self.config else self.trader.spin_loss.value()
            return buy_price * (1 - loss_cut / 100)

        stop_price = buy_price - (atr * multiplier)
        return max(0, stop_price)

    def check_atr_stop_loss(self, code) -> Tuple[bool, float]:
        if self.config:
            if not self.config.use_atr_stop:
                return False, 0
            mult = self.config.atr_mult
        else:
            if not hasattr(self.trader, "chk_use_atr_stop") or not self.trader.chk_use_atr_stop.isChecked():
                return False, 0
            multiplier = getattr(self.trader, "spin_atr_mult", None)
            mult = multiplier.value() if multiplier else 2.0

        info = self.trader.universe.get(code, {})
        current_price = info.get("current", 0)
        stop_price = self.calculate_atr_stop_loss(code, mult)

        if stop_price > 0 and current_price <= stop_price:
            self.log(f"[{info.get('name', code)}] ATR 손절 발동: 현재가 {current_price:,} <= 손절가 {stop_price:,.0f}")
            return True, stop_price

        return False, stop_price

    def calculate_rsi(self, code, period=14):
        if code not in self.trader.universe:
            return 50

        info = self.trader.universe[code]
        prices = info.get("price_history", [])

        if len(prices) < period + 1:
            return 50

        gains = []
        losses = []
        for i in range(1, period + 1):
            change = prices[-i] - prices[-(i + 1)]
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
        return 100 - (100 / (1 + rs))

    def check_rsi_condition(self, code):
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
        current_volume = info.get("current_volume", 0)
        avg_volume = info.get("avg_volume_20", 0) or info.get("avg_volume_5", 0)

        if avg_volume == 0:
            return True

        actual_mult = current_volume / avg_volume
        return actual_mult >= required_mult

    def check_liquidity_condition(self, code) -> bool:
        if self.config:
            if not self.config.use_liquidity:
                return True
            min_value = self.config.min_avg_value * 100_000_000
        else:
            if not hasattr(self.trader, "chk_use_liquidity") or not self.trader.chk_use_liquidity.isChecked():
                return True
            min_value = Config.DEFAULT_MIN_AVG_VALUE
            min_value_spin = getattr(self.trader, "spin_min_value", None)
            if min_value_spin:
                min_value = int(min_value_spin.value() * 100_000_000)

        info = self.trader.universe.get(code, {})
        avg_value = info.get("avg_value_20", 0)
        if avg_value <= 0:
            return True

        if avg_value < min_value:
            self.log(f"[{info.get('name', code)}] 유동성 부족: 평균 거래대금 {avg_value:,.0f}원 < 기준 {min_value:,.0f}원")
            return False

        return True

    def check_spread_condition(self, code) -> bool:
        if self.config:
            if not self.config.use_spread:
                return True
            max_spread = self.config.max_spread
        else:
            if not hasattr(self.trader, "chk_use_spread") or not self.trader.chk_use_spread.isChecked():
                return True
            max_spread_spin = getattr(self.trader, "spin_spread_max", None)
            max_spread = max_spread_spin.value() if max_spread_spin else Config.DEFAULT_MAX_SPREAD_PCT

        info = self.trader.universe.get(code, {})
        ask = info.get("ask_price", 0)
        bid = info.get("bid_price", 0)
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
        if self.config:
            if not self.config.use_macd:
                return True
        else:
            if not hasattr(self.trader, "chk_use_macd") or not self.trader.chk_use_macd.isChecked():
                return True

        info = self.trader.universe.get(code, {})
        prices = info.get("price_history", [])
        if len(prices) < 30:
            return True

        macd, signal, _hist = self.calculate_macd(prices)
        if macd <= signal:
            self.log(f"[{info.get('name', code)}] MACD {macd:.2f} <= Signal {signal:.2f} 진입 보류")
            return False
        return True

    def calculate_bollinger(self, prices, k=2.0, period=20):
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
        if self.config:
            if not self.config.use_bb:
                return True
            k = self.config.bb_k
        else:
            if not hasattr(self.trader, "chk_use_bb") or not self.trader.chk_use_bb.isChecked():
                return True
            k = self.trader.spin_bb_k.value()

        prices = self.trader.universe.get(code, {}).get("price_history", [])
        current_price = self.trader.universe.get(code, {}).get("current", 0)
        if len(prices) < 20 or current_price == 0:
            return True

        upper, _middle, _lower = self.calculate_bollinger(prices, k=k)
        if current_price >= upper:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] 볼린저 상단 돌파 ({current_price:,} >= {upper:,.0f}) 진입 보류")
            return False

        return True

    def calculate_atr(self, high_list, low_list, close_list, period=14):
        if len(high_list) < period + 1:
            return 0

        tr_list = []
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)

        if len(tr_list) < period:
            return 0

        atr = sum(tr_list[-period:]) / period
        return atr

    def calculate_dmi(self, high_list, low_list, close_list, period=14):
        if len(high_list) < period + 1:
            return 0, 0, 0

        tr_list = []
        p_dm_list = []
        m_dm_list = []
        for i in range(1, len(high_list)):
            h = high_list[i]
            l = low_list[i]
            prev_c = close_list[i - 1]

            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)

            prev_h = high_list[i - 1]
            prev_l = low_list[i - 1]
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
        if self.config:
            if not self.config.use_dmi:
                return True
            threshold = self.config.adx_threshold
        else:
            if not hasattr(self.trader, "chk_use_dmi") or not self.trader.chk_use_dmi.isChecked():
                return True
            threshold = self.trader.spin_adx.value()

        info = self.trader.universe.get(code, {})
        high_list = info.get("high_history", [])
        low_list = info.get("low_history", [])
        close_list = info.get("price_history", [])
        if len(high_list) < 20:
            return True

        p_di, m_di, adx = self.calculate_dmi(high_list, low_list, close_list)
        if p_di <= m_di:
            return False
        if adx < threshold:
            return False
        return True

    def calculate_ma(self, prices, period, ma_type="SMA"):
        if len(prices) < period:
            return None

        if ma_type == "SMA":
            return sum(prices[-period:]) / period
        if ma_type == "EMA":
            multiplier = 2 / (period + 1)
            ema = prices[0]
            for price in prices[1:]:
                ema = (price - ema) * multiplier + ema
            return ema
        return None

    def check_ma_crossover(self, code, short_period=5, long_period=20):
        if self.config:
            if not self.config.use_ma:
                return None
            short_period = self.config.ma_short
            long_period = self.config.ma_long
        else:
            if not hasattr(self.trader, "chk_use_ma") or not self.trader.chk_use_ma.isChecked():
                return None
            short_period = Config.DEFAULT_MA_SHORT

        info = self.trader.universe.get(code, {})
        prices = info.get("price_history", [])
        if len(prices) < long_period + 2:
            return None

        short_ma_now = self.calculate_ma(prices, short_period)
        long_ma_now = self.calculate_ma(prices, long_period)
        short_ma_prev = self.calculate_ma(prices[:-1], short_period)
        long_ma_prev = self.calculate_ma(prices[:-1], long_period)

        if (
            short_ma_now is None
            or long_ma_now is None
            or short_ma_prev is None
            or long_ma_prev is None
        ):
            return None

        if short_ma_prev <= long_ma_prev and short_ma_now > long_ma_now:
            self.log(f"[{info.get('name', code)}] 🌟 골든크로스 발생 (MA{short_period}>{long_period})")
            return "golden"
        if short_ma_prev >= long_ma_prev and short_ma_now < long_ma_now:
            self.log(f"[{info.get('name', code)}] ☠️ 데드크로스 발생 (MA{short_period}<{long_period})")
            return "dead"
        return None

    def get_regime_profile(self, code) -> Tuple[str, float, float]:
        info = self.trader.universe.get(code, {})
        current = float(info.get("current", 0) or 0)
        if current <= 0:
            return "normal", 1.0, 0.0

        high_list = info.get("high_history", [])
        low_list = info.get("low_history", [])
        close_list = info.get("price_history", [])
        if len(high_list) < 15 or len(low_list) < 15 or len(close_list) < 15:
            return "normal", 1.0, 0.0

        atr = float(self.calculate_atr(high_list, low_list, close_list, period=14) or 0)
        if atr <= 0:
            return "normal", 1.0, 0.0
        atr_pct = (atr / current) * 100.0

        cfg = self.config
        if cfg and bool(getattr(cfg, "use_regime_sizing", True)):
            elevated = float(
                getattr(cfg, "regime_elevated_atr_pct", getattr(Config, "DEFAULT_REGIME_ELEVATED_ATR_PCT", 2.5))
            )
            extreme = float(
                getattr(cfg, "regime_extreme_atr_pct", getattr(Config, "DEFAULT_REGIME_EXTREME_ATR_PCT", 4.0))
            )
            scale_elevated = float(
                getattr(
                    cfg,
                    "regime_size_scale_elevated",
                    getattr(Config, "DEFAULT_REGIME_SIZE_SCALE_ELEVATED", 0.7),
                )
            )
            scale_extreme = float(
                getattr(
                    cfg,
                    "regime_size_scale_extreme",
                    getattr(Config, "DEFAULT_REGIME_SIZE_SCALE_EXTREME", 0.4),
                )
            )
        else:
            elevated = float(getattr(Config, "DEFAULT_REGIME_ELEVATED_ATR_PCT", 2.5))
            extreme = float(getattr(Config, "DEFAULT_REGIME_EXTREME_ATR_PCT", 4.0))
            scale_elevated = float(getattr(Config, "DEFAULT_REGIME_SIZE_SCALE_ELEVATED", 0.7))
            scale_extreme = float(getattr(Config, "DEFAULT_REGIME_SIZE_SCALE_EXTREME", 0.4))

        if atr_pct >= extreme:
            return "extreme", max(0.1, scale_extreme), atr_pct
        if atr_pct >= elevated:
            return "elevated", max(0.1, scale_elevated), atr_pct
        return "normal", 1.0, atr_pct
