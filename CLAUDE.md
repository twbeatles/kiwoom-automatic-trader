# Kiwoom Pro Algo-Trader - Claude AI 개발 가이드

> 키움증권 REST API 기반 자동매매 프로그램 (v4.5)
>
> **최종 업데이트**: 2026-03-09

---

## 프로젝트 구조 (현행)

```text
키움증권 자동 매매 프로그램/
├── 키움증권 자동매매.py        # 엔트리포인트 래퍼(main)
├── app/
│   ├── main_window.py         # KiwoomProTrader 클래스(조립)
│   ├── mixins/
│   │   ├── _typing.py
│   │   ├── ui_build.py
│   │   ├── market_data_tabs.py
│   │   ├── system_shell.py
│   │   ├── api_account.py
│   │   ├── trading_session.py
│   │   ├── order_sync.py
│   │   ├── execution_engine.py
│   │   ├── persistence_settings.py
│   │   └── dialogs_profiles.py
│   └── support/
│       ├── execution_policy.py
│       ├── widgets.py
│       └── worker.py
├── api/
│   ├── auth.py
│   ├── rest_client.py
│   ├── websocket_client.py
│   └── models.py
├── strategy_manager.py
├── config.py
├── ui_dialogs.py
├── tools/
│   ├── refactor_manifest.py
│   └── refactor_verify.py
├── docs/refactor/
│   ├── baseline_manifest.json
│   └── post_refactor_manifest.json
├── pyrightconfig.json
└── KiwoomTrader.spec
```

핵심 포인트:
- `키움증권 자동매매.py`는 더 이상 모놀리식 본체가 아닙니다.
- 실제 클래스는 `app.main_window.KiwoomProTrader` 입니다.
- 기능별 구현은 믹스인으로 분리되어 있습니다.
- 정적 분석 시 믹스인은 `app/mixins/_typing.py`의 `TraderMixinBase`를 공통 베이스로 사용합니다.

---

## 메인 클래스 구성

### `KiwoomProTrader` (`app/main_window.py`)

- 직접 구현 메서드:
  - `__init__`
  - `_connect_config_signals`
- 클래스 시그널:
  - `sig_log`
  - `sig_execution`
  - `sig_order_execution`
  - `sig_update_table`

### 믹스인 책임 분리

| 모듈 | 책임 |
|------|------|
| `app/mixins/ui_build.py` | 대시보드/탭/UI 위젯 구성 |
| `app/mixins/market_data_tabs.py` | 차트/호가/조건검색/순위 조회 |
| `app/mixins/system_shell.py` | 로깅, 트레이, 메뉴, 단축키, 종료 |
| `app/mixins/api_account.py` | API 연결/계좌 동기화/실거래 가드 |
| `app/mixins/trading_session.py` | 시작/중지/유니버스/강제청산 |
| `app/mixins/order_sync.py` | 실시간 주문 상태 동기화 |
| `app/mixins/execution_engine.py` | 매수/매도 실행 엔진 |
| `app/mixins/persistence_settings.py` | 내역/통계/설정 저장·복원 |
| `app/mixins/dialogs_profiles.py` | 프리셋/프로필/검색/수동주문/예약 |

---

## 런타임 핵심 플로우

1. 앱 시작:
- `키움증권 자동매매.py` -> `main()`
- `KiwoomProTrader()` 생성

2. API 연결:
- `connect_api()`
- 연결은 Worker 기반 비동기 처리(`_connect_inflight` 재진입 가드)
- 인증 실패 시 `_reset_connection_state()`로 상태 정리

3. 매매 시작:
- `start_trading()`
- 실거래(`is_mock=False`)는 `_confirm_live_trading_guard()` 통과 필요
- 유니버스 초기화 직후 `get_positions()` 스냅샷 동기화 성공 시에만 시작

4. 실시간 처리:
- 체결: `_on_execution()`
- 주문체결: `_on_order_execution()`
- 매매 중지 상태(`is_running=False`)에서는 체결 기반 주문 진입 차단
- 포지션 동기화 재시도 초과 시 종목 상태 `sync_failed`로 fail-safe 차단

5. 종료:
- `stop_trading()` -> 구독 해제/타이머 정리
- `closeEvent()`에서 종료 플로우 보장

---

## 설정/전략 관련 최신 포인트

- `TradingConfig` 신규 필드:
  - `use_entry_scoring: bool`
  - `entry_score_threshold: int`

- `Config` 실거래 가드:
  - `LIVE_GUARD_ENABLED`
  - `LIVE_GUARD_PHRASE`
  - `LIVE_GUARD_TIMEOUT_SEC`

