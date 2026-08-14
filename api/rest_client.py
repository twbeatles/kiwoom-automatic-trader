"""
키움증권 REST API 클라이언트

시세 조회, 계좌 조회, 주문 등 REST API 호출을 담당합니다.
"""

import logging
import time
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import KiwoomAuth
from .endpoints import LIVE_REST_BASE_URL
from .models import (
    StockQuote, OrderBook, AccountInfo, Position, 
    OrderResult, DailyOHLC, OpenOrder, OrderType, PriceType,
    DepositDetail, ExecutedOrder, TickCandle, SectorQuote, VIEvent
)


def _safe_int(value: Any, default: int = 0, *, absolute: bool = False) -> int:
    try:
        if value is None:
            return default
        text = str(value).strip().replace(",", "")
        if text in {"", "-", "+", "--"}:
            return default
        result = int(float(text))
        return abs(result) if absolute else result
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip().replace(",", "").replace("%", "")
        if text in {"", "-", "+", "--"}:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


class KiwoomRESTClient:
    """키움증권 REST API 클라이언트"""
    
    BASE_URL = LIVE_REST_BASE_URL
    
    # TR 코드 정의
    TR_CODES = {
        # 시세 조회
        "STOCK_CURRENT": "ka10001",      # 주식기본정보요청/현재가
        "STOCK_HOGA": "ka10004",         # 주식호가요청
        "STOCK_DAILY": "ka10005",        # 일봉차트
        "STOCK_MINUTE": "ka10006",       # 분봉차트
        "STOCK_TICK": "ka10007",         # 틱차트
        "STOCK_WEEKLY": "ka10008",       # 주봉/월봉차트
        "SECTOR_INDEX": "ka10010",       # 업종지수차트/시세
        
        # 계좌 조회
        "ACCOUNT_BALANCE": "ka30001",    # 계좌평가잔고
        "ACCOUNT_DEPOSIT": "ka30002",    # 예수금상세
        "ACCOUNT_LIST": "ka30003",       # 계좌목록조회
        
        # 주문 (키움 REST 국내주식 주문 표준 api-id)
        "ORDER_BUY": "kt10000",          # 주식매수주문
        "ORDER_SELL": "kt10001",         # 주식매도주문
        "ORDER_MODIFY": "kt10002",       # 주식정정주문
        "ORDER_CANCEL": "kt10003",       # 주식취소주문
        "ORDER_STOCK": "kt10000",        # 호환용 매수 alias
        
        # 순위/기타
        "RANK_VOLUME": "ka20001",        # 거래량상위
        "RANK_FLUCTUATION": "ka20002",   # 등락률상위
        "CONDITION_LIST": "ka20003",     # 조건식목록
        "CONDITION_SEARCH": "ka20004",   # 조건검색
        "INVESTOR_TRADING": "ka20005",   # 투자자별매매동향
        "PROGRAM_TRADING": "ka20006",    # 프로그램매매동향
        "MARKET_STATUS": "ka20007",      # 시장운영정보
        "INDEX_QUOTE": "ka20008",        # 지수현재가
        "VI_STATUS": "ka20009",          # VI발동현황

        # 미체결 / 체결
        "ORDER_OPEN": "ka10075",         # 미체결주문조회
        "ORDER_EXECUTED": "ka10076",     # 당일체결주문조회
    }
    
    def __init__(self, auth: KiwoomAuth, base_url: Optional[str] = None):
        """
        Args:
            auth: KiwoomAuth 인스턴스 (인증 관리)
        """
        self.auth = auth
        self.logger = logging.getLogger('KiwoomRESTClient')
        self.base_url = str(base_url or getattr(auth, "base_url", self.BASE_URL) or self.BASE_URL).rstrip("/")
        self.session_namespace = str(getattr(auth, "session_namespace", "kiwoom_live") or "kiwoom_live")
        
        # 요청 세션 설정 (재시도 로직 포함)
        self.session = self._create_session()
        
        # 요청 속도 제한 (1초에 최대 5건)
        self._last_request_time = 0
        self._min_request_interval = 0.2  # 200ms
        self._lock = threading.Lock()
        
    def _create_session(self) -> requests.Session:
        """재시도 로직이 포함된 세션 생성"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        return session
    
    def _rate_limit(self):
        """요청 속도 제한 (Thread-Safe)"""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()
    
    def _request(self, method: str, endpoint: str, 
                 tr_code: Optional[str] = None,
                 data: Optional[Dict] = None,
                 params: Optional[Dict] = None,
                 cont_yn: str = "N",
                 next_key: str = "") -> Optional[Dict]:
        """
        API 요청 수행 (키움 필수 헤더 api-id 포함)
        
        Args:
            method: HTTP 메서드 (GET/POST)
            endpoint: API 엔드포인트 경로
            tr_code: 키움 TR 코드 (헤더 api-id로 전송)
            data: POST 바디 데이터
            params: 쿼리 파라미터
            cont_yn: 연속조회 여부 ('Y'/'N')
            next_key: 연속조회 키
            
        Returns:
            응답 JSON 딕셔너리, 실패 시 None
        """
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            **self.auth.get_auth_header(),
            "cont-yn": str(cont_yn or "N"),
        }
        if tr_code:
            headers["api-id"] = str(tr_code)
        if next_key:
            headers["next-key"] = str(next_key)
        
        if not headers.get("Authorization"):
            self.logger.error("인증 토큰이 없습니다. 먼저 로그인해주세요.")
            return None
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, params=params, timeout=10)
            else:
                response = self.session.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # 키움 API 응답 코드 확인
                return_code = result.get("return_code", 0)
                if return_code != 0:
                    error_msg = result.get("return_msg", "알 수 없는 오류")
                    self.logger.warning(f"API 오류 ({return_code}): {error_msg}")
                
                return result
            else:
                self.logger.error(f"HTTP 오류: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"네트워크 오류: {e}")
            return None
        except Exception as e:
            self.logger.error(f"요청 예외: {e}")
            return None

    def _parse_market_type(self, output: Dict) -> str:
        """시장 구분 파싱"""
        mkt_gb = output.get("mkt_gb", "")
        if mkt_gb == "1":
            return "KOSPI"
        elif mkt_gb == "2":
            return "KOSDAQ"
        return "unknown"

    # =========================================================================
    # 시세 조회 API
    # =========================================================================
    
    def get_stock_quote(self, code: str) -> Optional[StockQuote]:
        """
        주식 현재가 조회
        
        Args:
            code: 종목코드 (예: "005930")
            
        Returns:
            StockQuote 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["STOCK_CURRENT"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/stkprice", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            return StockQuote(
                code=code,
                name=output.get("stk_nm", ""),
                current_price=_safe_int(output.get("cur_prc", 0), absolute=True),
                change=_safe_int(output.get("chg_amt", 0)),
                change_rate=_safe_float(output.get("chg_rt", 0)),
                open_price=_safe_int(output.get("open_prc", 0), absolute=True),
                high_price=_safe_int(output.get("high_prc", 0), absolute=True),
                low_price=_safe_int(output.get("low_prc", 0), absolute=True),
                volume=_safe_int(output.get("acc_vol", 0)),
                prev_close=_safe_int(output.get("yes_prc", 0), absolute=True),
                ask_price=_safe_int(output.get("ask_prc", 0), absolute=True),
                bid_price=_safe_int(output.get("bid_prc", 0), absolute=True),
                timestamp=output.get("stk_tm", ""),
                market_type=self._parse_market_type(output),
                sector=output.get("sect_nm", "기타")  # sect_nm이 없으면 '기타'
            )
        
        return None
    
    def get_order_book(self, code: str) -> Optional[OrderBook]:
        """
        호가 정보 조회
        
        Args:
            code: 종목코드
            
        Returns:
            OrderBook 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["STOCK_HOGA"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/stkhoga", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []
            
            for i in range(1, 11):
                ask_prices.append(_safe_int(output.get(f"ask_prc{i}", 0), absolute=True))
                ask_volumes.append(_safe_int(output.get(f"ask_vol{i}", 0)))
                bid_prices.append(_safe_int(output.get(f"bid_prc{i}", 0), absolute=True))
                bid_volumes.append(_safe_int(output.get(f"bid_vol{i}", 0)))
            
            return OrderBook(
                code=code,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                total_ask_volume=_safe_int(output.get("tot_ask_vol", 0)),
                total_bid_volume=_safe_int(output.get("tot_bid_vol", 0)),
                timestamp=output.get("stk_tm", "")
            )
        
        return None
    
    def get_daily_chart(self, code: str, count: int = 60) -> List[DailyOHLC]:
        """
        일봉 차트 데이터 조회
        
        Args:
            code: 종목코드
            count: 조회할 봉 개수 (최대 100)
            
        Returns:
            DailyOHLC 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_DAILY"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkdaily", tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("date", ""),
                    open_price=_safe_int(item.get("open_prc", 0), absolute=True),
                    high_price=_safe_int(item.get("high_prc", 0), absolute=True),
                    low_price=_safe_int(item.get("low_prc", 0), absolute=True),
                    close_price=_safe_int(item.get("close_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", 0))
                ))
        
        return candles
    
    # =========================================================================
    # 계좌 조회 API
    # =========================================================================
    
    def get_account_info(self, account_no: str) -> Optional[AccountInfo]:
        """
        계좌 평가 정보 조회
        
        Args:
            account_no: 계좌번호
            
        Returns:
            AccountInfo 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["ACCOUNT_BALANCE"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntbal", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            return AccountInfo(
                account_no=account_no,
                deposit=_safe_int(output.get("deposit", 0)),
                available_amount=_safe_int(output.get("ord_psbl_amt", 0)),
                total_buy_amount=_safe_int(output.get("tot_buy_amt", 0)),
                total_eval_amount=_safe_int(output.get("tot_eval_amt", 0)),
                total_profit=_safe_int(output.get("tot_eval_pl", 0)),
                total_profit_rate=_safe_float(output.get("tot_eval_pl_rt", 0))
            )
        
        return None
    
    def get_positions(self, account_no: str) -> Optional[List[Position]]:
        """
        보유 종목 조회
        
        Args:
            account_no: 계좌번호
            
        Returns:
            Position 리스트
        """
        tr_code = self.TR_CODES["ACCOUNT_BALANCE"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntbal", tr_code=tr_code, data=data)
        
        if not result:
            return None
        if result.get("return_code") != 0:
            return None

        positions = []
        stocks = result.get("stocks", [])

        for item in stocks:
            positions.append(Position(
                code=item.get("stk_cd", ""),
                name=item.get("stk_nm", ""),
                quantity=_safe_int(item.get("hold_qty", 0)),
                available_qty=_safe_int(item.get("sell_psbl_qty", 0)),
                buy_price=_safe_int(item.get("buy_prc", 0)),
                current_price=_safe_int(item.get("cur_prc", 0), absolute=True),
                buy_amount=_safe_int(item.get("buy_amt", 0)),
                eval_amount=_safe_int(item.get("eval_amt", 0)),
                profit=_safe_int(item.get("eval_pl", 0)),
                profit_rate=_safe_float(item.get("eval_pl_rt", 0))
            ))

        return positions

    @property
    def supports_open_orders(self) -> bool:
        return True

    def get_open_orders(self, account_no: str) -> List[OpenOrder]:
        """미체결 주문 조회.

        키움 REST TR `ka10075`(미체결요청) 기반.
        여러 필드명 후보를 허용하고 실패 시 빈 리스트를 반환하여 안전하게 동작하도록 한다.
        """
        tr_code = self.TR_CODES["ORDER_OPEN"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
        }

        try:
            result = self._request("POST", "/api/dostk/ordunfilled", tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"미체결 주문 조회 예외: {exc}")
            return []

        if not result or result.get("return_code") != 0:
            return []

        rows = result.get("output", [])
        if not isinstance(rows, list):
            # 단건 응답인 경우 단일 dict를 리스트로 정규화
            if isinstance(rows, dict):
                rows = [rows]
            else:
                return []

        orders: List[OpenOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            try:
                order_no = str(item.get("ord_no") or item.get("org_ord_no") or "").strip()
                code = str(item.get("stk_cd") or "").strip()
                if not order_no or not code:
                    continue
                raw_side = str(item.get("ord_tp") or item.get("bs_tp") or "").strip()
                side = "buy" if raw_side == "1" else ("sell" if raw_side == "2" else raw_side)
                orders.append(
                    OpenOrder(
                        order_no=order_no,
                        code=code,
                        side=side,
                        quantity=_safe_int(item.get("ord_qty", 0)),
                        remaining_qty=_safe_int(
                            item.get("unexec_qty", item.get("not_cncl_qty", item.get("rmn_qty", 0)))
                        ),
                        price=_safe_int(item.get("ord_prc", 0), absolute=True),
                        status=str(item.get("ord_st") or item.get("cnf_tp") or "").strip(),
                    )
                )
            except Exception as exc:
                self.logger.warning(f"미체결 주문 파싱 실패(건 건너뜀): {exc}")
                continue

        return orders
    
    # =========================================================================
    # 주문 API
    # =========================================================================
    
    def send_order(self, 
                   account_no: str,
                   code: str,
                   order_type: OrderType,
                   quantity: int,
                   price: int = 0,
                   price_type: PriceType = PriceType.LIMIT) -> OrderResult:
        """
        주식 주문 전송 (키움 공식 주문 엔드포인트 POST /api/dostk/ordr)
        
        Args:
            account_no: 계좌번호
            code: 종목코드
            order_type: 주문유형 (매수/매도)
            quantity: 주문수량
            price: 주문가격 (시장가 주문 시 0)
            price_type: 호가유형 (지정가/시장가 등)
            
        Returns:
            OrderResult 객체
        """
        tr_code = self.TR_CODES["ORDER_BUY"] if order_type == OrderType.BUY else self.TR_CODES["ORDER_SELL"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "stk_cd": code,
            "ord_tp": order_type.value,
            "ord_qty": quantity,
            "ord_prc": price if price_type == PriceType.LIMIT else 0,
            "prc_tp": price_type.value
        }
        
        result = self._request("POST", "/api/dostk/ordr", tr_code=tr_code, data=data)
        
        if result:
            return_code = result.get("return_code", -1)
            
            if return_code == 0:
                output = result.get("output", {})
                return OrderResult(
                    success=True,
                    order_no=output.get("ord_no", ""),
                    code=code,
                    order_type=order_type.value,
                    quantity=quantity,
                    price=price,
                    message="주문 전송 성공"
                )
            else:
                return OrderResult(
                    success=False,
                    code=code,
                    order_type=order_type.value,
                    quantity=quantity,
                    price=price,
                    message=result.get("return_msg", "주문 실패"),
                    error_code=return_code
                )
        
        return OrderResult(
            success=False,
            code=code,
            message="네트워크 오류",
            error_code=-1
        )
    
    def buy_market(self, account_no: str, code: str, quantity: int) -> OrderResult:
        """시장가 매수"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.BUY,
            quantity=quantity,
            price=0,
            price_type=PriceType.MARKET
        )
    
    def sell_market(self, account_no: str, code: str, quantity: int) -> OrderResult:
        """시장가 매도"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.SELL,
            quantity=quantity,
            price=0,
            price_type=PriceType.MARKET
        )
    
    def buy_limit(self, account_no: str, code: str, quantity: int, price: int) -> OrderResult:
        """지정가 매수"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.BUY,
            quantity=quantity,
            price=price,
            price_type=PriceType.LIMIT
        )
    
    def sell_limit(self, account_no: str, code: str, quantity: int, price: int) -> OrderResult:
        """지정가 매도"""
        return self.send_order(
            account_no=account_no,
            code=code,
            order_type=OrderType.SELL,
            quantity=quantity,
            price=price,
            price_type=PriceType.LIMIT
        )
    
    def cancel_order(self, account_no: str, order_no: str, code: str, quantity: int) -> OrderResult:
        """주문 취소 (키움 공식 주문 엔드포인트 POST /api/dostk/ordr)"""
        tr_code = self.TR_CODES["ORDER_CANCEL"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "org_ord_no": order_no,
            "stk_cd": code,
            "ord_qty": quantity
        }
        
        result = self._request("POST", "/api/dostk/ordr", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            return OrderResult(
                success=True,
                order_no=order_no,
                code=code,
                message="주문 취소 성공"
            )
        
        return OrderResult(
            success=False,
            order_no=order_no,
            code=code,
            message=result.get("return_msg", "취소 실패") if result else "네트워크 오류"
        )
    
    def modify_order(self, account_no: str, order_no: str, code: str, quantity: int, price: int, price_type: PriceType = PriceType.LIMIT) -> OrderResult:
        """주문 정정 (키움 공식 주문 엔드포인트 POST /api/dostk/ordr)"""
        tr_code = self.TR_CODES["ORDER_MODIFY"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "org_ord_no": order_no,
            "stk_cd": code,
            "ord_qty": quantity,
            "ord_prc": price,
            "prc_tp": price_type.value
        }
        
        result = self._request("POST", "/api/dostk/ordr", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            return OrderResult(
                success=True,
                order_no=order_no,
                code=code,
                quantity=quantity,
                price=price,
                message="주문 정정 성공"
            )
        
        return OrderResult(
            success=False,
            order_no=order_no,
            code=code,
            quantity=quantity,
            price=price,
            message=result.get("return_msg", "정정 실패") if result else "네트워크 오류"
        )
    
    # =========================================================================
    # 유틸리티
    # =========================================================================
    
    def get_account_list(self) -> List[str]:
        """
        계좌 목록 조회
        
        Returns:
            계좌번호 리스트
        """
        tr_code = self.TR_CODES["ACCOUNT_LIST"]
        result = self._request("POST", "/api/dostk/acntlist", tr_code=tr_code, data={})
        
        if result and result.get("return_code") == 0:
            return result.get("accounts", [])
        
        return []
    
    def get_stock_name(self, code: str) -> str:
        """종목명 조회"""
        quote = self.get_stock_quote(code)
        return quote.name if quote else ""
    
    # =========================================================================
    # 차트 API 확장
    # =========================================================================
    
    def get_minute_chart(self, code: str, interval: int = 1, count: int = 60) -> List[DailyOHLC]:
        """
        분봉 차트 데이터 조회
        
        Args:
            code: 종목코드
            interval: 분봉 간격 (1, 3, 5, 10, 15, 30, 60)
            count: 조회할 봉 개수 (최대 100)
            
        Returns:
            DailyOHLC 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_MINUTE"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code,
            "interval": interval,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkminute", tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("datetime", ""),
                    open_price=_safe_int(item.get("open_prc", 0), absolute=True),
                    high_price=_safe_int(item.get("high_prc", 0), absolute=True),
                    low_price=_safe_int(item.get("low_prc", 0), absolute=True),
                    close_price=_safe_int(item.get("close_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", 0))
                ))
        
        return candles
    
    def get_weekly_chart(self, code: str, count: int = 52) -> List[DailyOHLC]:
        """주봉 차트 데이터 조회"""
        tr_code = self.TR_CODES["STOCK_WEEKLY"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkweekly", tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("date", ""),
                    open_price=_safe_int(item.get("open_prc", 0), absolute=True),
                    high_price=_safe_int(item.get("high_prc", 0), absolute=True),
                    low_price=_safe_int(item.get("low_prc", 0), absolute=True),
                    close_price=_safe_int(item.get("close_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", 0))
                ))
        
        return candles
    
    # =========================================================================
    # 조건검색 API
    # =========================================================================
    
    def get_condition_list(self) -> List[Dict[str, Any]]:
        """
        조건검색식 목록 조회
        
        Returns:
            [{"index": 0, "name": "조건식명"}, ...]
        """
        tr_code = self.TR_CODES["CONDITION_LIST"]
        result = self._request("POST", "/api/dostk/condition/list", tr_code=tr_code, data={})
        
        conditions = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                conditions.append({
                    "index": _safe_int(item.get("cond_idx", 0)),
                    "name": item.get("cond_nm", "")
                })
        
        return conditions
    
    def search_by_condition(self, condition_index: int, condition_name: str = "") -> List[Dict[str, Any]]:
        """
        조건검색 실행
        
        Args:
            condition_index: 조건식 인덱스
            condition_name: 조건식 이름 (옵션)
            
        Returns:
            [{"code": "종목코드", "name": "종목명"}, ...]
        """
        tr_code = self.TR_CODES["CONDITION_SEARCH"]
        data = {
            "cond_idx": condition_index,
            "cond_nm": condition_name
        }
        
        result = self._request("POST", "/api/dostk/condition/search", tr_code=tr_code, data=data)
        
        stocks = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                stocks.append({
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": _safe_int(item.get("cur_prc", 0), absolute=True),
                    "change_rate": _safe_float(item.get("chg_rt", 0)),
                    "volume": _safe_int(item.get("vol", 0))
                })
        
        return stocks
    
    # =========================================================================
    # 순위 정보 API
    # =========================================================================
    
    def get_volume_ranking(self, market: str = "0", count: int = 30) -> List[Dict[str, Any]]:
        """
        거래량 상위 종목 조회
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            count: 조회 개수
            
        Returns:
            거래량 순위 리스트
        """
        tr_code = self.TR_CODES["RANK_VOLUME"]
        data = {
            "tr_cd": tr_code,
            "mkt_tp": market,
            "req_cnt": min(count, 50)
        }
        
        result = self._request("POST", "/api/dostk/ranking/volume", tr_code=tr_code, data=data)
        
        rankings = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for i, item in enumerate(output_list):
                rankings.append({
                    "rank": i + 1,
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": _safe_int(item.get("cur_prc", 0), absolute=True),
                    "change_rate": _safe_float(item.get("chg_rt", 0)),
                    "volume": _safe_int(item.get("vol", 0)),
                    "volume_rate": _safe_float(item.get("vol_rt", 0))
                })
        
        return rankings
    
    def get_fluctuation_ranking(self, market: str = "0", sort_type: str = "1", count: int = 30) -> List[Dict[str, Any]]:
        """
        등락률 상위 종목 조회
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            sort_type: "1"=상승률, "2"=하락률
            count: 조회 개수
            
        Returns:
            등락률 순위 리스트
        """
        tr_code = self.TR_CODES["RANK_FLUCTUATION"]
        data = {
            "tr_cd": tr_code,
            "mkt_tp": market,
            "sort_tp": sort_type,
            "req_cnt": min(count, 50)
        }
        
        result = self._request("POST", "/api/dostk/ranking/fluctuation", tr_code=tr_code, data=data)
        
        rankings = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for i, item in enumerate(output_list):
                rankings.append({
                    "rank": i + 1,
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": _safe_int(item.get("cur_prc", 0), absolute=True),
                    "change": _safe_int(item.get("chg_amt", 0)),
                    "change_rate": _safe_float(item.get("chg_rt", 0)),
                    "volume": _safe_int(item.get("vol", 0))
                })
        
        return rankings
    
    def get_investor_trading(self, code: str) -> Dict[str, Any]:
        """
        투자자별 매매 동향 조회
        
        Args:
            code: 종목코드
            
        Returns:
            투자자별 순매수량/금액
        """
        tr_code = self.TR_CODES["INVESTOR_TRADING"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/investor", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return {
                "code": code,
                "individual_buy": _safe_int(output.get("indv_buy", 0)),
                "individual_sell": _safe_int(output.get("indv_sell", 0)),
                "foreign_buy": _safe_int(output.get("frgn_buy", 0)),
                "foreign_sell": _safe_int(output.get("frgn_sell", 0)),
                "institution_buy": _safe_int(output.get("inst_buy", 0)),
                "institution_sell": _safe_int(output.get("inst_sell", 0)),
                "individual_net": _safe_int(output.get("indv_net", 0)),
                "foreign_net": _safe_int(output.get("frgn_net", 0)),
                "institution_net": _safe_int(output.get("inst_net", 0))
            }
        
        return {}
    
    def get_program_trading(self, code: str) -> Dict[str, Any]:
        """
        프로그램 매매 동향 조회
        
        Args:
            code: 종목코드
            
        Returns:
            프로그램 순매수량/금액
        """
        tr_code = self.TR_CODES["PROGRAM_TRADING"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/program", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return {
                "code": code,
                "arb_buy": _safe_int(output.get("arb_buy", 0)),
                "arb_sell": _safe_int(output.get("arb_sell", 0)),
                "nonarb_buy": _safe_int(output.get("nonarb_buy", 0)),
                "nonarb_sell": _safe_int(output.get("nonarb_sell", 0)),
                "total_buy": _safe_int(output.get("tot_buy", 0)),
                "total_sell": _safe_int(output.get("tot_sell", 0)),
                "net": _safe_int(output.get("net", 0))
            }
        
        return {}

    # =========================================================================
    # 시장 상태/지수 API (v4 확장)
    # =========================================================================

    def get_market_status(self) -> Dict[str, Any]:
        """시장 상태 조회 (지원 시). 지원되지 않으면 빈 dict 반환."""
        tr_code = self.TR_CODES["MARKET_STATUS"]
        result = self._request("POST", "/api/dostk/market/status", tr_code=tr_code, data={})
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            if isinstance(output, dict):
                return output
        return {}

    def get_index_quote(self, index_code: str) -> Dict[str, Any]:
        """지수 시세 조회 (지원 시). 지원되지 않으면 빈 dict 반환."""
        if not index_code:
            return {}
        tr_code = self.TR_CODES["INDEX_QUOTE"]
        data = {"idx_cd": index_code}
        result = self._request("POST", "/api/dostk/index/quote", tr_code=tr_code, data=data)
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            if isinstance(output, dict):
                return output
        return {}

    def get_market_indexes(self) -> List[SectorQuote]:
        """
        주요 시장 지수 시세 조회 (코스피: 001, 코스닥: 101, 코스피200: 201)
        
        Returns:
            SectorQuote 리스트
        """
        major_indexes = [
            ("001", "코스피"),
            ("101", "코스닥"),
            ("201", "코스피200"),
        ]
        quotes: List[SectorQuote] = []
        for idx_cd, name in major_indexes:
            try:
                res = self.get_index_quote(idx_cd)
                if res:
                    quotes.append(SectorQuote(
                        code=idx_cd,
                        name=res.get("idx_nm", name),
                        current_price=_safe_float(res.get("cur_idx", 0.0)),
                        change=_safe_float(res.get("chg_idx", 0.0)),
                        change_rate=_safe_float(res.get("chg_rt", 0.0)),
                        open_price=_safe_float(res.get("open_idx", 0.0)),
                        high_price=_safe_float(res.get("high_idx", 0.0)),
                        low_price=_safe_float(res.get("low_idx", 0.0)),
                        volume=_safe_int(res.get("acc_vol", 0)),
                        volume_amount=_safe_int(res.get("acc_trd_val", 0)),
                    ))
            except Exception as exc:
                self.logger.warning(f"지수({idx_cd}) 조회 실패: {exc}")
                continue
        return quotes

    def get_deposit_detail(self, account_no: str) -> Optional[DepositDetail]:
        """
        예수금 상세 정보 조회 (ka30002)
        
        Args:
            account_no: 계좌번호
            
        Returns:
            DepositDetail 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["ACCOUNT_DEPOSIT"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntdeposit", tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return DepositDetail(
                account_no=account_no,
                deposit=_safe_int(output.get("deposit", 0)),
                d1_deposit=_safe_int(output.get("d1_deposit", output.get("d1_estm_dps", 0))),
                d2_deposit=_safe_int(output.get("d2_deposit", output.get("d2_estm_dps", 0))),
                withdrawable_amount=_safe_int(output.get("draw_psbl_amt", output.get("wdrw_psbl_amt", 0))),
                order_available_amount=_safe_int(output.get("ord_psbl_amt", output.get("ord_psbl_cash", 0))),
                receivable_amount=_safe_int(output.get("rcvbl_amt", 0)),
                collateral_amount=_safe_int(output.get("subst_amt", 0)),
                stock_eval_amount=_safe_int(output.get("tot_eval_amt", output.get("stk_eval_amt", 0))),
                total_assets=_safe_int(output.get("tot_asst_amt", 0)),
            )
        return None

    def get_executed_orders(self, account_no: str, date: str = "") -> List[ExecutedOrder]:
        """
        당일 체결 주문 목록 조회 (ka10076)
        
        Args:
            account_no: 계좌번호
            date: 조회일자 (YYYYMMDD, 기본값: 당일)
            
        Returns:
            ExecutedOrder 리스트
        """
        tr_code = self.TR_CODES["ORDER_EXECUTED"]
        data = {
            "tr_cd": tr_code,
            "acnt_no": account_no,
            "inqr_dt": date or datetime.now().strftime("%Y%m%d"),
        }
        
        try:
            result = self._request("POST", "/api/dostk/ordexecuted", tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"체결 주문 조회 예외: {exc}")
            return []
            
        if not result or result.get("return_code") != 0:
            return []
            
        rows = result.get("output", [])
        if not isinstance(rows, list):
            if isinstance(rows, dict):
                rows = [rows]
            else:
                return []
                
        orders: List[ExecutedOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            raw_side = str(item.get("ord_tp") or item.get("bs_tp") or "").strip()
            side = "buy" if raw_side == "1" else ("sell" if raw_side == "2" else raw_side)
            orders.append(ExecutedOrder(
                exec_no=str(item.get("exec_no") or item.get("cntr_no") or "").strip(),
                order_no=str(item.get("ord_no") or "").strip(),
                code=str(item.get("stk_cd") or "").strip(),
                name=str(item.get("stk_nm") or "").strip(),
                side=side,
                order_type=str(item.get("prc_tp") or "").strip(),
                quantity=_safe_int(item.get("ord_qty", 0)),
                exec_quantity=_safe_int(item.get("exec_qty", item.get("cntr_qty", 0))),
                exec_price=_safe_int(item.get("exec_prc", item.get("cntr_prc", 0)), absolute=True),
                exec_amount=_safe_int(item.get("exec_amt", item.get("cntr_amt", 0))),
                exec_time=str(item.get("exec_tm") or item.get("cntr_tm") or "").strip(),
                fee=_safe_int(item.get("fee", 0)),
                tax=_safe_int(item.get("tax", 0)),
            ))
        return orders

    def get_tick_chart(self, code: str, count: int = 60) -> List[TickCandle]:
        """
        틱 차트 데이터 조회 (ka10007)
        
        Args:
            code: 종목코드
            count: 조회할 틱 개수 (최대 100)
            
        Returns:
            TickCandle 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_TICK"]
        data = {
            "tr_cd": tr_code,
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stktick", tr_code=tr_code, data=data)
        
        candles: List[TickCandle] = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                candles.append(TickCandle(
                    time=str(item.get("time") or item.get("stk_tm") or "").strip(),
                    price=_safe_int(item.get("cur_prc", 0), absolute=True),
                    volume=_safe_int(item.get("vol", item.get("cntr_qty", 0))),
                    change=_safe_int(item.get("chg_amt", 0)),
                    change_rate=_safe_float(item.get("chg_rt", 0.0)),
                    side=str(item.get("cntr_tp") or "").strip(),
                    cum_volume=_safe_int(item.get("acc_vol", 0)),
                ))
        return candles

    def get_vi_status(self, market: str = "0") -> List[VIEvent]:
        """
        변동성완화장치(VI) 발동 현황 조회 (ka20009)
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            
        Returns:
            VIEvent 리스트
        """
        tr_code = self.TR_CODES["VI_STATUS"]
        data = {
            "tr_cd": tr_code,
            "mkt_tp": market,
        }
        
        result = self._request("POST", "/api/dostk/vi/status", tr_code=tr_code, data=data)
        
        events: List[VIEvent] = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                events.append(VIEvent(
                    code=str(item.get("stk_cd") or "").strip(),
                    name=str(item.get("stk_nm") or "").strip(),
                    vi_type=str(item.get("vi_tp") or "").strip(),
                    vi_status=str(item.get("vi_st") or "발동").strip(),
                    trigger_time=str(item.get("trg_tm") or "").strip(),
                    release_time=str(item.get("rls_tm") or "").strip(),
                    trigger_price=_safe_int(item.get("trg_prc", 0), absolute=True),
                    base_price=_safe_int(item.get("base_prc", 0), absolute=True),
                    deviance_rate=_safe_float(item.get("dev_rt", 0.0)),
                ))
        return events

