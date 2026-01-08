"""
키움증권 REST API 데이터 모델

API 응답 및 요청에 사용되는 데이터 구조를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class OrderType(Enum):
    """주문 유형"""
    BUY = "1"           # 신규 매수
    SELL = "2"          # 신규 매도
    BUY_CANCEL = "3"    # 매수 취소
    SELL_CANCEL = "4"   # 매도 취소
    BUY_MODIFY = "5"    # 매수 정정
    SELL_MODIFY = "6"   # 매도 정정


class PriceType(Enum):
    """호가 유형"""
    LIMIT = "00"        # 지정가
    MARKET = "03"       # 시장가
    CONDITIONAL = "05"  # 조건부지정가
    BEST = "06"         # 최유리지정가
    PRIORITY = "07"     # 최우선지정가
    AFTER_MARKET = "61" # 장후시간외종가


class MarketType(Enum):
    """시장 구분"""
    KOSPI = "1"
    KOSDAQ = "2"


@dataclass
class StockQuote:
    """주식 시세 정보"""
    code: str                    # 종목코드
    name: str = ""               # 종목명
    current_price: int = 0       # 현재가
    change: int = 0              # 전일대비
    change_rate: float = 0.0     # 등락률 (%)
    open_price: int = 0          # 시가
    high_price: int = 0          # 고가
    low_price: int = 0           # 저가
    volume: int = 0              # 거래량
    volume_amount: int = 0       # 거래대금
    prev_close: int = 0          # 전일종가
    ask_price: int = 0           # 매도호가 (최우선)
    bid_price: int = 0           # 매수호가 (최우선)
    timestamp: str = ""          # 체결시각


@dataclass
class OrderBook:
    """호가 정보"""
    code: str
    ask_prices: List[int] = field(default_factory=list)   # 매도호가 (1~10)
    ask_volumes: List[int] = field(default_factory=list)  # 매도호가수량
    bid_prices: List[int] = field(default_factory=list)   # 매수호가 (1~10)
    bid_volumes: List[int] = field(default_factory=list)  # 매수호가수량
    total_ask_volume: int = 0    # 총 매도잔량
    total_bid_volume: int = 0    # 총 매수잔량
    timestamp: str = ""


@dataclass
class AccountInfo:
    """계좌 정보"""
    account_no: str              # 계좌번호
    deposit: int = 0             # 예수금
    available_amount: int = 0    # 주문가능금액
    total_buy_amount: int = 0    # 총매입금액
    total_eval_amount: int = 0   # 총평가금액
    total_profit: int = 0        # 총평가손익
    total_profit_rate: float = 0.0  # 총수익률 (%)


@dataclass
class Position:
    """보유 종목"""
    code: str                    # 종목코드
    name: str = ""               # 종목명
    quantity: int = 0            # 보유수량
    available_qty: int = 0       # 매도가능수량
    buy_price: int = 0           # 매입단가
    current_price: int = 0       # 현재가
    buy_amount: int = 0          # 매입금액
    eval_amount: int = 0         # 평가금액
    profit: int = 0              # 평가손익
    profit_rate: float = 0.0     # 수익률 (%)


@dataclass
class OrderResult:
    """주문 결과"""
    success: bool
    order_no: str = ""           # 주문번호
    code: str = ""               # 종목코드
    order_type: str = ""         # 주문유형
    quantity: int = 0            # 주문수량
    price: int = 0               # 주문가격
    message: str = ""            # 결과 메시지
    error_code: int = 0          # 오류 코드


@dataclass
class ExecutionData:
    """체결 데이터 (실시간)"""
    code: str                    # 종목코드
    name: str = ""               # 종목명
    exec_time: str = ""          # 체결시각
    exec_price: int = 0          # 체결가
    exec_volume: int = 0         # 체결수량
    exec_change: int = 0         # 전일대비
    total_volume: int = 0        # 누적거래량
    ask_price: int = 0           # 매도호가
    bid_price: int = 0           # 매수호가


@dataclass  
class DailyOHLC:
    """일봉 데이터"""
    date: str                    # 일자 (YYYYMMDD)
    open_price: int = 0          # 시가
    high_price: int = 0          # 고가
    low_price: int = 0           # 저가
    close_price: int = 0         # 종가
    volume: int = 0              # 거래량
    volume_amount: int = 0       # 거래대금
