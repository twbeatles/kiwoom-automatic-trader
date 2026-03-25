# 실제 API 준비 가이드

기준일: 2026-03-25  
기준: 현재 저장소 코드 + 공식 문서 확인

이 문서는 이 프로젝트를 실제 API와 연결해 운영하기 전에 무엇을 준비해야 하는지 정리한 실무용 체크리스트다.  
포털 UI, 신청 절차, 권한명은 공급자 정책에 따라 바뀔 수 있으므로 실제 신청 화면은 반드시 공식 문서를 다시 확인해야 한다.

## 1. 한눈에 보는 준비물

| 구분 | 필수 여부 | 준비 항목 | 이 프로젝트에서 쓰는 값 |
| --- | --- | --- | --- |
| 키움증권 REST | 필수 | App Key, Secret Key, API 사용 가능한 계좌, 실시간 수신 가능 환경 | `App Key`, `Secret Key`, 계좌 선택 |
| 키움증권 WebSocket | 실전 운영 권장 | `websockets` 라이브러리, WSS 접속 가능 네트워크 | 실시간 체결/주문/지수 수신 |
| NAVER Open API | 시장 인텔리전스 권장 | Client ID, Client Secret | `NAVER Client ID`, `NAVER Client Secret` |
| OpenDART | 시장 인텔리전스 권장 | API 인증키 | `DART API Key` |
| FRED | 선택 | API Key | `FRED API Key` |
| AI Provider | 선택 | OpenAI 또는 Gemini API Key | `AI API Key`, `AI Provider`, `AI Model` |
| Telegram | 선택 | Bot Token, Chat ID | `봇 토큰`, `챗 ID` |
| 로컬 보안 | 필수 | Keyring 사용 가능 OS 환경, 설정 파일/로그 파일 관리 | Windows Credential Manager 권장 |

## 2. 현재 코드가 실제로 요구하는 것

현재 코드 기준으로 실거래/실시간 운영에 직접 연결되는 핵심 모듈은 아래와 같다.

- 키움 인증: [api/auth.py](d:\twbeatles-repos\kiwoom-automatic-trader\api\auth.py)
- 키움 REST 호출: [api/rest_client.py](d:\twbeatles-repos\kiwoom-automatic-trader\api\rest_client.py)
- 키움 WebSocket: [api/websocket_client.py](d:\twbeatles-repos\kiwoom-automatic-trader\api\websocket_client.py)
- API 연결 UI: [app/mixins/api_account.py](d:\twbeatles-repos\kiwoom-automatic-trader\app\mixins\api_account.py)
- 시장 인텔리전스 API 입력 UI: [app/mixins/market_intelligence.py](d:\twbeatles-repos\kiwoom-automatic-trader\app\mixins\market_intelligence.py)
- 설정/비밀값 저장: [app/mixins/persistence_settings.py](d:\twbeatles-repos\kiwoom-automatic-trader\app\mixins\persistence_settings.py)
- 실거래 가드: [app/mixins/trading_session.py](d:\twbeatles-repos\kiwoom-automatic-trader\app\mixins\trading_session.py)

실거래 가드도 이미 들어가 있다.

- 실주문은 현재 `asset_scope = kr_stock_live` 일 때만 허용된다.
- `short_enabled = True` 이면 실주문이 차단된다.
- `Config.STRATEGY_CAPABILITIES` 에서 `live_supported = True` 인 전략만 실거래 가능하다.

현재 코드 기준 실거래 허용 전략:

- `volatility_breakout`
- `time_series_momentum`
- `ma_channel_trend`
- `orb_donchian_breakout`
- `rsi_bollinger_reversion`
- `dmi_trend_strength`
- `investor_program_flow`

추가 정합성 메모:

- `pairs_trading_cointegration`, `stat_arb_residual`, `ff5_factor_ls`처럼 전략팩에서 SHORT 방향을 반환할 수 있는 전략은 현재 실주문 대상이 아니라 백테스트/시뮬레이션 범위로 보는 편이 맞다.
- `portfolio_mode`, `enable_backtest`, `portfolio/allocator.py`는 확장 경로로는 존재하지만 실주문 라우팅의 직접 제어 스위치는 아니다.
- `분할 매수` 설정은 현재 UI/설정/프로필 경로까지 연결되어 있으며, 실제 주문 분할 제출 로직은 후속 구현 범위다.

## 3. 가장 먼저 확인할 현재 코드 제약

이 부분은 운영 전에 반드시 이해해야 한다.

### 3.1 `모의투자` 체크박스의 현재 의미

UI에는 `모의투자` 체크박스가 있지만, 현재 코드에서 `KiwoomAuth.BASE_URL` 과 `KiwoomRESTClient.BASE_URL` 은 모두 `https://api.kiwoom.com` 으로 고정돼 있다.

즉 현재 상태에서는:

- `chk_mock` 는 실주문 가드 완화 판단에는 쓰인다.
- 하지만 인증/REST/WebSocket 엔드포인트를 모의 전용 주소로 분기하는 구현은 보이지 않는다.

운영 의미:

- 실제 실전 연결 전, 모의투자 전용 엔드포인트를 별도로 써야 하는 정책이라면 이 부분은 별도 확인 또는 구현이 필요하다.
- 문서상 “모의투자” 라벨만 믿고 바로 연결하면 위험하다.

### 3.2 비밀값 저장 방식

비밀값은 기본적으로 `keyring` 으로 저장한다.  
하지만 `keyring` 이 없거나 OS Keyring 저장이 실패하면 설정 파일 평문 fallback 이 가능하다.

실제 영향:

- `keyring` 정상 동작 시: OS 보안 저장소 사용
- `keyring` 실패 시: `kiwoom_settings.json` 에 평문 저장 가능

이 프로젝트에서 민감정보로 취급해야 할 값:

- 키움 `app_key`, `secret_key`
- NAVER `client_id`, `client_secret`
- DART `api_key`
- FRED `api_key`
- AI `api_key`

## 4. 공급자별 준비 가이드

## 4.1 키움증권 REST/WebSocket

실거래를 하려면 최소 아래가 준비돼야 한다.

- 키움증권 계정
- API 사용 가능한 계좌
- REST API App Key / Secret Key
- 실시간 체결 수신 가능한 환경
- 주문 제약이 없는 인증 상태

실무 준비 체크리스트:

1. 키움 REST API 포털에서 API 사용 신청 상태를 확인한다.
2. App Key / Secret Key 를 발급받는다.
3. 실거래에 사용할 계좌가 API 조회 및 주문 권한을 갖는지 확인한다.
4. 복수 ID 또는 인증서 사용 계정이면 포털 안내에 따라 추가 인증, 공동인증서, 자동서명 정책을 확인한다.
5. 허용 IP 또는 접속 환경 제한이 있다면 현재 운용 PC의 공인 IP/환경을 등록한다.
6. 사내망, VDI, 원격 접속 환경이면 HTTPS/WSS outbound 제한이 없는지 먼저 확인한다.
7. 실시간 수신이 끊기면 전략이 사실상 무력화되므로 네트워크 안정성을 별도 점검한다.

현재 프로젝트 연결 흐름:

- UI `🔐 API/알림` 탭에서 `앱 키`, `시크릿 키` 입력
- `API 연결` 버튼 클릭
- 계좌 목록 수신
- 계좌 선택
- 이후 REST + WebSocket 사용

실제 입력 필드:

- `App Key`
- `Secret Key`
- `모의투자`

주의:

- 실주문 시작 전에 계좌 목록이 정상적으로 떠야 한다.
- 계좌 목록이 비어 있으면 이 프로젝트는 연결 실패로 처리한다.
- 실시간 수신용 `websockets` 라이브러리가 없으면 WebSocket 클라이언트가 뜨지 않는다.

## 4.2 NAVER Open API

현재 이 프로젝트는 NAVER 키 한 세트로 두 기능을 같이 사용한다.

