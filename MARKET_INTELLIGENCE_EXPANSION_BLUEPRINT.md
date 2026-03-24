# 시장 인텔리전스 확장 청사진

작성일: 2026-03-24  
분석 기준: `CLAUDE.md`, `README.md`, 현재 코드베이스 실구현  
중점 목표: "프로그램이 시황/뉴스/공시/매크로를 능동적으로 해석하고, 매매 판단에 보조 신호로 반영"하도록 확장

---

## 1) 결론

### 2026-03-24 구현 동기화

현재 문서의 핵심 제안 중 아래 항목은 코드 반영이 끝났다.

- `TradingConfig.market_intelligence` 및 `settings_version = 5`
- `app/mixins/market_intelligence.py` 신규 믹스인
- NAVER 뉴스 / NAVER Datalab / OpenDART / FRED / 선택형 AI provider 추가
- 전용 `🧠 인텔리전스` 탭 및 API 설정 그룹
- `news_risk_guard`, `disclosure_event_guard`, `macro_regime_guard`, `theme_heat_filter`, `intel_fresh_guard`
- `BacktestIntelligenceEvent` 기반 intelligence sidecar replay
- `data/market_intelligence_events.jsonl` 이벤트 로그 및 `data/dart_corp_codes.json` 캐시
- `README.md` / `CLAUDE.md` / `GEMINI.md` / `KiwoomTrader.spec` / `.gitignore` 문서·빌드 정합성 동기화

남은 과제는 운영 고도화 중심이다.

- 전체 테스트 스위트 기준 장전 브리핑/실 API 응답 모킹 범위 추가
- AI 예산/호출 이력 UI 고도화
- JSONL/CSV 리플레이 로더와 세션 리뷰 화면 개선

이 프로젝트는 이미 시황 판단 기능을 붙이기 좋은 구조를 갖고 있다.

- `app/mixins/trading_session.py`에 외부 데이터 비동기 수집 루프가 이미 있다.
- `strategy_manager.py`와 `strategies/pack.py`에 외부 데이터 신선도(`external_data_fresh`)와 전략팩 평가 경로가 이미 있다.
- `data/providers/` 아래에 `DartProvider`, `MacroProvider`, `KiwoomProvider`, `CsvProvider`가 준비되어 있다.
- `app/main_window.py` 진단 탭에는 `external_status`, `external_updated_at`, `market_state`, `guard reason`을 보여줄 기반이 이미 있다.

즉, 새 시스템을 처음부터 만드는 것보다 현재의 `external_data` 경로를 `market intelligence` 계층으로 확장하는 것이 가장 현실적이고 저비용이다.

---

## 2) 현재 코드베이스 진단

### 강점

- 실시간/외부데이터 처리와 UI가 분리되어 있다.
- 전략 평가가 `StrategyManager -> StrategyPackEngine`으로 정리되어 있어 신규 필터/오버레이 추가가 쉽다.
- 설정 저장/복원 스키마(`settings_version = 5`)가 현재 기준으로 안정화되어 있다.
- 백테스트 엔진이 별도 모듈로 분리되어 있어 나중에 외생 이벤트를 붙이기 좋다.
- 외부 데이터가 stale일 때 진입을 보류하는 fail-closed 패턴이 이미 구현되어 있다.

### 약점

- 현재 외부 데이터는 사실상 `investor_net`, `program_net` 두 축에 거의 한정된다.
- `DartProvider`, `MacroProvider`는 존재하지만 실거래 루프에 거의 연결되어 있지 않다.
- 뉴스/공시/시황 요약을 저장하는 canonical 모델이 없다.
- "왜 지금 진입/보류했는가"를 설명해주는 이벤트 레벨 진단이 부족하다.
- 백테스트는 가격 기반 가드에는 강하지만 뉴스/공시 같은 외생 이벤트 재현은 아직 약하다.

---

## 3) 최우선 추가 기능 제안

### F1. 시장 인텔리전스 허브

핵심 아이디어:

- 기존 `external_data`를 단순 수급 조회가 아니라 "시황 인텔리전스 수집 계층"으로 확장한다.
- 종목 단위와 시장 단위 상태를 같은 구조에 적재한다.

