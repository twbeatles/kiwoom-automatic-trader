# 급변동/서킷브레이커 대응 전략 확장 청사진

작성일: 2026-03-05  
최종 동기화: 2026-03-24 (v4 Guard 유지 + v5 설정 스키마 + 시장 인텔리전스 통합 반영 기준)

추가 동기화: 2026-03-24

- 프로젝트 canonical 설정 스키마는 현재 `settings_version = 5`입니다.
- v4 guard 자체는 유지되며, `market_intelligence` 계층이 전략팩/백테스트에 추가 통합되었습니다.
- 본 문서는 v4 guard 확장 청사진/구현 이력을 설명하는 문서로 유지합니다.

## 1) 목표

급등/급락, VI(변동성완화장치), 서킷브레이커, 유동성 급감 구간에서

- 신규 진입 리스크 자동 억제
- 기존 포지션 청산 경로 유지
- 시장 정상화 후 안전한 재가동

을 유지하는 Fail-Closed 체계를 운영한다.

## 2) 구현 상태 요약

- 범위: `F1~F8` 전부 반영 완료
- 정책: `Fail-Closed` (불확실/오류 시 신규 진입 차단, 청산 허용)
- 감지: 가격기반 1차 + 공식 상태연동 탐색(지원 시 우선, 미지원 시 proxy 폴백)
- 스키마: 현재 canonical은 `settings_version = 5`, v4 guard 필드는 그대로 유지
- 동기화: 라이브/전략팩/백테스트 guard 의미 일치

## 3) F1~F8 구현 결과

## F1. 시장 충격 글로벌 가드

- 규칙: `abs(ret_1m) >= shock_1m_pct` 또는 `abs(ret_5m) >= shock_5m_pct`
- 동작: 세션 `risk_mode=shock` 전환, cooldown 동안 신규 매수 차단
- 기본값: `shock_1m_pct=1.5`, `shock_5m_pct=2.8`, `shock_cooldown_min=10`

## F2. VI/서킷브레이커 상태 가드

- 상태: `normal | vi | halt | reopen_cooldown`
- 우선순위: 공식 상태 필드 우선, 미지원 시 proxy 판정
- proxy: `abs(ret_1m_code) >= vi_proxy_1m_pct` 또는 `spread_pct >= vi_proxy_spread_pct`
- 기본값: `vi_cooldown_min=7`, `vi_proxy_1m_pct=4.0`, `vi_proxy_spread_pct=1.2`

## F3. 변동성 레짐 기반 동적 축소

- 지표: `atr_pct = ATR14 / current * 100`
- 구간: `normal | elevated | extreme`
- 스케일: `elevated=0.7`, `extreme=0.4`
- 최대 보유수: 레짐에 따라 보수적으로 축소

## F4. 유동성 스트레스 가드

- 조건: `spread_pct > stress_spread_pct` 또는 `avg_value_20` 저하
- 기본값: `stress_spread_pct=1.0`, `stress_min_value_ratio=0.35`
- 동작: 스트레스 구간 신규 진입 차단

## F5. 슬리피지 가드

- 최근 `slippage_window_trades`의 평균 절대 슬리피지 bps 계산
- 평균이 `max_slippage_bps` 초과 시 신규 진입 차단
- 기본값: `max_slippage_bps=15.0`, `slippage_window_trades=20`

## F6. 재개장 점진 재가동

- `vi/halt` 해제 직후 `reopen_cooldown` 상태 유지
- 쿨다운 구간에서 신규 진입 제한 유지(Fail-Closed)

## F7. 주문 실패 스파이크 차단

- 최근 `order_health_window_sec` 내 실패 수 집계
- 임계 초과 시 `order_health_mode=degraded` 진입
- 기본값: `order_health_fail_count=5`, `order_health_window_sec=60`, `order_health_cooldown_sec=180`

## F8. 관측/감사 로그 강화

- 차단 사유를 `guard reason`으로 기록
- 진단 컬럼 확장: `market state`, `guard reason`, `risk mode`, `health mode`
- KPI 필드: `guard_block_count_by_reason`, `shock_mode_minutes`, `order_health_degraded_count`, `avg_slippage_bps`

## 4) 데이터 모델/설정 스키마(v5 current)

### 4.1 TradingConfig / Config 신규 필드(반영됨)

- `use_shock_guard`, `shock_1m_pct`, `shock_5m_pct`, `shock_cooldown_min`
- `use_vi_guard`, `vi_cooldown_min`, `vi_proxy_1m_pct`, `vi_proxy_spread_pct`
- `use_regime_sizing`, `regime_elevated_atr_pct`, `regime_extreme_atr_pct`
- `regime_size_scale_elevated`, `regime_size_scale_extreme`
- `use_liquidity_stress_guard`, `stress_spread_pct`, `stress_min_value_ratio`
- `use_slippage_guard`, `max_slippage_bps`, `slippage_window_trades`
- `use_order_health_guard`, `order_health_fail_count`, `order_health_window_sec`, `order_health_cooldown_sec`

### 4.2 모델/인터페이스 확장(반영됨)

