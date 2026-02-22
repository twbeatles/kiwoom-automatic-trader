"""Modular strategy pack orchestrator.

This engine is intentionally lightweight and delegates indicator math to
`StrategyManager` helper methods where possible.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .types import Signal, SignalDirection, StrategyContext, StrategyResult


class StrategyPackEngine:
    def __init__(self, manager: Any):
        self.manager = manager

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config
        info = context.info
        prices = info.get("price_history", [])
        current = float(info.get("current", 0) or 0)
        target = float(info.get("target", 0) or 0)

        pack = getattr(cfg, "strategy_pack", None) or {}
        primary = str(pack.get("primary_strategy", "volatility_breakout"))
        entry_filters = list(pack.get("entry_filters", []))
        risk_overlays = list(pack.get("risk_overlays", []))

        conditions: Dict[str, bool] = {}
        metrics: Dict[str, float] = {
            "current": current,
            "target": target,
            "entry_score": 100.0,
        }
        signals: List[Signal] = []

        primary_passed, primary_dir, primary_strength = self._evaluate_primary(primary, context)
        conditions[f"primary:{primary}"] = primary_passed
        signals.append(
            Signal(
                strategy_id=primary,
                direction=primary_dir,
                strength=primary_strength,
                metadata={"pack": "primary"},
            )
        )

        for f_name in entry_filters:
            passed, metric_value = self._evaluate_filter(str(f_name), context)
            conditions[f"filter:{f_name}"] = passed
            if metric_value is not None:
                metrics[f"filter:{f_name}"] = float(metric_value)

        for overlay in risk_overlays:
            passed = self._evaluate_risk_overlay(str(overlay), context)
            conditions[f"risk:{overlay}"] = passed

        if getattr(cfg, "use_entry_scoring", False):
            score_ok, score = self.manager.check_entry_score_condition(context.code)
            conditions["entry_score"] = bool(score_ok)
            metrics["entry_score"] = float(score)
        else:
            conditions["entry_score"] = True

        passed = all(conditions.values())
        reason = None if passed else "one_or_more_conditions_failed"
        return StrategyResult(
            passed=passed,
            conditions=conditions,
            metrics=metrics,
            signals=signals,
            reason=reason,
        )

    def _evaluate_primary(self, primary: str, context: StrategyContext) -> Tuple[bool, SignalDirection, float]:
        info = context.info
        prices = info.get("price_history", [])
        current = float(info.get("current", 0) or 0)
        target = float(info.get("target", 0) or 0)
        cfg = context.config

        if primary == "volatility_breakout":
            passed = target > 0 and current >= target
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 1.0 if passed else 0.0

        if primary == "ma_channel_trend":
            if len(prices) < max(20, getattr(cfg, "ma_long", 20)):
                return False, SignalDirection.FLAT, 0.0
            ma_short = self.manager.calculate_ma(prices, getattr(cfg, "ma_short", 5)) or 0
            ma_long = self.manager.calculate_ma(prices, getattr(cfg, "ma_long", 20)) or 0
            passed = current > ma_short > ma_long > 0
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.9 if passed else 0.0

        if primary == "orb_donchian_breakout":
            # Use rolling channel breakout as a proxy for ORB/Donchian.
            period = max(5, int(getattr(cfg, "strategy_params", {}).get("donchian_period", 20)))
            if len(prices) < period + 1:
                return False, SignalDirection.FLAT, 0.0
            channel_high = max(prices[-period - 1 : -1])
            passed = current > channel_high
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.85 if passed else 0.0

        if primary == "rsi_bollinger_reversion":
            rsi = self.manager.calculate_rsi(context.code, getattr(cfg, "rsi_period", 14))
            bb_upper, bb_mid, bb_lower = self.manager.calculate_bollinger(prices, k=getattr(cfg, "bb_k", 2.0))
            passed = bb_lower > 0 and current <= bb_mid and rsi <= 40
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.8 if passed else 0.0

        if primary == "dmi_trend_strength":
            passed = self.manager.check_dmi_condition(context.code)
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.8 if passed else 0.0

        if primary == "investor_program_flow":
            # Optional external pipeline can enrich these fields.
            investor_net = float(info.get("investor_net", 0) or 0)
            program_net = float(info.get("program_net", 0) or 0)
            passed = investor_net > 0 and program_net > 0
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.7 if passed else 0.0

        if primary == "time_series_momentum":
            lookback = max(20, int(getattr(cfg, "strategy_params", {}).get("momentum_lookback", 60)))
            if len(prices) < lookback:
                return False, SignalDirection.FLAT, 0.0
            ret = (prices[-1] / max(1e-8, prices[-lookback])) - 1.0
            passed = ret > 0
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, min(1.0, max(0.0, ret * 5))

        if primary == "cross_sectional_momentum":
            rs = float(info.get("relative_strength", 0) or 0)
            passed = rs >= 0.7
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, rs

        if primary == "pairs_trading_cointegration":
            z = float(info.get("spread_zscore", 0) or 0)
            if z <= -2.0:
                return True, SignalDirection.LONG, min(1.0, abs(z) / 4.0)
            if bool(getattr(cfg, "short_enabled", False)) and z >= 2.0:
                return True, SignalDirection.SHORT, min(1.0, abs(z) / 4.0)
            return False, SignalDirection.FLAT, 0.0

        if primary == "stat_arb_residual":
            rz = float(info.get("residual_zscore", 0) or 0)
            if rz <= -1.5:
                return True, SignalDirection.LONG, min(1.0, abs(rz) / 3.0)
            if bool(getattr(cfg, "short_enabled", False)) and rz >= 1.5:
                return True, SignalDirection.SHORT, min(1.0, abs(rz) / 3.0)
            return False, SignalDirection.FLAT, 0.0

        if primary == "ff5_factor_ls":
            factor_score = float(info.get("ff5_score", 0) or 0)
            if factor_score >= 0.5:
                return True, SignalDirection.LONG, min(1.0, factor_score)
            if bool(getattr(cfg, "short_enabled", False)) and factor_score <= -0.5:
                return True, SignalDirection.SHORT, min(1.0, abs(factor_score))
            return False, SignalDirection.FLAT, 0.0

        if primary == "quality_value_lowvol":
            score = float(info.get("qvl_score", 0) or 0)
            passed = score >= 0.4
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, min(1.0, max(0.0, score))

        if primary == "volatility_targeting_overlay":
            realized_vol = float(info.get("realized_vol", 0) or 0)
            target_vol = float(getattr(cfg, "strategy_params", {}).get("target_vol", 0.25))
            passed = realized_vol > 0 and realized_vol <= target_vol
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.6 if passed else 0.0

        if primary == "risk_parity_portfolio":
            inv_vol_weight = float(info.get("risk_parity_weight", 0) or 0)
            passed = inv_vol_weight > 0
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, min(1.0, inv_vol_weight)

        if primary == "execution_algo_twap_vwap_pov":
            participation = float(info.get("participation_rate", 0) or 0)
            passed = participation <= float(getattr(cfg, "strategy_params", {}).get("max_participation", 0.2))
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.5 if passed else 0.0

        if primary == "market_making_spread":
            ask = float(info.get("ask_price", 0) or 0)
            bid = float(info.get("bid_price", 0) or 0)
            if ask <= 0 or bid <= 0 or ask <= bid:
                return False, SignalDirection.FLAT, 0.0
            spread_pct = (ask - bid) / ((ask + bid) / 2.0) * 100.0
            low = float(getattr(cfg, "strategy_params", {}).get("mm_spread_low", 0.05))
            high = float(getattr(cfg, "strategy_params", {}).get("mm_spread_high", 0.5))
            passed = low <= spread_pct <= high
            return passed, SignalDirection.LONG if passed else SignalDirection.FLAT, 0.4 if passed else 0.0

        # Unknown strategy id -> fail closed.
        return False, SignalDirection.FLAT, 0.0

    def _evaluate_filter(self, name: str, context: StrategyContext) -> Tuple[bool, Optional[float]]:
        code = context.code
        info = context.info

        if name == "rsi":
            rsi = self.manager.calculate_rsi(code, getattr(context.config, "rsi_period", 14))
            return self.manager.check_rsi_condition(code), rsi

        if name == "volume":
            avg_volume = float(info.get("avg_volume_20", 0) or info.get("avg_volume_5", 0) or 0)
            cur_volume = float(info.get("current_volume", 0) or 0)
            mult = (cur_volume / avg_volume) if avg_volume > 0 else 0.0
            return self.manager.check_volume_condition(code), mult

        if name == "macd":
            # Avoid duplicate MACD computation; `check_macd_condition` already calculates it.
            return self.manager.check_macd_condition(code), None

        if name == "bollinger":
            return self.manager.check_bollinger_condition(code), None

        if name == "stoch_rsi":
            k, _ = self.manager.calculate_stochastic_rsi(code)
            return self.manager.check_stochastic_rsi_condition(code), k

        if name == "liquidity":
            avg_value = float(info.get("avg_value_20", 0) or 0)
            return self.manager.check_liquidity_condition(code), avg_value

        if name == "spread":
            ask = float(info.get("ask_price", 0) or 0)
            bid = float(info.get("bid_price", 0) or 0)
            spread = ((ask - bid) / ((ask + bid) / 2.0) * 100.0) if ask > 0 and bid > 0 else 0.0
            return self.manager.check_spread_condition(code), spread

        if name == "mtf":
            return self.manager.check_mtf_condition(code), None

        if name == "gap":
            _, gap_ratio = self.manager.analyze_gap(code)
            return self.manager.check_gap_condition(code), gap_ratio

        # Unknown filter is considered pass-through for forward compatibility.
        return True, None

    def _evaluate_risk_overlay(self, name: str, context: StrategyContext) -> bool:
        code = context.code
        cfg = context.config

        if name == "max_holdings":
            max_holdings = int(getattr(cfg, "max_holdings", 5))
            current_count = int(getattr(self.manager.trader, "_holding_or_pending_count", 0))
            return current_count < max_holdings

        if name == "market_limit":
            return self.manager.check_market_diversification(code)

        if name == "sector_limit":
            return self.manager.check_sector_limit(code)

        if name == "daily_loss_limit":
            trader = self.manager.trader
            if not getattr(cfg, "use_risk_mgmt", True):
                return True
            initial = float(
                context.portfolio_state.get(
                    "daily_initial_deposit",
                    getattr(trader, "daily_initial_deposit", getattr(trader, "initial_deposit", 0)),
                )
                or 0
            )
            realized = float(
                context.portfolio_state.get(
                    "daily_realized_profit",
                    getattr(trader, "daily_realized_profit", getattr(trader, "total_realized_profit", 0)),
                )
                or 0
            )
            if initial <= 0:
                return True
            loss_rate = (realized / initial) * 100.0
            max_loss = float(getattr(cfg, "max_daily_loss", 3.0))
            return loss_rate > -max_loss

        return True
