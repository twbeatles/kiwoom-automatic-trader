# Kiwoom Automatic Trader 프로젝트 구조 분석

작성일: 2026-03-05  
최종 동기화: 2026-03-25  
분석 기준: 실제 저장소 코드 + `README.md`, `CLAUDE.md`, `GEMINI.md`, `STRATEGY_EXPANSION_BLUEPRINT.md`, `MARKET_INTELLIGENCE_EXPANSION_BLUEPRINT.md`, `MARKET_INTELLIGENCE_AUTOTRADING_ADDENDUM.md`, `REAL_API_PREPARATION_GUIDE.md`, `IMPLEMENTATION_REVIEW_2026-03-25.md`

## 1) 요약

현재 프로젝트는 `엔트리 래퍼(키움증권 자동매매.py) + app/mixins 분할 아키텍처 + 전략/백테스트/시장 인텔리전스 sidecar` 구조로 정리되어 있습니다.

실시간 자동매매 핵심 축은 다음과 같습니다.

- UI/상태: `app/main_window.py`, `app/mixins/ui_build.py`
- 세션/수명주기: `app/mixins/trading_session.py`
- 체결 기반 실행 엔진: `app/mixins/execution_engine.py`
- 시장 인텔리전스/리플레이/감사 로그: `app/mixins/market_intelligence.py`
- 전략/포지션 크기 계산: `strategy_manager.py`, `strategies/pack.py`, `portfolio/allocator.py`
- 주문/계좌 동기화 Fail-safe: `app/mixins/order_sync.py`
- 저장/스키마 마이그레이션: `app/mixins/persistence_settings.py`
- API 통신: `api/rest_client.py`, `api/websocket_client.py`
- 백테스트 parity: `backtest/engine.py`

핵심 특징은 기존 가격 기반 전략 엔진 위에 `시장 인텔리전스 -> 정책 계산 -> 주문/감사 로그 -> 리플레이 뷰어` 체인이 실제로 연결되어 있다는 점입니다.

## 2) 실제 코드베이스 규모 (2026-03-25 실측)

패키지별 Python 파일 수와 라인 수:

| 패키지 | py 파일 수 | 라인 수 |
|---|---:|---:|
| `app/` | 19 | 9207 |
| `api/` | 5 | 1755 |
| `tests/` | 59 | 3722 |
| `strategies/` | 4 | 426 |
| `tools/` | 4 | 405 |
| `backtest/` | 2 | 735 |
| `data/` | 10 | 673 |
| `portfolio/` | 2 | 39 |

핵심 파일 Top 10:

1. `app/mixins/market_intelligence.py` (2265)
2. `strategy_manager.py` (1780)
3. `app/mixins/ui_build.py` (1174)
4. `app/mixins/trading_session.py` (1042)
5. `app/mixins/persistence_settings.py` (836)
6. `config.py` (834)
7. `api/rest_client.py` (807)
8. `backtest/engine.py` (803)
9. `app/mixins/execution_engine.py` (756)
10. `app/main_window.py` (734)

## 3) 엔트리포인트와 조립 구조

### 엔트리

- `키움증권 자동매매.py`
  - `QApplication` 생성
  - 전역 예외 훅 설정
  - `app.main_window.KiwoomProTrader` 표시

### 조립 클래스

- `app/main_window.py`
  - `KiwoomProTrader`는 다수 믹스인을 다중상속으로 조립
  - 공용 상태:
    - `_global_risk_mode`
    - `_market_risk_mode`
    - `_portfolio_budget_scale`
    - `_sector_blocks`
    - `_theme_heat_map`
    - `_aggregate_news_risk`
    - `_candidate_universe`
  - 공용 시그널:
    - `sig_log`
    - `sig_execution`
    - `sig_order_execution`
    - `sig_update_table`

### 믹스인 책임

- `ui_build.py`: 메인 탭, 초보자용 핵심 설정, 상세 설정 하위 탭, 진단 표 구성
- `api_account.py`: API 연결, 계좌정보, 실거래 가드
- `trading_session.py`: 시작/중지, 유니버스 초기화, 시간청산, 지수 상태 반영
- `execution_engine.py`: 틱 기반 매수/매도 판단, 시장 인텔리전스 정책 실행, 감사 로그 호출
- `market_intelligence.py`: 뉴스/공시/트렌드/매크로 수집, 정책 계산, 후보 유니버스, 이벤트/감사 리플레이
- `order_sync.py`: 주문/체결 이벤트 반영, 포지션 동기화, sync 실패 차단
- `persistence_settings.py`: 설정 저장/복원, 스키마 마이그레이션, keyring 연동
- `dialogs_profiles.py`: 프리셋/프로필/수동주문/예약
- `market_data_tabs.py`: 차트/호가/조건검색/순위 탭과 후보 유니버스 갱신 훅
- `system_shell.py`: 로깅/트레이/타이머/종료 플로우
- `app/support/ui_text.py`: 한글 표시 라벨, 콤보박스 표시값/실제값 분리 헬퍼

