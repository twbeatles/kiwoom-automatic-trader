# Project Audit

> **프로젝트**: Kiwoom Pro Algo-Trader v4.5 (키움증권 REST/WebSocket 기반 자동매매, PyQt6 데스크톱)
> **감사 일시**: 2026-09-28 (UTC)
> **감사 방식**: 코드 감사만 수행, 코드 수정 없음. 기존 `PROJECT_AUDIT.md`(2026-08-14판, 구구조 기준)는 본 문서로 대체한다.
> **실행한 테스트**: `python -m pytest tests/unit --override-ini addopts= --tb=no -q` → **332 passed, 2 subtests passed** (약 2.6초, 본 감사 세션에서 직접 실행)

## 0. Follow-up Disposition (2026-09-29, 코드 수정 수행)

본 감사에서 제안된 전 항목을 구현했다. 검증: `tests/unit` **356 passed**(신규 24) · `pyright` 0 errors · `refactor_verify` 통과 · `compileall` 통과.

| 항목 | 조치 | 회귀 테스트 |
|---|---|---|
| ISSUE-001 pending 고착 | 성공-빈 연속 3회 시 ka10075 재조회 → 미확인 주문 해제·환불, 모호하면 `sync_failed` 격리 (`PENDING_RECONCILE_EMPTY_SYNCS`) | `test_pending_reconcile_stale.py` 4건 |
| ISSUE-002 긴급청산 | 완료 로그를 요청 제출 + 콜백 집계 최종 보고로 변경, cleanup 비동기화, live guard 통일, 30초 sweeper | `test_emergency_liquidate_reporting.py` 5건 |
| ISSUE-003 프로필 | 원자 저장(tmp+replace), 손상 시 `.bak` 보존 + 빈 덮어쓰기 거부 + 다이얼로그 안내 | `test_profile_corrupt_backup.py` 4건 |
| 미체결 자동취소 Gap | `STALE_LIMIT_ORDER_CANCEL_SEC`(기본 0=비활성), 1초 타이머 스위퍼, 확정은 WS 이벤트가 처리 | `test_phase2_safety_nets.py` 3건 |
| 주문거부 분류 Gap | transient/final/unknown 분류 + universe 기록, 자동 재제출은 의도적으로 미구현(중복주문 방지) | `test_phase2_safety_nets.py` 2건 |
| closeEvent Gap | 정리 예외 시에도 accept+quit 보장, 동기 저장 예외 확대(`OSError`→`Exception`) | `test_close_event_hardening.py` 1건 |
| 토큰 secret Gap | 캐시 바인딩을 App Key+Secret 해시로 변경(교체 시 무효화) | `test_phase2_safety_nets.py` 1건 |
| 외부보유 Gap | read-only 유지, 손실이 손절 기준 초과 시 경고만(`_watch_external_loss`, 자동청산 없음) | `test_external_loss_watch.py` 4건 |
| D1/D2 문서 | 5 워크스페이스 대응표 + UI 도식 갱신, 테스트 수 356으로 정정 | — |

## 1. Executive Summary

* **프로젝트 전체 상태**: 핵심 매매 경로(진입 가드 → 주문 제출 → 체결 동기화 → 청산/중지)와 영속성(원자적 저장)에 대해 방어 로직이 촘촘히 들어간 성숙한 상태다. 기본 `execution_mode=signal_only`가 실주문을 원천 차단하고, 실거래 guard·주문 검증 choke point·주문 정리(cleanup) 경로가 갖춰져 있다. 단위 테스트 332개가 모두 통과한다.
* **전체 위험도**: **Needs Work (중)** — 데이터 파괴급 결함은 확인되지 않았으나, 실거래 자금 흐름과 직결된 상태 고착 1건(High)이 strong Likely로 남는다.
* **가장 중요한 문제 3개**:
  1. [ISSUE-001] WS 체결 이벤트 유실 + REST 성공-빈 응답 조합에서 pending 주문 상태가 영구 고착 → 해당 종목 재진입 차단 + 예약 현금 잠금 (High / Likely).
  2. [ISSUE-002] 긴급 전량청산이 비동기 매도 결과를 기다리지 않고 "청산 완료"를 로그하며, 동기 cleanup이 UI 스레드를 블로킹한다 (Medium / Confirmed).
  3. [ISSUE-003] `ProfileManager`가 비원자적 쓰기를 사용하고, 손상된 프로필 파일을 빈 상태로 로드한 뒤 다음 저장 때 덮어쓴다 (Medium / Likely).
