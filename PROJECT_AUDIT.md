# Project Audit

> 기준 일자: 2026-07-27 (수정 적용: 2026-07-28)
> 대상 저장소: `kiwoom-automatic-trader` (Kiwoom Pro Algo-Trader v4.5)
> 감사 관점: 기능 구현상 잠재 문제, 예외 처리, 동시성, 보안, README/CLAUDE.md 정합성
> 감사 방법: README.md / CLAUDE.md 정독 → CodeGraph MCP 기반 호출 관계/영향 범위 분석 → 의심 영역 직접 열람
>
> ✅ **수정 적용 상태(2026-07-28)**: 아래 권장 수정안(Critical 2건, High 4건, Medium 3건, Low 1건 + Telegram 이스케이프 + 미체결 REST adapter)이 모두 코드에 반영되었습니다. 신규 단위 테스트 11개 파일이 추가되었고, 전체 검증(compileall / pytest 172 passed / pyright 0 errors / refactor_verify 통과)을 통과했습니다. 상세 내용은 CLAUDE.md `9. PROJECT_AUDIT 기반 안정성 패치 (2026-07-28)` 섹션을 참고하세요.

---

## 1. Executive Summary

이 프로젝트는 키움증권 REST API + WebSocket 기반 PyQt6 자동매매 프로그램으로, `signal_only` 기본 실행 모드, 실거래 보호 확인(`_confirm_live_trading_guard`), 예약금(virtual deposit) 기반 over-commit 방지, 주문 상태머신(`submitted/partial/filled/cancelled/rejected/sync_failed`), Qt 메인 스레드 디스패처 기반 WebSocket 콜백 처리 등 **실거래 시스템으로서 갖출 핵심 안전장치를 대부분 잘 갖추고 있다**. 코드는 feature 패키지(`app/features/*`)로 분리되어 있고 단위 테스트도 144개 수준으로 풍부하다.

그러나 **실거래 손실로 직결될 수 있는 기능적 결함 몇 가지**가 확인되었다. 전체 위험도는 **High**로 평가한다. 핵심 요약:

- **Critical**: `_execute_buy()`의 시장가 주문에서 `current_price == 0`일 때 잔액 검증이 무의미해지며, 가격 0 기준으로 예약금까지 잡은 뒤 시장가 주문이 전송될 수 있다. 체결가 추적·장부가 꼬일 수 있는 실거래 손실 경로다.
- **Critical**: `KiwoomAuth.get_token()` / `_request_new_token()`이 락 없이 WebSocket 스레드·REST Worker 스레드·UI 스레드에서 동시 호출될 수 있어, 토큰 만료 시점에 중복 발급 요청과 `_access_token`/`_expires_at` 경쟁 쓰기가 발생할 수 있다.
- **High**: `_save_settings()`(설정 파일)가 atomic write(`os.replace`)를 사용하지 않아, 저장 중 크래시/종료 시 `kiwoom_settings.json`이 깨지거나 절단될 수 있다. 반면 거래내역은 atomic write를 사용하고 있어 정합성이 불일치한다.
- **High**: 종료/중지 경로의 `_cleanup_active_orders()`가 폴링 루프 안에서 `app.processEvents()`를 호출한다. 이 시점에 동일 인스턴스의 시그널 슬롯(체결/주문 동기화)이 재진입되어 pending state가 변경되면 cleanup 판단이 부정확해질 수 있다.
- **High**: `keyring` 미사용 환경에서 secret fallback 정책이 `is_mock`일 때 무조건 평문 저장을 허용(`allow_secret_fallback = allow_plaintext or is_mock`)한다. 모의투자더라도 API key/secret이 평문으로 남는 경로가 열려 있다.
- **Medium**: README의 `백업 spec 패턴`, `tests/unit` 카운트(README 곳곳에 144/120/104/83 등 서로 다른 수치 혼재), v4.5 신규 기능 설명의 정합성에 미세한 불일치가 있다.

