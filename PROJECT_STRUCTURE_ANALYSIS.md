# Kiwoom Automatic Trader 프로젝트 구조 분석

작성일: 2026-03-05  
최종 동기화: 2026-04-12
분석 기준: 현재 저장소 코드 + `README.md`, `CLAUDE.md`, `GEMINI.md`, `REAL_API_PREPARATION_GUIDE.md`, `IMPLEMENTATION_REVIEW_2026-04-08.md`

## 1) 요약

현재 프로젝트는 다음 4개 축으로 정리되어 있다.

- 엔트리/조립: `키움증권 자동매매.py`, `app/main_window.py`, `app/mixins/*.py`
- 전략/판단: `strategy_manager.py`, `strategies/pack.py`, `strategies/manager_mixins/*.py`
- UI 다이얼로그: `app/mixins/dialogs_profiles.py`, `dialogs/*.py`, `ui_dialogs.py`
- 운영/검증/패키징: `config.py`, `KiwoomTrader.spec`, `tests/unit`, `tools/*`

2026-04-12 기준 가장 중요한 구조 변화는 세 가지다.

1. `strategy_manager.py`는 더 이상 대형 단일 구현 파일이 아니라 orchestration 레이어다.  
   실제 계산 책임은 `strategies/manager_mixins/`로 분리됐다.
2. `ui_dialogs.py`는 더 이상 실제 구현 파일이 아니라 compatibility re-export 레이어다.  
   실제 다이얼로그 구현은 `dialogs/` 패키지에 있다.
3. `api/endpoints.py`, `external_positions`, `stop_trading()` 주문 정리 helper가 추가되면서
   API 모드 분기, 유니버스 외 보유 추적, 종료 정리 흐름이 각각 별도 구조로 승격됐다.

## 2) 실제 코드베이스 규모 (2026-04-12 실측)

패키지별 Python 파일 수와 라인 수:

| 패키지 | py 파일 수 | 라인 수 |
|---|---:|---:|
| `app/` | 19 | 10616 |
| `api/` | 6 | 1802 |
| `tests/` | 66 | 4287 |
| `strategies/` | 11 | 1781 |
| `dialogs/` | 7 | 575 |
| `tools/` | 4 | 405 |
| `backtest/` | 2 | 735 |
| `data/` | 10 | 673 |
| `portfolio/` | 2 | 39 |

핵심 파일 Top 10:

1. `app/mixins/market_intelligence.py` (2265)
2. `app/mixins/trading_session.py` (1619)
3. `app/mixins/ui_build.py` (1184)
4. `app/mixins/order_sync.py` (1039)
5. `app/mixins/execution_engine.py` (911)
6. `config.py` (839)
7. `app/mixins/persistence_settings.py` (836)
8. `api/rest_client.py` (795)
9. `app/main_window.py` (753)
10. `backtest/engine.py` (727)

루트 orchestration / compatibility 파일:

- `strategy_manager.py` (32)
- `ui_dialogs.py` (22)
- `키움증권 자동매매.py` (27)

## 3) 현재 디렉터리 역할

```text
kiwoom-automatic-trader/
├── api/                     # REST/WS 인증, live/mock 라우팅, 모델, 통신 클라이언트
├── app/
│   ├── main_window.py       # KiwoomProTrader 조립 클래스
│   ├── mixins/              # UI/세션/API/실행/동기화/인텔리전스/저장
│   └── support/             # worker/widgets/execution_policy/ui_text
├── backtest/                # 이벤트 드리븐 백테스트 엔진
├── data/providers/          # 뉴스/DART/매크로/트렌드/AI provider
├── dialogs/                 # 실제 다이얼로그 구현
├── portfolio/               # 예산 배분 확장 경로
├── strategies/
│   ├── pack.py              # 전략팩 엔진
│   └── manager_mixins/      # StrategyManager 세부 책임 분리
├── tests/unit/              # 단위 테스트
├── tools/                   # refactor/perf 검증 도구
├── strategy_manager.py      # StrategyManager orchestration 레이어
├── ui_dialogs.py            # dialogs compatibility re-export
├── config.py
└── KiwoomTrader.spec
```

## 4) 조립 계층

### 엔트리

- `키움증권 자동매매.py`
  - `QApplication` 생성
  - 전역 예외 훅 설정
  - `app.main_window.KiwoomProTrader` 표시

### 메인 클래스

- `app/main_window.py`
  - `KiwoomProTrader`는 다수 믹스인을 다중 상속으로 조립
  - 직접 구현 책임은 최소화돼 있고, 공용 시그널과 런타임 상태를 보관

### `app/mixins/*` 책임

- `ui_build.py`: 메인 탭/핵심 설정/상세 설정/진단 표 구성
- `api_account.py`: API 연결, 계좌 갱신, 실거래 보호 가드
- `trading_session.py`: 시작/중지, 유니버스 초기화, 외부 보유 추적, 예약/세션 수명주기
- `execution_engine.py`: 실시간 체결 기반 매수/매도 판단 및 실행
- `order_sync.py`: 주문/체결 상태 동기화와 fail-safe
- `market_intelligence.py`: 외부 데이터 수집, 정책 계산, 브리핑, 리플레이
- `persistence_settings.py`: 설정 저장/복원, 스키마 마이그레이션, keyring 연동
- `dialogs_profiles.py`: 다이얼로그 호출/결과 반영, 프로필/프리셋 연동
- `system_shell.py`: 로깅, 메뉴, 단축키, 트레이, 종료

## 5) 전략 계층

### 현재 구조

- `strategy_manager.py`
  - `StrategyManager` 생성자와 상태 조립만 담당
  - 외부 API는 그대로 유지:
    - `from strategy_manager import StrategyManager`

