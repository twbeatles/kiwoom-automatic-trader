# 시장 인텔리전스 자동매매 확장 부록

작성일: 2026-03-25  
기준: 현재 코드베이스 실구현 + 한글 UI 개편 반영

## 1) 목적

이 문서는 시장 인텔리전스가 실제 자동매매 경로에 어떻게 연결되어 있는지, 제안했던 확장 계획 중 무엇이 이미 구현되었는지, 실거래 운영 전 어떤 순서로 rollout 해야 하는지를 정리한다.

## 2) 구현 상태 요약

| 항목 | 상태 | 현재 구현 내용 |
|---|---|---|
| 설정/상태 스키마 | 완료 | `settings_version = 6`, `source_policy`, `soft_scale`, `position_defense`, `portfolio_budget`, `candidate_universe`, `replay` |
| provider 상태 분리 | 완료 | `ok_with_data`, `ok_empty`, `error`, `partial` 구분과 핵심 소스 실패 보수 처리 |
| 구조화 이벤트 로그 | 완료 | `market/sector/theme/symbol` scope 이벤트와 payload 기반 replay |
| soft-scale sizing | 완료 | `size_multiplier`, `portfolio_budget_scale`가 실제 진입 수량에 반영 |
| 보유 포지션 방어 | 완료 | `watch_only`, `reduce_size`, `tighten_exit`, `force_exit` |
| bounded AI overlay | 완료 | 임계치/예산/호출 수 제한, 보조 정책만 허용 |
| 감사 로그 | 완료 | `data/decision_audit.jsonl` |
| 리플레이 뷰어 | 완료 | `📼 인텔리전스 리플레이` 탭 |
| candidate universe | 완료 | dual-source 승격과 TTL 기반 활성 후보 유지 |

## 3) 실제 주문 연결 방식

### 신규 진입

1. 기존 전략이 먼저 통과한다.
2. 이후 시장 인텔리전스가 `action_policy`를 계산한다.
3. `block_entry`면 진입을 막는다.
4. 진입 가능하면 `size_multiplier`와 `portfolio_budget_scale`로 수량을 조정한다.
5. 최종 판단과 수량은 `decision_audit.jsonl`에 기록된다.

### 보유 포지션

1. 기본 손절/익절/트레일링 로직이 먼저 존재한다.
2. 시장 인텔리전스 `exit_policy`가 있으면 여기에 추가로 개입한다.
3. `reduce_size`는 일부 청산, `tighten_exit`는 트레일링 강화, `force_exit`는 즉시 청산으로 연결된다.

## 4) 강한 제약 조건

- AI는 최종 주문 권한자가 아니다.
- 일반 뉴스와 AI만으로는 `force_exit`를 직접 트리거하지 않는다.
- 핵심 소스 오류 시 상태를 억지로 `fresh` 처리하지 않는다.
- 긍정 뉴스는 단독 매수 신호가 아니라 수량/우선순위 보정용이다.

## 5) 운영 관점에서 바로 확인해야 할 위치

파일:

- `data/market_intelligence_events.jsonl`
- `data/decision_audit.jsonl`
- `REAL_API_PREPARATION_GUIDE.md`

실제 앱 화면:

- `🧠 인텔리전스 설정`
- `🧠 인텔리전스 현황`
- `🩺 시스템 진단`
- `📼 인텔리전스 리플레이`

## 6) 실거래 전 rollout 권장 순서

1. 시장 인텔리전스만 켜고 실주문은 끈 상태로 로그를 하루 이상 수집한다.
2. `decision_audit.jsonl`에서 차단 사유와 수량 조정이 기대대로 기록되는지 확인한다.
3. `📼 인텔리전스 리플레이` 탭으로 이벤트와 감사 로그가 한 세션 동안 일관되게 보이는지 확인한다.
4. AI는 끈 상태에서 NAVER/DART/FRED 품질을 먼저 검증한다.
5. 이후 AI를 예산 제한 하에 점진적으로 켠다.
6. 실거래 전에는 `REAL_API_PREPARATION_GUIDE.md` 체크리스트를 끝까지 점검한다.

## 7) 아직 운영상 남은 과제

1. 키움 모의/실전 엔드포인트 분기 정책이 더 필요하면 `chk_mock`와 인증/REST/WSS URL을 명시적으로 연결해야 한다.
2. 장기 운영을 위해 로그 로테이션과 세션 종료 요약 자동화가 있으면 좋다.
3. candidate universe 승격 임계치는 실거래 결과를 보면서 더 다듬어야 한다.
