"""Event-driven backtest engine.

Phase-1 target: deterministic daily simulation with minute extensibility.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass
class BacktestBar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class PositionState:
    side: str = "flat"  # flat/long/short
    quantity: float = 0.0
    entry_price: float = 0.0


@dataclass
class BacktestConfig:
    timeframe: str = "1d"
    commission_bps: float = 5.0
    slippage_bps: float = 3.0
    tradable_start: time = time(9, 0)
    tradable_end: time = time(15, 20)


@dataclass
class BacktestResult:
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class EventDrivenBacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        bars: Iterable[BacktestBar],
        signal_fn: Callable[[BacktestBar, Dict[str, PositionState]], Dict[str, str]],
        initial_cash: float = 100000000.0,
        allocation_per_trade: float = 0.1,
    ) -> BacktestResult:
        cash = float(initial_cash)
        positions: Dict[str, PositionState] = {}
        equity_curve: List[float] = []
        trades: List[Dict[str, Any]] = []

        ordered = sorted(bars, key=lambda b: (b.ts, b.symbol))
        for bar in ordered:
            if self.config.timeframe.endswith("m") and not self._is_tradable_time(bar.ts):
                continue

            if bar.symbol not in positions:
                positions[bar.symbol] = PositionState()

            symbol_state = positions[bar.symbol]
            signals = signal_fn(bar, positions) or {}
            action = (signals.get(bar.symbol) or "hold").lower()

            fill_price = self._apply_costs(bar.close, action)

            if action == "buy" and symbol_state.side == "flat":
                risk_cash = max(0.0, cash * allocation_per_trade)
                qty = (risk_cash / fill_price) if fill_price > 0 else 0.0
                if qty > 0:
                    cost = qty * fill_price
                    cash -= cost
                    symbol_state.side = "long"
                    symbol_state.quantity = qty
                    symbol_state.entry_price = fill_price
                    trades.append({"ts": bar.ts.isoformat(), "symbol": bar.symbol, "side": "buy", "price": fill_price, "qty": qty})

            elif action == "sell" and symbol_state.side == "long":
                proceeds = symbol_state.quantity * fill_price
                pnl = (fill_price - symbol_state.entry_price) * symbol_state.quantity
                cash += proceeds
                trades.append({
                    "ts": bar.ts.isoformat(),
                    "symbol": bar.symbol,
                    "side": "sell",
                    "price": fill_price,
                    "qty": symbol_state.quantity,
                    "pnl": pnl,
                })
                symbol_state.side = "flat"
                symbol_state.quantity = 0.0
                symbol_state.entry_price = 0.0

            elif action == "short" and symbol_state.side == "flat":
                risk_cash = max(0.0, cash * allocation_per_trade)
                qty = (risk_cash / fill_price) if fill_price > 0 else 0.0
                if qty > 0:
                    cash += qty * fill_price
                    symbol_state.side = "short"
                    symbol_state.quantity = qty
                    symbol_state.entry_price = fill_price
                    trades.append({"ts": bar.ts.isoformat(), "symbol": bar.symbol, "side": "short", "price": fill_price, "qty": qty})

            elif action == "cover" and symbol_state.side == "short":
                cost = symbol_state.quantity * fill_price
                pnl = (symbol_state.entry_price - fill_price) * symbol_state.quantity
                cash -= cost
                trades.append({
                    "ts": bar.ts.isoformat(),
                    "symbol": bar.symbol,
                    "side": "cover",
                    "price": fill_price,
                    "qty": symbol_state.quantity,
                    "pnl": pnl,
                })
                symbol_state.side = "flat"
                symbol_state.quantity = 0.0
                symbol_state.entry_price = 0.0

            equity = cash + self._mark_to_market(positions, {bar.symbol: bar.close})
            equity_curve.append(equity)

        result = BacktestResult(equity_curve=equity_curve, trades=trades)
        result.metrics = self._calculate_metrics(equity_curve, trades, initial_cash)
        return result

    def _apply_costs(self, raw_price: float, action: str) -> float:
        if raw_price <= 0:
            return 0.0
        fee = self.config.commission_bps / 10000.0
        slip = self.config.slippage_bps / 10000.0
        if action in {"buy", "cover"}:
            return raw_price * (1.0 + fee + slip)
        if action in {"sell", "short"}:
            return raw_price * (1.0 - fee - slip)
        return raw_price

    def _is_tradable_time(self, ts: datetime) -> bool:
        t = ts.time()
        return self.config.tradable_start <= t <= self.config.tradable_end

    @staticmethod
    def _mark_to_market(positions: Dict[str, PositionState], last_prices: Dict[str, float]) -> float:
        value = 0.0
        for symbol, state in positions.items():
            px = float(last_prices.get(symbol, state.entry_price) or 0)
            if state.side == "long":
                value += state.quantity * px
            elif state.side == "short":
                value -= state.quantity * px
        return value

    @staticmethod
    def _calculate_metrics(equity_curve: List[float], trades: List[Dict[str, Any]], initial_cash: float) -> Dict[str, float]:
        if not equity_curve:
            return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "trades": 0.0}
        peak = equity_curve[0]
        max_dd = 0.0
        for v in equity_curve:
            peak = max(peak, v)
            if peak > 0:
                dd = (peak - v) / peak * 100.0
                max_dd = max(max_dd, dd)
        ret = (equity_curve[-1] - initial_cash) / initial_cash * 100.0 if initial_cash > 0 else 0.0
        return {
            "return_pct": ret,
            "max_drawdown_pct": max_dd,
            "trades": float(len(trades)),
        }