수집 대상:

- 키움 투자자/프로그램 수급
- 네이버 뉴스 검색 API 기반 종목 헤드라인
- OpenDART 공시 이벤트
- 네이버 데이터랩 검색어 트렌드
- FRED 기반 거시지표

권장 canonical 필드 예시:

```python
info["market_intel"] = {
    "news_score": 0.0,
    "news_sentiment": "neutral",
    "news_headlines": [],
    "dart_events": [],
    "dart_risk_level": "normal",
    "macro_regime": "neutral",
    "theme_score": 0.0,
    "intel_updated_at": None,
    "intel_status": "idle",
    "intel_error": "",
}
```

왜 적합한가:

- 현재 구조의 `external_status`/`external_updated_at`를 그대로 확장할 수 있다.
- `StrategyPackEngine`에서 이미 외부데이터 의존 전략을 fail-closed로 막고 있어 안전하다.
- UI와 진단 탭에 이미 상태를 올릴 자리가 있다.

### F2. 뉴스/공시 이벤트 점수화 엔진

AI 없이도 바로 효과를 볼 수 있는 기능이다.

규칙 기반으로 먼저 구현할 것:

- 호재 키워드: `수주`, `계약 체결`, `실적 개선`, `가이던스 상향`, `자사주`, `배당 확대`
- 악재 키워드: `유상증자`, `전환사채`, `신주인수권부사채`, `실적 하향`, `소송`, `횡령`, `거래정지`, `감사의견`
- 중립/보류: 기사 중복, 홍보성 기사, 오래된 기사, 단순 시황 브리핑

산출값 예시:

- `news_score`: -100 ~ +100
- `headline_velocity`: 최근 N분 내 헤드라인 증가율
- `event_type`: `earnings`, `funding`, `contract`, `governance`, `halt`, `theme`
- `event_confidence`: 0.0 ~ 1.0

적용 방식:

- `news_risk_guard`: 악재 강도가 크면 신규 진입 차단
- `news_momentum_filter`: 긍정 기사 + 거래량 급증 동시 발생 시만 진입 허용
- `disclosure_event_guard`: 유상증자/CB/BW/감사의견 이슈 시 일정 시간 차단

### F3. AI 요약/판단 보조

AI는 기본 판단 엔진이 아니라 "압축기 + 구조화 도우미"로 써야 한다.

권장 원칙:

- AI가 주문을 직접 내리게 하지 않는다.
- AI는 텍스트를 구조화된 JSON으로 정리하는 역할만 맡긴다.
- AI 호출은 이벤트 발생 시에만 제한적으로 건다.

권장 트리거:

- `abs(news_score) >= 60`
- DART 주요 공시 발생
- 장중 5분 내 헤드라인 급증
- 거래량 랭킹 상위 + 테마 키워드 급증

권장 출력:

```json
{
  "summary": "2~3문장 요약",
  "stance": "bullish|bearish|neutral|uncertain",
  "risk_tags": ["rights_issue", "earnings_miss"],
  "confidence": 0.0,
  "action_hint": "block_entry|reduce_size|watch_only|allow"
}
```

AI를 붙여도 실제 주문 로직은 다음처럼 결정적으로 유지하는 것이 맞다.

- `action_hint = block_entry` 이면 보조 가드로만 사용
- `confidence`가 낮으면 무시
- 최종 진입 허용 여부는 기존 조건식과 신규 deterministic guard가 결정

### F4. 장전 브리핑 / 장중 경보

추가 가치가 매우 큰 기능이다.

장전 브리핑:

- 08:40~08:55 사이 보유/관심 종목의 밤사이 뉴스, DART 공시, 거시지표 변화를 요약
- 텔레그램 또는 UI 로그 패널에 1회 발행

장중 경보:

- "삼성전자: 3분 내 기사 5건 증가 + 외인/기관 동시 순매수 + 검색량 상승"
- "보유 종목: DART 유상증자/CB 공시 감지, 신규 매수 금지"

