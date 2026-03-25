# 기능 구현 관점 점검 메모

작성일: 2026-03-25  
검토 기준 문서: `CLAUDE.md`, `README.md`, `STRATEGY_EXPANSION_BLUEPRINT.md`  
검토 범위: 자동매매 시작/주문/동기화/시장 인텔리전스/설정/UI 초기화/수동 주문/전략팩

## 확인한 검증

- `python -m pytest -q tests/unit` -> 전체 통과
- `python -m compileall -q app api data backtest strategies portfolio` -> 통과
- 오프스크린 UI 초기화 스모크 테스트 -> 실패
  - `KiwoomProTrader()` 생성 시 `app/mixins/ui_build.py:571` 에서 `Config.DEFAULT_SPLIT_DROP_PERCENT` 참조로 즉시 예외 발생

## 총평

테스트 커버리지는 주문 동기화, 가드, 설정 마이그레이션, 시장 인텔리전스 쪽이 잘 잡혀 있다. 반면 실제 사용자가 바로 밟는 UI 초기화 경로와, 문서에 노출된 일부 기능의 "실행 경로 연결 여부"는 테스트 사각지대가 있다. 현재 가장 큰 문제는 앱 시작 크래시 1건과, 전략/주문 기능 중 일부가 UI에는 노출되지만 실제 주문 엔진에는 연결되지 않은 점이다.

## 우선순위 높은 이슈

1. 앱이 시작 직후 크래시할 수 있음

근거: `app/mixins/ui_build.py:571` 이 `Config.DEFAULT_SPLIT_DROP_PERCENT` 를 참조하지만, 실제 설정 상수는 `config.py:494` 의 `DEFAULT_SPLIT_PERCENT` 이다.

영향: 신규 실행 환경에서 메인 UI 초기화 자체가 실패한다. 단위 테스트는 이 경로를 직접 생성하지 않아 놓치고 있다.

권장: `Config.DEFAULT_SPLIT_PERCENT` 로 교정하고, `QApplication + KiwoomProTrader()` 오프스크린 스모크 테스트를 CI에 추가하는 것이 맞다.

2. 전략팩의 SHORT 시그널이 런타임에서 매수로 처리될 수 있음

근거: `strategies/pack.py:220-241` 은 `pairs_trading_cointegration`, `stat_arb_residual`, `ff5_factor_ls` 에 대해 `SignalDirection.SHORT` 를 반환한다. 하지만 `strategy_manager.py:1384-1412` 는 전략팩 결과를 `passed/conditions/metrics` 로만 평탄화하고 방향 정보를 버린다. 이후 `app/mixins/execution_engine.py:487-527` 는 `passed == True` 면 항상 `_execute_buy()` 를 호출한다.

영향: 모의투자/시뮬레이션에서 `short_enabled=True` 인 전략을 선택해도 실제로는 숏이 아니라 롱 주문으로 해석될 가능성이 있다. 백테스트 엔진은 `backtest/engine.py:254-344` 에서 `short/cover` 를 지원하므로, 백테스트와 실시간 의미가 어긋난다.

권장: 전략팩 결과에 방향(`long/short/flat`)을 유지한 채 실행 엔진까지 전달하거나, 실시간 엔진이 숏을 지원하기 전까지는 SHORT 가능 전략을 UI에서 완전히 비활성화하는 편이 안전하다.

3. 수동 주문 경로에 실거래 보호와 지정가 검증이 빠져 있음

근거: `app/mixins/dialogs_profiles.py:120-159` 의 수동 주문 경로는 연결 여부만 확인하고 바로 주문을 전송한다. 자동매매 시작 시 사용하는 `_confirm_live_trading_guard()` 호출은 없다. 또한 `ui_dialogs.py:464-482` 는 지정가 주문일 때 가격이 0원이어도 그대로 `order_result` 를 만들어 넘긴다.

영향: 실계좌 연결 상태에서 수동 주문이 자동매매보다 훨씬 약한 보호 수준으로 실행된다. 지정가 0원 주문 같은 잘못된 요청도 API까지 내려갈 수 있다.

권장: 수동 주문에도 별도 실거래 확인 가드를 넣고, 지정가 선택 시 `price > 0` 을 필수 검증해야 한다.

4. `분할 매수` 기능은 문서/UI에 노출되지만 실제 주문 엔진에 연결되어 있지 않음