아래 항목들은 모두 실제 코드 라인 근거를 제시한다.

---

## 2. Project Understanding

### 2.1 목적 및 전반적 구조

- **목적**: 키움증권 REST API 기반 프리미엄 자동매매. 변동성 돌파 전략 중심에 RSI/MACD/BB/StochRSI/ATR/DMI/MTF 등 보조 지표와 진입 점수 시스템을 결합.
- **아키텍처 특징**:
  - 메인 클래스 `KiwoomProTrader`는 `app/core/window.py`에 시그널/런타임 상태만 두고, 실제 기능은 `app/features/*` 하위 믹스인 패키지로 분산(UI 빌드 / 거래 세션 / 실행 / 주문 동기화 / 영속화 / 마켓 인텔리전스 / 진단).
  - 루트의 `config.py`, `strategy_manager.py`, `ui_dialogs.py`, `app/main_window.py`는 기존 import 호환용 facade.
  - `StrategyManager`는 orchestration 레이어이고 평가/지표/리스크/인텔은 `strategies/manager_mixins/*`로 분리.
  - `api/` 패키지는 REST/WS 모델, 인증(`KiwoomAuth`), live/mock 엔드포인트 라우팅(`api/endpoints.py`), 클라이언트로 구성.

### 2.2 주요 실행 흐름 (CodeGraph 호출 관계 기반)

1. **시작**: `키움증권 자동매매.py::main()` → `KiwoomProTrader()`.
2. **API 연결**: `connect_api()`(api_account.py:48) → Worker로 `_connect_api_worker` → `KiwoomAuth.test_connection` + 계좌 목록 조회 → 성공 시 `rest_client`/`ws_client`/`auth`/`accounts`를 메인 스레드로 전달. 재진입 가드 `_connect_inflight`.
3. **매매 시작**: `start_trading()`(trading_session/lifecycle.py:90)
   - 코드 검증 → 실거래 가드 → preflight 로그 → `_init_universe`(시세/일봉/분봉 로드) → `_sync_positions_snapshot`(계좌 포지션 강제 반영, 실패 시 시작 중단) → WebSocket 구독 → `is_running=True`.
   - 중복 시작/예약 상태 고착 방지용 `_trading_start_inflight`, `_scheduled_start_requested`.
4. **실시간 처리**:
   - WebSocket 수신 → `_MainThreadDispatcher.invoke` 시그널 → 메인 스레드에서 `_on_realtime`/`_on_order_realtime` 실행 → 다시 `sig_execution`/`sig_order_execution` 시그널 emit → `_on_execution`(매수/매도 판단) / `_on_order_execution`(주문 체결 동기화).
   - 매수 판단은 `_on_execution` 내에서 가드/레짐/포지션 사이징을 거쳐 `_execute_buy` 호출.
5. **주문 실행**: `_execute_buy`/`_execute_sell`(execution/buy_flow.py, sell_flow.py)
   - `execution_mode == signal_only`면 주문 API 미호출, 감사 로그만.
   - live면 `ExecutionPolicy.select_buy/select_sell`로 market/limit 라우팅 후 Worker 비동기 전송.
   - 예약금(`_reserved_cash_by_code`/`virtual_deposit`)으로 동일 자금 중복 주문 방지.
6. **주문 동기화**: `_pending_order_state` 상태머신 + `_manual_pending_state` + `_sync_position_from_account` 폴링. `sync_failed` 상태로 fail-safe 차단.
7. **종료**: `stop_trading()` → `_cleanup_active_orders`(주문 취소 시도 + 폴링) → `finalize_cleanup`(reserved cash 정리). `closeEvent`에서 종료 플로우 보장.

### 2.3 안전장치 현황 (긍정적 측면)