이 기능은 사용자 체감이 크고, AI가 없어도 규칙 기반으로 충분히 구현 가능하다.

### F5. 시황 레짐 / 테마 감지

현재는 가격/변동성 중심 레짐이 강하다. 여기에 "텍스트 기반 레짐"을 더하면 좋다.

추천 지표:

- 네이버 데이터랩 검색량 급증
- 거래량 랭킹/급등락 랭킹과의 교집합
- 종목군 공통 키워드 빈도
- KOSPI/KOSDAQ 지수 shock와 섹터별 뉴스 강도

가능한 산출값:

- `market_theme = ai/반도체/바이오/방산/2차전지/...`
- `theme_heat_score = 0 ~ 100`
- `market_news_regime = risk_on / risk_off / event_driven / neutral`

적용 예:

- `theme_heat_filter`: 현재 강한 테마와 무관한 종목은 진입 점수 보수화
- `risk_off_news_guard`: 시장 전체 악재 밀도가 높으면 전체 포지션 크기 축소

### F6. 이벤트 반영 백테스트 / 리플레이

이 기능이 있어야 "뉴스/공시 기반 기능이 실제로 돈이 되는지" 검증할 수 있다.

추천 확장:

- `BacktestBar` 또는 별도 이벤트 스트림에 `meta/event` 필드 추가
- CSV 기반 뉴스/공시 이벤트 리플레이 지원
- "이 이벤트를 막았으면 손실을 줄였는가?"를 측정

검증 지표:

- 악재 이벤트 직후 진입 회피율
- 호재 이벤트 직후 성과 개선율
- max drawdown 감소폭
- false positive 비율

---

## 4) 코드 기준 추천 구현 위치

| 위치 | 현재 역할 | 추천 확장 |
|---|---|---|
| `app/mixins/trading_session.py` | 외부 수급 refresh loop | `market_intel` refresh orchestration으로 일반화 |
| `strategies/pack.py` | 전략팩/리스크 오버레이 평가 | `news_risk_guard`, `disclosure_event_guard`, `macro_regime_guard`, `theme_heat_filter` 추가 |
| `strategy_manager.py` | 종합 진입 조건/메트릭 | `news_score`, `theme_score`, `macro_regime_score` 메트릭 통합 |
| `data/providers/dart_provider.py` | OpenDART 래퍼 | 실제 공시 이벤트 조회 함수 추가 |
| `data/providers/macro_provider.py` | FRED 시계열 조회 | 장전/장중 macro regime 계산에 연결 |
| `data/providers/` | provider 패키지 | `news_provider.py`, `naver_trend_provider.py` 추가 |
| `app/mixins/ui_build.py` | 탭/고급설정 UI | `시장 인텔리전스` 그룹 또는 별도 탭 추가 |
| `app/main_window.py` | 진단 패널 렌더링 | `intel status`, `news score`, `dart risk`, `macro regime` 표시 |
| `backtest/engine.py` | 이벤트 드리븐 가격 백테스트 | 뉴스/공시 이벤트 메타 리플레이 지원 |
| `tests/unit/` | 회귀 테스트 | stale/비용예산/event-guard/AI-disabled/fail-closed 테스트 추가 |

중요한 구조 포인트:

- `CLAUDE.md` 기준으로 새 기능이 커지면 `TradingSessionMixin`에 계속 덧칠하지 말고 새 믹스인으로 분리하는 편이 낫다.
- 추천 신규 믹스인 이름: `app/mixins/market_intelligence.py`
- type 체계는 `app/mixins/_typing.py` 패턴을 그대로 유지하는 것이 맞다.

---

## 5) 최소 비용/무료 우선 구성안

### 권장 1단계: 사실상 무료 구성

- 뉴스: NAVER Search API
- 검색 트렌드: NAVER Datalab Search Trend API
- 공시: OpenDART
- 거시: FRED
- 해석 엔진: 규칙 기반 점수화 + 키워드 사전
- 알림: 기존 Telegram notifier 재사용

장점:

- 추가 비용이 거의 없다.
- 현재 `requests` 기반 코드 스타일과 잘 맞는다.
- AI 없이도 "위험 공시 차단", "기사 급증 감지", "테마 과열 감지"가 가능하다.

### 권장 2단계: 저비용 AI 옵션

- 기본값은 `OFF`
- 고충격 이벤트에서만 호출
- 하루 예산/종목당 호출 횟수/장중 총 호출 수 제한

추천 정책:

- 1차: 규칙 기반 점수화
- 2차: 점수가 임계치 이상이거나 불확실할 때만 AI
- 3차: AI 출력은 JSON만 허용

실무적으로는 이 구조가 비용과 안정성의 균형이 가장 좋다.

---

## 6) 추천 API 조합 (2026-03-24 확인 기준)

### A안. 가장 추천

- NAVER News Search API
- NAVER Datalab Search Trend API
- OpenDART
- FRED
- AI 없음 또는 Gemini 2.5 Flash-Lite 선택 호출

추천 이유:

- 한국 종목 뉴스/검색량/공시 커버리지가 좋다.
- 현재 프로젝트가 KR 주식 실거래 컨텍스트이므로 글로벌 범용 뉴스 API보다 맞춤성이 높다.
- 공시와 검색량을 같이 보면 "시장 소음"과 "실제 이벤트"를 분리하기 쉽다.

### B안. AI 품질을 더 중시

- A안 + OpenAI `gpt-5-mini`

추천 조건:

- 비용보다 요약 품질/출력 일관성을 조금 더 중시할 때
- 기사 묶음 요약, 공시 전문 요약, 텔레그램 브리핑 문장 품질이 중요할 때

### 비추천

- AI에게 직접 매수/매도 결정을 맡기는 구조
- 모든 틱/모든 뉴스에 AI를 호출하는 구조
- stale 외부데이터인데도 신규 진입을 허용하는 구조

---

## 7) 추천 기능 우선순위

### P0. 반드시 먼저

1. `market_intelligence` canonical model 정의
2. NAVER News + OpenDART + Datalab provider 연결
3. 규칙 기반 이벤트 점수화
4. `news_risk_guard`, `disclosure_event_guard`
5. 진단 탭 노출

### P1. 다음 단계

1. 장전 브리핑
2. 장중 이벤트 경보
3. 테마/레짐 점수
4. AI 선택 호출

### P2. 검증 고도화

1. 이벤트 반영 백테스트
2. 세션 리포트
3. 종목별 "왜 보류했는지" 감사 로그

---

## 8) 구체적인 신규 기능 아이디어

### 8.1 뉴스 리스크 가드

- 악재 기사 또는 공시가 감지되면 일정 시간 신규 진입 차단
- 보유 포지션은 강제청산하지 않되 경고/축소 모드로 전환

### 8.2 공시 우선순위 분류기

- `유상증자`, `CB/BW`, `실적`, `수주`, `자사주`, `소송`, `감사의견`, `거래정지` 등으로 분류
- 이벤트 타입별로 `block / reduce / watch` 정책 차등 적용

### 8.3 테마 히트맵 자동 생성

- 랭킹 탭, 조건검색 결과, 뉴스 키워드, 검색량 데이터를 합쳐 현재 시장의 강한 테마 추정
- 관심 종목이 현재 주도 테마인지 표시

### 8.4 장전 종목 우선순위 재정렬

- 기존 입력 종목을 그대로 쓰되, 장전 브리핑 이후 우선순위 점수로 재정렬
- 상위 종목만 더 자주 external refresh

### 8.5 AI 세션 리뷰

- "오늘 왜 이 종목은 매수했고, 왜 다른 종목은 보류했는가"를 세션 종료 후 요약
- 실거래 판단 보조용 로그 해석 도구로 유용

### 8.6 이벤트 드리븐 유니버스 확장

- 사용자가 입력한 고정 종목 외에도
- 조건검색 상위 + 뉴스 급증 + 테마 일치 종목을 "관심 후보"로 자동 추천

---

## 9) 설정 스키마 제안

