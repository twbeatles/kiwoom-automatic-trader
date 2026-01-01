# Kiwoom Pro Algo-Trader v4.0

키움증권 OpenAPI+를 활용한 **전문가용 자동매매 프로그램**입니다.

## ✨ 주요 기능

### 핵심 매매 전략
| 전략 | 설명 |
|------|------|
| **변동성 돌파** | (전일 고가 - 전일 저가) × K + 당일 시가 돌파 시 매수 |
| **트레일링 스톱** | 목표 수익 도달 후 고점 대비 하락 시 매도 |
| **ATR 손절** | 변동성 기반 동적 손절 |

### 보조지표 필터
- RSI, MACD, 볼린저밴드, DMI/ADX, 거래량

### v4.0 신규 기능
| 기능 | 설명 |
|------|------|
| 📱 **텔레그램** | 매수/매도/손절 실시간 알림 |
| ⏰ **스케줄러** | 매매 시간대/요일 설정 |
| 📈 **차트** | 누적 수익률, 일별 손익 시각화 |
| 🧪 **백테스트** | 과거 데이터 전략 검증 |
| 🎮 **모의투자** | 페이퍼 트레이딩 |

---

## 🛠️ 설치

### 요구 사항
- **OS**: Windows 10/11
- **Python**: 3.8 ~ 3.11 **(32-bit 필수)**
- **Kiwoom**: [키움증권 OpenAPI+](https://www1.kiwoom.com/h/customer/download/VOpenApiInfoView) 설치

### 필수 패키지
```bash
pip install pyqt5
```

### 선택적 패키지
```bash
pip install python-telegram-bot  # 텔레그램 알림
pip install matplotlib           # 차트 시각화
```

---

## 🚀 실행

```bash
python "키움증권 자동매매.py"
```

---

## 📦 PyInstaller 빌드

```bash
pip install pyinstaller
pyinstaller KiwoomProTrader.spec
```

빌드 결과: `dist/KiwoomProTrader.exe`

---

## ⚠️ 주의사항

- 본 프로그램은 투자 보조 도구이며, **투자의 책임은 전적으로 사용자에게 있습니다.**
- 실계좌 사용 전 반드시 모의투자로 전략을 검증하세요.

---

## 📜 Version History

| 버전 | 변경사항 |
|------|---------|
| v4.0 | 텔레그램, 스케줄러, 차트, 백테스트, 모의투자 |
| v3.1 | Toast 알림, 일괄 매도, HiDPI 지원 |
| v3.0 | MACD/BB/DMI 필터, 프리셋 관리자 |

---

© 2024-2026 Kiwoom Pro Algo-Trader