- `strategies/manager_mixins/logging.py`
  - 공통 로그/중복 로그 억제

- `strategies/manager_mixins/market_intelligence.py`
  - 인텔 스냅샷/뉴스/DART/매크로/테마 guard

- `strategies/manager_mixins/signal_filters.py`
  - Stochastic RSI, MTF, 갭, 진입점수, 부분익절

- `strategies/manager_mixins/indicators.py`
  - RSI, MACD, Bollinger, ATR, DMI, MA, ATR stop

- `strategies/manager_mixins/portfolio_risk.py`
  - 동적 포지션 사이징, 시장/섹터 분산, 레짐 스케일, 목표가, 분할 주문 헬퍼

- `strategies/manager_mixins/evaluation.py`
  - 전략팩 평가, 레거시 buy condition 집계, decision cache

### 의미

- 전략 책임이 파일 기준으로 분리되어 SRP에 더 가깝게 정리되었다.
- 외부 호출부는 `StrategyManager` 단일 엔트리를 유지해 DIP/OCP 측면의 파급을 줄였다.
- 테스트는 여전히 루트 `strategy_manager.py` import 경로만 사용해 호환된다.

## 6) 다이얼로그 계층

### 현재 구조

- `dialogs/preset.py`
- `dialogs/help.py`
- `dialogs/stock_search.py`
- `dialogs/manual_order.py`
- `dialogs/profile_manager.py`
- `dialogs/schedule.py`

- `ui_dialogs.py`
  - 위 패키지를 re-export 한다.
  - 기존 import 경로 호환 유지:
    - `from ui_dialogs import ManualOrderDialog`
    - `from ui_dialogs import PresetDialog`

### 의미

- UI 다이얼로그 구현 책임이 모듈별로 분리되어 수정 범위가 명확해졌다.
- `app/mixins/dialogs_profiles.py`, 테스트 코드, 기존 import는 깨지지 않는다.

## 7) 런타임 핵심 플로우

### 연결

1. `connect_api()` 호출
2. Worker 기반 인증/계좌조회
3. 성공 시 REST/WS 클라이언트 및 계좌 상태 반영
4. 재연결 시 기존 Telegram notifier 정리 후 새 notifier 생성

### 매매 시작

1. `start_trading()` 입력/전략/live capability 검증
2. 실거래 보호문구 가드 `_confirm_live_trading_guard()`
3. 유니버스 초기화
4. 포지션 스냅샷 동기화 성공 시 시작
5. WebSocket 체결/주문체결/지수 구독 시작
6. 유니버스 외 보유는 `external_positions`에 읽기 전용 상태로 편입

### 실시간 진입/청산

- `ExecutionEngineMixin._on_execution()`
- `StrategyManager.evaluate_buy_conditions()`
- `action_policy`, `size_multiplier`, `portfolio_budget_scale` 반영
- `decision_audit.jsonl` 기록 후 주문 실행
- 시간청산/긴급청산은 `universe` + `external_positions`를 함께 청산 대상으로 본다

### 주문/동기화

- `pending_order_state` / aggregate pending / reserved cash 추적
- 분할 매수는 `use_split=True` + `execution_policy=limit` 에서 child 지정가 주문 즉시 제출
- 일부 reject/cancel 은 해당 slice 예약금만 환원
- 중지/긴급청산 경로는 활성 주문 취소를 먼저 시도하고 unresolved 건만 로컬 finalization 한다

## 8) 문서 / 패키징 정합성

### 현재 기준 문서

- `README.md`
- `CLAUDE.md`
- `GEMINI.md`
- `REAL_API_PREPARATION_GUIDE.md`
- `IMPLEMENTATION_REVIEW_2026-04-08.md`

### `KiwoomTrader.spec`

- explicit hiddenimports + `collect_submodules(...)` 를 함께 사용
- 현재는 `api`, `app`, `strategies`, `dialogs`, `backtest`, `portfolio`, `data.providers`를 수집
- `api.endpoints` explicit hiddenimport로 live/mock 라우터를 패키징에 명시 반영
- `dialogs/` 패키지 분리 후에도 빌드 누락이 없도록 `collect_submodules('dialogs')` 가 추가되었다

### `.gitignore`

- `build/`, `dist/`, `release/` 외에 `.pyinstaller/`, `*.spec.bak` 를 무시
- 런타임 산출물(`*.json`, `*.jsonl`, `*.db`)은 기본적으로 무시하되 필요한 정적 기준 파일은 예외로 추적

## 9) 검증 현황

2026-04-12 기준 재검증:

- `python -m pytest -q tests/unit`
- `python -m compileall -q app api data backtest strategies portfolio dialogs ui_dialogs.py strategy_manager.py tests/unit`

결과:

- `tests/unit` 전체 120개 테스트 통과
- 문법 컴파일 검증 통과

## 10) 현재 남아 있는 큰 파일 / 다음 분리 후보

다음 후보는 여전히 크기가 큰 다음 파일들이다.

1. `app/mixins/market_intelligence.py`
2. `app/mixins/ui_build.py`
3. `app/mixins/trading_session.py`
4. `app/mixins/order_sync.py`
5. `app/mixins/execution_engine.py`

우선순위 기준:

- 변경 빈도와 책임 혼재가 높은 파일부터
- 외부 API를 유지한 채 내부 helper/section package 로 이동 가능한 파일부터
- 테스트 커버가 이미 있는 경계부터

현재 구조 기준으로는 `strategy_manager.py` 와 `ui_dialogs.py` 의 모놀리식 위험은 상당 부분 제거된 상태다.