- 기본 `execution_mode = signal_only`로 실주문 기본 차단.
- 실거래 시작/수동 주문마다 문구 입력 + 타임아웃 보호 확인(`_confirm_live_trading_guard`).
- WebSocket 콜백이 Qt 메인 스레드 디스패처(`_MainThreadDispatcher`)를 경유하도록 설계되어 UI 객체 직접 조작 위험 회피.
- REST 응답 숫자 변환 헬퍼(`_safe_int`/`_safe_float`)가 빈 값/콤마/부호/`--` 등을 안전 처리.
- 토큰 캐시는 atomic write(`os.replace`) + `chmod 0o600` 권한 보호.
- 거래내역 저장은 single-writer 비동기 + atomic write + 종료 flush 강화.
- `sync_failed` fail-safe로 동기화 실패 종목 자동 주문 차단.
- 분할 매수는 `execution_policy=limit`에서만 허용, child 주문 다건 제출.

---

## 3. High-Risk Issues

### 3.1 [Critical] 자동 매수 시장가 주문의 가격 0 잔액 검증 우회

- **위치**: `app/features/execution/buy_flow.py:357-362, 420-447` (`_execute_buy`)
- **문제**:
  ```python
  current_price = int(price) if int(price) > 0 else int(info.get("current", 0) or 0)
  ...
  required_cash = int(quantity) * current_price if current_price > 0 else 0
  if required_cash > available_cash:   # required_cash == 0 이면 항상 통과
      ...
  # 이후 signal_only가 아니면 _reserve_cash_for_buy(code, 0) → 시장가 주문 전송
  ```
  `price` 인자가 0이고 `info["current"]`도 아직 갱신되지 않았거나 0인 경우, `required_cash = 0`이 되어 잔액 검증을 무조건 통과한다. 그 상태로 `_reserve_cash_for_buy(code, 0)`(0원 예약) 후 `ExecutionPolicy.select_buy`가 `policy != limit`이면 `rest_client.buy_market(account, code, quantity)`를 호출한다.
- **영향**:
  - 잔액 부족 상태에서도 시장가 매수 주문이 브로커로 전송될 수 있어 키움 측 거부 또는 의도치 않은 과잉 주문 발생 가능.
  - 예약금이 0으로 잡혀 동일 자금으로 다른 종목까지 중복 진입 가능(`_holding_or_pending_count` 추적도 부정확).
  - 체결 후 장부(buy_price/invest_amount)와 실제 체결가가 어긋나 손익/손절 계산이 왜곡.
- **근거**: `buy_flow.py:357, 420, 422, 447, 458-462` 와 `app/support/execution_policy.py:11-15`(price > 0일 때만 limit, 아니면 무조건 market).
- **권장 수정 방향**:
  - 시장가 주문 경로에서도 `current_price <= 0`이면 주문을 거부(`return`)하거나, 최근 체결가/호가 fallback으로 의미 있는 가격을 확보한 뒤 잔액 검증.
  - `required_cash` 산정 시 가격 미확정이면 주문을 보류하도록 가드 추가.
- **우선순위**: Critical

### 3.2 [Critical] 인증 토큰 갱신의 동시성 미보호 (race condition)

- **위치**: `api/auth.py:80-164` (`get_token`, `_request_new_token`, `get_auth_header`)
- **문제**:
  - `get_token()`이 `_access_token`/`_expires_at`을 읽고, 만료 시 `_request_new_token()`에서 이를 갱신하지만 어떠한 lock도 없다.
  - 호출 주체가 최소 3개 스레드:
    1. WebSocket 백그라운드 스레드(`_connect_and_listen`에서 매 연결 시 `self.auth.get_token()` 호출 — `websocket_client.py:174`)
    2. REST Worker 스레드들(`_rate_limit`은 lock이 있으나, `_request` 내에서 `self.auth.get_auth_header()` → `get_token()` 호출 — `rest_client.py:140`)
    3. UI/메인 스레드(연결 테스트 등)
  - 만료 시점 근처에서 두 스레드가 동시에 `_request_new_token`에 진입하면, 키움 API에 토큰 발급 요청이 중복 전송되고, 한쪽이 `_access_token`/`_expires_at`을 덮어쓰는 동안 다른 쪽이 읽는 경쟁이 발생한다.