근거: `strategy_manager.py:1300-1331` 에 `get_split_orders()` 가 존재하고, UI/설정도 `app/mixins/ui_build.py:561-573`, `app/main_window.py:271-273`, `app/mixins/persistence_settings.py` 전반에 연결되어 있다. 하지만 주문 실행 경로는 `app/mixins/execution_engine.py:543-599` 에서 단일 수량으로 한 번만 주문한다. 저장소 전체 검색 기준으로 `get_split_orders()` 는 정의 외 호출이 없다.

영향: 사용자는 분할 매수가 동작한다고 믿지만 실제 체결은 단일 주문으로 나간다. README 기능 설명과 런타임 동작이 어긋난다.

권장: `_execute_buy()` 앞단에서 주문 분할 스케줄을 실제로 생성해 순차 제출하도록 연결하거나, 구현 전까지는 UI/문서에서 기능을 숨기는 것이 낫다.

5. 수동 매수는 예약금과 보유/대기 카운트에 즉시 반영되지 않음

근거: 자동 주문은 `app/mixins/execution_engine.py:581-586` 에서 예약금을 차감하고 `_holding_or_pending_count` 를 즉시 증가시킨다. 반면 수동 주문 성공 경로는 `app/mixins/dialogs_profiles.py:161-176` 에서 `_set_pending_order()` 만 호출하고 예약금 차감이나 카운트 증가를 하지 않는다.

영향: 수동 매수 주문 직후 포지션 동기화가 오기 전까지 자동매매가 남은 현금을 과대평가할 수 있다. 같은 종목 또는 다른 종목에서 과주문 가능성이 생긴다.

권장: 수동 매수도 자동 주문과 동일한 예약금 차감 및 pending count 규칙을 공유하도록 공통화해야 한다.

## 추가 구현이 필요한 부분

1. `portfolio_mode`, `enable_backtest`, `portfolio/allocator.py` 는 현재 UI/설정 대비 실행 경로 연결이 약함

근거: `portfolio/allocator.py:15-48` 에 allocator 구현이 있지만, 저장소 검색 기준 런타임 경로에서 import/use 되지 않는다. `enable_backtest` 는 `config.py`, `app/main_window.py`, 설정 저장/로드 경로에는 있지만 실제 분기에서 소비되지 않는다.

영향: 사용자가 전략팩/포트폴리오/백테스트 관련 옵션을 바꿔도 일부는 효과가 없는 "장식용 설정"이 된다.

권장: 실제 기능을 연결하거나, 아직 phase-2 범위라면 UI에 "준비 중" 표시를 명확히 넣는 편이 혼란을 줄인다.

2. 예약 매매와 실거래 가드의 운영 충돌 가능성

근거: `app/mixins/system_shell.py:191-200` 의 예약 시작은 `start_trading()` 을 그대로 호출한다. `start_trading()` 은 다시 `app/mixins/api_account.py:304-360` 의 실거래 확인 다이얼로그를 띄운다.

영향: 예약 매매를 켜 두어도 실거래에서는 해당 시각에 사용자가 문구를 직접 입력하지 않으면 실제 시작이 막힌다. 트레이 최소화 상태나 무인 운영에서는 특히 혼란이 생길 수 있다.

권장: `예약 실거래는 사전 arm 후 1회만 허용` 같은 운영 모드를 두거나, 현재 정책을 UI에 명확히 고지하는 것이 필요하다.

## 테스트/운영 보강 제안

1. 오프스크린 UI 생성 테스트를 추가해 `KiwoomProTrader()` 초기화 실패를 바로 잡아야 한다.
2. 전략팩 SHORT 시그널에 대해 "실시간 엔진이 LONG으로 오해하지 않는다"는 회귀 테스트가 필요하다.
3. 수동 주문에 대해 실거래 가드, 지정가 유효성, 예약금 반영을 검증하는 테스트가 추가되어야 한다.
4. README/기능표에는 "완전 구현", "부분 구현", "설정만 존재"를 구분한 capability matrix를 두는 편이 좋다.

## 우선 처리 순서 제안

1. UI 시작 크래시 수정
2. 수동 주문 실거래 보호 및 지정가 검증 추가
3. SHORT 방향 처리 또는 UI 차단 중 하나를 명확히 선택
4. 분할 매수/포트폴리오 모드처럼 문서에 노출된 미연결 기능 정리
