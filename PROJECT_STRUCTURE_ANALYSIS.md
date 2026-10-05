# Kiwoom Automatic Trader 프로젝트 구조 분석

작성일: 2026-03-05
최종 동기화: 2026-06-10
분석 기준: 현재 저장소 코드, README/CLAUDE/GEMINI/REAL_API_PREPARATION_GUIDE, PyInstaller spec

## 2026-10-05: GitHub #3 / #4 책임 및 데이터 계약 보완

- 조건검색 목록·일반 검색·실시간 초기 스냅샷·해제와 종목 응답 파싱의 구현은
  `api/websocket_client.py`의 `KiwoomWebSocketClient`에 모았다. 일반 검색과
  실시간 스냅샷은 하나의 `_parse_condition_stock_rows`를 공유한다.
- `KiwoomRESTClient.get_condition_list`, `search_by_condition`,
  `request_condition_realtime`, `stop_condition_realtime`는 기존 인자와 반환
  형태를 유지하는 위임 래퍼다. UI의 Worker 호출 경로도 유지한다.
- 실시간 푸시 콜백은 기존 `subscribe_condition_realtime` /
  `unsubscribe_condition_realtime`가 담당한다. 일회성 초기 스냅샷 API와
  지속 연결 콜백 API를 서로 대체하지 않는다.
- 일봉 `high_history` / `low_history`에 대응하는 종가는 `daily_prices`다.
  `price_history`는 초기 일봉 종가에 실시간 체결가가 추가되고 앞부분이
  삭제되는 호환용 스트림이므로, 일봉 고·저가와 직접 결합하면 안 된다.
- `_daily_indicator_closes`가 ATR·DMI의 여섯 호출 경로에 동일한 종가 선택
  정책을 제공한다. `daily_prices` 키가 없는 이전 유니버스만
  `price_history`로 폴백하며, 명시적인 빈 일봉 데이터는 부족 데이터로 처리한다.
- ATR·DMI는 고가 N개에 저가 N개 이상, 이전 종가 N-1개 이상을 요구한다.
  부족 시 기존 반환 계약인 `0` / `(0, 0, 0)`을 사용한다. 배열을 끝에서
  자르는 것으로 시점을 추정하지 않으며, 직접 호출자는 같은 캔들 인덱스로
  정렬한 데이터를 전달해야 한다.

호환 영향: 정상 입력의 계산식과 공개 import/API는 유지한다. 체결 이력 삭제로
왜곡되던 ATR·DMI 값은 일봉 기준으로 교정되므로 손절가와 주문 수량이 달라질 수
있다. 일봉 배열은 기존처럼 유니버스 초기화 시 로드한 스냅샷이며 이번 변경이
장중 일봉 갱신이나 완성된 분봉 집계기를 추가하지는 않는다.

회귀 테스트: `test_indicator_history_alignment.py`(15개),
`test_condition_search_ownership.py`(8개). 지표 테스트와 기존 전략·수량 테스트
총 26개는 일반 unittest 실행으로 통과했다. 조건검색 신규 8개와 기존 계약 4개는
실제 메서드 AST를 격리해 요청/파싱/위임을 검증했고 통과했다. 검증 환경의
PyQt6·requests·pytest·pyright 설치 제한으로 전체 단위 테스트, Qt 통합 및
실제 키움 서버 접속 검증은 수행하지 못했다. compileall 및 refactor_verify는 통과했다.

