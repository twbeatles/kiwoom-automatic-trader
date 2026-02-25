# 주식 자동매매 + S11 프로그램매매 점검 리포트

- 점검 일자: 2026-02-25
- 대상 프로젝트: `kiwoom-automatic-trader`
- 점검 범위: 자동매매 전반 + `investor_program_flow(S11)` 심층
- 참조 문서: `CLAUDE.md`, `README.md`
- 실행 확인: `python -m pytest -q tests/unit` -> `42 passed`, `1 warning(langsmith/pydantic v1 on Python 3.14+)`

## 1) 점검 범위/방법

### 점검 범위
- 런타임 핵심 경로: API 연결, 유니버스 초기화, 매수/매도 실행, 주문/체결 동기화, 리스크 차단 로직.
- 전략 경로: 레거시 조건 평가 + 모듈형 전략팩(`StrategyPackEngine`) + `investor_program_flow(S11)`.
- 설정 경로: 저장/로드 스키마, 기본값 정합성, feature flag 반영 여부.

### 점검 방법
- 정적 코드 점검: 핵심 파일 라인 단위 확인.
- 문서-구현 정합성 점검: README/CLAUDE 명세 대비 실제 동작 비교.
- 회귀 베이스라인 확인: 단위 테스트 실행 상태 확인.

### 제외 범위
- 키움 실서버와의 실계좌 통신/실체결 검증.
- 실거래 성능 지표(슬리피지, 체결 지연) 계측.

## 2) 핵심 결론(요약)

- `P0` 2건, `P1` 3건, `P2` 3건의 잠재 리스크가 확인됨.
- 가장 치명적인 항목은 다음 2가지:
1. `S11 전략 데이터 계약 불일치 + 수집 경로 미연결`로 실질적으로 전략이 동작하기 어려운 구조.
2. `가용 현금 0 상태 매수 차단 우회` 가능성으로 주문 거부 반복 및 상태 혼선 가능.
- 현재 테스트는 통과 상태이나, 이번 이슈 대부분은 통합/운영 시나리오 성격이라 기존 단위테스트로는 포착되지 않음.

## 3) 심각도별 이슈 목록

### [P0-1] S11 전략이 사실상 동작 불가한 구조

- 근거:
  - 전략 엔진은 `investor_net`, `program_net` 키를 요구함: `strategies/pack.py:116`, `strategies/pack.py:117`.
  - REST 응답은 `individual_net/foreign_net/institution_net`, `net` 형태임: `api/rest_client.py:744`, `api/rest_client.py:745`, `api/rest_client.py:746`, `api/rest_client.py:778`.
  - provider 래퍼는 있으나 실행 경로에 연결되지 않음: `data/providers/kiwoom_provider.py:25`, `data/providers/kiwoom_provider.py:30`.
- 영향:
  - `investor_program_flow` 선택 시 조건이 상시 미충족(또는 오판)되어 전략 기대 동작과 실제가 분리됨.
- 재현 조건:
  - `primary_strategy=investor_program_flow` 선택 후 일반 유니버스 시작.
  - `universe[code]`에 canonical flow key가 채워지지 않아 `0`으로 평가됨.
- 권장 조치:
  - flow 데이터 정규화 계층 도입(REST raw -> canonical key 매핑).
  - S11용 수집 루프(주기/스로틀/TTL/실패 fallback) 런타임 연결.
  - S11 선택 시 데이터 신선도 미달이면 주문 차단(명시 로그 포함).
- 우선순위: 즉시(1순위).

### [P0-2] 가용 현금 0 상태에서 매수 차단 우회 가능

- 근거:
  - 매수 차단 조건: `required_cash > 0 and available_cash > 0 and required_cash > available_cash` (`app/mixins/execution_engine.py:283`).
  - `available_cash == 0`이면 위 조건이 거짓이 되어 주문 경로로 진행 가능.
- 영향:
  - 자금 부족 상황에서 주문 시도 반복, 거부/쿨다운/동기화 경로 혼선 가능.
- 재현 조건:
  - `virtual_deposit=0`, `required_cash>0` 상태에서 `_execute_buy()` 호출.
- 권장 조치:
  - 차단 조건을 `required_cash > available_cash`로 단순화(0 포함).
  - 주문 전 실계좌 주문가능금액 재조회(옵션) + 로깅 표준화.
- 우선순위: 즉시(1순위).

### [P1-1] 주문 동기화 트리거가 비체결 이벤트에도 과도 발동

- 근거:
  - 수량 파싱이 `exec_qty -> qty -> ord_qty` fallback (`app/mixins/order_sync.py:79`).
  - `qty > 0`이면 체결 여부와 무관하게 동기화 호출 (`app/mixins/order_sync.py:106`).
- 영향:
  - 접수/정정/거부 이벤트에서도 포지션 조회가 과도하게 호출되어 API 부하 및 로그 왜곡 가능.
- 재현 조건:
  - `ord_qty`만 존재하고 실제 체결이 아닌 주문 이벤트 수신.
