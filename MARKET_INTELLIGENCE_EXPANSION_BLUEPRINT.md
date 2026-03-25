# 시장 인텔리전스 확장 청사진

작성일: 2026-03-24  
최종 동기화: 2026-03-25  
기준: 현재 코드베이스 실구현 + 한글 UI 개편 반영

## 1) 문서 목적

이 문서는 시장 인텔리전스 계층이 어떤 소스를 수집하고, 어떻게 자동매매 정책으로 변환되며, 어떤 화면과 로그로 검증되는지 설명한다.

현재 저장소 기준으로 시장 인텔리전스는 아이디어 단계가 아니라 실제 주문 경로, 백테스트, 리플레이 화면까지 연결된 상태다.

## 2) 현재 구현 요약

현재 반영된 핵심 항목:

- `TradingConfig.market_intelligence` v6 스키마
- `app/mixins/market_intelligence.py` 전용 믹스인
- NAVER 뉴스, NAVER Datalab, OpenDART, FRED, 선택형 AI provider
- alias-aware 뉴스 질의와 dedup
- provider 상태 `ok_with_data`, `ok_empty`, `error`, `partial` 처리
- `action_policy`, `size_multiplier`, `exit_policy`, `portfolio_budget_scale` 계산
- 전역 `market/sector/theme/symbol` scope 이벤트 로그
- `data/market_intelligence_events.jsonl`
- `data/decision_audit.jsonl`
- `🧠 인텔리전스 설정`
- `🧠 인텔리전스 현황`
- `📼 인텔리전스 리플레이`
- candidate universe 승격
- 백테스트 replay parity

## 3) 자동매매 연결 방식

현재 연결은 아래 체인으로 이해하면 된다.

1. 수집
   - 뉴스
   - 공시
   - 검색량
   - 매크로
   - 선택형 AI 요약
2. 정규화
   - `event_type`
   - `event_severity`
   - `relevance_score`
   - `source_health`
3. 정책 변환
   - `allow`
   - `watch_only`
   - `reduce_size`
   - `tighten_exit`
   - `block_entry`
   - `force_exit`
4. 진입/보유 경로 반영
   - 진입 차단
   - 수량 조절
   - 보유 포지션 축소
   - 트레일링 강화
   - 결정론적 강제 청산
5. 기록/검토
   - 이벤트 JSONL
   - 감사 JSONL
   - 리플레이 탭

## 4) 정책 원칙

### 결정론 우선

- AI보다 규칙 기반 정책이 우선한다.
- 고위험 공시만 `force_exit` 후보가 된다.
- 일반 악재 뉴스/AI 요약은 `reduce_size`, `tighten_exit`까지만 허용한다.

### fail-closed

- 핵심 소스 오류가 있으면 `fresh`로 마감하지 않는다.
- stale/error 상태에서는 신규 진입을 더 보수적으로 본다.
- 청산 경로는 막지 않는다.

### 호재는 단독 매수 트리거가 아님

- 긍정 뉴스는 기본 전략 통과 뒤 수량/우선순위 보정만 한다.
- 시장 인텔리전스 단독으로 매수 신호를 생성하지 않는다.

## 5) 상태 모델 요약

종목별 `market_intel` 주요 필드:

- `status`
- `sources`
- `source_health`
- `news_score`
- `headline_velocity`
- `relevance_score`
- `dart_events`
- `dart_risk_level`
- `event_type`
- `event_severity`
- `macro_regime`
- `theme_score`
- `action_policy`
- `size_multiplier`
- `exit_policy`
- `portfolio_budget_scale`
- `seen_event_ids`
- `last_event_id`
- `ai_summary`

전역 상태:

- `_market_risk_mode`
- `_portfolio_budget_scale`
- `_sector_blocks`
- `_theme_heat_map`
- `_aggregate_news_risk`
- `_candidate_universe`

## 6) 운영 가시성

현재 운영 가시성은 별도 앱이 아니라 기존 UI 확장으로 처리한다.

- `🧠 인텔리전스 설정`: 외부 데이터/AI/차단 임계치 설정
- `🧠 인텔리전스 현황`: 종목별 상태와 소스 상태
- `🩺 시스템 진단`: `소스 상태`, `자동매매 정책`, `수량 배수`, `청산 정책`, `마지막 이벤트 ID`
- `📼 인텔리전스 리플레이`: 최근 이벤트/감사 로그, 시장 리스크 모드, 섹터 차단, 테마 과열, 원본 payload

## 7) 관련 산출물

- `data/market_intelligence_events.jsonl`
- `data/decision_audit.jsonl`
- `data/dart_corp_codes.json`

관련 문서:

- `MARKET_INTELLIGENCE_AUTOTRADING_ADDENDUM.md`
- `REAL_API_PREPARATION_GUIDE.md`
- `PROJECT_STRUCTURE_ANALYSIS.md`

## 8) 검증 기준

2026-03-25 재검증:

- `python -m pytest -q tests/unit`
- 결과: `tests/unit` 전체 104개 테스트 통과

시장 인텔리전스 관련 핵심 검증 범주:

- provider 상태 판정
- scoring/dedup
- policy runtime
- strategy pack 연동
- backtest replay
- settings schema migration

## 9) 남은 운영 과제

1. 실계좌/모의 엔드포인트 정책이 필요하면 키움 측 운영 방식에 맞춰 분기 로직을 명시적으로 완성해야 한다.
2. 라이브 로그 로테이션과 세션 종료 리포트가 추가되면 장기 운영성이 좋아진다.
3. 리플레이 탭에 날짜 필터, diff view, export 기능을 붙이면 세션 리뷰가 더 쉬워진다.