## 4) 런타임 핵심 플로우

### A. 연결

1. `connect_api()` 호출
2. Worker 스레드에서 인증/계좌조회
3. 성공 시 `rest_client`, `ws_client`, 계좌 콤보 반영
4. `_refresh_account_info_async()`로 예수금/총자산 동기화

### B. 매매 시작

1. `start_trading()` 입력 코드 검증
2. 실거래 보호문구 가드 `_confirm_live_trading_guard()`
3. live capability guard:
   - `asset_scope == kr_stock_live`
   - `short_enabled == False`
   - 전략별 `live_supported == True`
4. `_init_universe()`로 가격/거래량/호가/히스토리 초기화
5. `_sync_positions_snapshot()` 성공 후 시작
6. WebSocket 체결/주문체결/지수 구독 시작
7. 시장 인텔리전스 refresh loop와 리플레이 요약 상태가 함께 시작

### C. 실시간 진입/청산

- `ExecutionData` 수신 -> `ExecutionEngineMixin._on_execution()`
- 미보유:
  - 시간대/일일손실/최대보유수/쿨다운/guard 상태 차단
  - `strategy.evaluate_buy_conditions()` 통과 후
  - 시장 인텔리전스 `action_policy`, `size_multiplier`, `portfolio_budget_scale` 적용
  - `decision_audit.jsonl`에 평가 결과 기록 후 주문
- 보유:
  - ATR 손절, 고정 손절, 단계별 익절, 트레일링, 시간청산
  - 시장 인텔리전스 `exit_policy` 적용
  - `reduce_size`, `tighten_exit`, `force_exit`는 정책에 따라 매도 실행

### D. 시장 인텔리전스 -> 자동매매 연결

현재 구현된 연결 체인은 다음과 같습니다.

1. provider 수집
   - 뉴스
   - OpenDART
   - NAVER Datalab
   - FRED
   - 선택형 AI
2. 정규화/정책 계산
   - `status`, `sources`, `relevance_score`
   - `event_type`, `event_severity`
   - `action_policy`, `size_multiplier`, `exit_policy`
3. 글로벌 집계
   - `market_risk_mode`
   - `portfolio_budget_scale`
   - `sector_blocks`
   - `theme_heat_map`
   - `aggregate_news_risk`
4. 라이브 적용
   - 진입 차단
   - 소프트 사이징
   - 보유 포지션 방어
5. 운영 가시성
   - `data/market_intelligence_events.jsonl`
   - `data/decision_audit.jsonl`
   - `📼 인텔리전스 리플레이` 탭

### E. 종료

- `stop_trading()`에서 구독 해제/타이머 정리/reserved cash 환원
- `closeEvent()`에서 트레이 최소화/종료 정리/내역 flush 처리

## 5) 상태 모델 핵심

### universe 엔트리 주요 필드

- 가격/지표: `current`, `open`, `prev_close`, `prev_high`, `prev_low`, `target`
- 히스토리: `price_history`, `minute_prices`, `daily_prices`, `high_history`, `low_history`
- 거래량/유동성: `current_volume`, `avg_volume_5`, `avg_volume_20`, `avg_value_20`
- 체결/호가: `ask_price`, `bid_price`
- 포지션: `held`, `buy_price`, `invest_amount`, `buy_time`
- 리스크/상태: `status`, `max_profit_rate`, `cooldown_until`, `breakout_hits`, `partial_profit_levels`
- 외부데이터 호환 필드: `external_status`, `external_updated_at`, `external_error`
- 시장 인텔리전스:
  - `status`, `updated_at`, `source_health`
  - `news_score`, `news_sentiment`, `headline_velocity`, `relevance_score`
  - `dart_events`, `dart_risk_level`, `event_type`, `event_severity`
  - `theme_score`, `theme_keywords`, `macro_regime`
  - `action_policy`, `size_multiplier`, `exit_policy`, `portfolio_budget_scale`
  - `seen_event_ids`, `last_event_id`, `last_position_action_event_id`
  - `briefing_summary`, `ai_summary`