* **데이터 손상/유실 가능성 여부**: 거래내역·설정·토큰 캐시는 원자적 저장(tmp+replace)이라 크래시 절단에는 안전하다. 프로필 파일(`kiwoom_profiles.json`)만 비원자적이라 손상 시 전체 프로필 유실 가능성이 있다. 그 외 DB를 쓰지 않으므로 DB 손상 범주는 해당 없다.
* **가장 먼저 수정해야 할 영역**: 주문 상태머신(`app/features/order_sync/`, `app/features/execution/`) — ISSUE-001의 고착 조건에 대한 타임아웃/재조정(reconciliation)부터.

## 2. Project Understanding

* **프로젝트 목적**: 키움증권 REST API(주문/계좌/시세) + WebSocket(실시간 체결·호가·VI·조건검색)으로 동작하는 Windows 데스크톱 자동매매 프로그램. Fail-Closed 가드(쇼크/VI/스프레드/주문건강도/인텔리전스)와 `signal_only`/`live` 2단계 실행 모드가 안전 축이다.
* **주요 entrypoint**: `키움증권 자동매매.py` → `main()` → `app.core.window.KiwoomProTrader` (canonical 조립 클래스, `app/main_window.py`는 호환 re-export).
* **핵심 모듈**:
  - `api/auth.py` (`KiwoomAuth`: 토큰 발급·캐시·`threading.Lock` 이중확인, live/mock 분리 캐시).
  - `api/_rest_transport.py` (`RestTransport._request`: `api-id`/`cont-yn` 헤더 주입, 200ms rate limit, urllib3 Retry(total=3, 429/5xx, GET+POST), timeout 10s).
  - `api/_rest_orders.py` (주문 전송/취소/정정, 공식 계약 body).
  - `api/websocket_client.py` (별도 스레드 asyncio 루프, 토큰 백오프 5→10→20→60s, 재연결 지수 백오프+상한, Qt 디스패처 경유 메인스레드 콜백).
  - `app/features/trading_session/lifecycle.py` (`start_trading`/`stop_trading` 상태머신).
  - `app/features/execution/` (매수/매도 flow + `cash_reservation.py` 예약현금 + `virtual_deposit` 장부).
  - `app/features/order_sync/` (pending 상태머신, WS 실시간 반영, REST 포지션 동기화+재시도, 예약현금 정산).
  - `app/features/persistence/` (설정 v7 스키마·마이그레이션·원자적 저장, 거래내역 single-writer, Keyring 저장).
  - `app/features/dialogs/manual_orders.py` (수동주문 검증 choke point `_validate_manual_order_request` + `validated` 플래그).
  - `app/features/ui_build/workspaces.py` (5 워크스페이스 + 우측 주문티켓, 동일 choke point 공유).
  - `strategies/` + `manager_mixins/` (지표·시그널 필터·리스크 오버레이), `backtest/` (이벤트 드리븐 엔진), `data/providers/` (뉴스/DART/트렌드/FRED/AI).
* **데이터 저장 방식**: DB 없음. 전부 파일: `kiwoom_settings.json`(설정), `kiwoom_trade_history.json`(거래내역), `data/*.jsonl`(주문 생명주기·인텔 이벤트·결정 감사), 토큰 캐시(`kiwoom_token_cache_{live,mock}.json`), `data/stock_master_cache.json`, 프로필(`kiwoom_profiles.json`, `Config.DATA_DIR` 하위). 경로는 `Config.BASE_DIR`(레포 루트) 기준 절대경로.
* **외부 의존성**: 런타임 `PyQt6`, `requests`, `websockets`, `keyring`, `python-dateutil`만. 선택 의존 `darkdetect`(OS 테마 감지, 없어도 dark 폴백). OS 종속: `winreg`(자동실행), `winsound`(효과음, 가드 있음), Keyring Windows backend, PyInstaller spec의 `winreg` hiddenimport.
* **핵심 실행 흐름**:
  - 자동매수: `WS 체결틱 → _on_execution → 진입가드(쇼크/VI/스프레드/일일손실/인텔) → _execute_buy(현금예약+Worker 주문) → _on_buy_result(pending 등록) → WS 주문이벤트/_on_order_execution + REST 포지션동기화 → fill 정산(_add_trade·예약현금 소비/해제)`; 실패 시 상태 복원·주문건강도 기록.
  - 수동주문: `주문티켓/다이얼로그 → _validate_manual_order_request → validated=True → _dispatch_manual_order(signal_only 기록 | live guard + Worker) → _on_manual_order_result(pending/예약현금 등록)`.
  - 중지: `stop_trading → _cleanup_active_orders_async(취소 요청 Worker) → finalize(성공분만 pending/예약현금 정리, 미확인분 sync_failed 유지) → 구독해제/타이머정리 → 세션 리포트`.
  - 긴급청산: `_emergency_liquidate → _set_trading_stopped_state → _cleanup_active_orders(동기) → 보유 전종목 _execute_sell(시장가, 비동기)` (ISSUE-002 참조).
  - 종료: `closeEvent → stop_trading → telegram/sound/tray 정리 → 거래내역 flush → _stop_ui_timers → accept → _quit_application`.

