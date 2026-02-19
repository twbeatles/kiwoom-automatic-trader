"""
Kiwoom Pro Algo-Trader Config v4.3
REST API 기반 + 확장 기능 설정
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Dict, Set, Optional


_BASE_PATH = Path(__file__).resolve().parent

@dataclass
class TradingConfig:
    """실시간 트레이딩 설정 (UI와 로직 분리용)"""
    # 기본 설정
    codes: List[str] = field(default_factory=list)
    betting_ratio: float = 10.0
    
    # 전략 파라미터
    k_value: float = 0.5
    loss_cut: float = 2.0
    ts_start: float = 3.0
    ts_stop: float = 1.5
    
    # 지표 사용 여부 및 설정
    use_rsi: bool = True
    rsi_period: int = 14
    rsi_upper: int = 70
    rsi_lower: int = 30
    
    use_stoch_rsi: bool = False
    stoch_upper: int = 80
    stoch_lower: int = 20
    
    use_macd: bool = True
    use_bb: bool = False
    bb_k: float = 2.0
    
    use_volume: bool = True
    volume_mult: float = 1.5
    
    # 리스크 관리
    max_holdings: int = 5
    use_risk_mgmt: bool = True
    
    # v4.3 신규 전략
    use_mtf: bool = False
    use_gap: bool = False
    use_dynamic_sizing: bool = False
    use_atr_stop: bool = False
    atr_mult: float = 2.0
    
    use_liquidity: bool = False
    min_avg_value: int = 10  # 억 단위
    
    use_spread: bool = False
    max_spread: float = 0.5
    
    use_market_limit: bool = False
    market_limit: int = 70
    
    use_sector_limit: bool = False
    sector_limit: int = 30
    
    use_partial_profit: bool = False
    
    # 추가 필드 (v4.3 대응)
    use_dmi: bool = False
    adx_threshold: int = 25
    
    use_ma: bool = False
    ma_short: int = 5
    ma_long: int = 20
    
    use_split: bool = False
    split_count: int = 3
    split_percent: float = 0.5
    
    use_time_strategy: bool = False
    use_entry_scoring: bool = False
    entry_score_threshold: int = 60

    # 확장 전략팩/포트폴리오/백테스트 (v5.0)
    strategy_pack: Dict[str, Any] = field(default_factory=lambda: {
        "primary_strategy": "volatility_breakout",
        "entry_filters": ["rsi", "volume", "macd"],
        "exit_overlays": ["trailing_stop", "atr_stop"],
        "risk_overlays": ["max_holdings", "daily_loss_limit"],
    })
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    portfolio_mode: str = "single_strategy"
    short_enabled: bool = False
    asset_scope: str = "kr_stock_live"
    backtest_config: Dict[str, Any] = field(default_factory=lambda: {
        "timeframe": "1d",
        "lookback_days": 365,
        "commission_bps": 5.0,
        "slippage_bps": 3.0,
    })
    feature_flags: Dict[str, bool] = field(default_factory=lambda: {
        "use_modular_strategy_pack": True,
        "enable_backtest": True,
        "enable_external_data": True,
    })

    # 실행 정책/추가 리스크 옵션 (기존 UI/설정과 정합)
    execution_policy: str = "market"
    use_atr_sizing: bool = False
    risk_percent: float = 1.0
    use_breakout_confirm: bool = False
    breakout_ticks: int = 3
    use_cooldown: bool = False
    cooldown_min: int = 10
    use_time_stop: bool = False
    time_stop_min: int = 120


class Config:
    """프로그램 설정 상수"""
    
    # =========================================================================
    # REST API 설정
    # =========================================================================
    REST_API_BASE_URL = "https://api.kiwoom.com"
    WEBSOCKET_URL = "wss://api.kiwoom.com/ws/realtime"
    
    # 인증 설정
    DEFAULT_APP_KEY = ""
    DEFAULT_SECRET_KEY = ""
    TOKEN_CACHE_FILE = "kiwoom_token_cache.json"
    
    # API 요청 제한
    API_RATE_LIMIT = 5
    API_REQUEST_TIMEOUT = 10
    API_MAX_RETRIES = 3
    API_RETRY_DELAY = 1
    
    # =========================================================================
    # 기본값
    # =========================================================================
    DEFAULT_CODES = "005930,000660,042700,005380"
    DEFAULT_BETTING_RATIO = 10.0
    DEFAULT_K_VALUE = 0.5
    DEFAULT_TS_START = 3.0
    DEFAULT_TS_STOP = 1.5
    DEFAULT_LOSS_CUT = 2.0
    
    # =========================================================================
    # RSI 설정
    # =========================================================================
    DEFAULT_RSI_PERIOD = 14
    DEFAULT_RSI_UPPER = 70
    DEFAULT_RSI_LOWER = 30
    DEFAULT_USE_RSI = True
    
    # =========================================================================
    # 스토캐스틱 RSI 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_STOCH_RSI_PERIOD = 14
    DEFAULT_STOCH_K_PERIOD = 3
    DEFAULT_STOCH_D_PERIOD = 3
    DEFAULT_STOCH_UPPER = 80
    DEFAULT_STOCH_LOWER = 20
    DEFAULT_USE_STOCH_RSI = False
    
    # =========================================================================
    # MACD 설정
    # =========================================================================
    DEFAULT_MACD_FAST = 12
    DEFAULT_MACD_SLOW = 26
    DEFAULT_MACD_SIGNAL = 9
    DEFAULT_USE_MACD = True
    
    # =========================================================================
    # 볼린저 밴드 설정
    # =========================================================================
    DEFAULT_BB_PERIOD = 20
    DEFAULT_BB_STD = 2.0
    DEFAULT_USE_BB = False
    
    # =========================================================================
    # ATR 설정
    # =========================================================================
    DEFAULT_ATR_PERIOD = 14
    DEFAULT_ATR_MULTIPLIER = 2.0
    DEFAULT_USE_ATR = False
    DEFAULT_USE_ATR_STOP = False  # ATR 손절 (v4.3 신규)
    
    # =========================================================================
    # DMI/ADX 설정
    # =========================================================================
    DEFAULT_DMI_PERIOD = 14
    DEFAULT_ADX_THRESHOLD = 25
    DEFAULT_USE_DMI = False
    
    # =========================================================================
    # 거래량 설정
    # =========================================================================
    DEFAULT_VOLUME_MULTIPLIER = 1.5
    DEFAULT_VOLUME_PERIOD = 20
    DEFAULT_USE_VOLUME = True

    # =========================================================================
    # 유동성/스프레드 필터 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_LIQUIDITY = False
    DEFAULT_MIN_AVG_VALUE = 1_000_000_000  # 10억 (20일 평균 거래대금)
    DEFAULT_USE_SPREAD = False
    DEFAULT_MAX_SPREAD_PCT = 0.5
    
    # =========================================================================
    # 리스크 관리
    # =========================================================================
    DEFAULT_MAX_DAILY_LOSS = 3.0
    DEFAULT_MAX_HOLDINGS = 5
    DEFAULT_USE_RISK_MGMT = True
    
    # =========================================================================
    # 진입 점수 시스템 (v4.3 확장)
    # =========================================================================
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

    # =========================================================================
    # 실거래 보호 가드
    # =========================================================================
    LIVE_GUARD_ENABLED = True
    LIVE_GUARD_PHRASE = "실거래 시작"
    LIVE_GUARD_TIMEOUT_SEC = 15
    
    # =========================================================================
    # 단계별 익절 설정 (v4.3 확장)
    # =========================================================================
    PARTIAL_TAKE_PROFIT = [
        {'rate': 3.0, 'sell_ratio': 30},
        {'rate': 5.0, 'sell_ratio': 30},
        {'rate': 8.0, 'sell_ratio': 20},
    ]
    DEFAULT_USE_PARTIAL_PROFIT = False
    
    # =========================================================================
    # 갭 분석 설정 (v4.3 신규)
    # =========================================================================
    GAP_THRESHOLD = 2.0  # 갭 판단 기준 (%)
    DEFAULT_USE_GAP = False
    
    # =========================================================================
    # MTF 분석 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_MTF = False
    MTF_DAILY_PERIOD = 20
    MTF_MINUTE_PERIOD = 10
    
    # =========================================================================
    # 동적 포지션 사이징 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_DYNAMIC_SIZING = False
    DYNAMIC_SIZE_MIN_RATIO = 0.5  # 최소 축소율
    DYNAMIC_SIZE_MAX_RATIO = 1.5  # 최대 확대율
    
    # =========================================================================
    # 시장 분산 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_MARKET_LIMIT = False
    DEFAULT_MARKET_LIMIT = 70  # 한 시장 최대 비중 (%)
    
    # =========================================================================
    # 섹터 제한 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_SECTOR_LIMIT = False
    DEFAULT_SECTOR_LIMIT = 30  # 한 섹터 최대 비중 (%)
    
    # 섹터 코드 (참고용)
    SECTOR_CODES = {
        '음식료품': '001',
        '섬유의복': '002',
        '종이목재': '003',
        '화학': '004',
        '의약품': '005',
        '비금속광물': '006',
        '철강금속': '007',
        '기계': '008',
        '전기전자': '009',
        '의료정밀': '010',
        '운수장비': '011',
        '유통업': '012',
        '전기가스업': '013',
        '건설업': '014',
        '운수창고업': '015',
        '통신업': '016',
        '금융업': '017',
        '은행': '018',
        '증권': '019',
        '보험': '020',
        '서비스업': '021',
        '제조업': '022',
    }
    
    # =========================================================================
    # 이동평균 크로스오버 설정
    # =========================================================================
    DEFAULT_MA_SHORT = 5
    DEFAULT_MA_LONG = 20
    DEFAULT_USE_MA = False
    
    # =========================================================================
    # 시간대별 전략 설정
    # =========================================================================
    TIME_STRATEGY_AGGRESSIVE = {'start': '09:00', 'end': '09:30', 'k_mult': 1.4}
    TIME_STRATEGY_NORMAL = {'start': '09:30', 'end': '14:30', 'k_mult': 1.0}
    TIME_STRATEGY_CONSERVATIVE = {'start': '14:30', 'end': '15:20', 'k_mult': 0.6}
    DEFAULT_USE_TIME_STRATEGY = False
    
    # =========================================================================
    # 분할 주문 설정
    # =========================================================================
    DEFAULT_SPLIT_COUNT = 3
    DEFAULT_SPLIT_PERCENT = 0.5
    DEFAULT_USE_SPLIT = False

    # =========================================================================
    # 돌파 확인/쿨다운/시간청산 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_BREAKOUT_CONFIRM = False
    DEFAULT_BREAKOUT_TICKS = 3
    DEFAULT_USE_COOLDOWN = False
    DEFAULT_COOLDOWN_MINUTES = 10
    DEFAULT_USE_TIME_STOP = False
    DEFAULT_MAX_HOLD_MINUTES = 120
    
    # =========================================================================
    # ATR 포지션 사이징
    # =========================================================================
    DEFAULT_RISK_PERCENT = 1.0
    DEFAULT_USE_ATR_SIZING = False
    
    # =========================================================================
    # 사운드 알림 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_SOUND = False
    SOUND_USE_CUSTOM = False  # True: 커스텀 비프음, False: 시스템 사운드
    SOUND_EVENTS = {
        'buy': True,
        'sell': True,
        'profit': True,
        'loss': True,
        'error': True,
    }
    
    # =========================================================================
    # 다중 프로필 설정 (v4.3 신규)
    # =========================================================================
    PROFILES_DIR = "data"
    DEFAULT_PROFILE = None
    
    # =========================================================================
    # 테마 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_THEME = 'dark'  # 'dark' or 'light'
    
    # =========================================================================
    # 키보드 단축키 설정 (v4.3 신규)
    # =========================================================================
    SHORTCUTS = {
        'connect': 'Ctrl+L',
        'start_trading': 'Ctrl+S',
        'stop_trading': 'Ctrl+Q',
        'emergency_stop': 'Ctrl+Shift+X',
        'refresh': 'F5',
        'export_csv': 'Ctrl+E',
        'open_profile_manager': 'Ctrl+P',
        'open_presets': 'Ctrl+Shift+P',
        'toggle_theme': 'Ctrl+T',
        'show_help': 'F1',
        'search_stock': 'Ctrl+F',
        'manual_order': 'Ctrl+O',
    }
    
    # =========================================================================
    # 예약 매매 설정 (v4.3 신규)
    # =========================================================================
    DEFAULT_USE_SCHEDULE = False
    DEFAULT_SCHEDULE_START = '09:00'
    DEFAULT_SCHEDULE_END = '15:19'

    # =========================================================================
    # 시스템 설정 (v4.4 신규)
    # =========================================================================
    DEFAULT_AUTO_START = False
    DEFAULT_MINIMIZE_TO_TRAY = True
    
    # =========================================================================
    # 텔레그램 설정
    # =========================================================================
    DEFAULT_TELEGRAM_BOT_TOKEN = ""
    DEFAULT_TELEGRAM_CHAT_ID = ""
    DEFAULT_USE_TELEGRAM = False
    
    # =========================================================================
    # 시간 설정
    # =========================================================================
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 19
    NO_ENTRY_HOUR = 15
    
    # =========================================================================
    # 파일 경로
    # =========================================================================
    BASE_DIR = str(_BASE_PATH)
    DATA_DIR = str(_BASE_PATH / "data")
    SETTINGS_FILE = str(_BASE_PATH / "kiwoom_settings.json")
    PRESETS_FILE = str(_BASE_PATH / "kiwoom_presets.json")
    TRADE_HISTORY_FILE = str(_BASE_PATH / "kiwoom_trade_history.json")
    LOG_DIR = str(_BASE_PATH / "logs")
    
    # =========================================================================
    # 메모리 관리
    # =========================================================================
    MAX_LOG_LINES = 500
    MAX_PRICE_HISTORY = 100
    UI_REFRESH_INTERVAL_MS = 100
    DECISION_CACHE_MS = 100
    POSITION_SYNC_DEBOUNCE_MS = 200
    POSITION_SYNC_MAX_RETRIES = 5
    POSITION_SYNC_BACKOFF_MAX_MS = 5000
    LOG_DEDUP_SEC = 30
    TABLE_BATCH_LIMIT = 200
    ORDER_REJECT_COOLDOWN_SEC = 10
    
    # =========================================================================
    # 기본 프리셋 정의
    # =========================================================================
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
        },
        "scalping": {
            "name": "⚡ 스캘핑",
            "description": "빠른 진입/청산, 소량 다회전",
            "k": 0.3, "ts_start": 1.5, "ts_stop": 0.8, "loss": 1.0,
            "betting": 5.0, "rsi_upper": 65, "max_holdings": 3
        }
    }
    
    # =========================================================================
    # 툴팁 설명
    # =========================================================================
    TOOLTIPS = {
        "codes": "감시할 종목 코드를 콤마(,)로 구분하여 입력합니다.\n예: 005930,000660,042700",
        "betting": "총 예수금 대비 종목당 투자 비율입니다.\n권장: 5% ~ 20%",
        "k_value": "변동성 돌파 전략의 K 계수\n목표가 = 시가 + (전일 변동폭 × K값)\n권장: 0.3 ~ 0.5",
        "ts_start": "트레일링 스톱 발동 수익률\n권장: 3% ~ 10%",
        "ts_stop": "고점 대비 하락 허용폭\n권장: 1% ~ 3%",
        "loss_cut": "절대 손절 기준\n권장: 2% ~ 5%",
        "rsi": "과매수 판단 기준 RSI\n권장: 65 ~ 75",
        "max_holdings": "동시 보유 가능 최대 종목 수\n권장: 3 ~ 7개",
        "stoch_rsi": "스토캐스틱 RSI - RSI의 스토캐스틱\n과매수/과매도를 더 민감하게 감지",
        "mtf": "다중 시간프레임 - 일봉과 분봉 추세 일치시 진입",
        "gap": "갭 분석 - 갭 상승/하락에 따라 K값 조정",
        "dynamic_sizing": "동적 사이징 - 연속 손실시 투자금 축소",
        "atr_stop": "ATR 손절 - 변동성 기반 동적 손절선",
        "liquidity": "유동성 필터 - 20일 평균 거래대금 기준",
        "spread": "스프레드 필터 - 호가 스프레드가 낮을 때만 진입",
        "breakout_confirm": "돌파 확인 - 목표가 돌파 후 N틱 유지 시 진입",
        "cooldown": "쿨다운 - 매도 후 일정 시간 재진입 제한",
        "time_stop": "시간 청산 - 보유 시간이 기준을 넘으면 청산",
    }
    
    # =========================================================================
    # 도움말 콘텐츠
    # =========================================================================
    HELP_CONTENT = {
        "quick_start": """
