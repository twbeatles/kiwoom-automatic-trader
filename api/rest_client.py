"""
키움증권 REST API 클라이언트

시세 조회, 계좌 조회, 주문 등 REST API 호출을 담당합니다.
"""

import logging
import time
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

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


def _pick(mapping: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping[key]
    return default


def _as_records(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict) and value:
        return [value]
    return []


def _payload_dict(result: Optional[Dict[str, Any]], *keys: str) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    for key in keys:
        candidate = result.get(key)
        if isinstance(candidate, dict) and candidate:
            return candidate
    return result


def _payload_records(result: Optional[Dict[str, Any]], *keys: str) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    for key in keys:
        records = _as_records(result.get(key))
        if records:
            return records
    return []


def _trde_tp(price_type: PriceType) -> str:
    mapping = {
        PriceType.MARKET: "3",
        PriceType.CONDITIONAL: "5",
        PriceType.BEST: "6",
        PriceType.PRIORITY: "7",
        PriceType.AFTER_MARKET: "81",
    }
    return mapping.get(price_type, "0")


class KiwoomRESTClient:
    """키움증권 REST API 클라이언트"""
    
    BASE_URL = LIVE_REST_BASE_URL
    
    # TR 코드 정의 (키움 공식 REST api-id)
    TR_CODES = {
        # 시세/종목
        "STOCK_CURRENT": "ka10001",      # 주식기본정보요청
        "STOCK_HOGA": "ka10004",         # 주식호가요청
        "STOCK_DAILY": "ka10081",        # 주식일봉차트조회요청
        "STOCK_MINUTE": "ka10080",       # 주식분봉차트조회요청
        "STOCK_TICK": "ka10079",         # 주식틱차트조회요청
        "STOCK_WEEKLY": "ka10082",       # 주식주봉차트조회요청
        "SECTOR_INDEX": "ka20001",       # 업종현재가 (호환)

        # 계좌
        "ACCOUNT_BALANCE": "kt00018",    # 계좌평가잔고내역요청
        "ACCOUNT_DEPOSIT": "kt00001",    # 예수금상세현황요청
        "ACCOUNT_LIST": "ka00001",       # 계좌번호조회

        # 주문
        "ORDER_BUY": "kt10000",          # 주식매수주문
        "ORDER_SELL": "kt10001",         # 주식매도주문
        "ORDER_MODIFY": "kt10002",       # 주식정정주문
        "ORDER_CANCEL": "kt10003",       # 주식취소주문
        "ORDER_STOCK": "kt10000",        # 호환용 매수 alias

        # 순위/시세 확장 (Kiwoom-Securities/Kiwoom-REST-API 예제 기준)
        "RANK_VOLUME": "ka10030",        # 당일거래량상위요청
        "RANK_FLUCTUATION": "ka10027",   # 전일대비등락률상위요청
        "CONDITION_LIST": "ka10171",     # 조건검색 목록조회 (WebSocket CNSRLST)
        "CONDITION_SEARCH": "ka10172",   # 조건검색 요청 일반 (WebSocket CNSRREQ)
        "INVESTOR_TRADING": "ka10045",   # 종목별기관매매추이요청
        "PROGRAM_TRADING": "ka90013",    # 종목일별프로그램매매추이요청
        "INDEX_QUOTE": "ka20001",        # 업종현재가요청
        "VI_STATUS": "ka10054",          # 변동성완화장치발동종목요청

        # 미체결 / 체결
        "ORDER_OPEN": "ka10075",         # 미체결요청
        "ORDER_EXECUTED": "ka10076",     # 체결요청
    }

    PATHS = {
        "stkinfo": "/api/dostk/stkinfo",
        "mrkcond": "/api/dostk/mrkcond",
        "chart": "/api/dostk/chart",
        "acnt": "/api/dostk/acnt",
        "ordr": "/api/dostk/ordr",
        "rkinfo": "/api/dostk/rkinfo",
        "sect": "/api/dostk/sect",
    }
    DEFAULT_EXCHANGE = "KRX"
    
    def __init__(self, auth: KiwoomAuth, base_url: Optional[str] = None):
        """
        Args:
            auth: KiwoomAuth 인스턴스 (인증 관리)
        """
        self.auth = auth
        self.logger = logging.getLogger('KiwoomRESTClient')
        self.base_url = str(base_url or getattr(auth, "base_url", self.BASE_URL) or self.BASE_URL).rstrip("/")
        self.session_namespace = str(getattr(auth, "session_namespace", "kiwoom_live") or "kiwoom_live")
        self.ws_client = None
        
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
        if not tr_code:
            self.logger.error("API 요청에 api-id(TR 코드)가 없습니다. 키움 REST는 api-id 누락 시 1501 오류가 납니다.")
            return None

        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            **self.auth.get_auth_header(),
            "cont-yn": str(cont_yn or "N"),
            "api-id": str(tr_code),
        }
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

    def _rank_market_tp(self, market: str) -> str:
        mapping = {
            "0": "000",
            "1": "001",
            "2": "101",
            "000": "000",
            "001": "001",
            "101": "101",
        }
        return mapping.get(str(market or "").strip(), "000")

    def _index_market_tp(self, index_code: str) -> str:
        code = str(index_code or "").strip()
        if code.startswith("101"):
            return "1"
        if code.startswith("201"):
            return "2"
        return "0"

    def _stk_cd(self, value: Any) -> str:
        text = str(value or "").strip()
        if len(text) >= 7 and text[0] in {"A", "a"}:
            return text[1:]
        return text

    def _condition_ws(self):
        ws = getattr(self, "ws_client", None)
        if ws is not None and hasattr(ws, "request_once"):
            return ws
        try:
            from .websocket_client import KiwoomWebSocketClient
            return KiwoomWebSocketClient(self.auth)
        except Exception as exc:
            self.logger.warning(f"조건검색 WebSocket 클라이언트를 만들 수 없습니다: {exc}")
            return None

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
        result = self._request("POST", self.PATHS["stkinfo"], tr_code=tr_code, data={"stk_cd": code})
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            
            return StockQuote(
                code=code,
                name=str(_pick(output, "stk_nm", default="")),
                current_price=_safe_int(_pick(output, "cur_prc"), absolute=True),
                change=_safe_int(_pick(output, "pred_pre", "chg_amt")),
                change_rate=_safe_float(_pick(output, "flu_rt", "chg_rt")),
                open_price=_safe_int(_pick(output, "open_pric", "open_prc"), absolute=True),
                high_price=_safe_int(_pick(output, "high_pric", "high_prc"), absolute=True),
                low_price=_safe_int(_pick(output, "low_pric", "low_prc"), absolute=True),
                volume=_safe_int(_pick(output, "trde_qty", "acc_vol")),
                prev_close=_safe_int(_pick(output, "base_pric", "yes_prc"), absolute=True),
                ask_price=_safe_int(_pick(output, "ask_prc", "sel_fpr_bid"), absolute=True),
                bid_price=_safe_int(_pick(output, "bid_prc", "buy_fpr_bid"), absolute=True),
                timestamp=str(_pick(output, "stk_tm", default="")),
                market_type=self._parse_market_type(output),
                sector=str(_pick(output, "sect_nm", default="기타") or "기타"),
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
        result = self._request("POST", self.PATHS["mrkcond"], tr_code=tr_code, data={"stk_cd": code})
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            ordinals = ("1th", "2th", "3th", "4th", "5th", "6th", "7th", "8th", "9th", "10th")
            
            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []
            
            for i, ordinal in enumerate(ordinals, start=1):
                if i == 1:
                    ask_prices.append(_safe_int(_pick(output, "sel_fpr_bid", f"ask_prc{i}"), absolute=True))
                    ask_volumes.append(_safe_int(_pick(output, "sel_fpr_req", f"ask_vol{i}")))
                    bid_prices.append(_safe_int(_pick(output, "buy_fpr_bid", f"bid_prc{i}"), absolute=True))
                    bid_volumes.append(_safe_int(_pick(output, "buy_fpr_req", f"bid_vol{i}")))
                    continue
                ask_prices.append(_safe_int(_pick(output, f"sel_{ordinal}_pre_bid", f"ask_prc{i}"), absolute=True))
                ask_volumes.append(_safe_int(_pick(output, f"sel_{ordinal}_pre_req", f"ask_vol{i}")))
                bid_prices.append(_safe_int(_pick(output, f"buy_{ordinal}_pre_bid", f"bid_prc{i}"), absolute=True))
                bid_volumes.append(_safe_int(_pick(output, f"buy_{ordinal}_pre_req", f"bid_vol{i}")))
            
            return OrderBook(
                code=code,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes,
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                total_ask_volume=_safe_int(_pick(output, "tot_sel_req", "tot_ask_vol")),
                total_bid_volume=_safe_int(_pick(output, "tot_buy_req", "tot_bid_vol")),
                timestamp=str(_pick(output, "bid_req_base_tm", "stk_tm", default="")),
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
            "stk_cd": code,
            "base_dt": datetime.now().strftime("%Y%m%d"),
            "upd_stkpc_tp": "1",
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_dt_pole_chart_qry", "output")
            for item in output_list[: max(1, min(count, 100))]:
                candles.append(DailyOHLC(
                    date=str(_pick(item, "dt", "date", default="")),
                    open_price=_safe_int(_pick(item, "open_pric", "open_prc"), absolute=True),
                    high_price=_safe_int(_pick(item, "high_pric", "high_prc"), absolute=True),
                    low_price=_safe_int(_pick(item, "low_pric", "low_prc"), absolute=True),
                    close_price=_safe_int(_pick(item, "cur_prc", "close_prc"), absolute=True),
                    volume=_safe_int(_pick(item, "trde_qty", "vol")),
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
            "qry_tp": "1",
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
        }
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            return AccountInfo(
                account_no=account_no,
                deposit=_safe_int(_pick(output, "prsm_dpst_aset_amt", "deposit")),
                available_amount=_safe_int(_pick(output, "ord_alow_amt", "ord_psbl_amt")),
                total_buy_amount=_safe_int(_pick(output, "tot_pur_amt", "tot_buy_amt")),
                total_eval_amount=_safe_int(_pick(output, "tot_evlt_amt", "tot_eval_amt")),
                total_profit=_safe_int(_pick(output, "tot_evlt_pl", "tot_eval_pl")),
                total_profit_rate=_safe_float(_pick(output, "tot_prft_rt", "tot_eval_pl_rt")),
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
            "qry_tp": "1",
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
        }
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        
        if not result:
            return None
        if result.get("return_code") != 0:
            return None

        positions = []
        stocks = _payload_records(result, "acnt_evlt_remn_indv_tot", "stocks", "output")

        for item in stocks:
            positions.append(Position(
                code=str(_pick(item, "stk_cd", default="")),
                name=str(_pick(item, "stk_nm", default="")),
                quantity=_safe_int(_pick(item, "rmnd_qty", "hold_qty")),
                available_qty=_safe_int(_pick(item, "trde_able_qty", "sell_psbl_qty")),
                buy_price=_safe_int(_pick(item, "pur_pric", "buy_prc")),
                current_price=_safe_int(_pick(item, "cur_prc"), absolute=True),
                buy_amount=_safe_int(_pick(item, "pur_amt", "buy_amt")),
                eval_amount=_safe_int(_pick(item, "evlt_amt", "eval_amt")),
                profit=_safe_int(_pick(item, "evltv_prft", "eval_pl")),
                profit_rate=_safe_float(_pick(item, "prft_rt", "eval_pl_rt")),
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
            "all_stk_tp": "0",
            "trde_tp": "0",
            "stex_tp": "0",
        }

        try:
            result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"미체결 주문 조회 예외: {exc}")
            return []

        if not result or result.get("return_code") != 0:
            return []

        rows = _payload_records(result, "oso", "output")

        orders: List[OpenOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            try:
                order_no = str(item.get("ord_no") or item.get("org_ord_no") or "").strip()
                code = str(item.get("stk_cd") or "").strip()
                if not order_no or not code:
                    continue
                orders.append(
                    OpenOrder(
                        order_no=order_no,
                        code=code,
                        side=self._parse_order_side(item),
                        quantity=_safe_int(item.get("ord_qty", 0)),
                        remaining_qty=_safe_int(
                            _pick(item, "oso_qty", "unexec_qty", "not_cncl_qty", "rmn_qty", default=0)
                        ),
                        price=_safe_int(_pick(item, "ord_pric", "ord_prc", default=0), absolute=True),
                        status=str(item.get("ord_stt") or item.get("ord_st") or item.get("cnf_tp") or "").strip(),
                    )
                )
            except Exception as exc:
                self.logger.warning(f"미체결 주문 파싱 실패(건 건너뜀): {exc}")
                continue

        return orders

    @staticmethod
    def _parse_order_side(item: Dict[str, Any]) -> str:
        label = str(item.get("io_tp_nm") or item.get("ord_stt") or "").strip()
        if "매수" in label:
            return "buy"
        if "매도" in label:
            return "sell"
        raw_trde = str(item.get("trde_tp") or "").strip()
        if raw_trde == "2":
            return "buy"
        if raw_trde == "1":
            return "sell"
        raw_side = str(item.get("ord_tp") or item.get("bs_tp") or "").strip()
        if raw_side == "1":
            return "buy"
        if raw_side == "2":
            return "sell"
        return raw_side or raw_trde

    @staticmethod
    def _order_no_from_result(result: Optional[Dict[str, Any]]) -> str:
        if not isinstance(result, dict):
            return ""
        output = result.get("output")
        if isinstance(output, dict):
            value = output.get("ord_no")
            if value:
                return str(value)
        return str(result.get("ord_no") or "")
    
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
        trde_tp = _trde_tp(price_type)
        data = {
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
            "stk_cd": code,
            "ord_qty": str(int(quantity)),
            "trde_tp": trde_tp,
            "ord_uv": "" if trde_tp == "3" else str(int(price or 0)),
            "cond_uv": "",
        }
        
        result = self._request("POST", self.PATHS["ordr"], tr_code=tr_code, data=data)
        
        if result:
            return_code = result.get("return_code", -1)
            
            if return_code == 0:
                return OrderResult(
                    success=True,
                    order_no=self._order_no_from_result(result),
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
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
            "orig_ord_no": str(order_no),
            "stk_cd": code,
            "cncl_qty": str(int(quantity)),
        }
        
        result = self._request("POST", self.PATHS["ordr"], tr_code=tr_code, data=data)
        
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
            "dmst_stex_tp": self.DEFAULT_EXCHANGE,
            "orig_ord_no": str(order_no),
            "stk_cd": code,
            "mdfy_qty": str(int(quantity)),
            "mdfy_uv": str(int(price or 0)),
            "mdfy_cond_uv": "",
        }
        
        result = self._request("POST", self.PATHS["ordr"], tr_code=tr_code, data=data)
        
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
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data={})
        
        if result and result.get("return_code") == 0:
            accounts: List[str] = []
            for key in ("acctNo", "accounts", "output", "acnt_no"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    accounts.append(value.strip())
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            accounts.append(item.strip())
                        elif isinstance(item, dict):
                            text = str(item.get("acctNo") or item.get("acnt_no") or item.get("account") or "").strip()
                            if text:
                                accounts.append(text)
                if accounts:
                    break
            return accounts
        
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
            "stk_cd": code,
            "tic_scope": str(interval),
            "upd_stkpc_tp": "1",
            "base_dt": datetime.now().strftime("%Y%m%d"),
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_min_pole_chart_qry", "output")
            for item in output_list[: max(1, min(count, 100))]:
                candles.append(DailyOHLC(
                    date=str(_pick(item, "cntr_tm", "datetime", "dt", default="")),
                    open_price=_safe_int(_pick(item, "open_pric", "open_prc"), absolute=True),
                    high_price=_safe_int(_pick(item, "high_pric", "high_prc"), absolute=True),
                    low_price=_safe_int(_pick(item, "low_pric", "low_prc"), absolute=True),
                    close_price=_safe_int(_pick(item, "cur_prc", "close_prc"), absolute=True),
                    volume=_safe_int(_pick(item, "trde_qty", "vol")),
                ))
        
        return candles
    
    def get_weekly_chart(self, code: str, count: int = 52) -> List[DailyOHLC]:
        """주봉 차트 데이터 조회"""
        tr_code = self.TR_CODES["STOCK_WEEKLY"]
        data = {
            "stk_cd": code,
            "base_dt": datetime.now().strftime("%Y%m%d"),
            "upd_stkpc_tp": "1",
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_wk_pole_chart_qry", "output")
            for item in output_list[: max(1, min(count, 100))]:
                candles.append(DailyOHLC(
                    date=str(_pick(item, "dt", "date", default="")),
                    open_price=_safe_int(_pick(item, "open_pric", "open_prc"), absolute=True),
                    high_price=_safe_int(_pick(item, "high_pric", "high_prc"), absolute=True),
                    low_price=_safe_int(_pick(item, "low_pric", "low_prc"), absolute=True),
                    close_price=_safe_int(_pick(item, "cur_prc", "close_prc"), absolute=True),
                    volume=_safe_int(_pick(item, "trde_qty", "vol")),
                ))
        
        return candles
    
    # =========================================================================
    # 조건검색 API
    # =========================================================================
    
    def get_condition_list(self) -> List[Dict[str, Any]]:
        """조건검색식 목록 조회 (WebSocket ka10171 / CNSRLST)."""
        ws = self._condition_ws()
        if ws is None:
            return []
        result = ws.request_once({"trnm": "CNSRLST"})
        if not isinstance(result, dict):
            self.logger.warning("조건검색 목록 조회 실패: WebSocket CNSRLST 응답이 없습니다.")
            return []

        conditions: List[Dict[str, Any]] = []
        records = result.get("data") or result.get("output") or []
        if not isinstance(records, list):
            records = []
        for item in records:
            if isinstance(item, dict):
                conditions.append({
                    "index": _safe_int(_pick(item, "seq", "index", "cond_idx")),
                    "name": str(_pick(item, "name", "cond_nm", default="") or ""),
                })
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                conditions.append({
                    "index": _safe_int(item[0]),
                    "name": str(item[1] or ""),
                })
        return conditions

    def search_by_condition(self, condition_index: int, condition_name: str = "") -> List[Dict[str, Any]]:
        """조건검색 실행 (WebSocket ka10172 / CNSRREQ)."""
        del condition_name  # 공식 CNSRREQ는 seq만 사용
        ws = self._condition_ws()
        if ws is None:
            return []
        result = ws.request_once({
            "trnm": "CNSRREQ",
            "seq": str(condition_index),
            "search_type": "0",
            "stex_tp": "K",
        })
        if not isinstance(result, dict):
            self.logger.warning("조건검색 실행 실패: WebSocket CNSRREQ 응답이 없습니다.")
            return []

        stocks: List[Dict[str, Any]] = []
        records = result.get("data") or result.get("output") or []
        if not isinstance(records, list):
            records = []
        for item in records:
            if isinstance(item, dict):
                stocks.append({
                    "code": self._stk_cd(_pick(item, "9001", "stk_cd", "code")),
                    "name": str(_pick(item, "302", "stk_nm", "name", default="") or ""),
                    "current_price": _safe_int(_pick(item, "10", "cur_prc"), absolute=True),
                    "change_rate": _safe_float(_pick(item, "12", "flu_rt", "chg_rt")),
                    "volume": _safe_int(_pick(item, "13", "trde_qty", "vol")),
                })
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                stocks.append({
                    "code": self._stk_cd(item[0]),
                    "name": str(item[1] or ""),
                    "current_price": _safe_int(item[2] if len(item) > 2 else 0, absolute=True),
                    "change_rate": _safe_float(item[5] if len(item) > 5 else 0),
                    "volume": _safe_int(item[6] if len(item) > 6 else 0),
                })
        return [row for row in stocks if row.get("code")]
    
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
            "mrkt_tp": self._rank_market_tp(market),
            "sort_tp": "1",
            "mang_stk_incls": "0",
            "crd_tp": "0",
            "trde_qty_tp": "0",
            "pric_tp": "0",
            "trde_prica_tp": "0",
            "mrkt_open_tp": "0",
            "stex_tp": "3",
        }
        result = self._request("POST", self.PATHS["rkinfo"], tr_code=tr_code, data=data)
        records = _payload_records(result, "tdy_trde_qty_upper", "output")
        rankings = []
        for i, item in enumerate(records[: max(1, min(int(count or 30), 100))]):
            rankings.append({
                "rank": i + 1,
                "code": self._stk_cd(_pick(item, "stk_cd")),
                "name": str(_pick(item, "stk_nm", default="") or ""),
                "current_price": _safe_int(_pick(item, "cur_prc"), absolute=True),
                "change_rate": _safe_float(_pick(item, "flu_rt", "chg_rt")),
                "volume": _safe_int(_pick(item, "trde_qty", "vol")),
                "volume_rate": _safe_float(_pick(item, "trde_tern_rt", "vol_rt")),
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
        official_sort = {"1": "1", "2": "3", "3": "3", "4": "4"}.get(str(sort_type), "1")
        data = {
            "mrkt_tp": self._rank_market_tp(market),
            "sort_tp": official_sort,
            "trde_qty_cnd": "0000",
            "stk_cnd": "0",
            "crd_cnd": "0",
            "updown_incls": "1",
            "pric_cnd": "0",
            "trde_prica_cnd": "0",
            "stex_tp": "3",
        }
        result = self._request("POST", self.PATHS["rkinfo"], tr_code=tr_code, data=data)
        records = _payload_records(result, "pred_pre_flu_rt_upper", "output")
        rankings = []
        for i, item in enumerate(records[: max(1, min(int(count or 30), 100))]):
            rankings.append({
                "rank": i + 1,
                "code": self._stk_cd(_pick(item, "stk_cd")),
                "name": str(_pick(item, "stk_nm", default="") or ""),
                "current_price": _safe_int(_pick(item, "cur_prc"), absolute=True),
                "change": _safe_int(_pick(item, "pred_pre", "chg_amt")),
                "change_rate": _safe_float(_pick(item, "flu_rt", "chg_rt")),
                "volume": _safe_int(_pick(item, "now_trde_qty", "trde_qty", "vol")),
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
        end_dt = datetime.now().strftime("%Y%m%d")
        strt_dt = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        data = {
            "stk_cd": code,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "orgn_prsm_unp_tp": "1",
            "for_prsm_unp_tp": "1",
        }
        result = self._request("POST", self.PATHS["mrkcond"], tr_code=tr_code, data=data)
        records = _payload_records(result, "stk_orgn_trde_trnsn", "output")
        if not records:
            return {}
        row = records[0]
        institution_net = _safe_int(_pick(row, "orgn_daly_nettrde_qty", "inst_net"))
        foreign_net = _safe_int(_pick(row, "for_daly_nettrde_qty", "frgn_net"))
        individual_net = _safe_int(_pick(row, "indv_net"))
        return {
            "code": code,
            "individual_buy": _safe_int(_pick(row, "indv_buy")),
            "individual_sell": _safe_int(_pick(row, "indv_sell")),
            "foreign_buy": _safe_int(_pick(row, "frgn_buy")),
            "foreign_sell": _safe_int(_pick(row, "frgn_sell")),
            "institution_buy": _safe_int(_pick(row, "inst_buy")),
            "institution_sell": _safe_int(_pick(row, "inst_sell")),
            "individual_net": individual_net,
            "foreign_net": foreign_net,
            "institution_net": institution_net,
        }
    
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
            "stk_cd": code,
            "amt_qty_tp": "2",
            "date": "",
        }
        result = self._request("POST", self.PATHS["mrkcond"], tr_code=tr_code, data=data)
        records = _payload_records(result, "stk_daly_prm_trde_trnsn", "output")
        if not records:
            return {}
        row = records[0]
        buy_qty = _safe_int(_pick(row, "prm_buy_qty", "tot_buy"))
        sell_qty = _safe_int(_pick(row, "prm_sell_qty", "tot_sell"))
        net = _safe_int(_pick(row, "prm_netprps_qty", "net"), default=buy_qty - sell_qty)
        return {
            "code": code,
            "arb_buy": _safe_int(_pick(row, "arb_buy")),
            "arb_sell": _safe_int(_pick(row, "arb_sell")),
            "nonarb_buy": _safe_int(_pick(row, "nonarb_buy")),
            "nonarb_sell": _safe_int(_pick(row, "nonarb_sell")),
            "total_buy": buy_qty,
            "total_sell": sell_qty,
            "net": net,
        }

    # =========================================================================
    # 시장 상태/지수 API (v4 확장)
    # =========================================================================

    def get_market_status(self) -> Dict[str, Any]:
        """장 상태는 공식 REST TR이 없고 WebSocket REAL `0s`(장시작시간)만 존재한다."""
        return {}

    def get_index_quote(self, index_code: str) -> Dict[str, Any]:
        """업종현재가 조회 (ka20001 /api/dostk/sect)."""
        if not index_code:
            return {}
        tr_code = self.TR_CODES["INDEX_QUOTE"]
        data = {
            "mrkt_tp": self._index_market_tp(index_code),
            "inds_cd": str(index_code),
        }
        result = self._request("POST", self.PATHS["sect"], tr_code=tr_code, data=data)
        if not result:
            return {}
        output = _payload_dict(result, "output")
        current = _safe_float(_pick(output, "cur_prc", "cur_idx"))
        change = _safe_float(_pick(output, "pred_pre", "chg_idx"))
        change_rate = _safe_float(_pick(output, "flu_rt", "chg_rt"))
        if current == 0.0 and change == 0.0 and change_rate == 0.0 and not _pick(output, "cur_prc", "cur_idx"):
            return {}
        return {
            "idx_cd": str(index_code),
            "idx_nm": str(_pick(output, "idx_nm", "inds_nm", default="") or ""),
            "cur_idx": current,
            "chg_idx": change,
            "chg_rt": change_rate,
            "open_idx": _safe_float(_pick(output, "open_pric", "open_idx")),
            "high_idx": _safe_float(_pick(output, "high_pric", "high_idx")),
            "low_idx": _safe_float(_pick(output, "low_pric", "low_idx")),
            "acc_vol": _safe_int(_pick(output, "trde_qty", "acc_vol")),
            "acc_trd_val": _safe_int(_pick(output, "trde_prica", "acc_trd_val")),
            "cur_prc": current,
            "flu_rt": change_rate,
        }

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
                        name=str(_pick(res, "idx_nm", default="") or name),
                        current_price=_safe_float(_pick(res, "cur_idx", "cur_prc")),
                        change=_safe_float(_pick(res, "chg_idx", "pred_pre")),
                        change_rate=_safe_float(_pick(res, "chg_rt", "flu_rt")),
                        open_price=_safe_float(_pick(res, "open_idx", "open_pric")),
                        high_price=_safe_float(_pick(res, "high_idx", "high_pric")),
                        low_price=_safe_float(_pick(res, "low_idx", "low_pric")),
                        volume=_safe_int(_pick(res, "acc_vol", "trde_qty")),
                        volume_amount=_safe_int(_pick(res, "acc_trd_val", "trde_prica")),
                    ))
            except Exception as exc:
                self.logger.warning(f"지수({idx_cd}) 조회 실패: {exc}")
                continue
        return quotes

    def get_deposit_detail(self, account_no: str) -> Optional[DepositDetail]:
        """
        예수금 상세 정보 조회 (kt00001)
        
        Args:
            account_no: 계좌번호
            
        Returns:
            DepositDetail 객체, 실패 시 None
        """
        tr_code = self.TR_CODES["ACCOUNT_DEPOSIT"]
        result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data={"qry_tp": "3"})
        
        if result and result.get("return_code") == 0:
            output = _payload_dict(result, "output")
            return DepositDetail(
                account_no=account_no,
                deposit=_safe_int(_pick(output, "entr", "deposit")),
                d1_deposit=_safe_int(_pick(output, "d1_entra", "d1_deposit", "d1_estm_dps")),
                d2_deposit=_safe_int(_pick(output, "d2_entra", "d2_deposit", "d2_estm_dps")),
                withdrawable_amount=_safe_int(_pick(output, "pymn_alow_amt", "draw_psbl_amt", "wdrw_psbl_amt")),
                order_available_amount=_safe_int(_pick(output, "ord_alow_amt", "ord_psbl_amt", "ord_psbl_cash")),
                receivable_amount=_safe_int(_pick(output, "ch_uncla", "rcvbl_amt")),
                collateral_amount=_safe_int(_pick(output, "repl_amt", "subst_amt")),
                stock_eval_amount=_safe_int(_pick(output, "tot_eval_amt", "stk_eval_amt")),
                total_assets=_safe_int(_pick(output, "tot_asst_amt", "prsm_dpst_aset_amt")),
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
            "qry_tp": "0",
            "sell_tp": "0",
            "stex_tp": "0",
        }
        
        try:
            result = self._request("POST", self.PATHS["acnt"], tr_code=tr_code, data=data)
        except Exception as exc:
            self.logger.warning(f"체결 주문 조회 예외: {exc}")
            return []
            
        if not result or result.get("return_code") != 0:
            return []
            
        rows = _payload_records(result, "cntr", "output")
                
        orders: List[ExecutedOrder] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            orders.append(ExecutedOrder(
                exec_no=str(item.get("exec_no") or item.get("cntr_no") or "").strip(),
                order_no=str(item.get("ord_no") or "").strip(),
                code=str(item.get("stk_cd") or "").strip(),
                name=str(item.get("stk_nm") or "").strip(),
                side=self._parse_order_side(item),
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
        틱 차트 데이터 조회 (ka10079)
        
        Args:
            code: 종목코드
            count: 조회할 틱 개수 (최대 100)
            
        Returns:
            TickCandle 리스트 (최신순)
        """
        tr_code = self.TR_CODES["STOCK_TICK"]
        data = {
            "stk_cd": code,
            "tic_scope": "1",
            "upd_stkpc_tp": "1",
        }
        result = self._request("POST", self.PATHS["chart"], tr_code=tr_code, data=data)
        
        candles: List[TickCandle] = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "stk_tic_chart_qry", "output")[: max(1, min(count, 100))]
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
        변동성완화장치(VI) 발동 현황 조회 (ka10054)
        
        Args:
            market: "0"=전체, "1"=코스피, "2"=코스닥
            
        Returns:
            VIEvent 리스트
        """
        tr_code = self.TR_CODES["VI_STATUS"]
        market_map = {"0": "000", "1": "001", "2": "101"}
        data = {
            "mrkt_tp": market_map.get(str(market), "000"),
            "bf_mkrt_tp": "0",
            "motn_tp": "0",
            "skip_stk": "000000000",
            "trde_qty_tp": "0",
            "min_trde_qty": "0",
            "max_trde_qty": "0",
            "trde_prica_tp": "0",
            "min_trde_prica": "0",
            "max_trde_prica": "0",
            "motn_drc": "0",
            "stex_tp": "3",
            "stk_cd": "",
        }
        result = self._request("POST", self.PATHS["stkinfo"], tr_code=tr_code, data=data)
        
        events: List[VIEvent] = []
        if result and result.get("return_code") == 0:
            output_list = _payload_records(result, "motn_stk", "output")
            for item in output_list:
                events.append(VIEvent(
                    code=str(item.get("stk_cd") or "").strip(),
                    name=str(item.get("stk_nm") or "").strip(),
                    vi_type=str(item.get("viaplc_tp") or item.get("vi_tp") or "").strip(),
                    vi_status=str(item.get("vi_st") or "발동").strip(),
                    trigger_time=str(item.get("trde_cntr_proc_time") or item.get("trg_tm") or "").strip(),
                    release_time=str(item.get("virelis_time") or item.get("rls_tm") or "").strip(),
                    trigger_price=_safe_int(_pick(item, "motn_pric", "trg_prc"), absolute=True),
                    base_price=_safe_int(_pick(item, "static_stdpc", "dynm_stdpc", "base_prc"), absolute=True),
                    deviance_rate=_safe_float(_pick(item, "static_dispty_rt", "dynm_dispty_rt", "dev_rt")),
                ))
        return events