- **영향**:
  - 드물지만 만료 경계에서 401/인증 실패 폭주, 또는 유효하지 않은 토큰으로 주문/조회 실패 가능.
  - `_save_token_cache()` 동시 실행 시 `.tmp` 파일 충돌 가능(동일 경로 덮어쓰기).
- **근거**: `auth.py:80, 92, 96, 98, 147, 194`; 호출 지점 `rest_client.py:140`, `websocket_client.py:174`.
- **권장 수정 방향**:
  - `KiwoomAuth`에 `threading.Lock`을 두고, `get_token`/`_request_new_token`/`get_auth_header`/`_save_token_cache` 임계구역을 보호.
  - 또는 double-checked locking 패턴으로 토큰 캐시 hit는 lock 없이 읽고, miss만 lock 내에서 재확인 후 발급.
- **우선순위**: Critical

### 3.3 [High] 설정 파일 저장이 비원자적 (깨짐 위험)

- **위치**: `app/features/persistence/settings_io.py:277-279` (`_save_settings`)
- **문제**:
  ```python
  Path(Config.SETTINGS_FILE).parent.mkdir(parents=True, exist_ok=True)
  with open(Config.SETTINGS_FILE, "w", encoding="utf-8") as file:
      json.dump(settings, file, ensure_ascii=False, indent=2)
  ```
  `os.replace` 기반 atomic write를 사용하지 않는다. 같은 프로젝트의 `_atomic_write_json`(persistence/schema.py:142)는 `tmp → os.replace` 패턴을 쓰고 있어 정합성이 불일치.
- **영향**:
  - 저장 도중 프로세스 크래시/전원 차단/강제 종료 시 `kiwoom_settings.json`이 절단되거나 `json.JSONDecodeError` 발생 → 다음 기동 시 `_load_settings`가 예외(다만 `_load_settings`에 try/except가 있어 치명적이지는 않으나 설정이 날아감).
  - 사용자가 백업 없이 설정을 잃을 수 있음.
- **근거**: `settings_io.py:277-279` vs `persistence/schema.py:142-148`(`_atomic_write_json`은 atomic).
- **권장 수정 방향**: `_save_settings`의 파일 기록부를 `_atomic_write_json(Config.SETTINGS_FILE, settings)`로 교체. README/CLAUDE.md의 "거래내역 저장은 atomic write" 설명과 설정 저장을 동일 정책으로 통일.
- **우선순위**: High

### 3.4 [High] 종료/중지 cleanup의 processEvents 재진입 위험

- **위치**: `app/features/trading_session/cleanup.py:313-322` (`_cleanup_active_orders`)
- **문제**:
  ```python
  while unresolved and time.monotonic() < deadline:
      self._force_account_position_sync(...)
      unresolved = [t for t in live_targets if self._cleanup_target_is_active(t)]
      ...
      app = QCoreApplication.instance()
      if app is not None:
          app.processEvents()   # ← 메인 스레드 이벤트 루프를 강제 펌프
      time.sleep(0.2)
  ```
  `processEvents()`는 대기 중인 시그널(체결/주문 동기화/타이머/예약)을 즉시 디스패치한다. cleanup 진행 중 `_on_order_execution`이 재진입되어 `_pending_order_state`/`universe[code]["status"]`를 바꾸면, 직후 `_cleanup_target_is_active(target)` 판단이 부정확해진다.
- **영향**:
  - 미체결 주문을 "해결됨"으로 잘못 판단하거나 반대로 영원히 unresolved로 남길 수 있음.
  - stop/emergency 경로에서 reserved cash 정합성이 틀어질 수 있음(README가 의도한 "취소 실패/미확인 주문은 sync_failed로 보존" 정책이 우발적으로 깨짐).