## 3. Audit Coverage & Limitations

* **실제 확인한 주요 모듈**: entrypoint·`app/core/window.py` 상태 필드, trading_session(lifecycle/cleanup/table/positions), execution(buy/sell/cash_reservation), order_sync(pending_api/pending_state/realtime/position_sync), persistence(schema/settings_io/trade_history), dialogs(manual_orders), ui_build(workspaces), `api/` 전 REST/WS/auth/models, `app/configuration/base.py` 경로·단축키·상수, `profile_manager.py`, telegram/sound notifier 표면, providers 타임아웃 표면.
* **CodeGraph로 분석한 호출 관계** (총 5회 explore, 전부 결과 수신·인용):
  1. `entrypoint main KiwoomProTrader start_trading stop_trading execution flow` — 라이프사이클·매도flow·윈도우 상태·셸 closeEvent.
  2. `KiwoomRESTClient _request auth token order execution get_positions persistence settings save load` — transport·계좌·토큰캐시·설정IO.
  3. `_on_execution _on_order_execution _pending_order_state reserved cash _cleanup_active_orders emergency liquidate` — 주문 상태·예약현금·정리·실시간 반영.
  4. `websocket_client reconnect token _connect_and_listen subscribe execution order threadpool Worker` — 재연결·백오프·구독복원.
  5. `manual order validate reserved cash history flush atomic write keyring plaintext fallback schedule start` — 검증·flush·원자저장 체인.
* **직접 열람으로 보완**: `pending_state.py` `_update_pending_from_order_event`, `trade_history.py` `_add_trade`(payload 원시형 확인), `position_sync.py` fill 정산, `table.py` `_emergency_liquidate`, `system_shell.py` closeEvent, `schema.py` 마이그레이션·원자저장, `auth.py` 캐시 검증, `workspaces.py` 주문티켓, `_rest_transport.py` Retry 장착, `profile_manager.py` 로드/저장.
* **실행한 테스트**: 위 332 passed 1회 (전체 `tests/unit`). 개별 이슈 재현 테스트는 작성·실행하지 않았다(감사 범위상 코드 확정 근거만 사용).
* **확인하지 못한 환경/외부 서비스**: 실 키움 REST/WS 서버(모의·실전 모두), 실 GUI 구동·장중 데이터, Windows 트레이·레지스트리·Keyring 실동작, PyInstaller 빌드 산출 실행, Linux/macOS(공식 지원 외).
* **분석상의 한계**: CodeGraph 인덱스가 일부 파일에서 stale 경고를 냈으므로 해당 파일은 직접 열람본을 우선했다. 동적 디스패치(`getattr` 분기: 인텔 루프·마켓상태 업데이터 등)는 후보까지만 추적했다. 런타임 재현이 없어 신뢰도는 최대 Likely로 capped했다(ISSUE-002의 로그 순서 제외).

## 4. High-Risk Issues

### [ISSUE-001] WS 이벤트 유실 시 pending 상태 영구 고착 — 재진입 차단 + 예약현금 잠금

