import datetime
import time
from typing import Dict, Optional, Tuple

from config import Config
from strategies import StrategyContext


class StrategyManagerEvaluationMixin:
    def _evaluate_with_strategy_pack(
        self,
        code: str,
        now_ts: float,
    ) -> Optional[Tuple[bool, Dict[str, bool], Dict[str, float]]]:
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
                    "daily_realized_profit": float(
                        getattr(self.trader, "daily_realized_profit", getattr(self.trader, "total_realized_profit", 0))
                    ),
                    "daily_initial_deposit": float(
                        getattr(self.trader, "daily_initial_deposit", getattr(self.trader, "initial_deposit", 0))
                    ),
                },
            )
            pack_result = self.pack_engine.evaluate(context)
            return pack_result.passed, dict(pack_result.conditions), dict(pack_result.metrics)
        except Exception as exc:
            self.log(f"[전략팩] 평가 실패, 레거시 엔진으로 폴백: {exc}")
            return None

    def evaluate_buy_conditions(
        self,
        code: str,
        now_ts: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, bool], Dict[str, float]]:
        now_ts = now_ts if now_ts is not None else time.time()
        cache_window_sec = Config.DECISION_CACHE_MS / 1000.0
        cache_item = self._decision_cache.get(code)
        if cache_item and (now_ts - cache_item.get("ts", 0.0)) < cache_window_sec:
            return cache_item["result"]

        pack_result = self._evaluate_with_strategy_pack(code, now_ts)
        if pack_result is not None:
            passed, conditions, metrics = pack_result
            for key in (
                "risk:shock_mode_guard",
                "risk:shock_guard",
                "risk:vi_guard",
                "risk:regime_guard",
                "risk:news_risk_guard",
                "risk:disclosure_event_guard",
                "risk:macro_regime_guard",
                "risk:liquidity_stress_guard",
                "risk:slippage_guard",
                "risk:order_health_guard",
                "filter:theme_heat_filter",
                "filter:intel_fresh_guard",
            ):
                conditions.setdefault(key, True)
            metrics.setdefault("shock_score", 0.0)
            metrics.setdefault("estimated_slippage_bps", 0.0)
            metrics.setdefault("guard_blocked", 0.0)
            metrics.setdefault("regime", 0.0)
            metrics.setdefault("news_score", 0.0)
            metrics.setdefault("theme_score", 0.0)
            metrics.setdefault("macro_score", 0.0)
            metrics.setdefault("headline_velocity", 0.0)
            normalized = (bool(passed), dict(conditions), dict(metrics))
            self._decision_cache[code] = {"ts": now_ts, "result": normalized}
            return normalized

        info = self.trader.universe.get(code, {})
        prices = info.get("price_history", [])
        high_list = info.get("high_history", [])
        low_list = info.get("low_history", [])
        daily_prices = info.get("daily_prices", prices)
        minute_prices = info.get("minute_prices", prices)
        current = float(info.get("current", 0) or 0)
        target = float(info.get("target", 0) or 0)

        def log_once(key: str, message: str):
            self.log_dedup(code, key, message, now_ts=now_ts)

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
            "shock_score": 0.0,
            "estimated_slippage_bps": 0.0,
            "guard_blocked": 0.0,
            "regime": 0.0,
            "atr_pct": 0.0,
            "news_score": 0.0,
            "theme_score": 0.0,
            "macro_score": 0.0,
            "headline_velocity": 0.0,
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
            macd, signal, _hist = self.calculate_macd(prices)
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

        market_intel = self.get_market_intel_snapshot(code, now_ts=now_ts)
        metrics["news_score"] = float(market_intel["news_score"])
        metrics["theme_score"] = float(market_intel["theme_score"])
        metrics["headline_velocity"] = float(market_intel["headline_velocity"])
        metrics["macro_score"] = {"risk_off": -1.0, "neutral": 0.0, "risk_on": 1.0}.get(
            str(market_intel["macro_regime"]),
            0.0,
        )
        news_guard_ok, _news_score = self.check_market_news_risk_guard(code, now_ts=now_ts)
        disclosure_guard_ok, _dart_risk = self.check_market_disclosure_event_guard(code, now_ts=now_ts)
        macro_guard_ok, _macro_regime = self.check_market_macro_regime_guard(code, now_ts=now_ts)
        theme_filter_ok, _theme_score = self.check_market_theme_heat_filter(code, now_ts=now_ts)
        intel_fresh_ok, _intel_age = self.check_market_intel_fresh_guard(code, now_ts=now_ts)
        market_intel_status = str(market_intel.get("status", "idle") or "idle")
        conditions["news_risk_guard"] = bool(news_guard_ok)
        conditions["disclosure_event_guard"] = bool(disclosure_guard_ok)
        conditions["macro_regime_guard"] = bool(macro_guard_ok)
        conditions["theme_heat_filter"] = bool(theme_filter_ok) if market_intel_status not in {"idle", "disabled"} else True
        conditions["intel_fresh_guard"] = bool(intel_fresh_ok) if market_intel_status not in {"idle", "disabled"} else True
        if market_intel["enabled"] and not conditions["news_risk_guard"]:
            log_once(
                "market_news_risk",
                f"[{info.get('name', code)}] 뉴스 점수 {market_intel['news_score']:+.0f}로 신규 진입 차단",
            )
        if market_intel["enabled"] and not conditions["disclosure_event_guard"]:
            log_once("market_disclosure_risk", f"[{info.get('name', code)}] 고위험 공시 감지로 신규 진입 차단")
        if market_intel["enabled"] and not conditions["macro_regime_guard"]:
            log_once(
                "market_macro_risk",
                f"[{info.get('name', code)}] risk_off 레짐과 악성 뉴스 조합으로 신규 진입 차단",
            )

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

        regime_name, regime_scale, atr_pct = self.get_regime_profile(code)
        metrics["atr_pct"] = float(atr_pct)
        metrics["regime"] = {"normal": 0.0, "elevated": 1.0, "extreme": 2.0}.get(regime_name, 0.0)

        spread_pct = float(metrics.get("spread_pct", 0.0) or 0.0)
        avg_slippage_bps = 0.0
        slip_series = getattr(self.trader, "_recent_slippage_bps", None)
        if slip_series:
            window = int(
                getattr(
                    cfg,
                    "slippage_window_trades",
                    getattr(Config, "DEFAULT_SLIPPAGE_WINDOW_TRADES", 20),
                )
            )
            samples = list(slip_series)[-max(1, window) :]
            if samples:
                avg_slippage_bps = sum(abs(float(v)) for v in samples) / len(samples)
        metrics["estimated_slippage_bps"] = float(avg_slippage_bps)

        shock_mode = str(getattr(self.trader, "_global_risk_mode", "normal"))
        shock_until = getattr(self.trader, "_global_risk_until", None)
        shock_active = shock_mode == "shock" and (
            not isinstance(shock_until, datetime.datetime) or datetime.datetime.now() < shock_until
        )
        metrics["shock_score"] = 1.0 if shock_active else 0.0
        conditions["shock_guard"] = not (bool(getattr(cfg, "use_shock_guard", True)) and shock_active)

        market_state = str(info.get("market_state", "normal") or "normal")
        conditions["vi_guard"] = not (
            bool(getattr(cfg, "use_vi_guard", True)) and market_state in {"vi", "halt", "reopen_cooldown"}
        )

        conditions["regime_guard"] = True

        if bool(getattr(cfg, "use_liquidity_stress_guard", True)):
            min_value = float(getattr(cfg, "min_avg_value", getattr(Config, "DEFAULT_MIN_AVG_VALUE", 1_000_000_000)))
            if min_value < 10_000_000:
                min_value *= 100_000_000
            ratio = float(getattr(cfg, "stress_min_value_ratio", getattr(Config, "DEFAULT_STRESS_MIN_VALUE_RATIO", 0.35)))
            stress_spread = float(getattr(cfg, "stress_spread_pct", getattr(Config, "DEFAULT_STRESS_SPREAD_PCT", 1.0)))
            liquidity_stress = spread_pct > stress_spread or (avg_value > 0 and avg_value < min_value * ratio)
            conditions["liquidity_stress_guard"] = not liquidity_stress
        else:
            conditions["liquidity_stress_guard"] = True

        max_slippage = float(getattr(cfg, "max_slippage_bps", getattr(Config, "DEFAULT_MAX_SLIPPAGE_BPS", 15.0)))
        conditions["slippage_guard"] = not (
            bool(getattr(cfg, "use_slippage_guard", True)) and avg_slippage_bps > max_slippage
        )

        order_health_mode = str(getattr(self.trader, "_order_health_mode", "normal"))
        order_health_until = getattr(self.trader, "_order_health_until", None)
        order_health_degraded = order_health_mode == "degraded" and (
            not isinstance(order_health_until, datetime.datetime) or datetime.datetime.now() < order_health_until
        )
        conditions["order_health_guard"] = not (
            bool(getattr(cfg, "use_order_health_guard", True)) and order_health_degraded
        )

        if not all(
            conditions.get(k, True)
            for k in (
                "shock_guard",
                "vi_guard",
                "news_risk_guard",
                "disclosure_event_guard",
                "macro_regime_guard",
                "liquidity_stress_guard",
                "slippage_guard",
                "order_health_guard",
            )
        ):
            metrics["guard_blocked"] = 1.0

        result = (all(conditions.values()), conditions, metrics)
        self._decision_cache[code] = {"ts": now_ts, "result": result}
        return result

    def check_all_buy_conditions(self, code) -> Tuple[bool, Dict[str, bool]]:
        passed, conditions, _metrics = self.evaluate_buy_conditions(code)
        return passed, conditions
