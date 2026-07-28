# 실제 API 준비 가이드

기준일: 2026-06-10
기준: 현재 저장소 코드, `README.md`, `CLAUDE.md`, `GEMINI.md`, `KiwoomTrader.spec`

이 문서는 Kiwoom Pro Algo-Trader를 실제 API와 연결하기 전에 준비해야 할 항목과 운영 순서를 정리한다. 현재 기본 정책은 실거래 사고 방지를 우선하며, 신규/모의 환경에서는 `signal_only`와 완화형 인텔리전스 guard로 먼저 검증하도록 설계되어 있다.

## 1. 준비물

| 구분 | 필수 여부 | 준비 항목 | 프로젝트 연결 지점 |
| --- | --- | --- | --- |
| 키움증권 REST | 필수 | App Key, Secret Key, API 사용 가능 계좌 | `api/auth.py`, `api/rest_client.py` |
| 키움증권 WebSocket | 권장 | 실시간 수신 가능한 네트워크 | `api/websocket_client.py` |
| NAVER Open API | 권장 | Client ID, Client Secret | 뉴스/검색트렌드 provider |
| OpenDART | 권장 | API Key | 공시 provider |
| FRED | 선택 | API Key | 매크로 provider |
| AI Provider | 선택 | OpenAI 또는 Gemini API Key | AI 요약 provider |
| Telegram | 선택 | Bot Token, Chat ID | 운영 알림 |
| 로컬 보안 | 필수 | Windows Credential Manager/keyring 사용 가능 환경 | secret 저장 |

## 2. 실행 모드

현재 설정 스키마는 `settings_version = 7`이다.

- 기본 실행 모드: `execution_mode = "signal_only"`
- 실주문 모드: `execution_mode = "live"`

`signal_only`에서는 자동매매, 수동 주문, 분할 주문 모두 브로커 REST 주문 API를 호출하지 않는다. 주문 payload, 전략명, 종목, 수량, 가격, 사유만 `data/order_lifecycle_events.jsonl`에 감사 로그로 남긴다.

실제 주문을 내기 전에는 다음 조건을 모두 확인해야 한다.

- 상세 설정에서 실행 모드를 `live`로 변경
- 실전 계좌라면 `_confirm_live_trading_guard()` 보호 확인 통과
- 거래 시작 preflight 로그에서 API 모드, 계좌, WebSocket, 인텔리전스 strict, 미체결 조회 지원 여부 확인
- 주문 가능 전략이 `asset_scope = kr_stock_live`, `short_enabled = False`, `live_supported = True` 조건을 만족

## 3. API 연결 체크리스트

1. 키움증권 API 신청 상태와 계좌 권한을 확인한다.
2. App Key와 Secret Key를 입력하고 API 연결을 실행한다.
3. 계좌 목록이 정상 조회되는지 확인한다.
4. WebSocket 연결과 체결/주문 이벤트 수신 상태를 확인한다.
5. 모의/실전 전환 시 REST/WS endpoint와 토큰 캐시 namespace가 함께 바뀌는지 로그로 확인한다.
6. 네트워크가 HTTPS/WSS outbound를 차단하지 않는지 확인한다.

현재 endpoint 기준:

- 실전 REST: `https://api.kiwoom.com`
- 실전 WebSocket: `wss://api.kiwoom.com:10000/api/dostk/websocket`
- 모의 REST: `https://mockapi.kiwoom.com`
- 모의 WebSocket: `wss://mockapi.kiwoom.com:10000/api/dostk/websocket`
- 토큰 캐시: `kiwoom_token_cache_live.json`, `kiwoom_token_cache_mock.json`

## 4. 시장 인텔리전스

인텔리전스 provider는 뉴스, 공시, 검색트렌드, 매크로, AI 요약으로 구성된다.

기본 정책:

- 데이터 누락, stale, refreshing, error 상태는 경고와 감사 로그를 남기고 진입을 허용한다.
- 실거래 fail-closed가 필요하면 `market_intelligence.source_policy.strict_entry_guard = true`로 바꾼다.
- `block_entry`, 고위험 DART, `force_exit`처럼 신뢰 가능한 고위험 신호는 strict 여부와 무관하게 기존 차단/청산 정책을 유지한다.