- 뉴스 검색 API
- 데이터랩 검색어 트렌드 API

준비 항목:

- NAVER Developers 애플리케이션 등록
- `검색 API` 권한
- `데이터랩(검색어 트렌드)` 권한
- Client ID
- Client Secret

운영 포인트:

- 뉴스 검색은 종목 alias 기반으로 여러 질의를 보낸다.
- 데이터랩은 종목명/alias 기반으로 여러 질의를 보내 상대 검색량을 계산한다.
- 실제 운용 시 호출량은 종목 수, refresh 주기, alias 수에 비례해 늘어난다.

현재 코드상 연결 필드:

- `NAVER Client ID`
- `NAVER Client Secret`

권장 설정:

- 초기에는 유니버스를 작게 시작한다.
- `refresh_sec.news`, `refresh_sec.dart`, `refresh_sec.datalab` 을 너무 짧게 두지 않는다.
- AI보다 먼저 NAVER 뉴스/Datalab 품질을 확인한다.

## 4.3 OpenDART

OpenDART 는 공시 리스크 판단에 직접 쓰인다.  
현재 구현에서는 `funding`, `governance`, `earnings`, `contract`, `halt`, `correction` 계열 이벤트로 정규화하고, 고위험 키워드가 잡히면 `force_exit` 까지 이어질 수 있다.

준비 항목:

- OpenDART API 인증키

현재 코드상 연결 필드:

- `DART API Key`

운영 포인트:

- DART 는 시장 인텔리전스에서 가장 민감한 소스 중 하나다.
- 현재 구현은 `receipt_no` 기준 incremental cursor 를 사용한다.
- corp code 캐시는 `data/dart_corp_codes.json` 에 유지될 수 있다.

## 4.4 FRED

FRED 는 매크로 레짐 판단에 사용된다.  
현재 기본 시리즈는 `VIXCLS`, `DGS10` 이다.

준비 항목:

- FRED API Key

현재 코드상 연결 필드:

- `FRED API Key`

운영 포인트:

- 필수는 아니지만 `market_risk_mode`, `portfolio_budget_scale` 계산에 영향을 준다.
- NAVER/DART 만큼 직접적이지는 않지만, 리스크 오프 필터 품질에 영향이 있다.

## 4.5 AI Provider

AI는 선택 기능이다. 기본은 규칙 기반이 우선이고, AI는 보조 해석만 한다.

준비 항목:

- OpenAI API Key 또는 Gemini API Key 중 하나
- 운영할 모델명
- 일일 예산
- 종목당 최대 호출 수

현재 코드상 연결 필드:

- `AI 요약 사용`
- `AI Provider` = `gemini` 또는 `openai`
- `AI Model`
- `AI API Key`

운영 포인트:

- 기본적으로 처음에는 `OFF` 로 두는 것이 맞다.
- 실제 운영 초기에는 AI를 끈 상태로 규칙 기반 동작을 먼저 검증한다.
- 이후 `min_score_to_call`, `max_calls_per_day`, `max_calls_per_symbol`, `daily_budget_krw` 를 보수적으로 조정한다.
- 현재 정책상 AI 단독으로 `force_exit` 권한을 주지 않는 것이 안전하다.

## 4.6 Telegram

필수는 아니지만 운영 알림에 매우 유용하다.

준비 항목:

- Bot Token
- Chat ID

운영 포인트:

- 장전 브리핑, 차단 경보, 연결 상태 추적에 유용하다.
- 민감정보를 메시지에 직접 포함하지 않도록 주의한다.

## 5. 로컬 환경 준비

실전 운영 전 로컬 환경도 API 준비의 일부다.

필수 권장 환경:

- Windows
- Python 3.10+
- `PyQt6`
- `requests`
- `websockets`
- `keyring`
- 인터넷 outbound HTTPS/WSS 허용

실무 체크:

- OS 시간이 정확해야 한다.
- 백신/보안 솔루션이 WebSocket 을 차단하지 않는지 본다.
- 사내 프록시 환경이면 `api.kiwoom.com`, `openapi.naver.com`, `opendart.fss.or.kr`, `api.stlouisfed.org`, `api.openai.com` 또는 `generativelanguage.googleapis.com` 연결을 확인한다.
- 노트북 절전, 네트워크 끊김, VPN 자동 재연결 정책이 실시간 수신에 영향을 주지 않는지 확인한다.

## 6. 저장 파일과 보안 관리

현재 코드 기준 주요 파일 경로:

- 설정 파일: `kiwoom_settings.json`
- 토큰 캐시: `kiwoom_token_cache.json`
- 시장 인텔리전스 이벤트 로그: `data/market_intelligence_events.jsonl`
- 의사결정 감사 로그: `data/decision_audit.jsonl`
- 거래내역: `kiwoom_trade_history.json`

보안 원칙:

1. `kiwoom_settings.json`, `kiwoom_token_cache.json`, `data/*.jsonl` 을 외부 공유나 Git 커밋 대상에서 제외한다.
2. `keyring` 이 정상 동작하는 환경을 우선 사용한다.
3. 운영 PC는 개인용과 분리하거나 최소한 OS 계정을 분리한다.
4. 원격제어 툴 사용 시 클립보드/파일 전송 로그를 점검한다.
5. 에러 스크린샷을 공유할 때 App Key, Secret, API Key, 계좌번호를 반드시 가린다.

## 7. 실제 UI 입력 매핑

실제 입력 위치는 아래처럼 나뉜다.

### `🔐 API/알림` 탭

- `앱 키`
- `시크릿 키`
- `모의투자`
- `봇 토큰`
- `챗 ID`
- `텔레그램 알림 사용`

### `🧠 인텔리전스 설정` 탭

- `시장 인텔리전스 사용`
- `NAVER 뉴스`
- `OpenDART`
- `NAVER Datalab`
- `FRED Macro`
- `NAVER Client ID`
- `NAVER Client Secret`
- `DART API Key`
- `FRED API Key`

### `🧠 인텔리전스 설정 > AI 요약`

- `AI 요약 사용`
- `AI 제공사`
- `모델 이름`
- `AI API Key`
- `AI 하루 호출수`
- `AI 종목당 호출수`
- `AI 하루 예산(원)`

## 8. 실전 투입 전 권장 순서

아래 순서대로 진행하는 것이 가장 안전하다.

1. `keyring` 동작부터 확인한다.
2. 키움 App Key/Secret 만 먼저 입력하고 연결 테스트를 한다.
3. 계좌 목록이 정상적으로 내려오는지 본다.
4. WebSocket 이 실제로 체결/호가를 받는지 확인한다.
5. NAVER 키를 넣고 `뉴스` 와 `Datalab` 을 각각 수동 새로고침해 본다.
6. DART 키를 넣고 공시 수집이 되는지 본다.
7. FRED 키를 넣고 `macro` 상태가 갱신되는지 본다.
8. 이 단계까지는 AI를 끈다.
9. `🧠 인텔리전스 현황` 탭에서 `소스 상태`, `자동매매 정책`, `수량 배수`, `청산 정책` 을 확인한다.
10. `📼 인텔리전스 리플레이` 탭에서 이벤트 로그와 감사 로그가 누적되는지 확인한다.
11. 소수 종목, 보수적 설정, 매우 작은 비중으로 시뮬레이션 또는 제한된 운영을 시작한다.
12. 충분히 검증한 뒤에만 실전 비중을 올린다.

## 9. 운영 전 점검 체크리스트

### 연결

- 키움 REST 연결 성공
- 계좌 목록 조회 성공
- 계좌 정보 조회 성공
- WebSocket 연결 성공

### 주문 가드

- `asset_scope = kr_stock_live`
- `short_enabled = False`
- 선택 전략이 `live_supported = True`

### 시장 인텔리전스