- `ExecutionData` 선택 필드: `trading_status`, `market_event`, `index_code`, `index_value`
- `IndexTick` dataclass 추가
- `websocket_client` 인덱스 구독: `subscribe_index`, `set_on_index`

### 4.3 설정 마이그레이션(반영됨)

- canonical: `settings_version = 5`
- `settings_version < 5` 로드 시 v4 guard 키와 `market_intelligence` 블록 자동 보강
- 기존 값 우선, 신규 키만 default 주입

## 5) 파일별 반영 지점

- `config.py`: v4 가드 필드/기본값/스키마 상수
- `app/mixins/ui_build.py`: 고급설정 핵심 토글/임계치, 진단 컬럼
- `app/main_window.py`: global risk/order health 상태 저장 및 진단 반영
- `app/mixins/trading_session.py`: 인덱스 피드 + shock/VI 상태 계산/복구
- `app/mixins/execution_engine.py`: `_can_enter_trade()` 단일 진입 게이트
- `app/mixins/order_sync.py`: 실패 이벤트 집계 + degraded 자동 복구
- `strategy_manager.py`: guard 조건/metrics 확장 + 레짐 스케일 훅
- `strategies/pack.py`: risk overlay 가드 확장(fail-closed)
- `api/models.py`, `api/websocket_client.py`, `api/rest_client.py`: 상태/인덱스 확장
- `app/mixins/_typing.py`: 동적 Qt mixin 정적 분석용 type-only 베이스
- `app/mixins/persistence_settings.py`, `app/mixins/dialogs_profiles.py`: v4 키 parity
- `backtest/engine.py`: guard parity 평가 입력 반영

## 6) 테스트 동기화

신규 테스트:

- `tests/unit/test_shock_guard_entry_block.py`
- `tests/unit/test_vi_state_machine.py`
- `tests/unit/test_reopen_cooldown_restriction.py`
- `tests/unit/test_regime_sizing_scale.py`
- `tests/unit/test_liquidity_stress_guard.py`
- `tests/unit/test_slippage_guard_policy_switch.py`
- `tests/unit/test_order_health_degrade.py`
- `tests/unit/test_guard_reason_diagnostics.py`
- `tests/unit/test_settings_schema_v4.py`
- `tests/unit/test_settings_schema_v4_compat.py`
- `tests/unit/test_strategy_pack_guard_overlays.py`
- `tests/unit/test_backtest_guard_parity.py`

검증 결과(2026-03-05):

- `python -m pytest tests/unit --disable-warnings`
- `68 passed in 1.36s`

추가 반영(2026-03-07):

- `tests/unit/test_order_sync_pending_state_machine.py`
- `tests/unit/test_regime_sizing_single_apply.py`
- `tests/unit/test_investment_cost_basis_ledger.py`
- `tests/unit/test_shock_fallback_representative.py`
- `tests/unit/test_time_stop_session_policy.py`
- `tests/unit/test_trade_history_single_writer.py`
- `tests/unit/test_sync_failed_manual_release.py`
- `tests/unit/test_backtest_engine.py` (다종목 MTM 최신가 캐시 회귀 보강)

최신 검증 결과(2026-03-24):

- `python -m pytest tests/unit --disable-warnings`
- `90 passed in 0.53s`

추가 동기화(2026-03-09):

- `pyrightconfig.json`을 루트 추적 파일로 추가하여 repo-wide 정적 분석 기준을 고정
- `pyright .` -> `0 errors, 0 warnings` (2026-03-09 당시 환경)
- `KiwoomTrader.spec` / 문서 / `.gitignore`를 `app/mixins/_typing.py` 및 현재 구조 기준으로 동기화
- UTF-8 인코딩 스캔 결과 디코드 실패 및 `U+FFFD` 없음

추가 메모(2026-03-24):

- 현재 워크스페이스에서 `pyright .`를 다시 실행하려면 `PyQt6`, `requests`, `websockets`, `urllib3`, `keyring` 로컬 의존성 설치가 필요
- `KiwoomTrader.spec`는 시장 인텔리전스 신규 provider/mixin을 hiddenimport에 반영했고, 런타임 JSON/JSONL 산출물은 번들에서 제외

## 7) 수용 기준 반영 상태

1. 급변동 임계치 초과 시 신규 진입 즉시 차단 + reason 코드 기록: 충족  
2. VI/HALT 및 proxy VI 상태에서 신규 매수 차단, 청산 허용: 충족  
3. 재개장 쿨다운 제한: 충족  
4. 주문 실패 스파이크 degraded 전환/자동 복구: 충족  
5. v3 설정 로드 시 v4 자동 보강: 충족  
6. 라이브/전략팩/백테스트 guard 의미 동기화: 충족  
7. 기존/신규 테스트 통과: 충족

## 8) 후속 고도화 과제

1. 공식 서킷/VI 상태 API 연동 성공률 및 장애시 폴백 로깅 고도화
2. `reopen_cooldown` 구간의 점수/틱 강화 규칙 세분화
3. 운영 KPI 자동 리포트(세션/일자별 집계) 추가

---

구조 분석 상세는 [`PROJECT_STRUCTURE_ANALYSIS.md`](./PROJECT_STRUCTURE_ANALYSIS.md)를 참조.
