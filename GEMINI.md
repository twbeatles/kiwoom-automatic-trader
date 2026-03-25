# Kiwoom Pro Algo-Trader - Gemini AI 가이드

> 키움증권 REST API 기반 자동매매 프로그램 (v4.5)
>
> **최종 업데이트**: 2026-03-25

---

## 빠른 이해

이 프로젝트는 현재 **엔트리 래퍼 + 앱 패키지 분할 구조**입니다.

- 실행 진입점: `키움증권 자동매매.py`
- 실구현 클래스: `app/main_window.py`의 `KiwoomProTrader`
- 기능 모듈: `app/mixins/*.py`
- 타입 보조: `app/mixins/_typing.py`의 `TraderMixinBase`
- 공용 지원: `app/support/widgets.py`, `app/support/worker.py`
- 주문 라우팅 지원: `app/support/execution_policy.py`
- UI 텍스트/콤보 표시값 헬퍼: `app/support/ui_text.py`

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

app/mixins/market_intelligence.py
  - 뉴스/공시/검색트렌드/매크로 수집, 브리핑, 경보, 인텔리전스 탭

app/mixins/persistence_settings.py
  - 거래내역, 통계, 설정 저장/복원

app/mixins/dialogs_profiles.py
  - 프리셋/프로필/수동주문/예약 다이얼로그

app/mixins/_typing.py
  - pyright용 type-only Qt mixin 베이스
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
pyright .
python -c "import py_compile, pathlib; py_compile.compile('키움증권 자동매매.py', doraise=True); [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('app').rglob('*.py')]"
python tools/refactor_verify.py
python -m pytest -q tests/unit
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
| `data/market_intelligence_events.jsonl` | 시장 인텔리전스 이벤트 로그 |
| `data/decision_audit.jsonl` | 시장 인텔리전스 결정 감사 로그 |
| `data/dart_corp_codes.json` | OpenDART 종목코드 캐시 |

---

## 2026-03-25 문서/리플레이/운영 가이드 동기화

1. 현재 canonical 설정 스키마는 `settings_version = 6` 입니다.
2. `TradingConfig.market_intelligence`는 `source_policy`, `soft_scale`, `position_defense`, `portfolio_budget`, `candidate_universe`, `replay`를 포함합니다.
3. 메인 UI는 `🎯 핵심 설정`, `🛠 상세 설정`, `🧠 인텔리전스 설정`, `🧠 인텔리전스 현황`, `📼 인텔리전스 리플레이`, `🔐 API/알림` 구조이며, 감사 로그는 `data/decision_audit.jsonl`에 기록됩니다.
4. 운영 문서:
   - `MARKET_INTELLIGENCE_AUTOTRADING_ADDENDUM.md`
   - `REAL_API_PREPARATION_GUIDE.md`
5. 최신 검증 결과는 `python -m pytest -q tests/unit` 기준 `tests/unit` 전체 104개 테스트 통과 (2026-03-25 재실행 기준) 입니다.

6. 구현 정합성 메모
- `IMPLEMENTATION_REVIEW_2026-03-25.md`에 코드 기준 잠재 이슈와 후속 구현 과제를 별도 정리했습니다.
- `분할 매수`는 현재 UI/설정/프로필 경로까지 연결되어 있으며, 실주문 분할 라우팅은 후속 구현 범위입니다.
- 전략팩의 SHORT 방향 전략(`pairs_trading_cointegration`, `stat_arb_residual`, `ff5_factor_ls`)은 현재 실주문이 아니라 백테스트/시뮬레이션 범위로 취급해야 합니다.
- 문서 정합성 점검 시 `QApplication + KiwoomProTrader()` 오프스크린 UI 생성 스모크 테스트를 함께 보는 편이 안전합니다.

---

## 2026-03-24 시장 인텔리전스 동기화

1. 현재 canonical 설정 스키마는 `settings_version = 6` 입니다.
2. `TradingConfig.market_intelligence`와 `universe[code]["market_intel"]`가 현재 시장 인텔리전스 상태의 기준 필드입니다.
3. 신규 provider:
   - `data/providers/news_provider.py`
   - `data/providers/naver_trend_provider.py`
   - `data/providers/ai_provider.py`