## 🚀 빠른 시작 가이드

### 1단계: API 설정
1. 키움증권 REST API 신청
2. App Key / Secret Key 입력
3. API 연결 버튼 클릭

### 2단계: 종목 선택
- 종목 코드를 콤마로 구분하여 입력
- 또는 조건검색 결과 적용
- 즐겨찾기 저장/불러오기 활용

### 3단계: 전략 선택
- 초보자: **보수적** 프리셋 권장
- 경험자: **표준** 프리셋으로 시작
- 고급: 직접 파라미터 조정

### 4단계: 매매 시작
"🚀 매매 시작" 버튼 클릭

### ⌨️ 단축키
- Ctrl+S: 매매 시작
- Ctrl+Q: 매매 중지
- Ctrl+Shift+X: 긴급 청산
- Ctrl+P: 프로필 관리
- Ctrl+Shift+P: 프리셋 관리
- F5: 새로고침
        """,
        "strategy": """
## 📈 전략 설명

### 기본 전략: 변동성 돌파
- 목표가 = 시가 + (전일 변동폭 × K값)
- 현재가가 목표가 돌파 시 매수

### 보조 지표
- **RSI (14)**: 과매수(70+) 시 진입 보류
- **MACD**: 골든크로스 확인
- **볼린저밴드**: 하단 이탈 시 진입
- **스토캐스틱 RSI**: 더 민감한 과매수/과매도 감지

