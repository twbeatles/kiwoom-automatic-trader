# 기능 구현 관점 점검 메모

작성일: 2026-04-08  
기준 문서: `README.md`, `CLAUDE.md`, `REAL_API_PREPARATION_GUIDE.md`  
검토 범위: 예약 매매, 수동 주문, 분할 매수, SHORT 전략 경계, 연구용 백테스트 설정 표시

2026-04-12 재확인 메모:

- 2026-04-08 시점의 핵심 지적사항은 코드에 반영된 상태를 유지하고 있다.
- 다만 이후 코드에는 `api/endpoints.py`, `external_positions`, 종료 시 주문 정리, Telegram notifier 재초기화 등 추가 구현이 더 들어갔고, 이 문서도 그 사실을 반영해 보강했다.

## 반영 완료

### 1. 예약 매매 상태 고착 수정

- 예약 타이머가 `start_trading()` 을 호출할 때 시작 성공 시점에만 `schedule_started = True` 로 전환되도록 교정했다.
- 시작 실패 후에도 다음 타이머 tick 에서 재시도 가능하도록 `schedule_started`, `_trading_start_inflight`, `_scheduled_start_requested` 상태를 정리했다.

### 2. 수동 주문 보호/검증 강화

- 실계좌 수동 주문은 주문마다 `_confirm_live_trading_guard()` 를 다시 통과해야 한다.
- 수동 주문 요청은 6자리 숫자 코드, 지정가 1원 이상, 예상 필요금액 검증을 통과해야 한다.
- 수동 매수 성공 시 예약금을 즉시 반영하고, 유니버스 외 종목도 `_manual_pending_state` 와 reserved cash 로 추적한다.

### 3. SHORT 전략 자동매매 차단

- `pairs_trading_cointegration`, `stat_arb_residual`, `ff5_factor_ls` 는 자동매매 비지원/백테스트 전용으로 고정했다.
- 전략 선택 UI 라벨에 백테스트 전용 표기를 추가했고, `start_trading()` 은 해당 전략 선택 시 자동매매 시작을 차단한다.

### 4. 분할 매수 실주문 연결

- `use_split=True` 이고 주문 방식이 `limit` 일 때 child 지정가 주문을 즉시 다건 제출하도록 연결했다.
- child 주문별 order number, 예약금, pending 상태를 aggregate pending 구조로 추적한다.
- 일부 child reject/cancel 시 남은 child 주문은 유지하고, 취소/거부된 slice 의 예약금만 환원한다.

### 5. 연구용 설정 상태 표기

- `portfolio_mode`, `enable_backtest`, 백테스트 시간 단위/조회 기간/수수료/슬리피지 UI는 유지하되 연구용/미연결 상태를 명시했다.
- README 에 capability matrix 를 추가해 `UI 노출`, `설정 저장`, `자동매매 연결`, `백테스트/연구`, `테스트 커버` 상태를 한눈에 보이도록 정리했다.

## 현재 남아 있는 경계

- `portfolio_mode`, `enable_backtest`, `backtest_config`, `portfolio/allocator.py`, `EventDrivenBacktestEngine` 는 여전히 UI 직접 실행 경로에 연결되지 않았다.
- SHORT 방향 전략은 자동매매에서 차단만 했고, 실시간 실행 엔진이 direction 을 전달하는 구조 확장은 아직 하지 않았다.
- 백테스트 엔진과 UI 실행/결과 뷰 연결은 후속 구현 범위다.

## 2026-04-12 추가 반영 사항

### 1. API 모드 라우팅 정합화

- `api/endpoints.py` 를 추가해 live/mock REST/WebSocket 엔드포인트와 토큰 캐시 파일을 분리했다.
- `KiwoomAuth`, `KiwoomRESTClient`, `KiwoomWebSocketClient` 가 이 라우팅 결과를 공통으로 사용한다.

### 2. 유니버스 외 보유 종목 추적 확대

- 계좌 스냅샷 동기화는 유니버스 외 보유 종목을 `external_positions` 에 `read_only=True` 상태로 유지한다.
- 진단 표/상세 패널/수동 매도 가능수량 확인은 `external_positions` 를 함께 참조한다.
- 시간청산과 긴급 전체 청산은 현재 `external_positions` 까지 포함해 대상을 수집한다.

### 3. 종료 시 활성 주문 정리

- `stop_trading()` 와 긴급청산 경로는 활성 주문 취소를 먼저 시도하고, unresolved 건은 로컬 pending/manual pending/reserved cash 정리로 마무리한다.
- split child 주문, 일반 pending 주문, 유니버스 외 수동 주문을 각각 구분해 정리한다.

### 4. 수동 매도 검증 강화

- 수동 매도는 최신 계좌 포지션의 `available_qty` 를 우선 조회해 초과 주문을 차단한다.
- 이번 재확인 과정에서 매도 검증 분기 문자열이 깨져 있던 버그를 수정했고, 회귀 테스트를 추가했다.

### 5. 연결 재설정 상태 정리

- API 재연결 또는 연결 해제 시 기존 Telegram notifier 를 명시적으로 중지/교체하도록 정리했다.
- 연결 해제 시 `external_positions` 와 진단 캐시도 함께 초기화한다.

## 검증

- `python -m pytest -q tests/unit` 통과
- `python -m compileall -q app api data backtest strategies portfolio dialogs ui_dialogs.py strategy_manager.py tests/unit` 통과
- 현재 기준 `tests/unit` 전체 120개 테스트 통과

## 이번에 추가한 회귀 테스트 포인트

- 예약 매매 시작 실패 후 다음 tick 재시도
- 실계좌 수동 주문의 주문별 보호 확인
- 수동 주문 코드/지정가 검증
- 수동 매도 가능수량 초과 주문 차단
- 유니버스 외 수동 매수 예약금 정합성
- 유니버스 외 수동 매수 체결 시 `external_positions` 승격
- `stop_trading()`/긴급청산 경로의 활성 주문 정리
- 분할 매수 child 주문 제출 및 일부 reject 환원
- SHORT 전략의 자동매매 시작 차단
