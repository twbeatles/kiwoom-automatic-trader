# 기능 구현 점검 리포트 (2026-03-07)

## 참조 문서
- `CLAUDE.md`
- `README.md`

## 점검 범위
- 핵심 런타임: API 연결, 매매 시작/중지, 주문 실행, 체결 동기화, 리스크 가드
- 설정/저장: 설정 스키마(v4), 거래내역 저장
- 전략/백테스트: `strategy_manager.py`, `strategies/pack.py`, `backtest/engine.py`

## 실행 확인
- `python -m pytest -q tests/unit` -> 통과 (83 passed)
- `python tools/refactor_verify.py` -> parity 통과
- `python tools/perf_smoke.py` -> 정상

## 2026-03-09 후속 동기화 메모

- 이 문서는 2026-03-07 시점의 기능 구현 점검 리포트이며, 아래 항목은 이후 코드/문서 동기화 결과입니다.
- repo 전반 정적 분석 기준을 `pyrightconfig.json`으로 고정했고 `pyright .` 결과는 `0 errors, 0 warnings`입니다.
- 동적 Qt mixin 정적 분석용 helper로 `app/mixins/_typing.py`가 추가되었으며 런타임 동작 변경 목적은 아닙니다.
- `KiwoomTrader.spec`, `.gitignore`, 주요 `.md` 문서는 현재 구조와 검증 절차 기준으로 동기화되었습니다.

## 반영 완료 현황 (2026-03-07)

- 단계 1(실거래 코어 안정화) 반영 완료
  - 레짐 사이징 중복 제거 및 전략 경로 일원화
  - `pending_order_state` 상태머신 확장(`submitted/partial/filled/cancelled/rejected/sync_failed`)
  - 부분체결 예약금 정합화(체결분만 차감, 주문 종료 시 최종 정리)
  - 시장/섹터 투자금 원가 기반 장부 감소 보정
  - 쇼크 가드 fallback 시장별 대표 종목 단일 시계열 적용
  - 세션 인입 포지션 `TIME_STOP` 제외, 세션 신규 진입 포지션만 적용
  - 진단 탭 최소 확장(재동기화/`sync_failed` 해제 요청/상세 사유 패널)
- 단계 2(백테스트/저장 신뢰성 강화) 반영 완료
  - 다종목 MTM 최신가 캐시 반영
  - 거래내역 저장 single-writer(순차 저장) 전환
  - 종료 flush 경로 강화(최신 스냅샷 보장)
- 회귀 테스트 보강 완료
  - 주문/동기화 상태머신, 레짐 사이징 1회 적용, 투자금 장부, MTM, 저장 순서/flush, TIME_STOP 정책, sync_failed 수동 해제 안전 규칙 추가 검증

## 잠재 이슈 (기능 구현 관점)

### 1. 레짐 사이징이 일부 경로에서 중복 적용됨 (우선순위: 높음)
- 현상:
  - `execution_engine`에서 수량 계산 후 레짐 스케일을 다시 적용합니다.
  - 그런데 `strategy_manager.calculate_position_size()`와 `_default_position_size()`는 이미 내부에서 레짐 스케일을 적용합니다.
- 근거 코드:
  - `app/mixins/execution_engine.py:389-396`
  - `strategy_manager.py:1113`, `strategy_manager.py:1127`
- 영향:
  - `elevated/extreme` 구간에서 주문 수량이 의도보다 과도하게 줄어들 수 있습니다.
  - 경로별(dynamic vs atr/default) 사이징 일관성이 깨집니다.
- 개선 제안:
  - 레짐 스케일 적용 지점을 1곳으로 단일화(권장: `strategy_manager` 내부로 통합).

### 2. 부분 체결 시 예약금/대기주문 상태를 너무 빨리 해제함 (우선순위: 높음)
- 현상:
  - 체결 수량 증가(`delta > 0`)가 발생하면 예약금을 즉시 전량 해제하고,
  - pending 주문도 바로 제거합니다.
- 근거 코드:
  - `app/mixins/order_sync.py:395`
  - `app/mixins/order_sync.py:453-455`
- 영향:
  - 지정가 주문의 부분 체결 상황에서 미체결 잔량이 남아도 예약금이 풀릴 수 있습니다.
  - 같은 종목/다른 종목에 추가 매수가 허용되어 자금 과할당 리스크가 발생할 수 있습니다.
- 개선 제안:
  - 주문번호 기준 미체결 잔량 추적(remaining qty) 도입.
  - 예약금은 “체결분만 차감, 미체결분은 유지” 방식으로 변경.

### 3. 시장/섹터 투자금 추적이 매도 체결가 기준이라 누적 오차 발생 (우선순위: 중간~높음)
- 현상:
  - 매도 시 `fill_price * sell_qty`를 차감합니다.
  - 손실 매도에서는 매수원가 대비 덜 차감되어 투자금 잔여치가 남습니다.