- **근거**: `cleanup.py:313-322`, 그리고 `realtime.py:_on_order_execution`이 `_pending_order_state`를 변경하는 전체 경로.
- **권장 수정 방향**:
  - polling 대기 중에는 `_shutdown_in_progress`/별도 reentry guard로 order sync 콜백이 상태를 변경하지 못하게 억제.
  - 또는 `processEvents()` 제거하고 순수 폴링 + 타임아웃 후 강제 finalize로 단순화(이미 finalize 경로가 있음).
- **우선순위**: High

### 3.5 [High] keyring 미사용 시 모의투자 평문 secret fallback 자동 허용

- **위치**: `app/features/persistence/settings_io.py:243-258` (`_save_settings`)
- **문제**:
  ```python
  allow_plaintext = bool(settings.get("allow_plaintext_secret_fallback", False))
  is_mock = bool(settings.get("is_mock", False))
  allow_secret_fallback = allow_plaintext or is_mock   # ← is_mock이면 평문 허용
  ...
  if KEYRING_AVAILABLE:
      ...  # keyring 사용
  else:
      for setting_name, _ in self._secret_field_names():
          value = secret_values.get(setting_name, "")
          if value and allow_secret_fallback:
              settings[setting_name] = value   # 평문으로 JSON에 저장
  ```
  keyring이 설치되지 않은 환경에서 모의투자(`is_mock=True`)이면 사용자가 `allow_plaintext_secret_fallback`을 켜지 않아도 app_key/secret_key/naver/dart/fred/ai 키가 평문으로 저장된다.
- **영향**:
  - 모의투자용 API key라도 실거래용과 동일한 키를 재사용하는 사용자에게는 민감정보 노출 경로.
  - README "🔒 보안" 섹션의 "API Key: keyring 모듈로 OS 레벨 암호화 저장" 설명과 모순되는 동작.
- **근거**: `settings_io.py:243-258`, `_secret_field_names()`(schema.py:80-89)가 7개 secret 필드를 반환.
- **권장 수정 방향**: `is_mock`에 의한 자동 평문 허용을 제거하고, 평문 fallback은 항상 명시적 `allow_plaintext_secret_fallback=True`일 때만 허용. 모의투자에서도 keyring 미가용 시 사용자에게 경고 후 키를 저장하지 않는 정책이 더 안전.
- **우선순위**: High

### 3.6 [High] cleanup 동기 경로의 REST 직렬 호출이 UI 블록 / 타임아웃 위험

- **위치**: `app/features/trading_session/cleanup.py:291-322` (`_cleanup_active_orders` 동기 부분)
- **문제**: live_targets 각각에 대해 `client.cancel_order(...)`를 메인 스레드에서 직렬 호출(동기, `requests` timeout=10초). 대상이 많으면 `deadline = now + 8.0`초를 초과할 수 있고, 그 동안 UI가 멈춘다. (비동기 변형 `_cleanup_cancel_requests_worker`도 존재하나, `_cleanup_active_orders` 자체가 동기 경로로도 호출됨)
- **영향**: 다수 미체결 주문이 있을 때 emergency/stop 버튼 응답성 저하, 타임아웃 초과로 미해결 건이 `sync_failed`로 남아 reserved cash가 보존됨(사용자에게 혼란).
- **근거**: `cleanup.py:291-311`(직렬 cancel 호출), `rest_client.py:149,151`(timeout=10).
- **권장 수정 방향**: cancel 요청 자체를 Worker 비동기 병렬 처리하고, 메인 스레드는 결과 수신만 담당. 또는 cleanup의 REST timeout을 cleanup deadline과 정합되게 단축.
- **우선순위**: High

### 3.7 [Medium] WebSocket 재연결 폭주 시 토큰 요청 폭주