* **위치:** `app/features/order_sync/realtime.py` `_on_order_execution` (64–65행), `app/features/execution/buy_flow.py` `_on_execution` (100–102행), `app/features/order_sync/position_sync.py` `_on_position_sync_result`, `app/features/execution/cash_reservation.py`
* **우선순위:** High
* **신뢰도:** Likely (코드 흐름상 확정적이나 장중 재현은 미수행)
* **문제:** 활성 pending(`submitted`/`partial`)이 존재하면 `_on_execution`이 해당 종목의 모든 틱 평가를 조기 반환한다. pending 해소는 (a) WS 주문 이벤트, (b) REST 포지션 동기화의 delta 정산, (c) `sync_failed` 전이, (d) 수동 해제/중지 정리뿐이다. 그런데 WS 이벤트가 유실되고(재연결 공백·구독 복원 전 수신분은 replay 없음) REST 동기화가 "성공-빈 포지션"으로 반환되면, 해당 종목 테스트가 명시적으로 단언하듯 pending은 `submitted`로 그대로 남는다(`test_pending_timeout_does_not_auto_clear`: 빈 동기화 후에도 pending 유지·상태 `submitted`).
* **발생 조건:** 해당 종목에 활성 pending이 있는 상태에서 (1) WS 주문 이벤트(거부/취소/체결) 유실, (2) 이후 REST `get_positions`는 성공하나 해당 종목 포지션 없음(미체결·거부·장외 취소 등). 장중 WS 재연결·공지정지·이벤트 공백 시 현실적.
* **영향:** 해당 종목의 자동 진입이 무기한 차단되고, 매수 예약현금이 `_reserved_cash_by_code`에 묶인 채 `virtual_deposit`이 과소 표시되어 다른 종목의 주문 가능금액 검증·사이징까지 왜곡된다. `sync_failed` 격리(재시도 5회 초과 시)는 "동기화 오류" 경로에서만 동작하고 "성공-빈" 경로에서는 발동하지 않으므로 fail-safe가 빗나간다.
* **근거:** `realtime.py:64` — cleanup 폴링 중이 아닐 때만 pending을 이벤트로 갱신(역으로 이벤트 없으면 갱신 없음). `buy_flow.py:100-102` — 활성 pending이면 틱 평가 전체 스킵. `pending_api.py:40` — `until`(5초)이 기록되지만 자동 pending에는 만료 청소가 없음(`_cleanup_manual_pending_state`는 manual 맵 전용). 단위 테스트가 빈 동기화 후 pending 잔류를 정상으로 고정.
* **반증 확인:** REST 세션 레벨 Retry(total=3, 429/5xx)·WS 토큰 백오프·지수 백오프 재연결·구독 복원·포지션 동기화 재시도+`sync_failed`·수동 해제·중지 시 정리 등 다층 보호를 확인했다. 그러나 어느 것도 "성공했으나 비어 있는 동기화 결과 vs 살아있는 pending"의 불일치를 해소하지 못한다: 재시도 카운터는 오류 경로에서만 증가하고, 성공-빈 결과는 pending을 그대로 둔다.
* **호출/영향 범위:** caller: WS 스레드→`sig_order_execution`→`_on_order_execution`, 1초 타이머→`_sync_position_from_account`; callee: `_update_pending_from_order_event`, `_on_position_sync_result`, `_apply_pending_fill`, `_consume/_release_reserved_cash*`. 영향 모듈: execution 진입평가, 현금 장부(`virtual_deposit`), 진단 테이블(pending 잔류 표시), 중지 정리(placeholders 경로).
* **권장 수정 방향:** 성공한 포지션 동기화 결과와 pending의 정합 조정(reconciliation) 추가 — 예: 연속 N회 "성공-빈 + 해당 주문번호 미확인"이면 주문번호 단건조회(미체결 조회 ka10075 adapter가 이미 있음) 후 취소/거부/체결없음 확정 시 pending 해제+예약현금 환불, 확정 불가 시 `sync_failed`로 격리. `until` 필드를 자동 pending에도 강제 만료가 아닌 "재조회 트리거"로 활용.
* **필요한 회귀 테스트:** (Unit) 활성 pending + WS 무이벤트 + 연속 3회 성공-빈 동기화 입력 시 pending 해제·예약현금 환불·`virtual_deposit` 복원을 단언. (Unit) 주문번호가 미체결 조회에서 취소/거부로 확인되면 즉시 해제됨을 단언. (Integration, mock REST) WS 이벤트를 중간에 끊고 재연결한 뒤 동일 시나리오에서 고착이 발생하지 않음을 단언.

### [ISSUE-002] 긴급청산의 완료 로그 선행 + 동기 cleanup의 UI 스레드 블로킹

