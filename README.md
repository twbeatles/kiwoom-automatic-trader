# 🚀 Kiwoom Pro Algo-Trader v4.1

키움증권 REST API 기반 프리미엄 자동매매 프로그램 (PyQt6)

## ✨ v4.1 주요 변경사항 (UI/UX 리팩토링)

사용자 경험을 극대화하기 위해 UI/UX를 전면적으로 개선했습니다.

- **🎨 Premium Dark Theme**: 눈이 편안하고 세련된 다크 테마 적용
- **💎 Glassmorphism Design**: 반투명 그라디언트와 깊이감 있는 카드 UI
- **⚡ Reactive UI**: 실시간 상태에 반응하는 애니메이션 인디케이터
- **📟 Modern Log Terminal**: 가독성이 향상된 컬러 코딩 로그 시스템
- **💹 Dynamic Data Grid**: 수익/손실에 따라 실시간으로 변하는 테이블 디자인

---

## ✨ 주요 기능

### 📈 자동매매
- **변동성 돌파 전략** (Larry Williams)
- **트레일링 스톱** (수익 보존) + 자동 손절매
- **RSI, MACD, 볼린저밴드, DMI 필터**
- **일일 손실 한도** / 시간 자동 청산

### 📊 시세 조회
| 탭 | 기능 |
|----|------|
| 📈 차트 | 일봉/주봉/분봉 OHLCV 및 보조지표 |
| 📋 호가창 | 10단 매수/매도 호가 및 잔량 분석 |
| 🔍 조건검색 | 영웅문4 조건식 실시간 연동 |
| 🏆 순위 | 거래량/등락률 실시간 랭킹 |

### 🔔 스마트 알림
- **텔레그램 봇**: 매매 체결, 에러, 수익률 실시간 전송
- **시스템 트레이**: 백그라운드 실행 및 상태 아이콘

---

## 🛠️ 설치 및 실행

### 필수 조건
- Windows 10/11 (64bit 권장)
- Python 3.10 이상
- 키움증권 REST API 신청

### 설치
```bash
pip install -r requirements.txt
python "키움증권 자동매매.py"
```

---

## 📁 프로젝트 구조

```
├── 키움증권 자동매매.py   # 메인 실행 파일 (UI)
├── config.py              # 설정 및 상수
├── strategy_manager.py    # 매매 전략(Algo)
├── api/                   # REST API 코어
│   ├── auth.py            # OAuth2 인증
│   ├── rest_client.py     # HTTP 요청
│   ├── websocket_client.py # 실시간 시세
│   └── models.py          # 데이터 모델
```

---

## 🏗️ 실행 파일 빌드 (경량화)

최적화된 PyInstaller 설정을 통해 가볍고 빠른 실행 파일을 생성합니다.

```bash
# 빌드 실행
pyinstaller KiwoomTrader.spec
```

---

## ⚠️ 주의사항

- 본 프로그램은 개인 학습 및 연구 목적으로 제작되었습니다.
- **모의투자** 환경에서 충분한 테스트 후 사용하시기 바랍니다.
- **투자 손실에 대한 책임은 전적으로 사용자에게 있습니다.**
