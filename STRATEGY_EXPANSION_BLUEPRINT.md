# STRATEGY_EXPANSION_BLUEPRINT

## 1. Scope
- One-shot integrated release.
- Live execution scope: KR stock long-only.
- Long/short + multi-asset: backtest/simulation support in phase-1.
- External data: free/official APIs first.

## 2. Strategy Catalog
| ID | Strategy | Data | Live Support | Notes |
|---|---|---|---|---|
| S01 | Time-Series Momentum | Daily return/trend | Simulation | Implement via strategy pack + backtest |
| S02 | Cross-Sectional Momentum | Relative strength universe | Simulation | Requires cross-symbol ranking dataset |
| S03 | MA/Channel Trend | Price + moving averages | Live (Long) | `ma_channel_trend` |
| S04 | ORB/Donchian Breakout | Intraday high/low | Live (Long) | `orb_donchian_breakout` proxy |
| S05 | Pairs Trading | Pair spread/cointegration | Simulation | Requires pair universe and spread model |
| S06 | Stat-Arb Residual | Multi-factor residuals | Simulation | Factor model extension |
| S07 | RSI/BB Reversion | RSI + Bollinger | Live (Long) | `rsi_bollinger_reversion` |
| S08 | DMI/ADX Trend Filter | High/low/close + ADX | Live (Long) | `dmi_trend_strength` |
| S09 | FF5 L/S | Fundamentals + returns | Simulation | DART + factor pipeline |
| S10 | Quality/Value/LowVol | Fundamental + vol metrics | Simulation | Built from S09 infra |
| S11 | Investor/Program Flow | Net flow metrics | Live (Long) | `investor_program_flow` |
| S12 | Volatility Targeting | ATR/realized vol | Live (Long) | Existing ATR sizing extended |
| S13 | Risk Parity Portfolio | Asset vol/cov | Simulation | `portfolio/allocator.py` |
| S14 | TWAP/VWAP/POV Exec | Tick/orderbook/time | Live (Long) | execution policy extension path |
| S15 | Market Making | Depth/spread microstructure | Simulation | Separate microstructure simulator |

## 3. Strategy-Pack Architecture
- `primary_strategy`: single strategy selector.
- `entry_filters`: list of filters (`rsi`, `volume`, `macd`, `spread`, etc.).
- `risk_overlays`: portfolio/risk constraints (`max_holdings`, `market_limit`, `daily_loss_limit`, etc.).
- `exit_overlays`: represented in runtime execution path (trailing stop, ATR stop, time stop, partial TP).

## 4. Data Layer Design
- `data/providers/kiwoom_provider.py`: market + flow wrappers.
- `data/providers/dart_provider.py`: corporate/fundamental retrieval.
- `data/providers/macro_provider.py`: macro series retrieval.
- `data/providers/csv_provider.py`: offline datasets for simulation/backtest.

## 5. Live vs Simulation Matrix
| Capability | Live | Sim/Backtest |
|---|---|---|
| KR stock long | Yes | Yes |
| KR stock short | No | Yes |
| Multi-asset | No | Yes |
| Fundamental factor L/S | No | Yes |
| Market making | No | Yes |

## 6. Backtest Specification
Engine: `backtest/engine.py`
- Event-driven iteration.
- Daily-first reproducible path.
- Minute extensibility with tradable-time windows.
- Cost model: commission + slippage (bps).
- Position states: flat/long/short.
- Deterministic output: equity curve + trade list + metrics.

## 7. Risk and Execution Rules
- Live safety:
  - must pass live-guard phrase/timeout.
  - `asset_scope` must be `kr_stock_live` for live execution.
  - `short_enabled=True` blocked in live.
- Risk controls:
  - max holdings
  - daily loss stop
  - market/sector concentration filters
- Execution abstraction:
  - `execution_policy`: `market` or `limit`.

## 8. Public Interface Changes
- `TradingConfig` extended with v3 fields.
- Settings/profiles persist/load these v3 fields.
- StrategyManager now routes through modular engine first when flag-enabled; legacy evaluator remains fallback-compatible.

## 9. Acceptance Criteria
- Historical baseline 9 unit tests remain green.
- Current baseline (2026-02-18): `pytest -q tests/unit` => **15 passed, 2 warnings**.
- Latest baseline (2026-02-19): `pytest -q tests/unit` => **37 passed, 1 warning**.
- New tests validate:
  - strategy-pack behavior,
  - v2->v3 settings migration,
  - backtest determinism,
  - execution policy behavior,
  - live safety constraints.

## 10. Future Expansion Hooks
- Add strategy registry for S01/S02/S05/S06/S09/S10/S15 production-grade implementations.
- Add covariance-aware allocator and drawdown-aware budget adaptation.
- Add broker abstraction layer if live multi-asset execution becomes required.

## 11. Implementation Status Addendum (2026-02-18)
- UI `Strategy Pack` selector currently exposes 16 strategy IDs and routes into `strategies/pack.py`.
- Primary strategy IDs already wired:
  - `volatility_breakout`, `time_series_momentum`, `cross_sectional_momentum`
  - `ma_channel_trend`, `orb_donchian_breakout`, `pairs_trading_cointegration`
  - `stat_arb_residual`, `rsi_bollinger_reversion`, `dmi_trend_strength`
  - `ff5_factor_ls`, `quality_value_lowvol`, `investor_program_flow`
  - `volatility_targeting_overlay`, `risk_parity_portfolio`
  - `execution_algo_twap_vwap_pov`, `market_making_spread`
- Live constraints remain unchanged in runtime:
  - non-`kr_stock_live` scope blocked in live mode
  - `short_enabled=True` blocked in live mode
- Data/provider modules are now physically present for extension:
  - `data/providers/kiwoom_provider.py`
  - `data/providers/dart_provider.py`
  - `data/providers/macro_provider.py`
  - `data/providers/csv_provider.py`

## 12. Stability Addendum (2026-02-19)
- Trading start now requires successful account-position snapshot sync after universe initialization.
- Per-code position-sync fail-safe is active: repeated sync failure sets `status=sync_failed` and blocks that code's auto orders.
- Daily loss governance now uses daily-scoped PnL baseline (`daily_realized_profit / daily_initial_deposit`).
- Runtime/documentation baseline should assume WebSocket deprecation cleanup is applied (`websockets>=11.0,<16`).