권장 순서:

1. NAVER 뉴스와 Datalab을 먼저 연결한다.
2. DART 공시 수집과 corp code 캐시 생성을 확인한다.
3. FRED 매크로는 선택적으로 켠다.
4. AI 요약은 마지막에 켜고 호출 한도와 일일 예산을 작게 둔다.

## 5. 보안과 저장 파일

secret 저장은 keyring이 우선이다. 실전 모드에서 keyring 저장 실패 시 평문 fallback은 기본 차단된다. 명시적으로 `allow_plaintext_secret_fallback = true`를 켠 경우에만 기존 설정 파일 fallback을 허용한다.

로컬 산출물:

- 설정: `kiwoom_settings.json`
- 토큰 캐시: `kiwoom_token_cache_live.json`, `kiwoom_token_cache_mock.json`
- 거래 내역: `kiwoom_trade_history.json`
- 시장 인텔리전스 이벤트: `data/market_intelligence_events.jsonl`
- 의사결정 감사 로그: `data/decision_audit.jsonl`
- 주문 생명주기/신호 전용 감사 로그: `data/order_lifecycle_events.jsonl`
- DART corp code 캐시: `data/dart_corp_codes.json`

주의:

- 위 파일은 `.gitignore`에서 로컬 산출물로 제외한다.
- 토큰 캐시는 atomic write와 best-effort 파일 권한 보호를 사용한다.
- 도구 메뉴의 `민감정보/토큰 삭제`로 keyring 항목, 평문 secret, 토큰 캐시를 정리할 수 있다.

## 6. 미체결 주문 조회

미체결 주문 조회는 키움 REST TR `ka400008`(미체결주문조회) 기반 adapter로 구현되어 있다.

- 내부 adapter: `KiwoomRESTClient.get_open_orders(account_no)`
- 지원 여부 표시: `supports_open_orders = True`
- 현재 동작: preflight에서 `supported (ka400008; schema pending verification)`로 표시
- 안전 장치: 공식 응답 스키마 교차 검증 전이므로 파싱 실패/빈 응담 시 예외를 전가하지 않고 빈 리스트를 반환한다. 실거래 전 키움 공식 가이드의 `ka400008` 응답 필드 매핑을 교차 확인할 것.

## 7. 실주문 전 운영 순서

1. `pip install -r requirements.txt`로 런타임 의존성을 설치한다.
2. 개발/검증 환경은 `pip install -r requirements-dev.txt`를 추가로 실행한다.
3. API 키를 입력하고 keyring 저장이 되는지 확인한다.
4. `signal_only`로 2~3거래일 동안 연결, 수신, 감사 로그만 검증한다.
5. 시장 인텔리전스 로그와 `data/decision_audit.jsonl`을 매일 확인한다.
6. 소수 종목, 최소 비중, 모의투자 또는 제한된 환경에서 `live`를 검증한다.
7. 실거래 전 preflight 로그에서 계좌/API/WebSocket/strict/open-order 상태를 확인한다.
8. 실거래 중 stop/emergency cleanup 로그와 주문 생명주기 로그를 함께 확인한다.

## 8. 검증 명령

```bash
python -m compileall -q app api data backtest strategies portfolio dialogs ui_dialogs.py strategy_manager.py "키움증권 자동매매.py"
python -m pytest tests\unit --override-ini addopts= --tb=short
python -m pyright .
python tools\refactor_verify.py
pyinstaller --clean KiwoomTrader.spec
```

2026-06-10 기준 검증 결과:

- `tests/unit` 전체 172개 테스트 통과
- Python 문법 컴파일 검증 통과
- `pyright .` 0 errors
- refactor verification 통과
- PyInstaller onefile 출력: `dist/KiwoomTrader_v4.5.exe`

## 9. 참고 링크

- 키움 REST API: https://openapi.kiwoom.com/m/main/home
- NAVER 뉴스 검색 API: https://developers.naver.com/docs/serviceapi/search/news/news.md
- NAVER Datalab API: https://developers.naver.com/docs/serviceapi/datalab/search/search.md
- OpenDART: https://opendart.fss.or.kr/
- FRED API: https://fred.stlouisfed.org/docs/api/fred/