- 권장 조치:
  - 체결 트리거를 `exec_qty > 0` 또는 체결 상태값으로 한정.
  - `ord_qty`는 메시지 표시용으로만 사용.
- 우선순위: 높음(2순위).

### [P1-2] 수동 주문(유니버스 외 종목) 시 pending 상태 잔존 가능

- 근거:
  - 수동 주문 성공 시 무조건 pending 등록 (`app/mixins/dialogs_profiles.py:161`, `app/mixins/dialogs_profiles.py:163`).
  - 포지션 동기화 배치 등록은 유니버스 종목만 수행 (`app/mixins/order_sync.py:166`, `app/mixins/order_sync.py:167`).
- 영향:
  - `_pending_order_state`에 잔존 상태가 남고, 이후 `_holding_or_pending_count` 집계 왜곡 가능.
- 재현 조건:
  - 유니버스에 없는 코드로 수동 매수 성공.
- 권장 조치:
  - 유니버스 외 수동 주문은 별도 상태 채널로 분리하거나 즉시 만료 처리.
  - pending 청소 주기(만료 스윕) 추가.
- 우선순위: 높음(2순위).

### [P1-3] 시간대 전략 목표가가 시작 시점 위주 1회 계산 구조

- 근거:
  - 시간대 K 함수 존재 (`strategy_manager.py:1055`) + 목표가 계산에 반영 (`strategy_manager.py:1088`, `strategy_manager.py:1089`).
  - 목표가 계산 호출이 시작/초기화 지점에 집중 (`app/mixins/trading_session.py:202`, `app/mixins/trading_session.py:391`).
- 영향:
  - 장중 시간대 전환(공격/기본/보수) 의도가 즉시 반영되지 않을 수 있음.
- 재현 조건:
  - 장 초반 시작 후 장중 시간대가 바뀌는 동안 target 재계산이 없는 경우.
- 권장 조치:
  - 시간 구간 경계(09:30, 14:30 등)에서 target 재산출 스케줄링.
  - 재산출 이벤트를 진단 로그로 노출.
- 우선순위: 높음(2순위).

### [P2-1] 일일 손실 기준이 주문가능금액 중심으로 왜곡될 수 있음

- 근거:
  - 기준 예수금 세팅: `deposit = info.available_amount` (`app/mixins/api_account.py:222`).
  - 손실률 계산: `daily_realized_profit / daily_initial_deposit` (`app/mixins/system_shell.py:217`).
- 영향:
  - 보유 포지션 비중이 큰 계좌에서 손실률 과대/과소 해석 가능.
- 재현 조건:
  - 주문가능금액과 총자산(평가금액) 괴리가 큰 상태.
- 권장 조치:
  - 리스크 기준 값을 `총자산 기반` 또는 `주문가능금액 기반` 중 설정으로 명시 분리.
- 우선순위: 중간(3순위).

### [P2-2] 설정 기본값 불일치(문서/Config vs 로드 기본)

- 근거:
  - 로드 기본값: `market_limit=30`, `sector_limit=20` (`app/mixins/persistence_settings.py:487`, `app/mixins/persistence_settings.py:491`).
  - Config 기본값: `70/30` (`config.py:275`, `config.py:281`).
- 영향:
  - 신규/누락 키 로드시 의도보다 보수적인 제한이 적용됨.
- 재현 조건:
  - 설정 파일에 해당 키가 없거나 구버전 파일 로드.
- 권장 조치:
  - 로드 기본값을 Config 상수로 통일.
  - 설정 마이그레이션 시 diff 로그 출력.
- 우선순위: 중간(3순위).

### [P2-3] `enable_external_data` 플래그가 실행 경로에서 실질 미사용

- 근거:
  - UI/Config 연동은 존재 (`app/main_window.py:279`, `app/main_window.py:366`).
  - 전략 평가/데이터 수집에서 해당 플래그 소비 경로 부재.
- 영향:
  - 사용자 기대(on/off)가 실제 동작에 반영되지 않음.
- 재현 조건:
  - 플래그를 토글해도 전략 입력 데이터/판단 결과가 동일.
- 권장 조치:
  - 외부데이터 수집 및 전략 입력 파이프라인에서 플래그를 강제 분기.
  - 비활성 상태에서 관련 전략 선택 시 경고/자동 fallback.
- 우선순위: 중간(3순위).

## 4) S11 전용 상세 진단

### 4.1 현재 데이터 계약 불일치

| 구분 | 현재 제공 키 | 전략 요구 키 | 상태 |
|---|---|---|---|
| 투자자 동향 | `individual_net`, `foreign_net`, `institution_net` | `investor_net` | 불일치 |
| 프로그램 동향 | `net` | `program_net` | 불일치 |

### 4.2 실행 경로 공백

- `KiwoomProvider`에 flow 메서드는 있으나, 자동매매 루프(`_on_execution`, `evaluate_buy_conditions`)에 주입되지 않음.
- 결과적으로 `universe`에 `investor_net/program_net`이 채워지지 않아 S11은 사실상 항상 불리한 판정으로 기울 수 있음.

### 4.3 S11 권장 타깃 아키텍처

