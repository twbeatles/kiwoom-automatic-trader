from typing import Dict, Optional, Tuple

from config import Config


class StrategyManagerSignalFilterMixin:
    def calculate_stochastic_rsi(
        self,
        code,
        rsi_period=14,
        stoch_period=14,
        k_period=3,
        d_period=3,
    ) -> Tuple[float, float]:
        if code not in self.trader.universe:
            return 50, 50

        info = self.trader.universe[code]
        prices = info.get("price_history", [])

        if len(prices) < rsi_period + stoch_period:
            return 50, 50

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

        stoch_k_values = []
        for i in range(len(rsi_values) - stoch_period + 1):
            window = rsi_values[i : i + stoch_period]
            min_rsi = min(window)
            max_rsi = max(window)
            if max_rsi - min_rsi > 0:
                stoch = (window[-1] - min_rsi) / (max_rsi - min_rsi) * 100
            else:
                stoch = 50
            stoch_k_values.append(stoch)

        if len(stoch_k_values) < k_period:
            return 50, 50

        k_value = sum(stoch_k_values[-k_period:]) / k_period

        if len(stoch_k_values) >= k_period + d_period - 1:
            k_smooth = []
            for i in range(d_period):
                idx = len(stoch_k_values) - d_period + i - k_period + 1
                if idx >= 0:
                    k_smooth.append(sum(stoch_k_values[idx : idx + k_period]) / k_period)
            d_value = sum(k_smooth) / len(k_smooth) if k_smooth else k_value
        else:
            d_value = k_value

        return k_value, d_value

    def _calculate_rsi_from_prices(self, prices, period):
        if len(prices) < period + 1:
            return 50

        gains = []
        losses = []
        for i in range(1, period + 1):
            change = prices[-i] - prices[-(i + 1)] if i + 1 <= len(prices) else 0
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
        if self.config:
            if not self.config.use_stoch_rsi:
                return True
            upper_limit = self.config.stoch_upper
        else:
            if not hasattr(self.trader, "chk_use_stoch_rsi") or not self.trader.chk_use_stoch_rsi.isChecked():
                return True
            upper = getattr(self.trader, "spin_stoch_upper", None)
            upper_limit = upper.value() if upper else 80

        k, _d = self.calculate_stochastic_rsi(code)

        if k >= upper_limit:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] StochRSI K={k:.1f} >= {upper_limit} (과매수) 진입 보류")
            return False

        return True

    def check_mtf_condition(self, code) -> bool:
        if self.config:
            if not self.config.use_mtf:
                return True
        else:
            if not hasattr(self.trader, "chk_use_mtf") or not self.trader.chk_use_mtf.isChecked():
                return True

        info = self.trader.universe.get(code, {})
        daily_prices = info.get("daily_prices", info.get("price_history", []))
        daily_trend = self._get_trend(daily_prices, 20)
        minute_prices = info.get("minute_prices", info.get("price_history", []))
        minute_trend = self._get_trend(minute_prices, 10)

        if daily_trend != "up" or minute_trend != "up":
            self.log(f"[{info.get('name', code)}] MTF 불일치: 일봉={daily_trend}, 분봉={minute_trend}")
            return False

        return True

    def _get_trend(self, prices, period) -> str:
        if len(prices) < period:
            return "neutral"

        short_ma = sum(prices[-5:]) / 5 if len(prices) >= 5 else prices[-1]
        long_ma = sum(prices[-period:]) / period
        current = prices[-1]

        if current > long_ma and short_ma > long_ma:
            return "up"
        if current < long_ma and short_ma < long_ma:
            return "down"
        return "neutral"

    def calculate_partial_take_profit(self, code, current_profit_rate: float) -> Optional[Dict]:
        if self.config:
            if not self.config.use_partial_profit:
                return None
        else:
            if not hasattr(self.trader, "chk_use_partial_profit") or not self.trader.chk_use_partial_profit.isChecked():
                return None

        info = self.trader.universe.get(code, {})
        executed_levels = info.get("partial_profit_levels", set())

        for i, level in enumerate(Config.PARTIAL_TAKE_PROFIT):
            if i not in executed_levels and current_profit_rate >= level["rate"]:
                return {
                    "sell_ratio": level["sell_ratio"],
                    "level": i,
                    "rate": level["rate"],
                }

        return None

    def mark_partial_profit_executed(self, code, level: int):
        if code in self.trader.universe:
            if "partial_profit_levels" not in self.trader.universe[code]:
                self.trader.universe[code]["partial_profit_levels"] = set()
            self.trader.universe[code]["partial_profit_levels"].add(level)

    def calculate_entry_score(self, code) -> Tuple[int, Dict[str, int]]:
        scores = {}
        info = self.trader.universe.get(code, {})
        prices = info.get("price_history", [])
        current = info.get("current", 0)
        target = info.get("target", 0)

        scores["target_break"] = Config.ENTRY_WEIGHTS.get("target_break", 20) if target > 0 and current >= target else 0

        if len(prices) >= 20:
            ma20 = sum(prices[-20:]) / 20
            ma5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else current
            scores["ma_filter"] = Config.ENTRY_WEIGHTS.get("ma_filter", 15) if current > ma20 and ma5 > ma20 else 0
        else:
            scores["ma_filter"] = Config.ENTRY_WEIGHTS.get("ma_filter", 15) // 2

        rsi = self.calculate_rsi(code, 14)
        if 30 <= rsi <= 60:
            scores["rsi_optimal"] = Config.ENTRY_WEIGHTS.get("rsi_optimal", 20)
        elif rsi < 70:
            scores["rsi_optimal"] = Config.ENTRY_WEIGHTS.get("rsi_optimal", 20) // 2
        else:
            scores["rsi_optimal"] = 0

        macd, signal, _hist = self.calculate_macd(prices)
        scores["macd_golden"] = Config.ENTRY_WEIGHTS.get("macd_golden", 20) if macd > signal else 0

        current_volume = info.get("current_volume", 0)
        avg_volume = info.get("avg_volume_5", 0)
        if avg_volume > 0 and current_volume >= avg_volume * 1.2:
            scores["volume_confirm"] = Config.ENTRY_WEIGHTS.get("volume_confirm", 15)
        elif avg_volume > 0 and current_volume >= avg_volume:
            scores["volume_confirm"] = Config.ENTRY_WEIGHTS.get("volume_confirm", 15) // 2
        else:
            scores["volume_confirm"] = 0

        if len(prices) >= 20:
            upper, middle, lower = self.calculate_bollinger(prices)
            if lower <= current <= middle:
                scores["bb_position"] = Config.ENTRY_WEIGHTS.get("bb_position", 10)
            elif current < lower:
                scores["bb_position"] = Config.ENTRY_WEIGHTS.get("bb_position", 10) // 2
            else:
                scores["bb_position"] = 0
        else:
            scores["bb_position"] = 0

        total = sum(scores.values())
        return total, scores

    def check_entry_score_condition(self, code) -> Tuple[bool, int]:
        if self.config:
            if not self.config.use_entry_scoring:
                return True, 100
            threshold = int(self.config.entry_score_threshold)
        else:
            use_entry = hasattr(self.trader, "chk_use_entry_score") and self.trader.chk_use_entry_score.isChecked()
            if not use_entry:
                return True, 100
            threshold_spin = getattr(self.trader, "spin_entry_score_threshold", None)
            threshold = int(threshold_spin.value()) if threshold_spin else Config.ENTRY_SCORE_THRESHOLD

        total, details = self.calculate_entry_score(code)

        if total < threshold:
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] 진입점수 {total}/{threshold} 미달: {details}")
            return False, total

        return True, total

    def analyze_gap(self, code) -> Tuple[str, float]:
        info = self.trader.universe.get(code, {})
        today_open = info.get("open", 0)
        prev_close = info.get("prev_close", 0)

        if prev_close == 0 or today_open == 0:
            return "no_gap", 0

        gap_ratio = (today_open - prev_close) / prev_close * 100
        gap_threshold = getattr(Config, "GAP_THRESHOLD", 2.0)

        if gap_ratio >= gap_threshold:
            return "gap_up", gap_ratio
        if gap_ratio <= -gap_threshold:
            return "gap_down", gap_ratio
        return "no_gap", gap_ratio

    def check_gap_condition(self, code) -> bool:
        if self.config:
            if not self.config.use_gap:
                return True
        else:
            if not hasattr(self.trader, "chk_use_gap") or not self.trader.chk_use_gap.isChecked():
                return True

        gap_type, gap_ratio = self.analyze_gap(code)

        if gap_type == "gap_up":
            info = self.trader.universe.get(code, {})
            self.log(f"[{info.get('name', code)}] ⚡ 갭상승 {gap_ratio:.1f}% 감지 - 보수적 진입")
            if gap_ratio > 5.0:
                return False

        return True

    def get_gap_adjusted_k(self, code) -> float:
        if self.config:
            base_k = self.config.k_value
        else:
            base_k = self.trader.spin_k.value()

        gap_type, gap_ratio = self.analyze_gap(code)

        if gap_type == "gap_up":
            adjustment = min(0.2, gap_ratio / 100)
            return max(0.2, base_k - adjustment)
        if gap_type == "gap_down":
            adjustment = min(0.15, abs(gap_ratio) / 100)
            return min(0.8, base_k + adjustment)

        return base_k