```json
{
  "market_intelligence": {
    "enabled": true,
    "use_news": true,
    "use_dart": true,
    "use_datalab": true,
    "use_macro": true,
    "news_provider": "naver",
    "ai_provider": "gemini",
    "ai_enabled": false,
    "ai_daily_budget_krw": 1000,
    "ai_max_calls_per_day": 30,
    "news_refresh_sec": 60,
    "macro_refresh_sec": 300,
    "briefing_time": "08:50",
    "block_on_negative_disclosure": true,
    "min_news_score_to_call_ai": 60
  }
}
```

주의:

- `CLAUDE.md` 기준으로 새 키를 추가하면 `_save_settings`, `_load_settings`, `_get_current_settings`, `_apply_settings` parity를 반드시 맞춰야 한다.
- 기존 `feature_flags["enable_external_data"]`와 충돌하지 않게 관계를 정리해야 한다.
- 가장 안전한 방식은 `enable_external_data` 아래에 `market_intelligence.enabled`를 두는 구조다.

---

## 10) 구현 원칙

### fail-closed 유지

- 외부데이터 stale/error면 해당 외부 의존 전략만 차단
- 또는 신규 진입만 차단하고 청산은 허용
- 현재 프로젝트의 v4 guard 철학을 그대로 유지

### AI 직접 주문 금지

- AI는 텍스트 분류/요약만
- 최종 매매 판단은 deterministic rule + threshold

### 비용 상한 내장

- 일일 호출 예산
- 종목당 최대 호출 수
- 뉴스 중복 제거
- 헤드라인 변화가 없으면 재호출 금지

### 테스트 우선

- stale guard
- negative disclosure block
- AI disabled fallback
- empty news payload
- duplicated headline dedup
- strategy pack guard parity
- backtest event parity

---

## 11) 실제로 가장 먼저 만들 기능 3개

가장 현실적인 첫 스프린트는 아래 3개다.

1. `OpenDART 주요 공시 감지 + 신규 진입 차단 가드`
2. `NAVER 뉴스 헤드라인 수집 + 규칙 기반 점수화`
3. `장전 브리핑 + 텔레그램 요약`

이 3개만 들어가도 사용자는 "이 프로그램이 가격만 보는 봇"에서 "시장 상황을 읽고 보수적으로 행동하는 봇"으로 체감하게 된다.

---

## 12) 참고한 공식 자료

확인일: 2026-03-24

- NAVER Search API 뉴스 검색: https://developers.naver.com/docs/serviceapi/search/news/news.md
- NAVER Datalab 검색어 트렌드: https://developers.naver.com/docs/serviceapi/datalab/search/search.md
- OpenDART 오픈API 소개: https://opendart.fss.or.kr/intro/main.do
- OpenDART 메시지/요청 제한 안내: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DE005&apiId=AE00062
- FRED API 문서: https://fred.stlouisfed.org/docs/api/fred/
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- OpenAI API pricing: https://platform.openai.com/pricing

요약된 비용/제한 메모:

- NAVER Search API: 하루 25,000회
- NAVER Datalab Search Trend API: 하루 1,000회
- OpenDART: 누구나 인증키 발급 후 사용 가능, 공식 에러 설명상 일반적으로 20,000건 이상 요청 시 제한 초과 가능
- FRED: API key 기반 사용
- Gemini 2.5 Flash-Lite: 무료 티어 존재, 유료 기준 text/image/video 입력 $0.10 / 1M tokens, 출력 $0.40 / 1M tokens
- OpenAI `gpt-5-mini`: 입력 $0.25 / 1M tokens, 출력 $2.00 / 1M tokens

---

## 13) 최종 제안

이 프로젝트는 이미 "가격 기반 자동매매기"에서 "시장 인텔리전스 보조형 자동매매기"로 확장할 준비가 되어 있다.

가장 좋은 방향은 다음이다.

- 1차: 무료 데이터 + 규칙 기반 인텔리전스
- 2차: 고충격 이벤트에만 저비용 AI 호출
- 3차: 전략팩/백테스트/진단 탭까지 완전 연결

이 순서가 비용, 안정성, 유지보수성, 실제 체감 효용을 모두 가장 잘 맞춘다.