* **위치:** `app/features/trading_session/table.py` `_emergency_liquidate` (90–131행)
* **우선순위:** Medium
* **신뢰도:** Confirmed (실행 순서·동기 호출이 코드상 확정적)
* **문제:** (a) 전종목 `_execute_sell`(비동기 Worker 제출) 직후 결과를 기다리지 않고 `"긴급 청산 완료: N개 종목"`을 로그한다. 개별 매도 실패는 뒤늦게 `_on_sell_error` 로그로만 남는다. (b) 그 직전 `_cleanup_active_orders("emergency_liquidate")`를 동기 호출(default timeout 8초)하므로 UI 스레드가 블로킹된다. (c) 수동 매도와 달리 `_confirm_live_trading_guard()`(실거래 문구 확인)를 거치지 않고 자체 확인창만으로 실전 시장가 일괄매도가 나간다.
* **발생 조건:** 보유 종목이 1개 이상인 상태에서 긴급청산 버튼/메뉴/단축키 실행. (a)는 항상, (b)는 미체결 pending 존재 시, (c)는 live 모드에서 항상.
* **영향:** 운영자가 "완료" 로그·텔레그램 메시지를 보고 청산 완료로 오인할 수 있으나 실제 체결은 뒤따라오며 일부 실패 가능. 급락장에서 수 초의 UI 프리즈가 추가 스트레스를 유발. 실거래 확인 문구 없이 전량 시장가 매도가 나가는 것은 수동주문 경로(매도마다 guard)와 보안 일관성이 어긋난다.
* **근거:** `table.py:112-124` — 동기 cleanup 후 루프에서 `_execute_sell` 호출, 131행에서 즉시 완료 로그. `_execute_sell`(`sell_flow.py:17-69`)은 Worker 제출 후 반환되며 결과는 콜백에서 처리. `table.py:102-109` 확인창은 있으나 live guard 호출 없음(대조: `manual_orders.py:216-219`의 `_manual_order_live_guard_required` + `_confirm_live_trading_guard`).
* **반증 확인:** 자체 `QMessageBox.warning` 확인창이 오클릭은 막는다. `signal_only` 모드에서는 `_execute_sell`이 실주문 없이 기록만 하므로 자금 영향이 없다. 그러나 확인창은 (a) 로그 선행, (b) UI 블로킹, (c) live guard 불일치를 해소하지 못한다.
* **호출/영향 범위:** caller: 대시보드 버튼·메뉴·단축키(`Ctrl+Shift+X`); callee: `_set_trading_stopped_state`, `_cleanup_active_orders`, `_execute_sell`→Worker→`_on_sell_result/_on_sell_error`, sound/telegram. 영향: 세션 상태, 전종목 포지션, 로그·알림 신뢰도.
* **권장 수정 방향:** 긴급청산도 `_cleanup_active_orders_async` 경로로 옮기거나 최소한 완료 로그를 "청산 요청 N건 제출"로 정정하고, 전건 결과 집계 후 최종 결과(성공/실패 종목 목록)를 로그+텔레그램으로 보고. live 모드에서는 기존 실거래 guard도 통과하도록 통일.
* **필요한 회귀 테스트:** (Unit) 일부 `_execute_sell`이 실패하도록 주입한 뒤 긴급청산 직후 로그에 "완료"가 없고, 콜백 집계 후 실패 종목이 명시됨을 단언. (Unit) live 모드 하네스에서 guard 미통과 시 주문 Worker가 제출되지 않음을 단언. (Integration) 미체결 pending 3건 + 보유 2종목 조건에서 긴급청산 호출이 장시간 블로킹 없이 반환됨을 단언(타이머/스레드 기반 측정).

### [ISSUE-003] ProfileManager 비원자적 저장 + 손상 파일의 빈 상태 덮어쓰기

