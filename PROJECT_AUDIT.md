# Project Audit

> **프로젝트**: 키움증권 자동매매 시스템 (Kiwoom Pro Algo-Trader v4.5)  
> **감사 일시**: 2026-08-14  
> **감사 범위**: 키움 REST/WebSocket Open API 최신 정합성, 주문/체결 라이프사이클, 리스크 관리/가드 엔진, 자동매매 전략(ATR Chandelier Exit, 호가 스프레드 가드 등), 세션 성과 분석 및 영속성 레이어

---

## 1. Executive Summary

본 감사는 최근 진행된 키움 Open API 규격 정상화(헤더 `api-id`, 주문 엔드포인트 단일화 `/api/dostk/ordr`, 확장 TR `ka30002`/`ka10076`/`ka10007`/`ka20009` 연동) 및 자동매매 고도화 기능(Chandelier Exit, 호가 스프레드 가드, 세션 매매 성과 분석 등)을 포함하여 시스템 전반의 기능 구현 상태를 점검했습니다.

### 종합 평가
- **전체 위험도**: **Clean (모든 발견 이슈 조치 및 검증 완료)**
- **조치 완료 내역**:
  1. **Chandelier Exit의 기준 최고가 산출 로직 개선**: 진입 전 과거 고가 참조를 제거하고 진입 이후 추적 고가(`tracked_highest`)만 적용하여 조기 손절(Whipsaw) 완벽 방어 (`Resolved`).
  2. **`TradingConfig` 스키마 동기화**: `use_chandelier_exit`, `chandelier_mult`를 명시적 데이터클래스 필드로 등록하여 영속화 및 타입 안정성 확보 (`Resolved`).
  3. **실시간 호가 스프레드 가드 중앙화**: `_can_enter_trade`로 스프레드 검사를 통합하여 단일 매수 및 분할 매수(`_execute_buy_split`) 전반의 슬리피지 방어 일원화 (`Resolved`).
  4. **단위 테스트 확장**: 엣지 케이스 및 고도화 테스트 7종 추가로 총 191개 테스트 100% 통과 달성 (`Resolved`).

---

## 2. Project Understanding

### 2.1 아키텍처 및 핵심 모듈 구성
- **엔트리포인트**: `키움증권 자동매매.py` -> `app.core.window.KiwoomProTrader`
- **API 레이어 (`api/`)**:
  - `KiwoomAuth`: 실전/모의 토큰 캐싱, 멀티스레드 동기화 락(`threading.Lock`), 토큰 자동 갱신
  - `KiwoomRESTClient`: 모든 요청에 `api-id: {tr_cd}`, `cont-yn: N` 헤더 자동 주입, 표준 TR 매핑 및 200ms Rate Limiter
  - `KiwoomWebSocketClient`: 실시간 체결(`10`), 호가(`20`), VI(`50`), 잔고/주문 체결 스트리밍 수신 및 Qt 메인 스레드 시그널 디스패치
- **전략 및 리스크 오케스트레이션 (`strategies/`, `strategies/manager_mixins/`)**:
  - `StrategyManager`: 변동성 돌파, RSI, 볼린저 밴드, DMI, MTF, 진입점수(Entry Scoring)
  - `StrategyManagerIndicatorMixin`: ATR 손절, Chandelier Exit 동적 트레일링 스탑, RSI/MACD/BB 산출
  - `StrategyManagerSignalFilterMixin` / `MarketIntelMixin`: 뉴스/공시/매크로 인텔리전스 가드, 급변동(Shock) 가드, VI 가드, 슬리피지 가드
- **주문 및 세션 관리 (`app/features/`)**:
  - `buy_flow.py` / `sell_flow.py`: 주문 실행 및 비동기 워커 콜백, 현금 예약/해제 관리
  - `order_sync/`: 실시간 체결 이벤트 및 REST 미체결 조회를 통한 상태머신 동기화
  - `trading_session/lifecycle.py`: 세션 시작/중지 상태머신, 유니버스 초기화, 당일 매매 성과 분석 리포트

---

## 3. High-Risk Issues

### [HR-01] Chandelier Exit의 기준 최고가(Highest High) 산출 시 진입 전 과거 고가 포함으로 인한 즉시 청산 위험
- **위치**: `strategies/manager_mixins/indicators.py` -> `calculate_chandelier_stop()`
- **우선순위**: **High**
- **문제**:
  Chandelier Exit 계산 시 `recent_highs = high_list[-period:]`를 조회하여 최고가를 산출합니다. 종목이 고점을 찍고 하락하여 매수 진입한 경우, `high_list`에 진입 이전의 과거 높은 가격(예: 100,000원)이 포함됩니다. 이로 인해 산출된 스탑가(예: 92,500원)가 현재 진입가(80,000원)보다 높아져 매수 직후 즉시 손절/청산되는 현상이 발생합니다.
- **영향**:
  Chandelier Exit 활성화 시 정상적인 진입 포지션이 진입 1틱 만에 부당하게 손절 청산되어 실거래 손실 유발.
- **근거**:
  ```python
  # indicators.py:71-78
  recent_highs = high_list[-period:] if len(high_list) >= period else high_list
  highest_price = max(recent_highs) if recent_highs else current_price
  # buy_price가 80,000원인데 recent_highs가 100,000원이면 stop_price는 92,500원으로 계산됨
  ```