1. 정규화 레이어
- `normalize_flow(raw_investor, raw_program) -> {investor_net, program_net, external_updated_at}`.

2. 수집 루프
- 종목별 주기 호출(예: 5~15초), 요청 속도 제한, 실패 재시도(backoff), TTL 캐시.

3. 전략 입력 계약
- `universe[code]` canonical 필드 강제.
- 신선도 임계치 초과 시 `stale` 상태로 판단하여 진입 차단.

4. 운영 가드
- S11 선택 + 데이터 미준비 시 주문 차단 및 사용자 로그 안내.

## 5) 즉시 조치(Quick Wins)

1. 매수 차단식 수정
- `required_cash > available_cash`로 수정(0 포함).

2. 주문 이벤트 체결 판정 분리
- 동기화 트리거에서 `ord_qty` 기반 판정 제거, `exec_qty` 중심으로 제한.

3. 유니버스 외 수동주문 pending 누수 방지
- 만료 스윕 또는 별도 상태 저장소 도입.

4. 설정 기본값 즉시 통일
- `market_limit/sector_limit` 로드 기본값을 `Config.DEFAULT_*` 사용으로 정리.

5. S11 보호 가드 추가
- `investor_program_flow` 선택 시 필수 키/신선도 검사 실패 시 매수 평가 스킵 + 경고 로그.

## 6) 구조 개선 로드맵

### Phase 0 (핫픽스, 1~2일)
- P0 2건 우선 수정(현금 가드, S11 기본 가드).
- P1 중 동기화 과발동 수정 포함.

### Phase 1 (안정화, 3~5일)
- S11 데이터 수집/정규화 파이프라인 정식 연결.
- pending 상태 수명주기(state machine) 정리.

### Phase 2 (구조화, 1~2주)
- 전략 capability 매트릭스 도입(실거래 가능/불가 명시 및 강제).
- 외부데이터 계약(주기/TTL/timeout/fallback) 모듈화.
- 종료 flush 정책(비동기/동기 선택) 추가.

## 7) 테스트 보강 항목

1. `S11 키 매핑 테스트`
- 목적: REST raw 키가 canonical(`investor_net/program_net`)로 변환되는지 확인.

2. `S11 데이터 부재 가드`
- 목적: stale/None 상태에서 주문이 차단되는지 확인.

3. `가용현금 0 매수 차단`
- 목적: `virtual_deposit==0`이면 `_execute_buy`가 즉시 종료되는지 확인.

4. `비체결 이벤트 동기화 억제`
- 목적: `ord_qty`만 있는 이벤트가 포지션 동기화를 유발하지 않는지 확인.

5. `수동주문-유니버스외 코드`
- 목적: pending 상태가 누수 없이 종료되는지 확인.

6. `시간대 전략 목표가 갱신`
- 목적: 시간 구간 전환 시 target 재산출 여부 확인.

7. `일일 손실 기준 정합`
- 목적: 손실 한도 기준(주문가능금액 vs 총자산) 계산 일관성 확인.

8. `설정 기본값 일관성`
- 목적: Config 기본값과 로드 기본값이 동일한지 확인.

9. `실거래 전략 가드`
- 목적: sim-only 전략 선택 시 live 시작이 차단되는지 확인.

## 8) 부록(근거 코드 위치)

### 핵심 근거 라인
- S11 요구 키: `strategies/pack.py:116`, `strategies/pack.py:117`
- 투자자/프로그램 raw 키: `api/rest_client.py:744`, `api/rest_client.py:745`, `api/rest_client.py:746`, `api/rest_client.py:778`
- provider 미연결 지점(존재만 함): `data/providers/kiwoom_provider.py:25`, `data/providers/kiwoom_provider.py:30`
- 매수 현금 가드: `app/mixins/execution_engine.py:283`
- 주문 수량 파싱/동기화 트리거: `app/mixins/order_sync.py:79`, `app/mixins/order_sync.py:106`
- 수동주문 pending 설정: `app/mixins/dialogs_profiles.py:161`, `app/mixins/dialogs_profiles.py:163`
- 유니버스 종목만 동기화 배치 등록: `app/mixins/order_sync.py:166`, `app/mixins/order_sync.py:167`
- 시간대 K 함수/적용: `strategy_manager.py:1055`, `strategy_manager.py:1088`, `strategy_manager.py:1089`
- target 계산 호출 지점: `app/mixins/trading_session.py:202`, `app/mixins/trading_session.py:391`
- 일일 손실 기준 입력/계산: `app/mixins/api_account.py:222`, `app/mixins/system_shell.py:217`
- 설정 기본값 불일치: `app/mixins/persistence_settings.py:487`, `app/mixins/persistence_settings.py:491`, `config.py:275`, `config.py:281`
- 외부데이터 플래그 반영만 존재: `app/main_window.py:279`, `app/main_window.py:366`

### 베이스라인 테스트 로그
- 실행: `python -m pytest -q tests/unit`
- 결과: `42 passed`
- 경고: `langsmith.schemas`의 Python 3.14 + pydantic v1 호환 경고 1건(테스트 실패 아님)