- NAVER 뉴스 상태 정상
- NAVER Datalab 상태 정상
- DART 상태 정상
- FRED 상태 정상 또는 의도적으로 비활성화
- AI는 초기엔 비활성 또는 매우 보수적 예산

### 로그/감사

- `data/market_intelligence_events.jsonl` 생성 확인
- `data/decision_audit.jsonl` 생성 확인
- `📼 인텔리전스 리플레이` 탭에서 최근 이벤트 확인
- `🩺 시스템 진단` 탭에서 `sync_failed`, `외부 데이터 오류`, `소스 상태` 확인

## 10. 자주 발생하는 문제

### 10.1 `API 연결 실패`

가능 원인:

- App Key / Secret 오입력
- API 사용 신청 미완료
- 계좌 권한 없음
- 네트워크 차단
- 토큰 발급 실패

### 10.2 계좌 목록이 비어 있음

가능 원인:

- API 연결은 됐지만 주문/계좌 조회 권한 미부여
- 포털 인증/인증서/추가 로그인 상태 미완료
- 실거래 계좌 연결 상태 문제

### 10.3 NAVER 403 또는 빈 응답

가능 원인:

- 애플리케이션에 해당 API 권한 미설정
- 잘못된 Client ID / Secret
- 호출량 초과
- 질의가 너무 협소해서 `ok_empty`

### 10.4 DART 가 비어 있음

가능 원인:

- 인증키 오입력
- 조회 기간 내 공시 부재
- 종목코드와 DART 고유번호 매핑 초기 단계

### 10.5 FRED 가 비어 있음

가능 원인:

- API Key 없음
- 키는 맞지만 시리즈 호출 실패
- 일시 네트워크 문제

### 10.6 AI가 동작하지 않음

가능 원인:

- `AI API Key` 누락
- Provider/Model 오입력
- 예산 초과
- 호출 횟수 초과
- 응답 포맷 파싱 실패

### 10.7 `모의투자` 인데 기대와 다르게 동작함

현재 코드 제한:

- `모의투자` 체크가 엔드포인트 전환까지 보장하지는 않는다.
- 실제 모의 전용 분기를 기대하면 별도 검토가 필요하다.

## 11. 권장 롤아웃 정책

초기 1주 운영 권장안:

1. 첫 2~3일은 주문 없이 API/로그만 검증한다.
2. 다음 2~3일은 소수 종목 + 최소 비중으로 운영한다.
3. AI는 마지막에 켠다.
4. `force_exit` 는 DART 기반 이벤트에서만 허용 상태를 유지한다.
5. 매일 장 종료 후 `📼 인텔리전스 리플레이` 탭과 `decision_audit.jsonl` 을 검토한다.

## 12. 공식 참고 링크

- 키움 REST API 포털: https://openapi.kiwoom.com/m/main/home
- 키움 REST API 로그인/신청 화면: https://openapi.kiwoom.com/mgmt/VOpenApiRegView?dummyVal=0
- NAVER 뉴스 검색 API: https://developers.naver.com/docs/serviceapi/search/news/news.md
- NAVER 데이터랩 검색어 트렌드 API: https://developers.naver.com/docs/serviceapi/datalab/search/search.md
- OpenDART 개발가이드 예시: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020055
- FRED API 문서: https://fred.stlouisfed.org/docs/api/fred/v2/index.html
- OpenAI API Key 도움말: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key
- Google AI Studio / Gemini API Key: https://ai.google.dev/aistudio/

## 13. 최종 결론

이 프로젝트를 실제 API와 연결하려면 준비물은 단순히 “키 몇 개”가 아니다.

- 브로커 권한
- 계좌 조회/주문 가능 상태
- 실시간 수신 환경
- 외부 데이터 API 키
- 보안 저장소
- 로그/감사 확인 체계
- 실전 가드 조건

여기까지 모두 준비돼야 실사용이 가능하다.  
특히 현재 코드 기준으로는 `모의투자` 엔드포인트 분기와 `keyring` fallback 보안 상태를 먼저 확인하는 것이 최우선이다.
