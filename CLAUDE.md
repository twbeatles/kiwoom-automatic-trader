# Kiwoom Pro Algo-Trader - Claude AI 개발 가이드

> 키움증권 REST API 기반 자동매매 프로그램 (v4.5)
>
> **최종 업데이트**: 2026-02-13

---

## 프로젝트 구조 (현행)

```text
키움증권 자동 매매 프로그램/
├── 키움증권 자동매매.py        # 엔트리포인트 래퍼(main)
├── app/
│   ├── main_window.py         # KiwoomProTrader 클래스(조립)
│   ├── mixins/
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
│   └── baseline_manifest.json
└── KiwoomTrader.spec
```

핵심 포인트:
- `키움증권 자동매매.py`는 더 이상 모놀리식 본체가 아닙니다.
- 실제 클래스는 `app.main_window.KiwoomProTrader` 입니다.
- 기능별 구현은 믹스인으로 분리되어 있습니다.

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

4. 실시간 처리:
- 체결: `_on_execution()`
- 주문체결: `_on_order_execution()`
- 매매 중지 상태(`is_running=False`)에서는 체결 기반 주문 진입 차단

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

- 설정 스키마(v2):
  - `settings_version: 2`
  - `betting_ratio`를 canonical로 사용
  - `betting`은 구버전 호환용으로 병행 유지

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

---

## 검증 커맨드

```bash
# 문법 검증
python -c "import py_compile, pathlib; py_compile.compile('키움증권 자동매매.py', doraise=True); [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('app').rglob('*.py')]"

# 분할 동등성 검증
python tools/refactor_verify.py
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