* **위치:** `profile_manager.py` `_load_profiles` (31–41행), `_save_profiles` (43–55행)
* **우선순위:** Medium
* **신뢰도:** Likely (손상 유발 재현은 미수행, 코드 흐름은 확정적)
* **문제:** 저장이 `open(..., 'w')` 직접 쓰기라 크래시·전원단절 시 파일 절단이 가능하다(설정·거래내역·토큰캐시의 tmp+`os.replace` 원자 저장과 불일치). 손상된 파일은 로드 시 `profiles={}`로 조용히 리셋되고, 다음 저장 때 빈 상태가 그대로 덮어써져 기존 프로필 전체가 복구 불가하게 사라진다.
* **발생 조건:** 프로필 파일이 깨진 상태(절단·잘못된 JSON·디스크 오류)에서 앱 기동 후 임의의 프로필 저장 동작 발생.
* **영향:** 저장된 매매 세팅 묶음(프로필) 전체 유실. 자금 직접 영향은 없으나 복구에 수작업 재구성이 필요하다. 설정 파일(`_atomic_write_json`)과 같은 모듈 수준의 보호가 여기만 빠져 있다.
* **근거:** `profile_manager.py:39-41` — `JSONDecodeError`/`OSError` 시 `{}` 리셋. `43-55행` — 무조건 덮어쓰기, 백업·원자교환 없음. 대조: `persistence/schema.py:146-152`의 `_atomic_write_json`, `api/auth.py:244-251`의 토큰 캐시 원자 저장.
* **반증 확인:** 손상 자체는 OS/디스크 조건이 필요하고 흔하지 않다. 그러나 일단 손상되면 리셋+덮어쓰기가 연쇄적으로 일어나며, 이를 막는 백업·원자성·손상 경고가 코드 어디에도 없다(로드 실패 로그조차 없음).
* **호출/영향 범위:** caller: `ProfileManager.__init__`→`_load_profiles`, 프로필 저장 UI; callee: 없음(독립). 영향 모듈: 프리셋·프로필 관리 UIのみ. 거래내역·설정·토큰에는 파급 없음.
* **권장 수정 방향:** `_save_profiles`를 `_atomic_write_json` 정책(tmp+replace)으로 통일하고, 손상 파일 로드 시 빈 상태로 진행하지 말고 (a) `.bak` 보존 + (b) 사용자에게 경고 후 복구 선택 제공, (c) 빈 덮어쓰기 금지 가드(로드 실패 플래그가 있으면 저장 전 확인).
* **필요한 회귀 테스트:** (Unit) 깨진 JSON 파일을 준 뒤 로드하면 원본이 `.bak`으로 보존되고 profiles가 비어 있지 않거나 명시적 복구 상태임을 단언. (Unit) 저장 중 예외 주입 시 기존 파일이 그대로 유지됨을 단언(원자성). (Unit) 로드 실패 플래그 상태에서 무확인 저장이 거부됨을 단언.

## 5. Potential Functional Gaps

* **[Likely Gap] 지정가 미체결 주문의 자동 타임아웃(Time-in-Force/자동취소) 부재.** `_cleanup_manual_pending_state`는 주문번호·예약현금이 없는 placeholder만 만료시키고, 실주문 미체결 잔량은 만료·자동취소·자동정정 로직이 없다. 장중 호가 이탈 시 자금이 묶인 채 방치될 수 있다. 중지/긴급청산 때만 정리된다.
* **[Likely Gap] `send_order` 계열 비즈니스 거부(`return_code != 0`)의 재시도·분류 없음.** 전송 레벨 Retry(429/5xx)는 세션에 장착되어 있으나, 주문 거부는 즉시 `OrderResult(success=False)`로 반환되고 호출자는 로그+건강도 기록만 한다. 일시적 거부(수량 단위·호가 이탈 등)와 확정적 거부(권한·장운영)를 구분한 재시도 정책이 없다. 단, 무분별 재시도는 중복주문 위험이 있어 설계 판단이 필요하다.
* **[추정] 유니버스 밖 보유(`external_positions`)의 틱 기반 청산 평가 공백.** `_on_execution`은 `code not in self.universe`면 즉시 반환하므로 외부 보유는 10초 폴링(`_start_external_refresh_loop`)에만 의존한다. 트레일링 스탑·시간청산의 반응이 최대 폴링 주기만큼 늦어질 수 있다. 의도된 read-only 설계일 수 있어 버그가 아닌 보완점으로만 기록한다.
* **[추정] `closeEvent` flush 경로의 예외 내성.** `_flush_trade_history_on_exit`→`_save_trade_history_sync`는 `OSError`만 잡고, `closeEvent`의 try에는 except가 없어(try/finally) flush·`stop_trading`·notifier 정리 중 예상 밖 예외가 나면 `event.accept()`·`_quit_application()`이 스킵되어 2026-09-27에 수정한 "종료 잔류"와 동형의 잔류가 재발할 수 있다. 현재 `_add_trade` payload는 전부 원시형(확인됨)이라 발생 가능성은 낮다.
* **[추정] 토큰 캐시가 secret에 바인딩되지 않음.** `_load_cached_token`은 mode+`app_key_hash`만 검증하므로, 동일 App Key에서 Secret만 교체되면旧 토큰을 만료까지 재사용한다. 실무 영향은 제한적이다.