4. 전략/전략팩/백테스트는 다음 guard/filter를 공유합니다.
   - `news_risk_guard`
   - `disclosure_event_guard`
   - `macro_regime_guard`
   - `theme_heat_filter`
   - `intel_fresh_guard`
5. 패키징은 `KiwoomTrader.spec`의 explicit hiddenimports + `collect_submodules('app')`, `collect_submodules('data.providers')`로 동기화됩니다.
6. 이벤트 로그는 `data/market_intelligence_events.jsonl`, 감사 로그는 `data/decision_audit.jsonl`를 사용합니다.
7. 최신 검증 결과는 상단 `2026-03-25 문서/리플레이/운영 가이드 동기화` 섹션을 기준으로 확인합니다.

---

## 주의사항

1. `키움증권 자동매매.py`에 비즈니스 로직을 다시 붙이지 않습니다.
2. 믹스인 간 책임을 넘나드는 수정은 최소화합니다.
3. 메서드/시그널/설정키 누락 여부는 `tools/refactor_verify.py`로 확인합니다.
4. 새 믹스인은 `TraderMixinBase` 상속 패턴을 유지해 런타임 MRO와 pyright 정합성을 함께 보장합니다.
5. 실거래 가드 및 주문 중복 방지 로직은 유지합니다.

---

## 2026-03-09 정적 분석/문서 동기화

1. 정적 분석 기준
- 루트 `pyrightconfig.json`을 추적하며 `pythonVersion = 3.14` 기준으로 repo 전체를 검사합니다.
- cache 디렉터리만 제외하고 테스트/도구 폴더도 포함합니다.

2. 동적 믹스인 타입 안정화
- `app/mixins/_typing.py`의 `TraderMixinBase`로 동적 UI 속성과 `QMainWindow` 성격을 type-check 단계에서만 부여합니다.
- 런타임 동작을 바꾸지 않고 pyright 오류를 줄이는 것이 목적입니다.

3. 최신 검증 결과
```bash
pyright .
python -m pytest -q tests/unit
```
- 결과: `0 errors, 0 warnings` (2026-03-09 당시 환경)
- 결과: `83 passed` (2026-03-09)

4. 패키징/무시 규칙 동기화
- `KiwoomTrader.spec` hiddenimports에 `app.mixins._typing`이 포함됩니다.
- `.gitignore`는 `pyrightconfig.json`을 예외로 유지합니다.
- 현재 워크스페이스에서 `pyright .`를 다시 실행하려면 `PyQt6`, `requests`, `websockets`, `urllib3`, `keyring` 로컬 의존성이 필요합니다.

---

## 2026-02-18 추가 업데이트

### 1) 구조 동기화 포인트
- `app/support/execution_policy.py`가 주문 실행 정책(`market`/`limit`) 라우팅을 담당합니다.
- 전략/연구 확장 경로가 실제 패키지로 존재합니다:
  - `strategies/`
  - `backtest/`
  - `portfolio/`
  - `data/providers/` (`kiwoom`, `dart`, `macro`, `csv`, `news`, `naver_trend`, `ai`)
- `tools/perf_smoke.py`로 전략 평가 성능 스모크 테스트를 수행할 수 있습니다.

### 2) 설정 스키마 기준
- 현재 canonical 스키마는 `settings_version = 6` 입니다.
- `settings_version < 6` 파일은 로드 시 v4 가드 키와 `market_intelligence` 블록이 자동 보강됩니다.

### 3) 테스트 기준
```bash
pytest -q tests/unit
```
- 테스트 건수는 지속 증가하므로, 최신 결과는 하단 `2026-03-05 v4 Guard 동기화` 섹션을 기준으로 확인합니다.

---

## 2026-02-19 안정성 동기화 보강

### 1) 매매 시작/동기화 정책
- `start_trading()`은 유니버스 초기화 직후 `get_positions()` 스냅샷 동기화가 성공해야 시작됩니다.
- 포지션 동기화 재시도 초과 시 종목 상태가 `sync_failed`로 전환되며 해당 종목 자동주문이 차단됩니다.

