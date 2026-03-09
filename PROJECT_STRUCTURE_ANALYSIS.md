# Kiwoom Automatic Trader 프로젝트 구조 분석

작성일: 2026-03-05  
최종 동기화: 2026-03-09  
분석 기준: 실제 저장소 코드 + `README.md`, `CLAUDE.md`, `GEMINI.md`

## 1) 요약

현재 프로젝트는 `엔트리 래퍼(키움증권 자동매매.py) + app/mixins 분할 아키텍처`로 잘 정리되어 있습니다.  
실시간 매매 핵심은 다음 축으로 동작합니다.

- UI/상태: `app/main_window.py` + `app/mixins/ui_build.py`
- 세션/수명주기: `app/mixins/trading_session.py`
- 체결 기반 매매 엔진: `app/mixins/execution_engine.py`
- 주문/계좌 동기화 Fail-safe: `app/mixins/order_sync.py`
- 전략 평가: `strategy_manager.py` + `strategies/pack.py`
- API 통신: `api/rest_client.py`, `api/websocket_client.py`

## 2) 실제 코드베이스 규모 (실측)

패키지별 Python 라인 수(주요 기준):

| 패키지 | py 파일 수 | 라인 수 |
|---|---:|---:|
| `app/` | 17 | 6240 |
| `api/` | 5 | 1755 |
| `strategy_manager.py` | 1 | 1519 |
| `tests/` | 54 | 3105 |
| `strategies/` | 4 | 401 |
| `tools/` | 4 | 405 |
| `backtest/` | 2 | 309 |
| `data/` | 7 | 257 |
| `portfolio/` | 2 | 39 |

핵심 파일 Top 5:

1. `strategy_manager.py` (1519)
2. `app/mixins/ui_build.py` (1081)
3. `app/mixins/trading_session.py` (1030)
4. `api/rest_client.py` (792)
5. `app/mixins/persistence_settings.py` (737)

## 3) 엔트리포인트와 조립 구조

### 엔트리

- `키움증권 자동매매.py`
  - `QApplication` 생성
  - 전역 예외 훅 설정
  - `KiwoomProTrader` 표시

### 조립 클래스

- `app/main_window.py`
  - `KiwoomProTrader`는 9개 믹스인을 다중상속으로 조립
  - 정적 분석 시 `app/mixins/_typing.py`의 `TraderMixinBase`를 통해 `QMainWindow` 성격과 동적 속성 접근을 타입으로 보강
  - 시그널:
    - `sig_log`
    - `sig_execution`
    - `sig_order_execution`
    - `sig_update_table`

믹스인 책임:

- `ui_build.py`: 탭/위젯/고급전략 UI 구성
- `api_account.py`: API 연결, 계좌정보, 실거래 가드
- `trading_session.py`: 시작/중지, 유니버스 초기화, 시간청산
- `execution_engine.py`: 틱 이벤트 기반 매수/매도 의사결정 및 주문 실행
- `order_sync.py`: 주문/체결 이벤트 반영, 포지션 동기화, sync 실패 차단
- `persistence_settings.py`: 설정/내역 저장, 스키마 호환
- `dialogs_profiles.py`: 프리셋/프로필/수동주문/예약
- `market_data_tabs.py`: 차트/호가/조건검색/순위
- `system_shell.py`: 로깅/트레이/타이머/종료 플로우

## 4) 런타임 핵심 플로우

### A. 연결

1. `connect_api()` 호출
2. Worker 스레드에서 인증/계좌조회
3. 성공 시 `rest_client`, `ws_client`, 계좌 콤보 반영
4. `_refresh_account_info_async()`로 예수금/총자산/가상예수금 동기화

### B. 매매 시작

1. `start_trading()` 입력 코드 검증
2. 실거래 보호문구 가드 `_confirm_live_trading_guard()`
3. live capability guard:
   - `asset_scope == kr_stock_live` 강제
   - `short_enabled == False` 강제
   - 전략 live_supported 체크
4. `_init_universe()`로 종목별 시세/일봉/분봉/평균거래량/스프레드 초기화
5. `_sync_positions_snapshot()` 성공해야만 시작 허용
6. WebSocket 체결/주문체결 구독 시작

### C. 실시간 의사결정

- `ExecutionData` 수신 -> `ExecutionEngineMixin._on_execution()`
- 보유 중:
  - ATR 손절
  - 고정 손절
  - 단계별 익절
  - 트레일링 스톱
  - 시간 청산
- 미보유:
  - 시간대 진입금지(15시 이후)
  - 일일손실 트리거 차단
  - 최대보유수 차단
  - 쿨다운 차단
  - 목표가 돌파 + 돌파확인틱
  - `strategy.evaluate_buy_conditions()` 통과 시 수량 계산 후 주문

### D. 주문/체결 동기화

- 주문 성공은 곧바로 체결로 간주하지 않음
- `_sync_position_from_account()` 배치/디바운스 호출
- 재시도 초과 시 `sync_failed` 상태로 종목 단위 자동주문 차단
- 동기화 복구 시 `sync_failed` 해제

### E. 종료

- `stop_trading()`에서 구독해제/타이머 정리/reserved cash 환원
- `closeEvent()`에서 강제종료/트레이 최소화/내역 flush 정책 처리

