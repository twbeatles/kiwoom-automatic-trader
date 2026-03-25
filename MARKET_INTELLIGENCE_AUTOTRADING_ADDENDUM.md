# 시장 인텔리전스 자동매매 연결 부록

작성일: 2026-03-25  
기준: 현재 코드베이스 실구현

## 1) 문서 목적

이 문서는 시장 인텔리전스가 실제 자동매매 경로에서 어떤 방식으로 주문 차단, 수량 조정, 포지션 방어에 연결되는지 운영 관점에서 정리한다.

## 2) 자동매매 연결 포인트

라이브 경로의 핵심 연결은 아래와 같다.

1. `start_trading()` 이후 시장 인텔리전스 refresh loop 시작
2. `ExecutionEngineMixin._on_execution()` 에서 기본 전략 평가
3. `StrategyManager.evaluate_buy_conditions()` 또는 `StrategyPackEngine.evaluate()` 에서 인텔리전스 guard/filter 합성
4. 통과 시 `size_multiplier`, `portfolio_budget_scale` 반영
5. `decision_audit.jsonl` 기록 후 주문 실행
6. 보유 포지션은 `exit_policy` 에 따라 `reduce_size`, `tighten_exit`, `force_exit` 적용

## 3) 진입 정책 의미

- `allow`: 추가 제약 없음
- `watch_only`: 경고/관찰 위주, 직접 차단은 아님
- `block_entry`: 신규 진입 차단
- `reduce_size`: 신규 진입 수량 축소
- `tighten_exit`: 보유 포지션의 청산 조건 강화
- `force_exit`: 결정론적 고위험 이벤트에서만 허용

## 4) 운영자가 확인해야 할 UI

- `🧠 인텔리전스 설정`
- `🧠 인텔리전스 현황`
- `📼 인텔리전스 리플레이`
- `🩺 시스템 진단`

특히 `📼 인텔리전스 리플레이`에서는 이벤트 로그와 감사 로그를 함께 보고, 어떤 이벤트가 어떤 주문 정책으로 이어졌는지 확인할 수 있다.

## 5) 현재 구현 경계

1. 시장 인텔리전스는 기본 전략을 대체하지 않는다.
- 독립적인 매수 신호 발생기가 아니라 기존 전략 위의 정책 오버레이로 이해해야 한다.

2. `portfolio_budget_scale`는 상태와 수량 계산에 반영된다.
- 다만 `portfolio/allocator.py` 수준의 별도 포트폴리오 엔진과 완전히 통합된 단계는 아니다.

3. SHORT 방향 전략은 현재 실주문 연결 대상이 아니다.
- 실주문 경로는 LONG 진입 중심이며, SHORT 전략은 백테스트/시뮬레이션 범위로 보는 편이 안전하다.

## 6) 운영 체크리스트

1. `feature_flags["enable_external_data"]` 가 켜져 있는지 확인
2. `market_intelligence.enabled` 가 켜져 있는지 확인
3. `소스 상태`가 `fresh` 또는 운영상 허용 가능한 상태인지 확인
4. `자동매매 정책`, `수량 배수`, `청산 정책`, `마지막 이벤트 ID` 를 확인
5. `decision_audit.jsonl` 에 실제 의사결정 스냅샷이 기록되는지 확인

## 7) 관련 파일

- `app/mixins/market_intelligence.py`
- `app/mixins/execution_engine.py`
- `strategy_manager.py`
- `strategies/pack.py`
- `backtest/engine.py`
- `REAL_API_PREPARATION_GUIDE.md`
- `IMPLEMENTATION_REVIEW_2026-03-25.md`