완전한 개발 환경에서의 후속 검증:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/unit --override-ini addopts= --tb=short
python -m pyright .
python tools/refactor_verify.py
```

전략 의견(#3): cooldown은 재주문 대기 가드이며 반등 신호를 뜻하지 않는다.
기존 MTF / DMI 필터는 선택 가능한 추세 확인 수단이지만, `minute_prices`에도
체결가가 추가되므로 엄밀한 완성 분봉 기반 반등 전략과 동일하지 않다.
반등 확인 / 일봉 10% 하락 진입은 별도의 전략 명세·봉 데이터 정렬·비용 포함
백테스트가 필요하므로 이번 구조 수정에서 기본 매수 정책으로 추가하지 않았다.

## 1. 요약

현재 프로젝트는 엔트리 래퍼, core window, feature 패키지, 설정 패키지, 전략 엔진, API 클라이언트, 운영/검증 도구로 분리되어 있다.

- 엔트리: `키움증권 자동매매.py`
- 메인 조립 클래스: `app/core/window.py`
- 기존 window import 호환: `app/main_window.py`
- UI/API/세션/주문/저장/진단/인텔리전스 feature 구현: `app/features/*`
- 기존 mixin import 호환: `app/mixins/*.py`
- 설정 canonical 구현: `app/configuration/base.py`
- 설정 호환 facade: `config.py`
- 전략 오케스트레이션 canonical 구현: `strategies/manager.py`
- 전략 호환 facade: `strategy_manager.py`
- 전략 세부 구현: `strategies/manager_mixins/*.py`
- 다이얼로그 구현: `dialogs/*.py`
- 다이얼로그 호환 re-export: `ui_dialogs.py`
- API 인증/REST/WebSocket: `api/*.py`
- 검증/리팩토링 도구: `tools/*.py`

2026-06-10 기준 핵심 변화는 큰 단일 mixin 파일을 `app/features/` 하위 책임별 패키지로 분리하고, `KiwoomProTrader`, `Config`, `StrategyManager`의 canonical 경로를 새 구조로 옮긴 것이다. 기존 public import 경로는 shim/facade로 유지한다.

## 2. 코드 규모

2026-06-10 로컬 측정 기준:

| 패키지/경로 | Python 파일 수 | 라인 수 |
| --- | ---: | ---: |
| `api/` | 6 | 1,883 |
| `app/` | 67 | 13,202 |
| `backtest/` | 2 | 735 |
| `data/` | 10 | 673 |
| `dialogs/` | 7 | 575 |
| `portfolio/` | 2 | 39 |
| `strategies/` | 13 | 1,836 |
| `tests/` | 75 | 4,828 |
| `tools/` | 5 | 405 |

큰 feature 패키지:

| 경로 | Python 파일 수 | 라인 수 |
| --- | ---: | ---: |
| `app/features/market_intelligence/` | 7 | 2,589 |
| `app/features/trading_session/` | 7 | 1,878 |
| `app/features/ui_build/` | 6 | 1,430 |
| `app/features/execution/` | 6 | 1,123 |
| `app/features/order_sync/` | 6 | 1,108 |
| `app/features/persistence/` | 4 | 1,050 |
| `app/features/diagnostics/` | 2 | 300 |

## 3. 디렉터리 역할

```text
kiwoom-automatic-trader/
├── api/                     # 인증, endpoint routing, REST/WS client, API 모델
├── app/
│   ├── core/window.py       # KiwoomProTrader canonical 조립 클래스
│   ├── features/            # UI, 세션, 실행, 동기화, 저장, 인텔리전스, 진단
│   ├── configuration/       # Config/TradingConfig canonical 구현과 category export
│   ├── mixins/              # 기존 import 경로 shim + 소형 mixin
│   └── support/             # worker, widgets, execution policy, ui text, backtest runner
├── backtest/                # 이벤트 드리븐 백테스트 엔진
├── data/providers/          # 뉴스, DART, 매크로, 검색트렌드, AI provider
├── dialogs/                 # 프리셋, 도움말, 종목검색, 수동주문, 프로필, 예약
├── portfolio/               # 리스크 예산 배분 확장 경로
├── strategies/              # StrategyManager, 전략팩, StrategyManager mixin
├── tests/unit/              # 단위 테스트
├── tools/                   # refactor/perf 검증 도구
├── config.py                # app.configuration.base 호환 facade
├── strategy_manager.py      # strategies.manager 호환 facade
├── KiwoomTrader.spec        # PyInstaller onefile 빌드 기준
└── docs/refactor/           # refactor manifest baseline
```

## 4. 런타임 플로우

API 연결:

1. `connect_api()`가 Worker를 통해 인증과 계좌 조회를 수행한다.
2. `api/endpoints.py`가 live/mock REST/WS endpoint와 토큰 캐시 namespace를 결정한다.
3. 연결 성공 시 REST client, WebSocket client, 계좌 상태, notifier 상태를 갱신한다.
4. WebSocket callback은 Qt main-thread dispatcher signal을 경유한다.

매매 시작:

1. 입력 종목, 전략 capability, live guard 조건을 확인한다.
2. 거래 시작 전 preflight 로그를 남긴다.
3. 유니버스 초기화와 계좌 포지션 스냅샷 동기화가 성공해야 시작한다.
4. 실시간 체결/주문 이벤트 구독을 시작한다.

주문 실행:

1. `execution_mode="signal_only"`이면 REST 주문 API 호출 없이 `data/order_lifecycle_events.jsonl`에 감사 로그만 기록한다.
2. `execution_mode="live"`이면 기존 주문 정책, 실거래 보호, 주문 실행 Worker를 통과한다.
3. 수동 주문과 분할 주문도 동일한 execution mode gate를 사용한다.
4. 정상 취소는 lifecycle 이벤트로 기록하고, 거부/실패만 주문 health failure로 기록한다.

중지/종료:

1. `stop_trading()`은 bounded cleanup worker로 활성 주문 취소 요청을 보낸다.
2. 성공 또는 상태 확인된 주문만 pending/manual pending/reserved cash에서 정리한다.
3. 실패 또는 미확인 주문은 `sync_failed`로 남겨 로컬 상태가 브로커보다 앞서가지 않게 한다.
4. 종료 fallback에서는 짧은 동기 정리만 수행한다.

## 5. Import 호환 정책

유지되는 기존 경로:

- `from app.main_window import KiwoomProTrader`
- `from app.mixins.trading_session import TradingSessionMixin, BackgroundUniversePayload`
- `from app.mixins.execution_engine import ExecutionEngineMixin`
- `from app.mixins.order_sync import OrderSyncMixin`
- `from app.mixins.persistence_settings import PersistenceSettingsMixin`
- `from app.mixins.market_intelligence import MarketIntelligenceMixin`
- `from app.mixins.ui_build import UIBuildMixin`
- `from config import Config, TradingConfig`
- `from strategy_manager import StrategyManager`

새 canonical 경로:

- `app.core.window.KiwoomProTrader`
- `app.features.*`
- `app.configuration.base.Config`
- `app.configuration.base.TradingConfig`
- `strategies.manager.StrategyManager`

## 6. 설정과 보안

현재 canonical schema:

- `settings_version = 7`
- `execution_mode = "signal_only"` 기본
- `allow_plaintext_secret_fallback = false` 기본
- `market_intelligence.source_policy.strict_entry_guard = false` 기본

secret 저장 정책:

- keyring 저장 우선
- 실전 모드에서 keyring 실패 시 평문 fallback 기본 차단
- opt-in 시에만 설정 파일 fallback 허용
- 도구 메뉴에서 민감정보/토큰 삭제 가능

## 7. Market Intelligence

상위 gate는 `feature_flags["enable_external_data"]`이고, 세부 설정은 `market_intelligence.enabled`이다.

기본 정책:

- freshness/source 문제는 warning + audit 후 진입 허용
- strict entry guard를 켜면 missing/stale/refreshing/error가 신규 진입 차단
- 고위험 DART, `block_entry`, `force_exit`는 strict 여부와 무관하게 유지

주요 산출물:

- `data/market_intelligence_events.jsonl`
- `data/decision_audit.jsonl`
- `data/order_lifecycle_events.jsonl`
- `data/dart_corp_codes.json`

## 8. PyInstaller Spec

`KiwoomTrader.spec` 기준:

- onefile 출력: `dist/KiwoomTrader_v4.5.exe`
- `icon.png`를 실제 앱 아이콘으로 연결
- `api`, `app`, `strategies`, `dialogs`, `backtest`, `portfolio`, `data.providers` 하위 모듈을 `collect_submodules(...)`로 수집
- `app.core`, `app.features`, `app.configuration`, `strategies.manager` canonical 경로를 explicit hiddenimport에 포함
- 시장 인텔리전스 JSON/JSONL, 주문 생명주기 로그, 토큰 캐시, 거래 내역은 런타임 생성 산출물이므로 번들 제외

## 9. Git Ignore

현재 `.gitignore` 원칙:

- build/dist/cache/venv는 제외
- `tmp*/` 테스트/빌드 임시 디렉터리는 제외
- runtime 설정, 토큰, 거래 내역, JSONL 로그, DB 파일은 제외
- `requirements.txt`, `requirements-dev.txt`, `pyrightconfig.json`, `docs/refactor/*.json`, `data/stock_master_cache.json`은 예외로 추적
- `data/order_lifecycle_events.jsonl`은 로컬 감사 로그로 제외

`git ls-files --deleted` 기준 추적 중인 삭제 문서는 없다.

## 10. 검증 현황

2026-06-10 기준:

```bash
python -m compileall -q app api data backtest strategies portfolio dialogs ui_dialogs.py strategy_manager.py "키움증권 자동매매.py"
python tools\refactor_verify.py
python -m pytest tests\unit --override-ini addopts= --tb=short
python -m pyright .
pyinstaller --clean KiwoomTrader.spec
```

현재까지 확인 완료:

- `tests/unit` 전체 172개 테스트 통과
- Python 문법 컴파일 검증 통과
- refactor verification 통과
- `python -m pyright .` 0 errors
- `pyinstaller --clean KiwoomTrader.spec` 성공
- `dist/KiwoomTrader_v4.5.exe` 생성 확인