## 5) 데이터 모델 핵심

### universe 엔트리(종목 상태) 주요 필드

- 가격/지표 기반: `current`, `open`, `prev_close`, `prev_high`, `prev_low`, `target`
- 히스토리: `price_history`, `minute_prices`, `daily_prices`, `high_history`, `low_history`
- 거래량/유동성: `current_volume`, `avg_volume_5`, `avg_volume_20`, `avg_value_20`
- 체결/호가: `ask_price`, `bid_price`
- 포지션: `held`, `buy_price`, `invest_amount`, `buy_time`
- 리스크/상태: `status`, `max_profit_rate`, `cooldown_until`, `breakout_hits`, `partial_profit_levels`
- 외부데이터: `investor_net`, `program_net`, `external_status`, `external_updated_at`, `external_error`

### 상태(state) 흐름

대표 상태:
- `watch`
- `buying` -> `buy_submitted` -> `holding`
- `selling` -> `sell_submitted` -> `watch`
- `trailing`
- `cooldown`
- `sync_failed` (Fail-safe 차단 상태)

## 6) 전략 엔진 구조

### 레거시 평가 경로

`StrategyManager.evaluate_buy_conditions()`가 단일 스냅샷으로 아래 조건을 평가:

- RSI
- 거래량
- 유동성
- 스프레드
- MACD
- 볼린저
- DMI/ADX
- Stoch RSI
- MTF
- 갭
- 시장 분산/섹터 제한
- MA 데드크로스 필터
- 진입 점수

### 모듈형 전략팩 경로

- `TradingConfig.feature_flags.use_modular_strategy_pack=True`면
  `strategies/pack.py`의 `StrategyPackEngine` 경로 사용
- primary/filter/risk overlay 분리
- 외부데이터 의존 전략(`investor_program_flow`)은 stale/disabled 시 fail-closed

## 7) 리스크/안전장치 현황

구현됨:

- 실거래 시작 보호문구 가드
- 일일 손실 한도(일일 기준 손익/기준금액)
- ATR 손절 + 고정 손절 + 트레일링 + 시간청산
- 재진입 쿨다운
- 주문-체결 비동기 동기화 + 재시도 + `sync_failed` 차단
- reserved cash(가상 예수금) 선점/환원
- v4 Shock guard(1m/5m 급변동 감지) + 세션 단위 진입 차단
- v4 VI/HALT guard + `reopen_cooldown` 상태 머신
- v4 Regime sizing(ATR% 기반 `elevated/extreme` 포지션 축소)
- v4 Liquidity stress guard(스프레드/거래대금 스트레스 진입 차단)
- v4 Slippage guard(최근 체결 평균 bps 기반 진입 차단)
- v4 Order health guard(실패 이벤트 급증 시 degraded 모드)
- 차단 reason code 및 진단 컬럼(`market state`, `guard reason`, `risk mode`, `health mode`)

## 8) 테스트/검증 현황

2026-03-09 실행:

- 명령: `python -m pytest -q tests/unit`
- 결과: `83 passed`
- 명령: `pyright .`
- 결과: `0 errors, 0 warnings`
- 인코딩 점검: UTF-8 디코드 실패 없음, `U+FFFD` 없음

커버되는 핵심 시나리오:

- 시작 시 포지션 스냅샷 동기화 강제
- 동기화 실패 누적 `sync_failed` 차단
- 일일 손실 롤오버/기준 전환
- 전략팩 엔진 경로 및 external stale guard
- 실행 정책(`market/limit`) 라우팅
- 설정 스키마/호환성
- Shock/VI/reopen_cooldown/regime/liquidity/slippage/order-health 가드
- 진단 컬럼/guard reason 노출
- 백테스트 guard parity
- 백테스트 다종목 MTM 최신가 캐시 회귀
- 거래내역 single-writer 저장 순서 보장
- 세션 인입 포지션 TIME_STOP 제외 정책

## 9) 문서-코드 동기화 메모

`README.md`/`CLAUDE.md`/`GEMINI.md`/`STRATEGY_EXPANSION_BLUEPRINT.md` 기준으로 v4 guard 정책, 정적 분석 기준, 설정 스키마를 동기화했습니다.

- canonical 설정 스키마: `settings_version = 4`
- 신규 가드 기본값/진단 컬럼/KPI 항목 문서 반영
- `pyrightconfig.json` 추적 및 `app/mixins/_typing.py` 역할을 문서에 반영
- README 구조 트리와 테스트 현황을 현재 기준으로 정리

## 10) 후속 고도화 지점

현재 v4 가드 통합은 완료되었고, 다음 고도화가 남아 있습니다.

1. 공식 시장상태(서킷/VI) API 안정 연동률 개선(현재는 지원 시 우선, 미지원 시 proxy 폴백)
2. `reopen_cooldown` 구간의 점수/틱/수량 강화 규칙 세분화
3. 운영 KPI의 장중/일별 리포트 자동 집계
4. 시장별 인덱스 피드 품질 저하 시 폴백 전략(다중 소스/지연 허용치) 고도화

---

상세 구현/운영 스펙은 [`STRATEGY_EXPANSION_BLUEPRINT.md`](./STRATEGY_EXPANSION_BLUEPRINT.md)에 정리되어 있습니다.
