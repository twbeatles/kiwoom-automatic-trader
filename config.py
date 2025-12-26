"""
Kiwoom Pro Algo-Trader Config
"""

class Config:
    """프로그램 설정 상수"""
    # 화면 번호
    SCREEN_DEPOSIT = "1002"
    SCREEN_DAILY = "1001"
    SCREEN_REAL = "2000"
    SCREEN_ORDER = "0101"
    
    # 기본값
    DEFAULT_CODES = "005930,000660,042700,005380"
    DEFAULT_BETTING_RATIO = 10.0
    DEFAULT_K_VALUE = 0.5
    DEFAULT_TS_START = 3.0
    DEFAULT_TS_STOP = 1.5
    DEFAULT_LOSS_CUT = 2.0
    
    # RSI 설정
    DEFAULT_RSI_PERIOD = 14
    DEFAULT_RSI_UPPER = 70
    DEFAULT_RSI_LOWER = 30
    DEFAULT_USE_RSI = True
    
    # MACD 설정 (v3.0 신규)
    DEFAULT_MACD_FAST = 12
    DEFAULT_MACD_SLOW = 26
    DEFAULT_MACD_SIGNAL = 9
    DEFAULT_USE_MACD = True
    
    # 볼린저 밴드 설정 (v3.0 신규)
    DEFAULT_BB_PERIOD = 20
    DEFAULT_BB_STD = 2.0
    DEFAULT_USE_BB = False
    
    # ATR 설정 (v3.0 신규)
    DEFAULT_ATR_PERIOD = 14
    DEFAULT_ATR_MULTIPLIER = 2.0
    DEFAULT_USE_ATR = False
    
    # 스토캐스틱 RSI 설정 (v3.0 신규)
    DEFAULT_STOCH_RSI_PERIOD = 14
    DEFAULT_STOCH_K_PERIOD = 3
    DEFAULT_STOCH_D_PERIOD = 3
    DEFAULT_USE_STOCH_RSI = False
    
    # DMI/ADX 설정 (v3.0 신규)
    DEFAULT_DMI_PERIOD = 14
    DEFAULT_ADX_THRESHOLD = 25
    DEFAULT_USE_DMI = False
    
    # 거래량 설정
    DEFAULT_VOLUME_MULTIPLIER = 1.5
    DEFAULT_VOLUME_PERIOD = 20
    DEFAULT_USE_VOLUME = True
    
    # 리스크 관리
    DEFAULT_MAX_DAILY_LOSS = 3.0
    DEFAULT_MAX_HOLDINGS = 5
    DEFAULT_USE_RISK_MGMT = True
    
    # 진입 점수 시스템 (v3.0 신규)
    ENTRY_SCORE_THRESHOLD = 60
    USE_ENTRY_SCORING = False
    ENTRY_WEIGHTS = {
        'target_break': 20,
        'ma_filter': 15,
        'rsi_optimal': 20,
        'macd_golden': 20,
        'volume_confirm': 15,
        'bb_position': 10,
    }
    
    # 다단계 익절 설정 (v3.0 신규)
    PARTIAL_TAKE_PROFIT = [
        {'rate': 3.0, 'sell_ratio': 30},
        {'rate': 5.0, 'sell_ratio': 30},
        {'rate': 8.0, 'sell_ratio': 20},
    ]
    DEFAULT_USE_PARTIAL_PROFIT = False
    
    # 파일 경로
    SETTINGS_FILE = "kiwoom_settings.json"
    PRESETS_FILE = "kiwoom_presets.json"
    TRADE_HISTORY_FILE = "kiwoom_trade_history.json"
    LOG_DIR = "logs"
    
    # 텔레그램 설정 (v3.1 신규)
    DEFAULT_TELEGRAM_BOT_TOKEN = ""
    DEFAULT_TELEGRAM_CHAT_ID = ""
    DEFAULT_USE_TELEGRAM = False
    
    # 시간 설정
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 19
    NO_ENTRY_HOUR = 15
    
    # API 재시도 설정 (v3.0 신규)
    API_MAX_RETRIES = 3
    API_RETRY_DELAY = 1
    
    # 메모리 관리 (v3.0 신규)
    MAX_LOG_LINES = 500
    
    # 기본 프리셋 정의 (v3.0 신규)
    DEFAULT_PRESETS = {
        "aggressive": {
            "name": "🔥 공격적",
            "description": "높은 수익을 추구하지만 리스크도 높음",
            "k": 0.6, "ts_start": 2.0, "ts_stop": 1.0, "loss": 3.0,
            "betting": 15.0, "rsi_upper": 75, "max_holdings": 7
        },
        "normal": {
            "name": "⚖️ 표준",
            "description": "균형 잡힌 수익과 리스크 관리",
            "k": 0.5, "ts_start": 3.0, "ts_stop": 1.5, "loss": 2.0,
            "betting": 10.0, "rsi_upper": 70, "max_holdings": 5
        },
        "conservative": {
            "name": "🛡️ 보수적",
            "description": "안정적인 수익, 낮은 리스크",
            "k": 0.4, "ts_start": 4.0, "ts_stop": 2.0, "loss": 1.5,
            "betting": 5.0, "rsi_upper": 65, "max_holdings": 3
        }
    }
    
    # 툴팁 설명 (v3.0 신규)
    TOOLTIPS = {
        "codes": "감시할 종목 코드를 콤마(,)로 구분하여 입력합니다.\n예: 005930,000660,042700",
        "betting": "총 예수금 대비 종목당 투자 비율입니다.\n권장: 5% ~ 20%",
        "k_value": "변동성 돌파 전략의 K 계수\n목표가 = 시가 + (전일 변동폭 × K값)\n권장: 0.3 ~ 0.5",
        "ts_start": "트레일링 스톱 발동 수익률\n권장: 3% ~ 10%",
        "ts_stop": "고점 대비 하락 허용폭\n권장: 1% ~ 3%",
        "loss_cut": "절대 손절 기준\n권장: 2% ~ 5%",
        "rsi": "과매수 판단 기준 RSI\n권장: 65 ~ 75",
        "max_holdings": "동시 보유 가능 최대 종목 수\n권장: 3 ~ 7개"
    }
    
    # 도움말 콘텐츠 (v3.0 신규)
    HELP_CONTENT = {
        "quick_start": """
## 🚀 빠른 시작 가이드

### 1단계: 로그인
키움증권 OpenAPI+ 로그인 창에서 로그인합니다.

### 2단계: 종목 선택
감시할 종목 코드를 콤마로 구분하여 입력합니다.
예: 005930,000660,042700

### 3단계: 전략 선택
- 초보자: **보수적** 프리셋 권장
- 경험자: **표준** 프리셋으로 시작
- 고급: 직접 파라미터 조정

### 4단계: 매매 시작
"🚀 전략 분석 및 매매 시작" 버튼을 클릭합니다.
        """,
        "strategy": """
## 📈 전략 설명

### 변동성 돌파 전략
래리 윌리엄스(Larry Williams)가 개발한 단기 트레이딩 전략입니다.

**핵심 원리:**
- 전일 고가 - 전일 저가 = 변동폭
- 목표가 = 당일 시가 + (변동폭 × K값)
- 현재가가 목표가를 돌파하면 매수

### 트레일링 스톱
- 목표 수익률 도달 시 고점 추적 시작
- 고점 대비 설정 하락폭 발생 시 매도
        """,
        "faq": """
## ❓ 자주 묻는 질문

**Q: 15시 이후에도 매수가 되나요?**
A: 아니요, 15시 이후에는 신규 매수가 중지됩니다.

**Q: 손실이 발생하면 어떻게 되나요?**
A: 설정된 손절률에 따라 자동으로 매도됩니다.

**Q: 프로그램 종료 시 보유 종목은?**
A: 자동 청산되지 않습니다. 수동 청산이 필요합니다.
        """
    }
