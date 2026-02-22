# 🚀 Kiwoom Pro Algo-Trader v4.5

키움증권 REST API 기반 프리미엄 자동매매 프로그램

<div align="center">

![Version](https://img.shields.io/badge/version-4.5-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.5+-orange.svg)
![License](https://img.shields.io/badge/license-MIT-red.svg)

</div>

---

## 📋 목차

- [소개](#-소개)
- [주요 기능](#-주요-기능)
- [v4.5 신규 기능](#-v45-신규-기능)
- [기술 스택](#-기술-스택)
- [프로젝트 구조](#-프로젝트-구조)
- [설치 및 실행](#-설치-및-실행)
- [사용 방법](#-사용-방법)
- [키보드 단축키](#-키보드-단축키)
- [매매 전략](#-매매-전략)
- [리스크 관리](#-리스크-관리)
- [2026-02-19 안정성 동기화 업데이트](#-2026-02-19-안정성-동기화-업데이트)
- [주의사항](#-주의사항)

---

## 📖 소개

**Kiwoom Pro Algo-Trader**는 키움증권 REST API를 활용한 전문가급 자동매매 프로그램입니다. 
PyQt6 기반의 직관적인 GUI와 30개 이상의 고급 기능을 제공하여 효율적인 알고리즘 트레이딩을 지원합니다.

### ✨ 주요 특징

- 🎯 **변동성 돌파 전략** - 래리 윌리엄스의 검증된 전략 기반
- 📊 **다중 기술지표** - RSI, MACD, Bollinger Bands, Stochastic RSI, ATR, DMI 등
- 🛡️ **고급 리스크 관리** - 동적 포지션 사이징, 시장/섹터 분산, ATR 손절
- 🎨 **프리미엄 UI/UX** - 모던 대시보드, 다크/라이트 테마
- 🖥️ **시스템 통합** - 윈도우 시작 시 자동 실행, 트레이 최소화 모드
- 📱 **실시간 모니터링** - WebSocket 기반 실시간 호가/체결 데이터
- 💾 **다중 프로필** - 설정 프로필 저장/불러오기

---

## 🎯 주요 기능

### 1. 📈 매매 전략 (13가지)

#### 기본 전략
- **변동성 돌파 전략** - 목표가 = 시가 + (전일 변동폭 × K값)
- **이동평균 크로스오버** - 단기/장기 이평선 골든크로스

#### 보조 지표
- **RSI (Relative Strength Index)** - 과매수/과매도 판단
- **Stochastic RSI** 🆕 - RSI보다 민감한 모멘텀 지표
- **MACD** - 추세 추종 및 골든크로스 확인
- **Bollinger Bands** - 변동성 기반 과매수/과매도
- **ATR (Average True Range)** - 변동성 측정
- **DMI/ADX** - 추세 강도 판단
- **거래량 분석** - 평균 거래량 대비 급증 확인

#### 고급 전략
- **다중 시간프레임(MTF)** 🆕 - 일봉+분봉 추세 일치 확인
- **진입 점수 시스템** 🆕 - 여러 지표 종합 점수화 (60점 이상 진입)
- **갭 분석** 🆕 - 시가갭에 따른 K값 자동 조정
- **시간대별 전략** - 장 초반/중반/후반 전략 차별화
- **유동성 필터** 🆕 - 20일 평균 거래대금 기준 필터
- **스프레드 필터** 🆕 - 호가 스프레드 제한
- **돌파 확인** 🆕 - 목표가 돌파 후 N틱 유지 시 진입

---

### 2. 🛡️ 리스크 관리 (10가지)

#### 손절/익절
- **트레일링 스톱** - 고점 추적 후 일정 비율 하락 시 청산
- **단계별 익절** 🆕 - 3%/5%/8% 도달 시 분할 청산 (30%/30%/20%)
- **ATR 손절** 🆕 - 변동성 기반 동적 손절선
- **손절률 설정** - 절대 손절 기준 (기본 2%)

#### 포지션 관리
- **동적 포지션 사이징** 🆝 - Anti-Martingale (연속 손실 시 투자금 자동 축소)
- **ATR 포지션 사이징** - 변동성에 따른 투자 규모 조정
- **분할 매수** - 여러 번에 걸쳐 분산 진입
- **최대 보유 종목 수 제한** - 과도한 분산 방지
- **재진입 쿨다운** 🆕 - 매도 후 일정 시간 재진입 제한
- **시간 청산** 🆕 - 보유 시간이 기준을 넘으면 자동 청산

#### 분산 투자
- **시장 분산** 🆕 - 코스피/코스닥 비중 제한 (기본 70%)
- **섹터 제한** 🆕 - 동일 업종 최대 투자 비중 (기본 30%)

#### 긴급 대응
- **긴급 전체 청산** 🆕 - 원클릭으로 모든 보유 종목 일괄 매도
- **일일 최대 손실 제한** - 일일 손실률 도달 시 자동 매매 중지

---

### 3. 🔧 편의 기능 (10가지)

- **완벽한 한글화** 🆕 - 모든 메뉴, 버튼, 메시지 한글 적용 (v4.4)
- **시스템 트레이** 🆕 - 종료 시 트레이로 최소화 (v4.4)
- **자동 실행** 🆕 - 윈도우 시작 시 프로그램 자동 실행 (v4.4)
- **종목 검색** - 종목명으로 코드 빠르게 검색
- **수동 주문** - GUI를 통한 수동 매수/매도 주문
- **예약 매매** - 시작/종료 시간 예약 (기본 09:00 ~ 15:19)
- **다중 프로필** - 설정 프로필 저장/불러오기
- **프리셋 시스템** - 공격적/표준/보수적/스캘핑 프리셋 제공
- **텔레그램 알림** - 매수/매도 실시간 알림
- **사운드 알림** - 거래 발생 시 알림음 재생
- **테마 전환** - 다크/라이트 테마 (Ctrl+T)

---

## 🆕 v4.5 신규 기능

v4.5는 **보안(Security)** 및 **시스템 통합(Integration)** 중심의 메이저 업데이트입니다.

### 🛡️ 보안 강화 (Security)
- **Safe Key Storage**: API Key/Secret을 `kiwoom_settings.json` (평문)에서 **Windows Credential Manager** (암호화)로 자동 마이그레이션
- **OS 레벨 보호**: 로컬 파일 탈취 시에도 중요 키 유출 방지

### 🖥️ 시스템 통합 (System Integration)
| 기능 | 설명 | 효과 |
|------|------|------|
| **자동 실행** | 윈도우 부팅 시 자동 시작 (Registry) | HTS/서버 점검 후 자동 복구 |
| **트레이 모드** | 종료 시 트레이로 최소화 | 실수로 인한 종료 방지 |
| **실시간 체결** | WebSocket 주문 체결(Chejan) 연동 | 즉각적인 잔고/주문 상태 동기화 |

### ⚡ 성능 최적화
- **비동기 주문**: 주문 요청을 Worker 스레드로 분리하여 UI 프리징 0.1초 미만으로 단축
- **비동기 API 연결**: `connect_api()`를 백그라운드 Worker로 분리해 연결 시 UI 응답성 유지
- **Thread-Safety**: API 요청 간 락(Lock) 구현으로 멀티스레드 안정성 확보
- **종료 경로 단일화**: 강제 종료/일반 종료 모두 `closeEvent()` 정리 루틴으로 통합

---

## 🛠️ 기술 스택

### Core
- **Python** 3.8+
- **PyQt6** 6.5+ - 모던 GUI 프레임워크
- **Kiwoom REST API** - 키움증권 공식 API

### Libraries
```
PyQt6>=6.5.0          # GUI 프레임워크
requests>=2.28.0      # HTTP 클라이언트
websockets>=11.0,<16  # WebSocket 실시간 통신 (호환 범위 고정)
keyring>=23.0.0       # 보안 키 저장
python-dateutil>=2.8.0 # 날짜/시간 처리
```

### API Architecture
- **REST API** - 주문, 잔고, 시세 조회
- **WebSocket** - 실시간 호가/체결 데이터
- **비동기 처리** - 논블로킹 네트워크 통신

---

## 📁 프로젝트 구조

> 기준: `git -c core.quotePath=false ls-files` (Git 추적 파일 1:1)

```text
키움증권 자동 매매 프로그램/
├── api/
│   ├── __init__.py
│   ├── auth.py
│   ├── models.py
│   ├── rest_client.py
│   └── websocket_client.py
├── app/
│   ├── mixins/
│   │   ├── __init__.py
│   │   ├── api_account.py
│   │   ├── dialogs_profiles.py
│   │   ├── execution_engine.py
│   │   ├── market_data_tabs.py
│   │   ├── order_sync.py
│   │   ├── persistence_settings.py
│   │   ├── system_shell.py
│   │   ├── trading_session.py
│   │   └── ui_build.py
│   ├── support/
│   │   ├── __init__.py
│   │   ├── execution_policy.py
│   │   ├── widgets.py
│   │   └── worker.py
│   ├── __init__.py
│   └── main_window.py
├── backtest/
│   ├── __init__.py
│   └── engine.py
├── backup/
│   ├── refactor_phase0/
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── refactor_phase1/
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── refactor_phase2/
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── refactor_phase3/
│   │   ├── app/
│   │   │   ├── mixins/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api_account.py
│   │   │   │   ├── dialogs_profiles.py
│   │   │   │   ├── execution_engine.py
│   │   │   │   ├── market_data_tabs.py
│   │   │   │   ├── order_sync.py
│   │   │   │   ├── persistence_settings.py
│   │   │   │   ├── system_shell.py
│   │   │   │   ├── trading_session.py
│   │   │   │   └── ui_build.py
│   │   │   ├── support/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── widgets.py
│   │   │   │   └── worker.py
│   │   │   ├── __init__.py
│   │   │   └── main_window.py
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── refactor_phase4/
│   │   ├── app/
│   │   │   ├── mixins/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api_account.py
│   │   │   │   ├── dialogs_profiles.py
│   │   │   │   ├── execution_engine.py
│   │   │   │   ├── market_data_tabs.py
│   │   │   │   ├── order_sync.py
│   │   │   │   ├── persistence_settings.py
│   │   │   │   ├── system_shell.py
│   │   │   │   ├── trading_session.py
│   │   │   │   └── ui_build.py
│   │   │   ├── support/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── widgets.py
│   │   │   │   └── worker.py
│   │   │   ├── __init__.py
│   │   │   └── main_window.py
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── refactor_phase5/
│   │   ├── app/
│   │   │   ├── mixins/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api_account.py
│   │   │   │   ├── dialogs_profiles.py
│   │   │   │   ├── execution_engine.py
│   │   │   │   ├── market_data_tabs.py
│   │   │   │   ├── order_sync.py
│   │   │   │   ├── persistence_settings.py
│   │   │   │   ├── system_shell.py
│   │   │   │   ├── trading_session.py
│   │   │   │   └── ui_build.py
│   │   │   ├── support/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── widgets.py
│   │   │   │   └── worker.py
│   │   │   ├── __init__.py
│   │   │   └── main_window.py
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── refactor_phase6/
│   │   ├── app/
│   │   │   ├── mixins/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── api_account.py
│   │   │   │   ├── dialogs_profiles.py
│   │   │   │   ├── execution_engine.py
│   │   │   │   ├── market_data_tabs.py
│   │   │   │   ├── order_sync.py
│   │   │   │   ├── persistence_settings.py
│   │   │   │   ├── system_shell.py
│   │   │   │   ├── trading_session.py
│   │   │   │   └── ui_build.py
│   │   │   ├── support/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── widgets.py
│   │   │   │   └── worker.py
│   │   │   ├── __init__.py
│   │   │   └── main_window.py
│   │   ├── KiwoomTrader.spec
│   │   └── 키움증권 자동매매.py
│   ├── KiwoomProTrader.spec
│   ├── upbit_trader.py
│   ├── verify_decoupling.py
│   ├── verify_phase3.py
│   ├── verify_phase4.py
│   └── 키움증권 자동매매_old.py
├── data/
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── csv_provider.py
│   │   ├── dart_provider.py
│   │   ├── kiwoom_provider.py
│   │   └── macro_provider.py
│   └── __init__.py
├── dist_new/
│   └── KiwoomTrader_v4.5.exe
├── portfolio/
│   ├── __init__.py
│   └── allocator.py
├── strategies/
│   ├── __init__.py
│   ├── base.py
│   ├── pack.py
│   └── types.py
├── tests/
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_backtest_engine.py
│   │   ├── test_dirty_table_refresh.py
│   │   ├── test_execution_policy.py
│   │   ├── test_force_quit_close_event.py
│   │   ├── test_order_sync_to_int.py
│   │   ├── test_position_sync_debounce.py
│   │   ├── test_settings_schema_compat.py
│   │   ├── test_settings_schema_v3.py
│   │   ├── test_strategy_decision_cache.py
│   │   ├── test_strategy_pack_engine.py
│   │   └── test_trading_session_state_machine.py
│   └── __init__.py
├── tools/
│   ├── __init__.py
│   ├── perf_smoke.py
│   ├── refactor_manifest.py
│   └── refactor_verify.py
├── .gitignore
├── CLAUDE.md
├── config.py
├── dark_theme.py
├── GEMINI.md
├── icon.png
├── KiwoomTrader.spec
├── light_theme.py
├── profile_manager.py
├── PROJECT_STRUCTURE_ANALYSIS.md
├── README.md
├── sound_notifier.py
├── STRATEGY_EXPANSION_BLUEPRINT.md
├── strategy_manager.py
├── telegram_notifier.py
├── ui_dialogs.py
└── 키움증권 자동매매.py
```

### 파일별 역할

| 파일 | 라인 수 | 주요 기능 |
|------|---------|-----------|
| `키움증권 자동매매.py` | 얇은 엔트리 | `app.main_window.KiwoomProTrader` 실행 래퍼 |
| `app/main_window.py` | 238 | 메인 클래스 선언 + 공용 시그널 + 초기화 |
| `app/mixins/*.py` | 분할 모듈 | UI/API/주문/저장/다이얼로그 기능별 구현 |
| `strategy_manager.py` | 1158 | 매매 전략 로직, 지표 계산 |
| `config.py` | 517 | 설정 상수, 실거래 가드, 기본값 |
| `ui_dialogs.py` | 577 | 검색/주문/설정 다이얼로그 |

---

## 🚀 설치 및 실행

### 1. 요구사항

- **Python** 3.8 이상
- **키움증권 API 계정** (App Key, Secret Key)
- **Windows OS** (PyQt6 호환)


### 2. 설치

```bash
# 저장소 클론 (또는 다운로드)
cd "키움증권 자동 매매 프로그램"

# 의존성 설치
pip install -r requirements.txt
```

### 3. 실행

```bash
python "키움증권 자동매매.py"
```

### 4. 빌드 (선택사항)

PyInstaller로 실행 파일 생성:

```bash
pyinstaller KiwoomTrader.spec
```

빌드된 실행 파일(ONEFILE)은 `dist/KiwoomTrader_v4.5.exe`로 생성됩니다.

---

## 🧪 리팩토링 동등성 검증

코드 분할 이후 누락 방지를 위해 아래 검증을 권장합니다.

```bash
# 기준선 생성 (최초 1회)
python tools/refactor_manifest.py --source "app/main_window.py" --output docs/refactor/baseline_manifest.json

# 현재 구조 동등성 검증
python tools/refactor_verify.py
```

검증 항목:
- `KiwoomProTrader` 메서드 집합 동등성
- 필수 시그널(`sig_log`, `sig_execution`, `sig_order_execution`, `sig_update_table`)
- `_save_settings/_load_settings/_get_current_settings/_apply_settings` 키 parity
- 단축키 키셋 parity

---

## 🔄 2026-02-19 안정성 동기화 업데이트

이번 추가 업데이트는 실제 저장소 상태(`tree /F /A`)와 테스트 실행 결과(`python -m pytest -q tests/unit`)를 기준으로 문서를 동기화한 내용입니다.

### 현재 코드베이스에서 확인된 핵심 패키지

- `app/support/execution_policy.py` - 주문 실행 정책(`market`/`limit`) 라우팅
- `strategies/` - `types.py`, `base.py`, `pack.py` 기반 모듈형 전략 엔진
- `backtest/engine.py` - 이벤트 드리븐 백테스트 엔진
- `portfolio/allocator.py` - 리스크 예산 기반 가중치 배분기
- `data/providers/` - `kiwoom`, `dart`, `macro`, `csv` 데이터 프로바이더 계층
- `tests/unit/` - 전략팩/백테스트/설정 스키마 v3/실행 정책 검증 테스트

### README 기존 트리 대비 보강 포인트

- `app/support/`에는 `widgets.py`, `worker.py` 외에 `execution_policy.py`가 포함됩니다.
- `docs/refactor/`에는 `baseline_manifest.json` 외에 `post_refactor_manifest.json`도 존재합니다.
- 루트 패키지로 `strategies/`, `backtest/`, `portfolio/`가 추가되어 확장 경로가 코드화되어 있습니다.
- `tools/perf_smoke.py`로 전략 평가 경로의 로컬 성능 스모크 테스트를 수행할 수 있습니다.
- `start_trading()`은 유니버스 초기화 후 계좌 포지션 스냅샷 동기화가 성공해야만 시작됩니다.
- 포지션 동기화 실패가 누적되면 종목 상태가 `sync_failed`로 전환되어 해당 종목 자동 주문이 차단됩니다.
- 설정/로그/내역 경로는 `Config.BASE_DIR` 기준 절대경로로 고정되어 실행 위치(CWD) 영향이 제거되었습니다.

### 테스트 현황 (2026-02-19)

```bash
python -m pytest -q tests/unit
```

- 테스트 결과는 실행 환경/의존성 버전에 따라 달라질 수 있으므로 위 커맨드로 실시간 확인합니다.

---

## 📚 사용 방법

### 1단계: API 설정

1. 키움증권에서 REST API 신청
2. App Key / Secret Key 발급
3. 프로그램 실행 후 **API 설정** 탭에서 키 입력
4. **🔗 API 연결** 버튼 클릭 (또는 `Ctrl+L`)

### 2단계: 종목 선택

**방법 1: 직접 입력**
```
005930,000660,042700,005380
```

**방법 2: 종목 검색 (Ctrl+F)** 🆕
- 종목명은 로컬 캐시에서 검색
- 6자리 종목코드는 API로 즉시 확인
- 검색 결과 클릭하여 추가

### 3단계: 전략 설정

#### 프리셋 사용 (초보자 권장)
- **🛡️ 보수적** - 안정적인 수익, 낮은 리스크
- **⚖️ 표준** - 균형 잡힌 수익과 리스크 (권장)
- **🔥 공격적** - 높은 수익, 높은 리스크
- **⚡ 스캘핑** - 빠른 진입/청산

#### 수동 설정 (고급 사용자)
- **K값** (0.3 ~ 0.5) - 변동성 돌파 계수
- **베팅 비율** (5% ~ 20%) - 종목당 투자 비율
- **트레일링 스톱** (발동: 3%, 하락: 1.5%)
- **손절률** (2%)
- **RSI 상한** (70)
- **최대 보유 종목** (5개)

### 4단계: 매매 시작

- **🚀 매매 시작** 버튼 클릭 (또는 `Ctrl+S`)
- 실시간 로그 모니터링
- 보유 종목 및 수익률 확인

### 5단계: 매매 중지

- **⏹️ 매매 중지** 버튼 클릭 (또는 `Ctrl+Q`)
- **🚨 긴급 청산** (또는 `Ctrl+Shift+X`) - 모든 보유 종목 즉시 매도 🆕

---

## ⌨️ 키보드 단축키

> 현재 기본 제공 단축키 - 12가지 빠른 조작

| 단축키 | 기능 | 설명 |
|--------|------|------|
| **Ctrl+L** | API 연결 | API 연결/재연결 |
| **Ctrl+S** | 매매 시작 | 자동매매 시작 |
| **Ctrl+Q** | 매매 중지 | 자동매매 중지 |
| **Ctrl+Shift+X** | 긴급 청산 🆕 | 모든 보유 종목 즉시 매도 |
| **Ctrl+F** | 종목 검색 🆕 | 종목명으로 코드 검색 |
| **Ctrl+O** | 수동 주문 🆕 | 수동 매수/매도 창 열기 |
| **Ctrl+P** | 프로필 관리 🆕 | 설정 프로필 저장/불러오기 |
| **Ctrl+Shift+P** | 프리셋 관리 🆕 | 프리셋 저장/불러오기 창 열기 |
| **Ctrl+E** | CSV 내보내기 | 거래내역 CSV 저장 |
| **Ctrl+T** | 테마 전환 🆕 | 다크/라이트 테마 토글 |
| **F5** | 새로고침 | 모든 데이터 새로고침 |
| **F1** | 도움말 | 사용 가이드 열기 |

---

## 📈 매매 전략

### 기본 전략: 변동성 돌파

래리 윌리엄스(Larry Williams)의 검증된 전략을 기반으로 합니다.

```
목표가 = 시가 + (전일 고가 - 전일 저가) × K값
```

- **K값 0.5** (표준) - 균형 잡힌 진입
- **K값 0.3** (보수적) - 신중한 진입
- **K값 0.6** (공격적) - 적극적인 진입

### 진입 조건

1. ✅ 현재가가 목표가 돌파
2. ✅ RSI < 70 (과매수 아님)
3. ✅ MACD 골든크로스 확인 (선택)
4. ✅ 거래량이 평균 대비 1.5배 이상 (선택)
5. ✅ 진입 점수 60점 이상 (선택) 🆕

### 청산 조건

#### 익절
- **단계별 익절** 🆕
  - 1단계: +3% → 30% 청산
  - 2단계: +5% → 추가 30% 청산
  - 3단계: +8% → 추가 20% 청산
  
- **트레일링 스톱**
  - 수익률이 3% 도달 시 발동
  - 고점 대비 1.5% 하락 시 청산

#### 손절
- **고정 손절** - 매수가 대비 -2% 손절
- **ATR 손절** 🆕 - ATR × 2.0 기반 동적 손절
- **15시 19분** - 시장 종료 전 전량 청산

---

## 🛡️ 리스크 관리

### 1. 포지션 관리

#### 동적 포지션 사이징 🆕 (Anti-Martingale)
```python
연속 3회 손실 → 투자 비율 50% 축소
연속 3회 이익 → 투자 비율 150% 확대 (최대)
```

#### ATR 포지션 사이징
```python
포지션 크기 = (계좌 잔고 × 리스크%) / ATR
```

### 2. 분산 투자

#### 시장 분산 🆕
- 코스피 최대 70%
- 코스닥 최대 70%
- 양 시장 균형 투자 권장

#### 섹터 제한 🆕
- 동일 업종 최대 30%
- 22개 업종 분류 기준 (config.py)

### 3. 일일 손실 제한

```python
일일 손실률 > 3% → 자동 매매 중지
```

### 4. 포지션 동기화 Fail-safe

- 주문/체결 동기화가 종목 단위로 반복 실패하면 상태가 `sync_failed`로 전환됩니다.
- `sync_failed` 종목은 자동 진입/청산을 즉시 차단하고, 다른 종목 매매는 계속됩니다.
- 이후 계좌 포지션 동기화가 성공하면 해당 종목은 `watch`/`holding`으로 자동 복구됩니다.

### 5. 보유 종목 수 제한

```python
최대: 7개 (공격적)
표준: 5개
최소: 3개 (보수적)
```

---

## 🔔 알림 기능

### 1. 사운드 알림 🆕

설정에서 활성화:
- 매수 체결
- 매도 체결
- 수익 발생
- 손실 발생
- 오류 발생

### 2. 텔레그램 알림

1. 텔레그램 봇 생성 (BotFather)
2. Bot Token 및 Chat ID 입력
3. 설정에서 활성화

---

## ⚙️ 고급 설정

### 진입 점수 시스템 🆕

6개 지표를 종합하여 0~100점 평가:

| 지표 | 가중치 | 설명 |
|------|--------|------|
| 목표가 돌파 | 20 | 변동성 돌파 확인 |
| 이평선 필터 | 15 | 5일선 > 20일선 |
| RSI 최적값 | 20 | RSI 40~60 구간 |
| MACD 골든크로스 | 20 | MACD > Signal |
| 거래량 확인 | 15 | 평균 대비 1.5배 |
| 볼린저밴드 위치 | 10 | 하단 부근 (20~50%) |

**60점 이상**일 때만 진입 (설정 시)

---

## 🎨 테마

### 다크 테마 (기본)
- GitHub 스타일 다크 테마
- 눈의 피로 감소
- 프리미엄 그라디언트

### 라이트 테마 🆕
- 밝은 배경
- 선명한 텍스트
- Ctrl+T로 전환

---

## 📊 데이터 파일

### kiwoom_settings.json
```json
{
  "settings_version": 3,
  "codes": "005930,000660",
  "k_value": 0.5,
  "betting_ratio": 10.0,
  "betting": 10.0,
  ...
}
```
설정 스키마(v3) 정책:
- canonical 스키마는 `settings_version = 3`
- 저장은 `betting_ratio`를 기준으로 사용
- `betting`은 legacy 파일 호환을 위해 병행 저장/로드
- `settings_version < 3` 파일은 로드 시 v3 필드(`strategy_pack`, `feature_flags`, `execution_policy` 등)가 자동 보강됩니다.

### kiwoom_presets.json
```json
{
  "aggressive": { ... },
  "normal": { ... },
  "conservative": { ... }
}
```

---

## ⚠️ 주의사항

### 🚨 면책 조항

> **본 프로그램은 개인 학습 및 연구 목적으로 제작되었습니다.**

- ⚠️ **모의투자 환경**에서 충분한 테스트 후 사용하시기 바랍니다.
- ⚠️ **투자 손실에 대한 책임**은 전적으로 사용자에게 있습니다.
- ⚠️ 알고리즘 트레이딩은 **높은 리스크**를 동반합니다.
- ⚠️ 과거 수익률이 **미래 수익을 보장하지 않습니다**.

### 📝 권장사항

1. **소액 투자**로 시작하여 전략 검증
2. **보수적 프리셋**으로 시작 권장
3. **손절 설정 필수** - 큰 손실 방지
4. **일일 점검** - 매매 내역 및 수익률 확인
5. **백테스팅** - 과거 데이터로 전략 검증

### 🔒 보안

- **API Key**: `keyring` 모듈로 OS 레벨 암호화 저장 (Windows Credential Manager)
- **토큰**: 메모리 + 캐시 파일 저장 (만료 시 자동 삭제)
- **네트워크**: HTTPS/WSS 사용 (TLS 암호화)
- **설정 파일**: 로컬 저장 (Key/Secret 제외)

---

## 🤝 기여

버그 리포트 및 기능 제안은 이슈로 등록해 주세요.

---

## 📄 라이선스

MIT License

---

## 📞 문의

- **작성자**: Kiwoom Pro Algo-Trader
- **버전**: 4.5
- **최종 업데이트**: 2026-02-19

---

<div align="center">

**💡 Smart Trading with Kiwoom Pro Algo-Trader 💡**

</div>