- 설정 스키마(v4):
  - canonical은 `settings_version: 4`
  - `betting_ratio`를 canonical로 사용
  - `betting`은 legacy 호환용으로 병행 저장/로드
  - `settings_version < 4` 파일은 로드 시 v4 가드 키 자동 보강

- 유니버스 표준 키:
  - `prev_high`, `prev_low`
  - `daily_prices`, `minute_prices`
  - (호환용) `price_history`

- 목표가 계산 기준:
  - 전일 고저(`prev_high`, `prev_low`) 우선

---

## 리팩토링/유지보수 작업 규칙

1. 엔트리포인트 호환 유지:
- `키움증권 자동매매.py`의 `main()` 시그니처 유지

2. 메서드 누락 금지:
- 분할/이동 후 `python tools/refactor_verify.py` 필수 실행

3. 설정 키 parity 유지:
- `_save_settings`, `_load_settings`
- `_get_current_settings`, `_apply_settings`

4. UI 응답성 유지:
- 조건검색/순위/계좌조회는 Worker 비동기 패턴 유지
- API 연결도 동기 호출로 되돌리지 않음

5. 믹스인 타입 체계 유지:
- 새 믹스인을 추가할 때도 `app/mixins/_typing.py`의 `TraderMixinBase` 상속 패턴을 유지합니다.
- 런타임 MRO를 바꾸지 않고 pyright만 안정화하는 것이 목적입니다.

---

## 검증 커맨드

```bash
# 정적 분석
pyright .

# 문법 검증
python -c "import py_compile, pathlib; py_compile.compile('키움증권 자동매매.py', doraise=True); [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('app').rglob('*.py')]"

# 분할 동등성 검증
python tools/refactor_verify.py

# 단위 테스트
python -m pytest -q tests/unit
```

---

## 빌드

```bash
pyinstaller KiwoomTrader.spec
```

출력(ONEFILE):
- `dist/KiwoomTrader_v4.5.exe`

---

## 자주 하는 실수

1. `KiwoomProTrader`를 `키움증권 자동매매.py`에서 직접 수정하는 경우
- 실제 구현은 `app/main_window.py` + `app/mixins/*.py`입니다.

2. 설정 키를 저장만 하고 로드/프로필 반영에서 누락하는 경우
- 키 parity 검증으로 반드시 확인합니다.

3. 실거래 가드 우회
- `start_trading()`의 실거래 보호 흐름은 제거/우회 금지입니다.

---

## 2026-03-09 정적 분석/문서 동기화 메모

1. pyright 기준 고정
- 루트 `pyrightconfig.json`을 추적하며, 분석 기준은 `pythonVersion = 3.14`입니다.
- 전역 진단 완화 없이 cache 디렉터리만 제외합니다.

2. 동적 Qt mixin 타입 보강
- `app/mixins/_typing.py`의 `TraderMixinBase`가 type-check 전용 `QMainWindow` 베이스 역할을 합니다.
- mixin 내부의 동적 UI 속성 접근은 이 베이스를 통해 pyright에 설명됩니다.

3. 패키징/문서 정합성
- `KiwoomTrader.spec` hiddenimports에 `app.mixins._typing`을 명시했습니다.
- `.gitignore`는 `pyrightconfig.json`을 예외로 유지해 정적 분석 설정을 버전 관리합니다.

4. 최신 검증 결과
```bash
pyright .
python -m pytest -q tests/unit
```
- 결과: `0 errors, 0 warnings`
- 결과: `83 passed` (2026-03-09)

---

## 2026-03-05 추가 동기화 메모

1. 설정 스키마 기준
- 현재 canonical은 `settings_version = 4`입니다.
- `settings_version < 4` 로드 시 v4 가드 키가 자동 보강됩니다(기존 값 우선, 누락 키만 default 주입).

2. 누락되기 쉬운 실제 모듈
- `app/support/execution_policy.py` (market/limit 주문 라우팅)
- `strategies/` (모듈형 전략팩 엔진)
- `backtest/engine.py` (이벤트 드리븐 백테스트)
- `portfolio/allocator.py` (리스크 예산 배분)
- `data/providers/` (`kiwoom`, `dart`, `macro`, `csv`)

3. 테스트 기준 업데이트
- 실행 기준: `python -m pytest -q tests/unit`
- 테스트 결과는 로컬 의존성 버전에 따라 달라질 수 있으므로 실행 커맨드 기준으로 판단

4. 추가 검증 커맨드
```bash
python tools/perf_smoke.py
```