- **위치**: `api/websocket_client.py:167-240` (`_connect_and_listen`)
- **문제**: 재연결 루프가 5회 지수 백오프 후 60초 대기로 리셋되지만, 각 시도마다 `self.auth.get_token()`을 호출. 3.2의 lock 미비와 결합되면 네트워크 불안정 시 토큰 발급 API가 반복 타격된다. 또한 `_restore_subscriptions()`이 재연결마다 실행되나, 구독 실패에 대한 재시도/검증이 없다.
- **영향**: 키움 API rate limit 도달 시 전체 인증 실패 가능.
- **근거**: `websocket_client.py:174, 203`.
- **권장 수정 방향**: 3.2 lock과 함께, get_token 실패 시 백오프를 token 요청에도 적용.
- **우선순위**: Medium

### 3.8 [Medium] 일일 손실 한도 계산이 timer 주기에만 의존

- **위치**: `app/mixins/system_shell.py:228-245` (`_on_timer`)
- **문제**: 일일 손실 한도 검사가 1초 timer 안에서만 수행된다. 빠른 연속 매도 체결로 `_add_trade`가 `daily_realized_profit`을 누적해도, 다음 timer tick 전에는 `_on_execution`의 매수 가드(`daily_loss_triggered` 체크 — `buy_flow.py:223`)만 작동한다. timer가 지연되면 한도 초과 후에도 진입이 가능.
- **영향**: 변동성 급변 시 한도 초과 폭이 커질 수 있음(다만 매수 차단 가드가 있어 완화됨).
- **근거**: `system_shell.py:237-245`, `buy_flow.py:222-224`.
- **권장 수정 방향**: `_add_trade`에서 매도 체결 누적 직후에도 즉시 한도 재평가, 또는 `_on_order_execution` fill 경로에서 `daily_loss_triggered`를 함께 갱신.
- **우선순위**: Medium

### 3.9 [Medium] 수동 주문 다이얼로그의 잔고/포지션 재검증 부재

- **위치**: `dialogs/manual_order.py:116-140` (`_execute_order`)
- **문제**: `ManualOrderDialog` 자체는 코드/가격 검증만 하고, 실제 잔액·보유수량 검증은 부모의 `_validate_manual_order_request`에 의존. 다이얼로그가 `rest_client`/`account`를 생성자로 받지만 검증에 사용하지 않는다. 부모 믹스인 경유 검증이 누락되는 호출 경로가 생기면 무방비.
- **영향**: 검증 경로가 단일 choke point가 아니라 회귀 시 우회 가능.
- **근거**: `manual_order.py:19-24, 116-140` vs `dialogs_profiles.py:106-182`.
- **권장 수정 방향**: 다이얼로그가 `order_result`를 반환한 뒤 반드시 `_validate_manual_order_request`를 거치도록 호출 경로를 단일화하고 테스트로 고정.
- **우선순위**: Medium

### 3.10 [Low] README/CLAUDE.md 검증 수치 불일치

- **위치**: README.md 여러 섹션(144/120/104/83 passed 혼재), CLAUDE.md도 동일.
- **문제**: 시점이 다른 검증 결과가 섹션별로 남아 있어 "현재 기준"이 모호. `pytest.ini`는 `addopts`를 비우는 패턴이 곳곳에 등장하는데, README에 `pytest.ini` 내용과 충돌 여부가 문서화되지 않음.
- **영향**: 신규 기여자가 검증 기준을 오인할 수 있음(기능적 결함은 아님).
- **근거**: README.md `## 🔄 ...` 섹션 다수.
- **권장 수정 방향**: "현재 검증 기준" 섹션을 단일화하고, 과거 수치는 날짜 명시 분리.
- **우선순위**: Low

---

## 4. Potential Functional Gaps

> 아래는 코드 기반 추정 항목. 확실하지 않은 부분은 "추정"으로 표시.