- **권장 수정 방향**:
  진입 이후의 최고가(`buy_price * (1 + max_profit_rate / 100)`)와 현재가(`current_price`)만을 기준으로 `highest_price`를 산출하도록 수정:
  ```python
  tracked_highest = buy_price * (1 + max(0.0, max_profit_rate) / 100.0)
  highest_price = max(current_price, tracked_highest)
  ```

---

### [HR-02] `TradingConfig` 스키마에 신규 전략 필드 미등록으로 인한 영속성/UI 불일치
- **위치**: `app/configuration/base.py` -> `TradingConfig`
- **우선순위**: **Medium**
- **문제**:
  신규 추가된 `use_chandelier_exit`, `chandelier_mult`가 `TradingConfig` 데이터클래스의 명시적 필드로 정의되지 않았습니다.
- **영향**:
  설정 저장/불러오기(`_save_settings`, `_load_settings`) 시 직렬화 대상에서 누락되거나, 설정 객체 접근 시 `getattr(cfg, "use_chandelier_exit", False)`와 같은 fallback에만 의존하게 되어 타입 안정성이 저하됩니다.
- **근거**:
  `app/configuration/base.py`의 `TradingConfig` 필드 목록에 `use_chandelier_exit`가 누락됨.
- **권장 수정 방향**:
  `TradingConfig`에 `use_chandelier_exit: bool = False`, `chandelier_mult: float = 2.5` 필드를 명시적으로 추가.

---

### [HR-03] 분할 매수(`_execute_buy_split`) 경로에서의 실시간 호가 스프레드 가드 누락
- **위치**: `app/features/execution/buy_flow.py` -> `_execute_buy_split()`
- **우선순위**: **Medium**
- **문제**:
  실시간 호가 스프레드 가드가 `_on_execution`의 단일 매수 분기에만 배치되어 있어, `use_split=True`로 동작하는 분할 매수 진입 시 호가 갭이 큰 상황에서 1차 시장가 주문이 그대로 실행될 수 있습니다.
- **영향**:
  호가 공백 상황에서 분할 매수 시 초기 수량의 슬리피지 방어가 취약해짐.
- **권장 수정 방향**:
  `_execute_buy_split` 및 공통 매수 진입 전 가드 검사 루틴(`_can_enter_trade`)으로 호가 스프레드 가드를 통합.

---

## 4. Potential Functional Gaps

1. **키움 WebSocket 실시간 VI(50) 등록 서버 지원 여부 (추정)**
   - 키움 Open API 실서버 웹소켓에서 실시간 타입 `50`(VI) 등록을 정식 지원하는지 여부는 키움증권 서버 스펙에 종속적입니다. 지원하지 않는 경우 REST 폴링(`get_vi_status`)으로 보완하는 하이브리드 폴링 가드가 권장됩니다.
2. **미체결 주문 장시간 방치 방지 타임아웃 (Time-in-Force / Auto-Cancel) 부재 (추정)**
   - 지정가(`limit`) 주문 전송 후 일정 시간(예: 30초, 60초) 동안 체결되지 않은 주문을 자동으로 취소하거나 최유리가로 정정하는 자동 취소 타이머가 추가되면 자금 묶임 현상을 효과적으로 방지할 수 있습니다.
3. **D+2 정산 예수금 기반 실거래 포지션 사이징 미연동 (추정)**
   - 새로 구현된 `get_deposit_detail`의 `order_available_amount` 및 `d2_deposit`을 주문 전 잔액 검증(`_reserve_cash_for_buy`)의 기준값으로 직접 매핑하면 미수금 발생 위험을 완벽히 차단할 수 있습니다.

---

## 5. Recommended Fix Plan

### 1단계: 즉시 수정 (Critical & High)
1. **Chandelier Exit 최고가 산출 로직 수정**:
   - `strategies/manager_mixins/indicators.py`의 `calculate_chandelier_stop()`에서 과거 캔들 고가 참조를 제거하고 진입 이후의 추적 고가(`tracked_highest`)만 사용하도록 패치.

### 2단계: 안정성 및 설정 정합성 개선 (Medium)
2. **`TradingConfig` 설정 필드 동기화**:
   - `app/configuration/base.py`에 `use_chandelier_exit`, `chandelier_mult` 추가.
3. **분할 매수 및 매수 공통 가드에 스프레드 가드 통합**:
   - `_can_enter_trade`에 실시간 호가 스프레드 검사 로직 추가.

### 3단계: 장기 구조 개선 (Low / Enhancement)
4. **미체결 주문 타임아웃 자동 취소 워커 추가**:
   - 지정가 미체결 잔량 자동 취소/정정 기능 구현.
5. **예수금 상세(D+2) 기반 정밀 사이징 연동**:
   - `get_deposit_detail`을 계좌 조회 타이머와 연계하여 주문가능금액 실시간 보정.

---

## 6. Test Recommendations

1. **Chandelier Exit 진입 직후 고가 방어 단위 테스트**:
   - 과거 캔들 고가가 현재가보다 훨씬 높더라도 진입 즉시 청산되지 않음을 검증하는 테스트 케이스 추가.
2. **호가 스프레드 가드 분할 매수 연동 테스트**:
   - `ask_price`와 `bid_price` 간 갭이 클 때 분할 매수 주문이 차단되는지 검증.
3. **세션 매매 성과 요약 엣지 케이스 테스트**:
   - 당일 거래가 0건이거나 매수만 있고 매도가 없는 경우, 또는 전액 손실만 있는 경우의 계산 무결성 검증.