5. 안정성/운영 동기화 포인트
- `start_trading()`은 유니버스 초기화 후 계좌 포지션 스냅샷 동기화 성공 시에만 매매를 시작합니다.
- 포지션 동기화 재시도 초과 시 종목 상태가 `sync_failed`로 전환되어 해당 종목 자동 주문이 차단됩니다.
- 설정/로그/거래내역 파일 경로는 `Config.BASE_DIR` 기준 절대경로로 고정되었습니다.
- 일일 손실 제한은 `daily_realized_profit / daily_initial_deposit` 기준으로 계산됩니다.

---

## 2026-03-07 기능 안정화 동기화 메모

1. 주문/동기화 상태머신 강화
- `pending_order_state`를 `submitted/partial/filled/cancelled/rejected/sync_failed`로 명시화했습니다.
- 주문번호/요청수량/누적체결/잔량/예상가/갱신시각을 함께 추적하도록 확장했습니다.
- `sync_failed` 수동 해제는 즉시 상태 전환이 아니라, 재동기화 성공 시 복구되도록 안전 규칙을 적용했습니다.

2. 포지션/리스크 정책 보정
- 레짐 스케일 적용 책임을 수량 계산 경로(`strategy_manager`)로 일원화했습니다.
- 부분체결 시 예약금은 체결분만 차감하고 잔여분은 주문 종료 시점에만 정리합니다.
- 매도 시 시장/섹터 투자금 감소를 체결대금 기준에서 원가 기반 장부 감소 방식으로 교정했습니다.
- 세션 시작 시점 보유 포지션은 `TIME_STOP` 대상에서 제외하고, 세션 신규 진입 포지션에만 `TIME_STOP`을 적용합니다.

3. 백테스트/저장 신뢰성 강화
- 백테스트 MTM을 다종목 `last_prices` 캐시 기반으로 계산해 포지션별 최신가 반영 정확도를 개선했습니다.
- 거래내역 저장을 single-writer(순차) 방식으로 바꿔 out-of-order 덮어쓰기 위험을 제거했습니다.
- 종료 시 flush 경로에서 최신 스냅샷이 반드시 기록되도록 종료 저장 경로를 보강했습니다.

4. 운영 UI 진단 탭 확장(최소 범위)
- `선택 종목 재동기화` / `sync_failed 해제 요청` 액션을 추가했습니다.
- pending state/잔량/sync_failed 사유와 선택 종목 상세 패널을 노출하도록 진단 탭을 확장했습니다.

5. 빌드 스펙 점검(`KiwoomTrader.spec`)
- 당시 변경은 런타임 로직 중심이었고, 이후 2026-03-09 정적 분석 helper 모듈(`app.mixins._typing`) hiddenimport가 추가되었습니다.

6. 최신 테스트 기준
```bash
python -m pytest -q tests/unit
```
- 결과: **83 passed** (2026-03-07)

---

## 2026-03-02 UI/UX 리팩토링 및 다크 테마 고도화

1. 고급 설정 탭 재조직 (`ui_build.py`):
- 기존 평면적 폼을 6개의 QGroupBox(기술지표, 리스크관리, 진입전략, 주문실행, v5.0, 시스템)로 분리해 가독성 강화.
- 기존 위젯 변수명과 시그널을 동일하게 유지해 하위 로직 호환성 100% 보장.

2. 프리미엄 다크 테마 적용 (`dark_theme.py`):
- 전면 리팩토링으로 대시보드 및 각종 위젯(QSplitter, ToolTip, Status 등 18종)의 스타일을 보완하여 UI 퀄리티 대폭 향상.

3. 버전 통일:
- 전체 소스 및 설정(.spec, config 등)의 기재 버전을 **v4.5**로 일원화.

6. v4 가드 상태머신(Fail-Closed)
- 기본 정책: `Fail-Closed` (불확실/오류 시 신규 진입 차단, 청산 허용)
- Shock: `abs(ret_1m) >= shock_1m_pct` 또는 `abs(ret_5m) >= shock_5m_pct` 시 global `shock` 진입
- VI/HALT: 공식 상태 우선, 미지원 시 price/spread proxy로 `vi` 판정
- `vi` 해제 후 `reopen_cooldown` 동안 신규 진입 차단
- Order health: 실패 이벤트 윈도우 임계치 초과 시 `degraded`, 쿨다운 후 자동 정상 복구

7. 진단/운영 지표(v4)
- 진단 컬럼: `market state`, `guard reason`, `risk mode`, `health mode`
- KPI: `guard_block_count_by_reason`, `shock_mode_minutes`, `order_health_degraded_count`, `avg_slippage_bps`