1. **미체결 주문(open orders) 조회 미지원** — CLAUDE.md에 "미체결 주문 조회는 adapter만 존재하며 공식 REST 엔드포인트가 확인되기 전까지 unsupported"라고 명시. 실거래 환경에서 startup/stop 시 잔존 미체결 복구가 어렵다(추정: 키움 REST에 미체결 조회 TR이 있으나 아직 연결 안 함).
2. **시장가 주문의 체결가 추적 보정 부족** — `_on_buy_result`/`_on_sell_result`에서 `result.order_no`를 pending에 넣지만, 체결가가 예상가와 크게 다를 때 `buy_price`/`invest_amount` 갱신이 계좌 동기화에만 의존(추정). 3.1과 결합 시 장부 왜곡 가능.
3. **Telegram 알림의 Markdown 미이스케이프** — `telegram_notifier.py:37`이 `parse_mode=Markdown`로 전송하지만 메시지에 `_`/`*`/`` ` `` 등이 포함되면 파싱 실패로 전송 누락 가능(추정).
4. **`_force_quit`/closeEvent와 `stop_trading`의 telegram.stop 중복** — `closeEvent`가 `self.telegram.stop()`을 직접 호출하고, `stop_trading` 경로에서도 notifier 정리가 일어날 수 있어 더블 stop 가능(추정; `TelegramNotifier.stop`은 멱등하지 않게 설계될 수 있음).
5. **백테스트 결과 파일 경로 검증 부족**(추정) — UI에서 CSV/JSONL 입력을 받으나, 파일 존재/인코딩/포맷 오류 시 사용자 피드백 경로가 명확하지 않음.
6. **`external_positions`의 시간청산/긴급청산 포함** — CLAUDE.md에 "external_positions까지 청산 대상에 포함"이라 명시되어 있으나, 사용자 의도와 다를 수 있음(외부 보유 종목을 자동으로 매도). 이는 의도된 동작이나 운영 가이드 보강이 필요(추정).
7. **PyInstaller ONEFILE 실행 시 `Config.BASE_DIR`** — README는 `Config.BASE_DIR` 기준 절대경로라고 하나, ONEFILE 모드에서 임시 해제 디렉터리가 BASE_DIR이 되면 설정/로그 위치가 사용자 예상과 달라질 수 있음(추정).

---

## 5. Recommended Fix Plan

### 1단계 — 즉시 수정 (실거래 손실/데이터 손상 직결)

1. **3.1 자동 매수 가격 0 가드**: `_execute_buy`에서 `current_price <= 0`이면 시장가 주문 거부. (buy_flow.py)
2. **3.2 토큰 갱신 동시성 보호**: `KiwoomAuth`에 `threading.Lock` 추가, `get_token`/`_request_new_token`/`get_auth_header`/`_save_token_cache` 보호. (auth.py)
3. **3.3 설정 저장 atomic write**: `_save_settings`를 `_atomic_write_json` 사용으로 교체. (settings_io.py)
4. **3.5 모의투자 평문 fallback 자동 허용 제거**: `allow_secret_fallback = allow_plaintext`로 단순화. (settings_io.py:245)

### 2단계 — 안정성 개선

5. **3.4 cleanup 재진입 억제**: `_shutdown_in_progress`/`_cleanup_in_progress` 가드로 폴링 중 order sync 콜백의 상태 변경 억제. (cleanup.py)
6. **3.6 cleanup REST 비동기화**: cancel_order를 Worker 병렬 처리, cleanup deadline과 REST timeout 정합. (cleanup.py)
7. **3.8 일일 손실 한도 즉시 평가**: `_add_trade` 매도 누적 후 한도 재평가. (trade_history.py / buy_flow.py)
8. **3.7 WebSocket 재연결 시 토큰 백오프**: get_token 실패 시 재연결 루프와 연동 백오프. (websocket_client.py)

### 3단계 — 구조/문서 개선

9. **3.9 수동 주문 검증 경로 단일화**: 다이얼로그 → `_validate_manual_order_request` 강제 경로 테스트 고정. (manual_order.py / dialogs_profiles.py)
10. **3.10 문서 정합성**: README/CLAUDE.md 검증 수치 단일화, 과거 섹션 날짜 분리.
11. **Potential Gap 3 (Telegram Markdown)**: `parse_mode` 제거 또는 메시지 이스케이프 헬퍼 도입.
12. **Potential Gap 1 (미체결 조회)**: 키움 REST 미체결 TR 확인 후 `get_open_orders` adapter 구현.

---

## 6. Test Recommendations

현재 `tests/unit`에 약 74개 파일(README 기준 144개 케이스)이 있어 광범위하지만, 아래 영역은 커버가 부족하거나 추가 필요:

### 6.1 반드시 추가해야 할 테스트 (1단계 수정 검증용)

1. **`test_execute_buy_zero_price_guard`** — `_execute_buy(code, qty, price=0)`이고 `info["current"]==0`일 때 시장가 주문이 전송되지 않음(buy_market 호출 없음)을 단언. (3.1)
2. **`test_auth_token_concurrent_refresh`** — 멀티스레드에서 동시에 `get_token(force_refresh=True)` 호출 시 `_request_new_token`(또는 mock된 token endpoint)이 정확히 1회만 호출됨을 단언. (3.2)
3. **`test_save_settings_atomic_write`** — 저장 중 예외 발생 시 기존 `kiwoom_settings.json`이 이전 내용으로 보존됨(`.tmp` → `os.replace`)을 단언. (3.3)
4. **`test_save_settings_mock_no_plaintext_secret`** — `is_mock=True`이고 `allow_plaintext_secret_fallback=False`일 때 secret이 settings에 쓰이지 않음을 단언. (3.5)

### 6.2 안정성 회귀 방지용 (2단계)

5. **`test_cleanup_reentry_guard`** — cleanup 폴링 중 `_on_order_execution`이 들어와도 `_pending_order_state`가 변경되지 않음을 단언. (3.4)
6. **`test_cleanup_cancel_timeout`** — 다수 live_targets + REST 지연 시 deadline 도과 후 `sync_failed`로 마킹되고 reserved cash가 보존됨을 단언. (3.6)
7. **`test_daily_loss_immediate_eval_on_sell`** — 연속 매도로 한도 초과 시 다음 timer tick 전에 `daily_loss_triggered=True`가 됨을 단언. (3.8)
8. **`test_websocket_reconnect_token_backoff`** — 재연결 반복 시 token 요청 횟수가 상한 이내임을 단언. (3.7)

### 6.3 통합/회귀 보강 (3단계)

9. **`test_manual_order_validation_choke_point`** — `ManualOrderDialog` 결과가 반드시 `_validate_manual_order_request`를 거침을 단언. (3.9)
10. **`test_telegram_markdown_escape`** — `_`/`*`/`` ` `` 포함 메시지가 전송됨을 단언(mock requests). (Gap 3)
11. **`test_open_orders_recovery`** (미체결 조회 구현 후) — startup 시 잔존 미체결이 발견되면 적절히 sync됨을 단언. (Gap 1)

### 6.4 기존 테스트 품질 개서 제안

- `signal_only` 경로 테스트(`test_signal_only_execution.py`)는 있으나, **live 경로의 실주문 호출 단언**(mock `buy_market`/`buy_limit` 호출 카운트)이 약한 것으로 보임. 3.1 수정과 함께 live 경로 호출 단언을 강화할 것.
- `test_order_cleanup_shutdown.py`가 있으나 `processEvents` 재진입 시나리오는 커버하지 못함 → 6.5 추가.

---

> 본 감사는 정적 분석(CodeGraph + 직접 열람) 기반이며, 런타임 재현/실거래 환경 검증은 포함하지 않는다. 위 권장 사항은 코드 근거를 바탕으로 한 제안이며, 실제 수정 전에는 해당 라인과 호출자를 다시 확인할 것을 권장.