## 6. Documentation Mismatches

* **[D1] README UI 탭 가이드가旧 탭 체계로 남아 있음.** README `메인 화면 및 UI 탭 상세 가이드`는 `[🎯핵심설정][🛠상세설정][🧠인텔리전스설정][🔐API/알림][📈차트][📋호가]...` 탭바와 이모지 탭명을 전제로 서술한다. 실제 구현은 5 워크스페이스 + 좌측 `FluentNavRail` + 숨김 탭바(`workspaces.py` `_hide_workspace_tab_bar`, `fluent_nav.py` `WORKSPACE_LABELS` 단일 출처)이며, README의 `UI 디자인 규칙(이모지 미사용)` 서술과 README 자체의 이모지 탭명도 서로 어긋난다.
* **[D2] README의 테스트 수 표기가 실제와 다름.** README 본문에 `266 테스트`, `304 tests` 표기가 남아 있으나 본 감사 실행 기준 332 passed이며 CLAUDE.md 최신 메모(332)와도 README가 불일치한다.
* **[D3] 그 외.** `REAL_API_PREPARATION_GUIDE.md` 계약표는 최신 TR 정렬(ka10074/ka10078/ka10100계열·WS ka10173/174·장상태 0s)과 일치함을 표면 확인. 진입점·설정 스키마 v7·2단계 실행모드·Fail-Closed 서술은 구현과 일치. D1·D2 외의 문서-구현 불일치는 확인되지 않았다.

## 7. Recommended Fix Plan

### Phase 1 — Immediate

1. ISSUE-001 reconciliation: 성공-빈 동기화 vs 활성 pending 불일치 해소(미체결 단건조회 후 해제/환불 또는 `sync_failed` 격리). 자금 장부(`virtual_deposit`) 직접 연관이라 최우선.
2. ISSUE-002 긴급청산 보고 정정: "완료" 로그를 요청-제출 의미로 고치고 결과 집계 후 최종 보고. live guard 통일은 같은 손질에 포함.

### Phase 2 — Stability

3. ISSUE-003 프로필 원자 저장 + 손상 시 백업·경고·빈 덮어쓰기 금지.
4. 미체결 지정가 타임아웃 정책(자동취소/정정) 도입 — 중복주문 방지를 위해 주문번호 확정 후에만 동작하도록 설계.
5. 주문 비즈니스 거부의 분류(일시/확정)와 제한적 재시도 정책. 재시도는 멱등 조건(동일 주문번호 조회 선행) 하에서만.
6. `closeEvent` 종료 경로에 방어적 except 추가 — 어떤 경우에도 `accept`+`quit`이 스킵되지 않도록(단, 예외 삼킴이 아닌 로깅 후 종료).

### Phase 3 — Structural

7. 외부보유 종목의 청산 평가를 틱 경로에 편입할지(읽기전용 유지 포함) 설계 결정 + 진단 노출.
8. 토큰 캐시에 secret 바인딩(또는 교체 감지 시 캐시 무효화) — 영향이 작아 후순위.
9. README UI 가이드(5 워크스페이스·레일·주문티켓 기준) 및 테스트 수 표기 갱신.

실제 코드는 수정하지 않는다.

## 8. Test Recommendations

