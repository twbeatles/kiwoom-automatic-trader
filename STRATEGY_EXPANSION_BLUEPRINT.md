# 급변동/가드/전략 확장 청사진

작성일: 2026-03-05  
최종 동기화: 2026-03-25  
기준: 현재 코드베이스 실구현 + 한글 UI 개편 반영

## 1) 문서 목적

이 문서는 현재 전략 엔진, v4 가드 계열, 시장 인텔리전스 방어 정책이 실제 자동매매 경로에서 어떻게 합성되는지 설명한다.  
현재 저장소 기준으로 전략 확장은 이미 구현 단계에 들어가 있으며, 본 문서는 운영/검증 기준 문서로 유지한다.

## 2) 현재 구현 상태 요약

- canonical 설정 스키마: `settings_version = 6`
- 정책 철학: `Fail-Closed`
- 전략 엔진, v4 가드, 시장 인텔리전스가 진입 게이트에서 함께 합성
- 라이브/전략팩/백테스트 의미를 최대한 일치시킴

핵심 구현 완료 항목:

1. Shock guard
2. VI/HALT guard + reopen cooldown
3. ATR 기반 regime sizing
4. liquidity stress guard
5. slippage guard
6. order health degraded 모드
7. 시장 인텔리전스 `block_entry/reduce_size/tighten_exit/force_exit` 연동
8. `decision_audit.jsonl` 기록과 `📼 인텔리전스 리플레이` 탭 검토 흐름

## 3) 실제 진입 순서

현재 진입 경로는 아래 순서로 이해하는 것이 맞다.

1. 가격/거래량/기술지표 기반 기본 전략 평가
2. v4 guard 계열 차단 여부 확인
3. 시장 인텔리전스 `action_policy` 적용
4. `size_multiplier`, `portfolio_budget_scale` 적용
5. 주문 실행 정책(`market`/`limit`) 적용
6. `decision_audit.jsonl` 기록 후 주문 실행

즉 시장 인텔리전스는 독립 매수 엔진이 아니라, 기존 전략이 통과한 이후 최종 진입 정책을 더 보수적이거나 약간 더 공격적으로 조정하는 계층이다.

## 4) 보유 포지션 방어

현재 보유 포지션에는 다음 정책이 연결된다.

- `watch_only`: 경고와 관찰만 수행
- `reduce_size`: 보유 수량 일부 축소
- `tighten_exit`: 트레일링/청산 조건 강화
- `force_exit`: 결정론적 고위험 공시에 한해서만 허용

강한 제약:

- 일반 뉴스나 AI 결과만으로는 `force_exit`를 직접 허용하지 않는다.
- AI는 보조 해석 도구이며 최종 권한은 규칙 기반 정책이 가진다.

## 5) 관련 설정 키

- `use_shock_guard`
- `use_vi_guard`
- `use_regime_sizing`
- `use_liquidity_stress_guard`
- `use_slippage_guard`
- `use_order_health_guard`
- `market_intelligence.soft_scale`
- `market_intelligence.position_defense`
- `market_intelligence.portfolio_budget`

마이그레이션 정책:

- `settings_version < 6` 파일은 로드 시 누락 키만 default 보강
- 기존 사용자 값 우선
- `betting_ratio` canonical 유지

## 6) UI/운영에서 보는 위치

- `🎯 핵심 설정`: 초보자용 기본 수치
- `🛠 상세 설정 > 시장 급변동 보호`: v4 guard 계열 설정
- `🧠 인텔리전스 설정`: 외부 데이터/AI/차단 임계치 설정
- `🧠 인텔리전스 현황`: 종목별 정책/점수/소스 상태
- `📼 인텔리전스 리플레이`: 이벤트/감사 로그 재생
- `🩺 시스템 진단`: 종목별 보호 사유, 자동매매 정책, 동기화 상태

## 7) 구현 파일 맵

- `config.py`: 기본값과 v6 스키마
- `strategy_manager.py`: 전략 평가, 점수화, 수량 계산
- `strategies/pack.py`: 전략팩/리스크 오버레이
- `app/mixins/execution_engine.py`: 진입 게이트, 포지션 방어 실행
- `app/mixins/trading_session.py`: 세션/지수 상태 반영
- `app/mixins/order_sync.py`: `sync_failed` 차단
- `backtest/engine.py`: guard + market intelligence parity replay

## 8) 검증 기준

2026-03-25 재검증:

- `python -m pytest -q tests/unit`
- 결과: `tests/unit` 전체 104개 테스트 통과

대표 검증 범주:

- shock/VI/reopen cooldown
- slippage/liquidity/order health
- settings schema migration
- strategy pack overlays
- backtest guard parity
- market intelligence policy runtime

## 9) 후속 고도화 과제

1. 공식 시장상태 API 품질이 더 좋아지면 proxy 비중을 줄일 수 있다.
2. `reopen_cooldown` 구간의 점수/틱/수량 가중을 더 세분화할 수 있다.
3. 세션/일자 단위 가드 KPI 자동 리포트가 추가되면 운영성이 좋아진다.
4. 실계좌 운영 결과를 바탕으로 `reduce_size` 비율과 `tighten_exit` 파라미터를 더 미세 조정할 수 있다.
