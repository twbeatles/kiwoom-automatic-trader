# Kiwoom Pro Algo-Trader v4.1

키움증권 REST API 기반 자동매매 프로그램

## ✨ 주요 기능

### 📈 매매 전략
- **변동성 돌파 전략** + 트레일링 스톱
- RSI, MACD, 볼린저밴드, DMI 필터
- 시간대별 K값 자동 조정

### 🔔 알림 시스템
- Windows 데스크톱 토스트 알림
- 사운드 알림 (winsound)
- 텔레그램 알림 연동

### 📊 백테스팅
- 과거 데이터 기반 시뮬레이션
- MDD, 샤프비율, 승률 계산
- 거래 내역 리포트

### 🔎 종목 스크리너
- 골든/데드 크로스 감지
- RSI 과매수/과매도
- 거래량 급증, 변동성 돌파

### 🛡️ 리스크 관리
- 드로다운 모니터링
- 연속 손실 자동 일시정지
- 종목별 블랙리스트

### 🎨 UI/UX
- 다크/라이트 테마
- 미니 모드 지원
- 우클릭 수동 매매

---

## 📦 설치

### 요구사항
- Python 3.10+
- Windows 10/11

### 의존성 설치
```bash
pip install -r requirements.txt
```

### 선택적 의존성
```bash
pip install plyer  # 데스크톱 알림 (선택)
```

---

## 🚀 실행

```bash
python "키움증권 자동매매.py"
```

---

## 📦 빌드

### PyInstaller 빌드 (단일 EXE)
```bash
pyinstaller KiwoomProTrader_v4.1.spec
```

빌드 결과: `dist/KiwoomProTrader.exe`

---

## 📁 파일 구조

```
├── 키움증권 자동매매.py    # 메인 애플리케이션
├── config.py              # 설정 상수
├── strategy_manager.py    # 매매 전략 로직
├── notification_manager.py # 알림 시스템
├── risk_manager.py        # 리스크 관리
├── stock_screener.py      # 종목 스크리너
├── backtest_engine.py     # 백테스팅 엔진
├── themes.py              # UI 테마
└── api/
    ├── auth.py            # 인증 관리
    ├── rest_client.py     # REST API
    └── websocket_client.py # WebSocket
```

---

## ⚙️ API 설정

1. 키움증권 Open API 신청
2. API Key/Secret 발급
3. 프로그램 내 API 탭에서 설정

---

## 📋 라이선스

MIT License

---

## 📞 주의사항

⚠️ **투자 책임**: 이 프로그램 사용으로 인한 손실은 본인 책임입니다.