- 근거 코드:
  - `app/mixins/order_sync.py:406`, `app/mixins/order_sync.py:423-424`
  - `strategy_manager.py:511-517`, `strategy_manager.py:563-569`
- 영향:
  - 실제 포지션이 0이어도 시장/섹터 투자금이 남아 분산 한도 체크가 왜곡될 수 있습니다.
- 개선 제안:
  - 투자금 추적 기준을 “원가 기반 포지션 장부”로 분리.
  - 매도 시 체결대금이 아니라 보유 장부금액(또는 잔여 원가)을 감소시키는 방식으로 변경.

### 4. 백테스트 다종목 평가 시 MTM(평가손익) 정확도가 떨어짐 (우선순위: 높음, 백테스트 신뢰성)
- 현상:
  - 각 바에서 현재 심볼 1개 가격만 전달해 평가하며, 다른 심볼은 진입가를 계속 사용합니다.
- 근거 코드:
  - `backtest/engine.py:194-195`
  - `backtest/engine.py:318-322`
- 영향:
  - 다종목 백테스트에서 equity curve, drawdown, 수익률 지표가 왜곡될 수 있습니다.
- 개선 제안:
  - 심볼별 `last_price` 캐시를 유지하고 MTM 시 전체 심볼 최신가를 사용.

### 5. 거래내역 비동기 저장이 순서 경쟁에 취약함 (우선순위: 중간)
- 현상:
  - `_history_dirty`가 true일 때 매 틱 비동기 저장을 시작하고 즉시 false로 내립니다.
  - 저장 worker 간 완료 순서가 바뀌면 오래된 스냅샷이 마지막에 기록될 수 있습니다.
- 근거 코드:
  - `app/mixins/system_shell.py:239-241`
  - `app/mixins/persistence_settings.py:238-248`, `app/mixins/persistence_settings.py:250-255`
- 영향:
  - 간헐적으로 최신 거래내역 일부가 파일에서 누락될 가능성이 있습니다.
- 개선 제안:
  - 단일 writer 큐(직렬화) 또는 “가장 최신 세대 번호만 쓰기” 방식 도입.
  - 저장 실패 시 `_history_dirty` 재설정으로 재시도 보장.

### 6. 인덱스 피드 미지원 시 쇼크 가드 fallback이 종목간 가격 스케일 혼합 가능 (우선순위: 중간)
- 현상:
  - 인덱스 피드가 없으면 종목 체결가를 시장 대표 시계열로 사용합니다.
  - 5초 간격 샘플링 중 서로 다른 가격대 종목이 섞일 수 있습니다.
- 근거 코드:
  - `app/mixins/execution_engine.py:209-216`
- 영향:
  - 쇼크 감지 수익률(ret_1m/ret_5m)가 비정상적으로 커져 오탐 차단 가능성이 있습니다.
- 개선 제안:
  - fallback 대표 종목을 시장별 1개로 고정하거나, 종목별 시계열 분리 후 지수형 집계 사용.

### 7. 시작 시 보유종목 `buy_time`을 현재 시각으로 초기화함 (우선순위: 중간)
- 현상:
  - 시작 직후 포지션 스냅샷 동기화에서 기존 보유종목의 `buy_time`을 now로 설정합니다.
- 근거 코드:
  - `app/mixins/trading_session.py:628-631`
- 영향:
  - `TIME_STOP` 사용 시 기존 보유 포지션의 보유시간이 리셋되어 청산이 지연될 수 있습니다.
- 개선 제안:
  - API에서 취득 가능하면 실제 매입시각 사용.
  - 불가하면 “세션 인입 포지션” 플래그를 두고 time-stop 정책을 별도 처리.

## 추가하면 좋은 보완 항목
1. 주문 상태머신 강화
- 주문번호 단위의 `submitted/partial/filled/cancelled/rejected`와 미체결 잔량 추적.

2. 백테스트 신뢰도 보강
- 다종목 MTM 회귀 테스트, 가드(Shock/VI/슬리피지/Order health) 패리티 테스트 추가.

3. 저장 안정성 강화
- 거래내역 저장 전용 단일 워커 + 종료 시 flush 완료 확인(ACK) 도입.

4. 운영 안전장치
- `sync_failed` 종목에 대한 UI 재동기화/해제 버튼 및 사유 상세 표시 강화.

## 테스트 보강 우선순위 제안
1. 부분 체결 + 미체결 잔량 + 예약금 유지 시나리오 (실주문 흐름 모사)
2. 레짐 사이징 중복 적용 방지 회귀 테스트
3. 시장/섹터 투자금 장부 정확도(이익/손실 매도 각각) 테스트
4. 다종목 백테스트 MTM 정확성 테스트
5. 거래내역 비동기 저장 순서 역전(의도적 sleep) 테스트
