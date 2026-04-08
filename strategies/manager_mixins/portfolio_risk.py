import datetime


class StrategyManagerPortfolioRiskMixin:
    def calculate_dynamic_position_size(self, code) -> int:
        info = self.trader.universe.get(code, {})
        current_price = info.get("current", 0)
        if current_price <= 0:
            return 0

        if self.config:
            base_invest = self.trader.deposit * (self.config.betting_ratio / 100)
            use_dynamic = self.config.use_dynamic_sizing
        else:
            base_invest = self.trader.deposit * (self.trader.spin_betting.value() / 100)
            use_dynamic = hasattr(self.trader, "chk_use_dynamic_sizing") and self.trader.chk_use_dynamic_sizing.isChecked()

        if not use_dynamic:
            base_qty = max(0, int(base_invest / current_price))
            return self.apply_regime_size_scale(code, base_qty)

        if self.consecutive_losses >= 3:
            adjusted_invest = base_invest * 0.5
            self.log(f"[동적사이징] 연속 {self.consecutive_losses}회 손실 - 투자금 50% 축소")
        elif self.consecutive_losses >= 2:
            adjusted_invest = base_invest * 0.75
        elif self.consecutive_wins >= 3:
            adjusted_invest = base_invest * 1.25
            self.log(f"[동적사이징] 연속 {self.consecutive_wins}회 이익 - 투자금 25% 확대")
        elif self.consecutive_wins >= 2:
            adjusted_invest = base_invest * 1.1
        else:
            adjusted_invest = base_invest

        max_invest = self.trader.deposit * 0.2
        min_invest = self.trader.deposit * 0.02
        adjusted_invest = max(min_invest, min(max_invest, adjusted_invest))

        base_qty = max(0, int(adjusted_invest / current_price))
        return self.apply_regime_size_scale(code, base_qty)

    def update_consecutive_results(self, is_profit: bool):
        if is_profit:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

    def check_market_diversification(self, code) -> bool:
        if self.config:
            if not self.config.use_market_limit:
                return True
            max_val = self.config.market_limit
        else:
            if not hasattr(self.trader, "chk_use_market_limit") or not self.trader.chk_use_market_limit.isChecked():
                return True
            max_ratio_spin = getattr(self.trader, "spin_market_limit", None)
            max_val = max_ratio_spin.value() if max_ratio_spin else 70

        market = self._get_stock_market(code)
        current_allocation = self.market_investments.get(market, 0)
        max_ratio = max_val / 100

        total_invested = sum(self.market_investments.values())
        if total_invested > 0:
            market_ratio = current_allocation / total_invested
            if market_ratio >= max_ratio:
                self.log(f"[분산관리] {market.upper()} 비중 {market_ratio*100:.0f}% >= {max_ratio*100:.0f}% 진입 보류")
                return False

        return True

    def _get_stock_market(self, code) -> str:
        info = self.trader.universe.get(code, {})
        if "market_type" in info and info["market_type"] != "unknown":
            return info["market_type"].lower()
        if code.startswith("0") or code.startswith("1") or code.startswith("2"):
            return "kospi"
        return "kosdaq"

    def update_market_investment(self, code, amount, is_buy=True, cost_amount=None):
        market = self._get_stock_market(code)
        if is_buy:
            self.market_investments[market] = self.market_investments.get(market, 0) + amount
        else:
            decrease = cost_amount if cost_amount is not None else amount
            self.market_investments[market] = max(0, self.market_investments.get(market, 0) - decrease)

    def check_sector_limit(self, code) -> bool:
        if self.config:
            if not self.config.use_sector_limit:
                return True
            max_val = self.config.sector_limit
        else:
            if not hasattr(self.trader, "chk_use_sector_limit") or not self.trader.chk_use_sector_limit.isChecked():
                return True
            max_amt = getattr(self.trader, "spin_sector_limit", None)
            max_val = max_amt.value() if max_amt else 30

        sector = self._get_stock_sector(code)
        current_allocation = self.sector_investments.get(sector, 0)
        max_sector_invest = self.trader.deposit * (max_val / 100)

        if current_allocation >= max_sector_invest:
            self.log(f"[섹터관리] {sector} 섹터 한도 도달 ({current_allocation:,.0f}원)")
            return False

        return True

    def _get_stock_sector(self, code) -> str:
        info = self.trader.universe.get(code, {})
        sector = info.get("sector", "")
        if sector and sector != "기타":
            return sector
        market_type = info.get("market_type", "")
        if market_type:
            return f"기타({market_type})"
        return "기타"

    def update_sector_investment(self, code, amount, is_buy=True, cost_amount=None):
        sector = self._get_stock_sector(code)
        if is_buy:
            self.sector_investments[sector] = self.sector_investments.get(sector, 0) + amount
        else:
            decrease = cost_amount if cost_amount is not None else amount
            self.sector_investments[sector] = max(0, self.sector_investments.get(sector, 0) - decrease)

    def apply_regime_size_scale(self, code, quantity: int) -> int:
        qty = max(0, int(quantity or 0))
        if qty <= 0:
            return 0
        regime, scale, _atr_pct = self.get_regime_profile(code)
        market_intel = self.get_market_intel_snapshot(code)
        if market_intel.get("enabled") and str(market_intel.get("macro_regime", "neutral")) == "risk_off":
            qty = max(1, int(qty * 0.7))
        if market_intel.get("enabled"):
            qty = max(1, int(qty * max(0.1, float(market_intel.get("size_multiplier", 1.0) or 1.0))))
            qty = max(1, int(qty * max(0.1, float(market_intel.get("portfolio_budget_scale", 1.0) or 1.0))))
        if regime in {"elevated", "extreme"}:
            return max(1, int(qty * float(scale)))
        return qty

    def calculate_position_size(self, code, risk_percent=1.0, atr_multiplier=2.0):
        info = self.trader.universe.get(code, {})
        high_list = info.get("high_history", [])
        low_list = info.get("low_history", [])
        close_list = info.get("price_history", [])
        if len(high_list) < 15 or len(low_list) < 15 or len(close_list) < 15:
            return self._default_position_size(code)

        atr = self.calculate_atr(high_list, low_list, close_list, period=14)
        if atr <= 0:
            return self._default_position_size(code)

        current_price = info.get("current", 0)
        if current_price <= 0:
            return 0

        stop_loss_amount = atr * atr_multiplier
        risk_amount = self.trader.deposit * (risk_percent / 100)
        position_size = int(risk_amount / stop_loss_amount) if stop_loss_amount > 0 else 0

        max_invest = (
            self.trader.deposit * (self.config.betting_ratio / 100)
            if self.config
            else self.trader.deposit * (self.trader.spin_betting.value() / 100)
        )
        max_quantity = int(max_invest / current_price) if current_price > 0 else 0
        final_size = min(position_size, max_quantity)

        if final_size > 0:
            self.log(f"[{info.get('name', code)}] ATR 사이징: ATR={atr:.0f}, 적정수량={final_size}주")

        return self.apply_regime_size_scale(code, max(0, final_size))

    def _default_position_size(self, code):
        info = self.trader.universe.get(code, {})
        current_price = info.get("current", 0)
        if current_price <= 0:
            return 0

        if self.config:
            invest_amount = self.trader.deposit * (self.config.betting_ratio / 100)
        else:
            invest_amount = self.trader.deposit * (self.trader.spin_betting.value() / 100)
        base_qty = max(0, int(invest_amount / current_price))
        return self.apply_regime_size_scale(code, base_qty)

    def get_time_based_k_value(self):
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
        info = self.trader.universe.get(code, {})
        prev_high = info.get("prev_high", 0) or info.get("high", 0)
        prev_low = info.get("prev_low", 0) or info.get("low", 0)
        today_open = info.get("open", 0)
        if prev_high == 0 or prev_low == 0 or today_open == 0:
            return 0

        if self.config and self.config.use_gap:
            k_value = self.get_gap_adjusted_k(code)
        elif self.config and self.config.use_time_strategy:
            k_value, _phase = self.get_time_based_k_value()
        else:
            k_value = self.config.k_value if self.config else self.trader.spin_k.value()

        target = today_open + (prev_high - prev_low) * k_value
        return target

    def get_split_orders(self, total_quantity, current_price, order_type="buy"):
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

            if order_type == "buy":
                price_adj = 1 - (split_percent / 100) * i
            else:
                price_adj = 1 + (split_percent / 100) * i

            adjusted_price = int(current_price * price_adj)
            orders.append((qty, adjusted_price))

        return orders

    def reset_tracking(self):
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.sector_investments.clear()
        self.market_investments = {"kospi": 0, "kosdaq": 0}
        self._decision_cache.clear()