* **ISSUE-001 Unit**: 활성 pending(`submitted`, 주문번호 O1, 예약현금 5000) + WS 무이벤트 + `get_positions` 성공-빈 결과 3회 연속 입력 → pending 해제·`_reserved_cash_by_code` 제거·`virtual_deposit` 5000 복원·상태 `watch` 복귀를 단언.
* **ISSUE-001 Unit**: 미체결 조회에서 O1이 취소로 확인되는 경우 1회 만에 즉시 해제·환불됨을 단언. 반대로 주문번호가 여전히 유효하면 pending 유지·`sync_failed` 미전이.
* **ISSUE-001 Integration (mock REST)**: WS `order_exec` 콜백을 일시 차단→재연결한 뒤 거부 이벤트가 유실된 시나리오에서 해당 종목이 다음 틱에 재진입 가능해짐을 단언.
* **ISSUE-002 Unit**: `_execute_sell` 2건 중 1건을 실패 주입 → 긴급청산 직후 로그에 "완료" 문자열이 없고, 콜백 집계 후 실패 종목 코드가 로그·리포트에 명시됨을 단언.
* **ISSUE-002 Unit**: live 모드 하네스에서 `_confirm_live_trading_guard`가 False 반환 시 Worker 제출 0건·포지션 상태 불변을 단언.
* **ISSUE-003 Unit**: 손상 JSON + 다음 저장 시도 → `.bak` 보존·빈 덮어쓰기 거부(또는 명시 확인 후 저장)를 단언. 저장 중 `OSError` 주입 → 기존 파일 바이트 동일을 단언.
* **E2E (핵심 흐름)**: `signal_only`에서 종목 등록→매매시작→틱 주입→신호 기록(`order_lifecycle_events.jsonl`)→중지→flush까지 REST 호출 0건·파일 기록 존재를 단언.
* **Concurrency**: WS 주문이벤트와 `_cleanup_active_orders` 폴링 동시 발생 시 pending 변이 억제(`_cleanup_polling`)가 유지되고 fill 동기화만 반영됨을 단언(기존 `test_cleanup_polling_reentry_guard` 확장).
* **Regression**: `test_pending_timeout_does_not_auto_clear`는 ISSUE-001 수정 시 스펙 변경 대상 — 성공-빈 반복 시 해제되도록 테스트를 갱신하고, 그 외 단일-빈 경우는 유지되는지 경계값으로 분리.
* **Platform-specific**: Windows 전용 경로(`winreg` 자동실행, `winsound`, Keyring Windows backend)는 CI가 Linux일 경우 skip 처리됨을 확인하고, 최소한 `_set_auto_start`의 예외 무해성(현재 broad 처리 여부)을 단언. GUI 미실행 환경에서는 `pytest-qt` 오프스크린 전제를 유지.

## 9. Final Assessment

* **Functional Correctness: Acceptable** — 핵심 경로 가드가 촘촘하고 검증 choke point가 일관되나, ISSUE-001의 고착 조건이 실거래 진입을 막을 수 있다.
* **Runtime Stability: Acceptable** — WS 재연결·백오프·단일작성자 flush·종료 quit이 갖춰져 있으나, 긴급청산의 동기 cleanup과 종료 경로의 예외 내성이 약하다.
* **Data Integrity: Acceptable** — 설정·내역·토큰은 원자 저장, 장부는 원가 기준. 단 예약현금 고착(ISSUE-001)과 프로필 비원자성(ISSUE-003)이 감점 요인.
* **Error Resilience: Needs Work** — 전송 레벨 재시도는 있으나 주문 상태 불일치(성공-빈 vs pending)에 대한 복구 루프가 없다.
* **Cross-platform Robustness: Acceptable** — Windows 전용이 명시적 요구사항이며, 그 범위 내에서는 가드(`winsound` 부재 대응, darkdetect 폴백)가 있다. Linux/macOS는 지원 외이므로 감점하지 않는다.
* **Test Confidence: Good** — 332 passed를 직접 확인. 주문 상태머신·데일리로스·스케줄·cleanup 재진입 등 위험 영역에 targeted 테스트가 있다. 다만 ISSUE-001의 고착 동작을 정상으로 고정한 테스트가 있어 스펙 변경이 필요하다.

**실제로 먼저 수정할 문제 3개**: (1) ISSUE-001 pending reconciliation, (2) ISSUE-002 긴급청산 결과 집계 보고, (3) ISSUE-003 프로필 원자 저장+백업.

---

*보안 스캔 참고: `subprocess`/`shell=True`/`os.system`/`eval`/`pickle` 사용 없음(검색 0건). 평문 secret은 `allow_plaintext_secret_fallback=True` 명시 시에만 저장되는 의도된 동작. 프로필명·CSV 경로는 파일 선택 다이얼로그 기반이라 path traversal 소지 없음. framework가 보장하는 동작(Qt 시그널 스레드 디스패치, urllib3 Retry 등)은 버그로 간주하지 않았다.*