### 2) 리스크/손익 기준
- 일일 손실 제한은 누적 세션 손익이 아니라 `daily_realized_profit / daily_initial_deposit` 기준으로 계산됩니다.
- 날짜 변경 시 일일 손익/기준 예수금이 롤오버됩니다.

### 3) 경로/환경 정합성
- `Config.BASE_DIR` 기반 절대경로로 설정/로그/거래내역/프리셋 파일 위치를 고정했습니다.
- `KiwoomAuth` 토큰 캐시 기본 경로도 `BASE_DIR` 기준으로 동기화되었습니다.

### 4) 최신 테스트 기준
```bash
pytest -q tests/unit
```
- 상세 수치는 하단 최신 동기화 섹션 기준으로 관리합니다.

---

## 2026-03-02 UI/UX 리팩토링 및 다크 테마 고도화

### 1) UI 레이아웃 개선
- `ui_build.py`의 상세 설정을 6개 하위 탭(진입 판단, 리스크 관리, 주문/청산, 전략팩/백테스트, 시장 급변동 보호, 시스템)으로 재구성하여 사용성 강화.
- 위젯 객체명과 시그널은 그대로 유지하여 비즈니스 로직(특히 설정 및 체결 동기화 로직)에 영향을 주지 않도록 설계되었습니다.

### 2) 다크 테마 및 버전 통합
- `dark_theme.py`를 전면 개편하여 누락된 위젯 스타일을 보완하고, 대시보드의 시인성을 높이는 프리미엄 테마를 완성했습니다.
- 코드베이스 전반의 버전을 **v4.5**로 통일했습니다.

---

## 2026-03-05 v4 Guard 동기화

1. Fail-Closed 정책
- 가드 판정 불확실/오류 시 신규 진입은 차단하고 청산은 허용합니다.

2. 상태머신
- `shock`: 시장 급변동 감지 시 세션 단위 진입 차단
- `vi/halt`: 종목 단위 진입 차단
- `reopen_cooldown`: VI/HALT 해제 직후 재개장 쿨다운
- `order_health=degraded`: 주문 실패 급증 시 세션 단위 진입 차단

3. 진단 컬럼
- `market state`, `guard reason`, `risk mode`, `health mode`

4. 최신 검증 결과
- `python -m pytest tests/unit --disable-warnings`
- 결과: **68 passed in 1.36s** (2026-03-05)

---

## 2026-03-07 기능 안정화 동기화

1. 주문/포지션 동기화 상태머신
- `pending_order_state`를 `submitted/partial/filled/cancelled/rejected/sync_failed` 상태로 확장.
- 주문번호/요청수량/누적체결/잔량/예상가/갱신시각 추적 반영.
- 부분체결 시 예약금 전액 해제 제거, 체결분만 차감.

2. 리스크/운영 정책 정합화
- 레짐 사이징 중복 제거(전략 수량 계산 경로로 일원화).
- 매도 시 시장/섹터 투자금 장부를 원가 기반으로 감소하도록 보정.
- 세션 인입 포지션은 `TIME_STOP` 제외, 세션 신규 진입 포지션만 적용.
- 진단 탭에 선택 종목 재동기화/`sync_failed` 해제 요청/상세 사유 패널 추가.

3. 백테스트/저장 안정성
- 백테스트 다종목 MTM을 심볼별 최신가 캐시 기반으로 보정.
- 거래내역 저장 경로를 single-writer(순차 저장)로 전환.
- 종료 flush 시 최신 스냅샷 강제 기록 경로를 추가.

4. 빌드 스펙 점검
- 당시 변경은 런타임 로직 중심이었고, 이후 2026-03-09 정적 분석 helper 모듈(`app.mixins._typing`) hiddenimport가 추가되었습니다.

5. 당시 검증 결과 (2026-03-07)
- `python -m pytest -q tests/unit`
- 결과: **83 passed** (2026-03-07)
