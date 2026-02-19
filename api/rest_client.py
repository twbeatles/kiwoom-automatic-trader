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
from .models import (
    StockQuote, OrderBook, AccountInfo, Position, 
    OrderResult, DailyOHLC, OrderType, PriceType
)


class KiwoomRESTClient:
    """키움증권 REST API 클라이언트"""
    
    BASE_URL = "https://api.kiwoom.com"
    
    # TR 코드 정의
    TR_CODES = {
        # 시세 조회
        "STOCK_CURRENT": "ka10001",      # 주식현재가
        "STOCK_HOGA": "ka10004",         # 주식호가
        "STOCK_DAILY": "ka10005",        # 일봉차트
        "STOCK_MINUTE": "ka10006",       # 분봉차트
        "STOCK_TICK": "ka10007",         # 틱차트
        
        # 계좌 조회
        "ACCOUNT_BALANCE": "ka30001",    # 계좌평가잔고
        "ACCOUNT_DEPOSIT": "ka30002",    # 예수금상세
        
        # 주문
        "ORDER_STOCK": "ka40001",        # 주식주문
        "ORDER_CANCEL": "ka40002",       # 주식주문취소
        "ORDER_MODIFY": "ka40003",       # 주식주문정정
        
        # 순위/기타
        "RANK_VOLUME": "ka20001",        # 거래량상위
        "RANK_FLUCTUATION": "ka20002",   # 등락률상위
    }
    
    def __init__(self, auth: KiwoomAuth):
        """
        Args:
            auth: KiwoomAuth 인스턴스 (인증 관리)
        """
        self.auth = auth
        self.logger = logging.getLogger('KiwoomRESTClient')
        
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
                 data: Optional[Dict] = None,
                 params: Optional[Dict] = None) -> Optional[Dict]:
        """
        API 요청 수행
        
        Args:
            method: HTTP 메서드 (GET/POST)
            endpoint: API 엔드포인트 경로
            data: POST 바디 데이터
            params: 쿼리 파라미터
            
        Returns:
            응답 JSON 딕셔너리, 실패 시 None
        """
        self._rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            **self.auth.get_auth_header()
        }
        
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
        data = {
            "tr_cd": self.TR_CODES["STOCK_CURRENT"],
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/stkprice", data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            return StockQuote(
                code=code,
                name=output.get("stk_nm", ""),
                current_price=abs(int(output.get("cur_prc", 0))),
                change=int(output.get("chg_amt", 0)),
                change_rate=float(output.get("chg_rt", 0)),
                open_price=abs(int(output.get("open_prc", 0))),
                high_price=abs(int(output.get("high_prc", 0))),
                low_price=abs(int(output.get("low_prc", 0))),
                volume=int(output.get("acc_vol", 0)),
                prev_close=abs(int(output.get("yes_prc", 0))),
                ask_price=abs(int(output.get("ask_prc", 0))),
                bid_price=abs(int(output.get("bid_prc", 0))),
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
        data = {
            "tr_cd": self.TR_CODES["STOCK_HOGA"],
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/stkhoga", data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []
            
            for i in range(1, 11):
                ask_prices.append(abs(int(output.get(f"ask_prc{i}", 0))))
                ask_volumes.append(int(output.get(f"ask_vol{i}", 0)))
                bid_prices.append(abs(int(output.get(f"bid_prc{i}", 0))))
                bid_volumes.append(int(output.get(f"bid_vol{i}", 0)))
            
            return OrderBook(
                code=code,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                total_ask_volume=int(output.get("tot_ask_vol", 0)),
                total_bid_volume=int(output.get("tot_bid_vol", 0)),
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
        data = {
            "tr_cd": self.TR_CODES["STOCK_DAILY"],
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkdaily", data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("date", ""),
                    open_price=abs(int(item.get("open_prc", 0))),
                    high_price=abs(int(item.get("high_prc", 0))),
                    low_price=abs(int(item.get("low_prc", 0))),
                    close_price=abs(int(item.get("close_prc", 0))),
                    volume=int(item.get("vol", 0))
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
        data = {
            "tr_cd": self.TR_CODES["ACCOUNT_BALANCE"],
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntbal", data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            
            return AccountInfo(
                account_no=account_no,
                deposit=int(output.get("deposit", 0)),
                available_amount=int(output.get("ord_psbl_amt", 0)),
                total_buy_amount=int(output.get("tot_buy_amt", 0)),
                total_eval_amount=int(output.get("tot_eval_amt", 0)),
                total_profit=int(output.get("tot_eval_pl", 0)),
                total_profit_rate=float(output.get("tot_eval_pl_rt", 0))
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
        data = {
            "tr_cd": self.TR_CODES["ACCOUNT_BALANCE"],
            "acnt_no": account_no
        }
        
        result = self._request("POST", "/api/dostk/acntbal", data=data)
        
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
                quantity=int(item.get("hold_qty", 0)),
                available_qty=int(item.get("sell_psbl_qty", 0)),
                buy_price=int(item.get("buy_prc", 0)),
                current_price=abs(int(item.get("cur_prc", 0))),
                buy_amount=int(item.get("buy_amt", 0)),
                eval_amount=int(item.get("eval_amt", 0)),
                profit=int(item.get("eval_pl", 0)),
                profit_rate=float(item.get("eval_pl_rt", 0))
            ))

        return positions
    
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
        주식 주문 전송
        
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
        data = {
            "tr_cd": self.TR_CODES["ORDER_STOCK"],
            "acnt_no": account_no,
            "stk_cd": code,
            "ord_tp": order_type.value,
            "ord_qty": quantity,
            "ord_prc": price if price_type == PriceType.LIMIT else 0,
            "prc_tp": price_type.value
        }
        
        result = self._request("POST", "/api/dostk/order", data=data)
        
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
        """주문 취소"""
        data = {
            "tr_cd": self.TR_CODES["ORDER_CANCEL"],
            "acnt_no": account_no,
            "org_ord_no": order_no,
            "stk_cd": code,
            "ord_qty": quantity
        }
        
        result = self._request("POST", "/api/dostk/ordcancel", data=data)
        
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
    
    # =========================================================================
    # 유틸리티
    # =========================================================================
    
    def get_account_list(self) -> List[str]:
        """
        계좌 목록 조회
        
        Returns:
            계좌번호 리스트
        """
        result = self._request("POST", "/api/dostk/acntlist", data={})
        
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
        data = {
            "tr_cd": self.TR_CODES["STOCK_MINUTE"],
            "stk_cd": code,
            "interval": interval,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkminute", data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("datetime", ""),
                    open_price=abs(int(item.get("open_prc", 0))),
                    high_price=abs(int(item.get("high_prc", 0))),
                    low_price=abs(int(item.get("low_prc", 0))),
                    close_price=abs(int(item.get("close_prc", 0))),
                    volume=int(item.get("vol", 0))
                ))
        
        return candles
    
    def get_weekly_chart(self, code: str, count: int = 52) -> List[DailyOHLC]:
        """주봉 차트 데이터 조회"""
        data = {
            "tr_cd": "ka10008",  # 주봉차트
            "stk_cd": code,
            "req_cnt": min(count, 100)
        }
        
        result = self._request("POST", "/api/dostk/stkweekly", data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            
            for item in output_list:
                candles.append(DailyOHLC(
                    date=item.get("date", ""),
                    open_price=abs(int(item.get("open_prc", 0))),
                    high_price=abs(int(item.get("high_prc", 0))),
                    low_price=abs(int(item.get("low_prc", 0))),
                    close_price=abs(int(item.get("close_prc", 0))),
                    volume=int(item.get("vol", 0))
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
        result = self._request("POST", "/api/dostk/condition/list", data={})
        
        conditions = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                conditions.append({
                    "index": int(item.get("cond_idx", 0)),
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
        data = {
            "cond_idx": condition_index,
            "cond_nm": condition_name
        }
        
        result = self._request("POST", "/api/dostk/condition/search", data=data)
        
        stocks = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for item in output_list:
                stocks.append({
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": abs(int(item.get("cur_prc", 0))),
                    "change_rate": float(item.get("chg_rt", 0)),
                    "volume": int(item.get("vol", 0))
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
        data = {
            "tr_cd": self.TR_CODES["RANK_VOLUME"],
            "mkt_tp": market,
            "req_cnt": min(count, 50)
        }
        
        result = self._request("POST", "/api/dostk/ranking/volume", data=data)
        
        rankings = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for i, item in enumerate(output_list):
                rankings.append({
                    "rank": i + 1,
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": abs(int(item.get("cur_prc", 0))),
                    "change_rate": float(item.get("chg_rt", 0)),
                    "volume": int(item.get("vol", 0)),
                    "volume_rate": float(item.get("vol_rt", 0))
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
        data = {
            "tr_cd": self.TR_CODES["RANK_FLUCTUATION"],
            "mkt_tp": market,
            "sort_tp": sort_type,
            "req_cnt": min(count, 50)
        }
        
        result = self._request("POST", "/api/dostk/ranking/fluctuation", data=data)
        
        rankings = []
        if result and result.get("return_code") == 0:
            output_list = result.get("output", [])
            for i, item in enumerate(output_list):
                rankings.append({
                    "rank": i + 1,
                    "code": item.get("stk_cd", ""),
                    "name": item.get("stk_nm", ""),
                    "current_price": abs(int(item.get("cur_prc", 0))),
                    "change": int(item.get("chg_amt", 0)),
                    "change_rate": float(item.get("chg_rt", 0)),
                    "volume": int(item.get("vol", 0))
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
        data = {
            "tr_cd": "ka20010",
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/investor", data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return {
                "code": code,
                "individual_buy": int(output.get("indv_buy", 0)),
                "individual_sell": int(output.get("indv_sell", 0)),
                "foreign_buy": int(output.get("frgn_buy", 0)),
                "foreign_sell": int(output.get("frgn_sell", 0)),
                "institution_buy": int(output.get("inst_buy", 0)),
                "institution_sell": int(output.get("inst_sell", 0)),
                "individual_net": int(output.get("indv_net", 0)),
                "foreign_net": int(output.get("frgn_net", 0)),
                "institution_net": int(output.get("inst_net", 0))
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
        data = {
            "tr_cd": "ka20011",
            "stk_cd": code
        }
        
        result = self._request("POST", "/api/dostk/program", data=data)
        
        if result and result.get("return_code") == 0:
            output = result.get("output", {})
            return {
                "code": code,
                "arb_buy": int(output.get("arb_buy", 0)),
                "arb_sell": int(output.get("arb_sell", 0)),
                "nonarb_buy": int(output.get("nonarb_buy", 0)),
                "nonarb_sell": int(output.get("nonarb_sell", 0)),
                "total_buy": int(output.get("tot_buy", 0)),
                "total_sell": int(output.get("tot_sell", 0)),
                "net": int(output.get("net", 0))
            }
        
        return {}