### 전역 상태

- `_global_risk_mode`: v4 guard 종합 모드
- `_market_risk_mode`: market intelligence 기반 시장 레짐
- `_portfolio_budget_scale`: 전체 포트폴리오 사이징 축소 비율
- `_sector_blocks`: 섹터 단위 진입 차단 상태
- `_theme_heat_map`: 테마 강도 집계
- `_aggregate_news_risk`: 시장 전체 뉴스 리스크 합산
- `_candidate_universe`: 이벤트 기반 승격 후보 종목

## 6) 백테스트/리플레이 구조

- `backtest/engine.py`는 `market`, `sector`, `theme`, `symbol` scope 이벤트를 재생
- payload 기반 신규 스키마와 legacy `raw_ref` 기반 기록을 모두 읽음
- 라이브와 동일하게 `action_policy`, `exit_policy`, `size_multiplier`, `portfolio_budget_scale`를 합성
- `force_exit`는 결정론적 고위험 공시에만 허용
- `📼 인텔리전스 리플레이` 탭은 라이브 로그를 그대로 읽어 최근 이벤트, 감사 로그, 시장 리스크 요약을 표시

## 7) 저장 산출물과 운영 문서

주요 로컬 산출물:

- `kiwoom_settings.json`
- `kiwoom_token_cache.json`
- `data/market_intelligence_events.jsonl`
- `data/decision_audit.jsonl`
- `data/dart_corp_codes.json`

운영/설계 문서:

- `README.md`
- `CLAUDE.md`
- `GEMINI.md`
- `STRATEGY_EXPANSION_BLUEPRINT.md`
- `MARKET_INTELLIGENCE_EXPANSION_BLUEPRINT.md`
- `MARKET_INTELLIGENCE_AUTOTRADING_ADDENDUM.md`
- `REAL_API_PREPARATION_GUIDE.md`
- `IMPLEMENTATION_REVIEW_2026-03-25.md`

## 8) 검증 현황

2026-03-25 재검증:

- 명령: `python -m pytest -q tests/unit`
- 결과: `tests/unit` 전체 104개 테스트 통과
- 로컬 재실행 시간: 약 27.8초

이번 재검증에서 함께 정리된 회귀:

- 진단 컬럼 인덱스 변경에 맞춘 테스트 정리
- `settings_version = 6` 기대값 반영
- `ExecutionEngineMixin`의 `get_market_position_defense_policy` 하위 호환 처리

## 9) 문서-코드 동기화 메모

2026-03-25 기준 canonical 정합성:

- canonical 설정 스키마: `settings_version = 6`
- 시장 인텔리전스는 `soft_scale`, `position_defense`, `portfolio_budget`, `candidate_universe`, `replay`를 포함
- 운영 로그는 `market_intelligence_events.jsonl` + `decision_audit.jsonl` 이중 구조
- UI는 `🎯 핵심 설정`, `🛠 상세 설정`, `🧠 인텔리전스 설정`, `🧠 인텔리전스 현황`, `📼 인텔리전스 리플레이`, `🔐 API/알림` 기준으로 설명
- 실제 API 준비는 `REAL_API_PREPARATION_GUIDE.md`를 기준 문서로 사용

## 10) 후속 고도화 지점

1. 실계좌/모의 분기 엔드포인트가 키움 정책상 더 필요하면 `chk_mock`와 인증/REST/WSS URL을 완전히 연결해야 함
2. 라이브 운영용 로그 로테이션과 장중 세션 리포트 자동 저장이 있으면 장기 운영성이 좋아짐
3. candidate universe 승격 종목의 자동 강등/만료 규칙을 운영 결과로 더 다듬을 수 있음
4. `📼 인텔리전스 리플레이` 탭에 일자별 필터와 diff view를 추가하면 세션 리뷰 효율이 올라감
5. `portfolio/allocator.py`, `portfolio_mode`, `enable_backtest`는 현재 구조상 확장 경로로 존재하지만, 실주문 수량 계산과 직접 결합된 상태는 아니므로 phase-2 연결 여부를 계속 추적해야 함
6. `분할 매수`는 UI/설정/헬퍼 계층까지 연결되어 있으나 주문 라우팅 단계의 실제 분할 제출은 아직 별도 구현이 필요함
