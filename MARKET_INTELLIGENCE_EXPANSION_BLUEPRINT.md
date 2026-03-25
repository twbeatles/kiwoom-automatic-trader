# 시장 인텔리전스 확장 청사진

작성일: 2026-03-24  
최종 동기화: 2026-03-25  
기준: 현재 코드베이스 실구현

## 1) 문서 목적

이 문서는 현재 저장소에서 `market intelligence` 계층이 어떤 소스와 상태 키를 사용하며, 전략/백테스트/리플레이와 어떻게 연결되는지 정리한다.

## 2) 현재 구현 범위

- canonical 설정 스키마: `settings_version = 6`
- 상위 게이트: `feature_flags["enable_external_data"]`
- 세부 스위치: `market_intelligence.enabled`
- 수집 소스:
  - NAVER 뉴스
  - OpenDART
  - NAVER Datalab
  - FRED
  - 선택형 AI 요약

## 3) 런타임 상태 키

핵심 상태는 `universe[code]["market_intel"]`에 유지된다.

- `status`, `updated_at`, `intel_status`, `intel_error`
- `news_score`, `news_sentiment`, `news_headlines`, `headline_velocity`, `relevance_score`
- `dart_events`, `dart_risk_level`, `dart_block_until`, `event_type`, `event_severity`
- `theme_score`, `theme_keywords`
- `macro_regime`
- `action_policy`, `size_multiplier`, `exit_policy`, `portfolio_budget_scale`
- `seen_event_ids`, `last_event_id`, `last_position_action_event_id`
- `briefing_summary`, `last_alert`, `ai_summary`

## 4) 정책 합성 순서

1. provider별 raw 데이터 수집
2. source status 정규화
3. 뉴스/공시/테마/매크로 점수화
4. `action_policy`, `size_multiplier`, `exit_policy`, `portfolio_budget_scale` 계산
5. 라이브 자동매매/포지션 방어/감사 로그에 반영
6. `📼 인텔리전스 리플레이` 탭과 JSONL 로그에서 재검토

## 5) 로그와 운영 산출물

- 이벤트 로그: `data/market_intelligence_events.jsonl`
- 결정 감사 로그: `data/decision_audit.jsonl`
- DART corp code 캐시: `data/dart_corp_codes.json`

이 로그는 현재 코드에서 리플레이 탭과 백테스트 sidecar replay가 함께 소비한다.

## 6) 라이브 적용 원칙

- 기본 철학은 `Fail-Closed`
- 데이터가 stale/error이면 신규 진입은 보수적으로 차단하고 청산은 허용
- `force_exit`는 고위험 공시 같은 결정론적 이벤트에 한해 허용
- AI는 보조 해석 레이어이며 단독 최종 권한이 아니다

## 7) 백테스트 parity

`backtest/engine.py`는 `BacktestIntelligenceEvent`를 읽어 다음 의미를 재생한다.

- `action_policy`
- `exit_policy`
- `size_multiplier`
- `portfolio_budget_scale`
- scope별(`market`, `sector`, `theme`, `symbol`) 상태 합성

즉 라이브와 백테스트의 시장 인텔리전스 의미를 최대한 맞추는 방향이다.

## 8) 현재 구현 경계

1. `market intelligence`는 독립 매수 엔진이 아니다.
- 기본 전략이 먼저 통과한 뒤 최종 진입 정책을 더 보수적으로 조정하는 계층이다.

2. AI 요약은 기본 `OFF` 기준으로 운영하는 편이 안전하다.
- 현재 구현도 규칙 기반 점수화를 우선으로 두고 있다.

3. `candidate_universe`와 `portfolio_budget`는 상태와 정책 계산에는 연결되어 있다.
- 다만 포트폴리오 전체 할당 로직을 별도 allocator와 완전히 결합한 상태는 아니다.

## 9) 핵심 구현 파일

- `app/mixins/market_intelligence.py`
- `strategy_manager.py`
- `strategies/pack.py`
- `backtest/engine.py`
- `data/providers/news_provider.py`
- `data/providers/dart_provider.py`
- `data/providers/naver_trend_provider.py`
- `data/providers/macro_provider.py`
- `data/providers/ai_provider.py`

## 10) 검증 기준

- `python -m pytest -q tests/unit`
- 대표 범주:
  - `test_market_intelligence_policy_runtime.py`
  - `test_market_intelligence_provider_status.py`
  - `test_market_intelligence_backtest_replay.py`
  - `test_market_intelligence_strategy_pack.py`
