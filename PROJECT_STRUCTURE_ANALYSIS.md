# PROJECT_STRUCTURE_ANALYSIS

## 1. Executive Summary
This repository is no longer a monolith. Runtime is assembled through `KiwoomProTrader` mixins and now includes a modular strategy-pack extension path, backtest package, portfolio allocator, and external-data provider layer.

## 2. Architecture Map
- Entry wrapper: `키움증권 자동매매.py`
- Main window assembly: `app/main_window.py`
- UI composition: `app/mixins/ui_build.py`
- Trading session orchestration: `app/mixins/trading_session.py`
- Realtime execution engine: `app/mixins/execution_engine.py`
- Order/position sync: `app/mixins/order_sync.py`
- API/account handling: `app/mixins/api_account.py`
- Persistence/settings: `app/mixins/persistence_settings.py`
- Dialogs/profiles: `app/mixins/dialogs_profiles.py`
- Strategy orchestrator: `strategy_manager.py`
- Strategy modular core: `strategies/`
- Backtest engine: `backtest/engine.py`
- Portfolio risk-budget allocator: `portfolio/allocator.py`
- Data providers: `data/providers/`

## 3. Module Responsibilities
- `strategy_manager.py`: indicator math + compatibility wrappers + strategy-pack routing.
- `strategies/pack.py`: `primary_strategy + entry_filters + risk_overlays` evaluation.
- `app/mixins/execution_engine.py`: order triggering and execution-policy routing (`market`/`limit`).
- `app/mixins/persistence_settings.py`: settings schema v3 save/load/migration.
- `app/mixins/dialogs_profiles.py`: profile capture/apply including v3 fields.
- `backtest/engine.py`: deterministic event-driven simulation (daily-first, minute-extensible).

## 4. Runtime Flow (Current)
1. `키움증권 자동매매.py` bootstraps Qt app and launches `KiwoomProTrader`.
2. `KiwoomProTrader` builds UI, loads settings, wires `TradingConfig` sync.
3. API connect builds auth/rest/ws clients asynchronously.
4. Start trading initializes universe from quote/daily/minute data.
5. Realtime ticks enter `_on_execution` and run buy/sell logic.
6. Buy gating uses `StrategyManager.evaluate_buy_conditions`.
7. If `feature_flags.use_modular_strategy_pack` is true, strategy-pack engine evaluates first; otherwise legacy path runs.
8. Orders are submitted through execution policy abstraction and synced by account-position reconciliation.

## 5. Settings Schema (v3)
Canonical settings now include:
- Existing: `betting_ratio`, `k_value`, `loss_cut`, indicators, risk, schedule, theme, etc.
- New: `strategy_pack`, `strategy_params`, `portfolio_mode`, `short_enabled`, `asset_scope`, `backtest_config`, `feature_flags`, `execution_policy`.

Migration:
- Files with `settings_version < 3` are default-filled with v3 keys at load time.
- Legacy keys (`betting`) remain accepted for backward compatibility.

## 6. README/CLAUDE/GEMINI vs Actual Code
### Declared in docs
- Entry wrapper + mixin-based architecture.
- Strategy manager centered decision logic.
- Settings parity and refactor-safe behavior.

### Actual code findings
- True in broad architecture, but execution path had direct UI widget coupling in `execution_engine`; now reduced with config-first lookup.
- Strategy engine was effectively a single large evaluator; now modular strategy-pack route exists while preserving legacy fallback.
- Existing docs listed advanced strategy options; code now has explicit `strategies/`, `backtest/`, `portfolio/`, and `data/providers/` packages to support them.

## 7. Tests and Quality Baseline
- Existing unit tests: 9 passing baseline retained target.
- Added architecture introduces deterministic components (`backtest`, `allocator`, strategy-pack) suitable for unit-level verification.

## 8. Technical Debt / Risk Hotspots
- `ui_build.py` remains large and highly stateful.
- Some modules contain legacy mojibake text artifacts; functional but readability debt remains.
- Strategy metadata and external-data schemas are still loosely typed dictionaries.
- Live path remains KR stock long-only by design; short/multi-asset are simulation-first.

## 9. Change Impact Assessment
- High impact: `config.py`, `strategy_manager.py`, `execution_engine.py`, settings/profile persistence.
- Medium impact: UI advanced tab and config signal wiring.
- Low impact: additive packages (`strategies`, `backtest`, `portfolio`, `data/providers`).

## 10. Operational Safety Constraints
- Real trading guard remains intact (`_confirm_live_trading_guard`).
- Live path now blocks non-`kr_stock_live` scope and short-enabled mode.
- Feature flags allow gradual enablement even in one-shot integrated release.
