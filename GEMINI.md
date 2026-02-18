# Kiwoom Pro Algo-Trader - Gemini AI 가이드

> 키움증권 REST API 기반 자동매매 프로그램 (v4.5)
>
> **최종 업데이트**: 2026-02-18

---

## 빠른 이해

이 프로젝트는 현재 **엔트리 래퍼 + 앱 패키지 분할 구조**입니다.

- 실행 진입점: `키움증권 자동매매.py`
- 실구현 클래스: `app/main_window.py`의 `KiwoomProTrader`
- 기능 모듈: `app/mixins/*.py`
- 공용 지원: `app/support/widgets.py`, `app/support/worker.py`

---

## 코드베이스 맵

```text
app/main_window.py
  - __init__
  - _connect_config_signals
  - signals: sig_log, sig_execution, sig_order_execution, sig_update_table

app/mixins/ui_build.py
  - UI 생성/탭 구성

app/mixins/market_data_tabs.py
  - 차트/호가/조건검색/순위조회

app/mixins/system_shell.py
  - 로깅, 메뉴, 트레이, 단축키, 종료

app/mixins/api_account.py
  - API 연결, 계좌 갱신, 실거래 확인 가드

app/mixins/trading_session.py
  - 시작/중지, 유니버스 초기화, 긴급청산

app/mixins/order_sync.py
  - 주문 상태 추적, 체결 동기화

app/mixins/execution_engine.py
  - 매수/매도 실행 및 콜백

app/mixins/persistence_settings.py
  - 거래내역, 통계, 설정 저장/복원

app/mixins/dialogs_profiles.py
  - 프리셋/프로필/수동주문/예약 다이얼로그
```

---

## 핵심 도메인 포인트

1. 실거래 안전장치
- `start_trading()`에서 실전 모드 시 확인 문구/타임아웃 가드 적용
- 관련 상수: `Config.LIVE_GUARD_*`

2. 전략 데이터 정합성
- `universe`에 `prev_high`, `prev_low`, `daily_prices`, `minute_prices` 유지
- 목표가는 전일 변동폭 기반

3. 진입점수 설정화
- 하드코딩 상수 대신 `TradingConfig.use_entry_scoring`, `TradingConfig.entry_score_threshold` 사용

4. 주문 안전성
- 실행 이벤트는 `is_running` 상태 가드 하에서만 신규 주문 검토

---

## 개발 시 권장 절차

1. 기능 수정 위치 확인
- UI면 `ui_build.py`
- 주문/체결이면 `execution_engine.py`, `order_sync.py`
- 설정/영속성은 `persistence_settings.py`

2. 변경 후 최소 검증

```bash
python -c "import py_compile, pathlib; py_compile.compile('키움증권 자동매매.py', doraise=True); [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('app').rglob('*.py')]"
python tools/refactor_verify.py
```

3. 설정 키 변경 시
- `_save_settings`
- `_load_settings`
- `_get_current_settings`
- `_apply_settings`
동시에 반영

---

## 실행/빌드

```bash
# 개발 실행
python "키움증권 자동매매.py"

# 빌드
pyinstaller KiwoomTrader.spec
```

출력(ONEFILE):
- `dist/KiwoomTrader_v4.5.exe`

---

## 설정 파일

| 파일 | 용도 |
|------|------|
| `kiwoom_settings.json` | 사용자 설정 저장 |
| `kiwoom_presets.json` | 프리셋 저장(필요 시 생성) |
| `kiwoom_token_cache.json` | 인증 토큰 캐시 |
| `data/*.json` | 프로필 데이터 |

---

## 주의사항

1. `키움증권 자동매매.py`에 비즈니스 로직을 다시 붙이지 않습니다.
2. 믹스인 간 책임을 넘나드는 수정은 최소화합니다.
3. 메서드/시그널/설정키 누락 여부는 `tools/refactor_verify.py`로 확인합니다.
4. 실거래 가드 및 주문 중복 방지 로직은 유지합니다.

---

## 2026-02-18 추가 업데이트

### 1) 구조 동기화 포인트
- `app/support/execution_policy.py`가 주문 실행 정책(`market`/`limit`) 라우팅을 담당합니다.
- 전략/연구 확장 경로가 실제 패키지로 존재합니다:
  - `strategies/`
  - `backtest/`
  - `portfolio/`
  - `data/providers/`
- `tools/perf_smoke.py`로 전략 평가 성능 스모크 테스트를 수행할 수 있습니다.

### 2) 설정 스키마 기준
- 현재 canonical 스키마는 `settings_version = 3` 입니다.
- v2 파일은 로드 시 v3 키가 자동 보강되며, `betting` 키는 호환 목적으로 계속 처리됩니다.

### 3) 테스트 기준
```bash
pytest -q tests/unit
```
- 2026-02-18 실행 결과: **15 passed, 2 warnings**
- 경고는 `websockets.legacy` deprecation 관련입니다.