### 리스크 관리
- **트레일링 스톱**: 고점 추적 청산
- **ATR 손절**: 변동성 기반 동적 손절
- **동적 사이징**: 연속손실 시 투자금 축소
- **섹터 분산**: 동일 업종 과집중 방지

### 진입 점수 시스템
여러 지표를 종합하여 점수화 (60점 이상 진입)
        """,
        "faq": """
## ❓ 자주 묻는 질문

**Q: 15시 이후에도 매수가 되나요?**
A: 아니요, 15시 이후에는 신규 매수가 중지됩니다.

**Q: 손실이 발생하면 어떻게 되나요?**
A: 설정된 손절률 또는 ATR 손절에 따라 자동으로 매도됩니다.

**Q: 긴급 청산은 어떻게 하나요?**
A: 🚨 긴급청산 버튼 또는 Ctrl+Shift+X 단축키

**Q: 프로필은 어떻게 저장하나요?**
A: 도구 메뉴 > 프로필 관리에서 저장/불러오기

**Q: 테마 변경은 어떻게 하나요?**
A: 보기 메뉴 > 테마 전환 또는 Ctrl+T
        """
    }

    SETTINGS_SCHEMA_VERSION = 3
    # =========================================================================
    # 전략팩/백테스트/실행 정책 (v5.0)
    # =========================================================================
    DEFAULT_STRATEGY_PACK = {
        "primary_strategy": "volatility_breakout",
        "entry_filters": ["rsi", "volume", "macd"],
        "exit_overlays": ["trailing_stop", "atr_stop"],
        "risk_overlays": ["max_holdings", "daily_loss_limit"],
    }
    DEFAULT_STRATEGY_PARAMS: Dict[str, Any] = {}
    DEFAULT_PORTFOLIO_MODE = "single_strategy"
    DEFAULT_SHORT_ENABLED = False
    DEFAULT_ASSET_SCOPE = "kr_stock_live"
    DEFAULT_BACKTEST_CONFIG = {
        "timeframe": "1d",
        "lookback_days": 365,
        "commission_bps": 5.0,
        "slippage_bps": 3.0,
    }
    FEATURE_FLAGS = {
        "use_modular_strategy_pack": True,
        "enable_backtest": True,
        "enable_external_data": True,
    }
    DEFAULT_EXECUTION_POLICY = "market"
